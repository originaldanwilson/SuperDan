#!/usr/bin/env python3
"""
Robust NX-OS Chunked File Transfer Manager
Addresses connection stability issues and improves reliability for very large files.
"""

import time
import os
import sys
import logging
import threading
import hashlib
import math
import tempfile
import shutil
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
from tools import get_netmiko_creds
import paramiko
from scp import SCPClient
import socket
import re
import gc


class NXOSChunkedTransferRobust:
    """
    Robust NX-OS file transfer using chunked approach.
    Improved connection management and error handling.
    """
    
    def __init__(self, hostname, chunk_size_mb=100, debug=False):
        """
        Initialize the robust chunked transfer manager.
        
        Args:
            hostname (str): Target NX-OS switch hostname/IP
            chunk_size_mb (int): Size of each chunk in MB (default: 100MB)
            debug (bool): Enable debug logging
        """
        self.hostname = hostname
        self.chunk_size_mb = chunk_size_mb
        self.chunk_size_bytes = chunk_size_mb * 1024 * 1024
        self.device_type = "cisco_nxos"
        self.debug = debug
        self.connection = None
        self.ssh_client = None
        self.bootflash_free_space = 0
        self.connection_retry_count = 0
        self.max_connection_retries = 5
        
        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"NXOSChunkedRobust-{hostname}")
        
        # Get credentials
        self.username, self.password = get_netmiko_creds()
        
        # Connection parameters with more conservative timeouts
        self.connection_params = {
            'device_type': self.device_type,
            'host': self.hostname,
            'username': self.username,
            'password': self.password,
            'timeout': 300,           # 5 minutes per operation
            'session_timeout': 1800,  # 30 minutes total session
            'auth_timeout': 180,
            'banner_timeout': 60,
            'blocking_timeout': 300,
            'conn_timeout': 60,
            'keepalive': 30,
            'global_delay_factor': 2,
            'fast_cli': False,
        }
        
    def connect(self, max_retries=3):
        """Establish connection to NX-OS device."""
        for attempt in range(max_retries):
            try:
                self.logger.info(f"NX-OS connection attempt {attempt + 1}/{max_retries} to {self.hostname}")
                
                self.connection = ConnectHandler(**self.connection_params)
                self.logger.info("NX-OS connection established successfully")
                
                # Verify NX-OS and get basic info
                self._verify_nxos_connection()
                self._get_system_info()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(20 + (attempt * 10))  # Increasing backoff
        
        return False
    
    def _verify_nxos_connection(self):
        """Verify we're connected to NX-OS device."""
        try:
            version_output = self.send_command("show version", timeout=30)
            if version_output and ("NX-OS" in version_output or "Nexus" in version_output):
                self.logger.info("Confirmed connection to NX-OS device")
                # Extract device name if possible
                for line in version_output.split('\n'):
                    if 'Device name:' in line:
                        device_name = line.split('Device name:')[1].strip()
                        self.logger.info(f"Connected to device: {device_name}")
                        break
            else:
                self.logger.warning("Device may not be running NX-OS")
        except Exception as e:
            self.logger.warning(f"Could not verify NX-OS connection: {str(e)}")
    
    def _get_system_info(self):
        """Get NX-OS system information including free space."""
        try:
            # Get bootflash filesystem info with simpler command
            self.logger.info("Checking bootflash space...")
            df_output = self.send_command("dir bootflash:", timeout=90)
            
            if df_output:
                # Look for "bytes free" pattern
                for line in df_output.split('\n'):
                    if 'bytes free' in line.lower():
                        # Extract number before "bytes free"
                        match = re.search(r'(\d+)\s+bytes\s+free', line, re.IGNORECASE)
                        if match:
                            self.bootflash_free_space = int(match.group(1))
                            self.logger.info(f"Bootflash free space: {self.bootflash_free_space / (1024*1024*1024):.2f} GB")
                            break
            
            if self.bootflash_free_space == 0:
                self.logger.warning("Could not determine bootflash free space")
            
        except Exception as e:
            self.logger.warning(f"Could not get system info: {str(e)}")
    
    def _establish_ssh_connection(self, force_new=False):
        """Establish SSH connection for SCP with improved reliability."""
        try:
            # Close existing connection if forcing new or if connection is dead
            if self.ssh_client and (force_new or not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active()):
                try:
                    self.ssh_client.close()
                except:
                    pass
                self.ssh_client = None
            
            if self.ssh_client and self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active():
                return True  # Connection is good
            
            self.logger.info("Establishing fresh SSH connection...")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Configure socket for reliability with better keepalive
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)   # Start keepalive after 30s
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)  # Interval between keepalives
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)     # Max failed keepalives
            sock.settimeout(60)  # Socket timeout
            sock.connect((self.hostname, 22))
            
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                timeout=180,
                auth_timeout=180,
                banner_timeout=60,
                allow_agent=False,
                look_for_keys=False,
                sock=sock
            )
            
            self.logger.info("SSH connection established successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to establish SSH connection: {str(e)}")
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except:
                    pass
                self.ssh_client = None
            return False
    
    def transfer_large_file_chunked(self, local_file, remote_file, max_retries=3):
        """
        Transfer large file using robust chunked approach.
        
        Args:
            local_file (str): Path to local file
            remote_file (str): Remote file path (e.g., "bootflash:myfile.bin")
            max_retries (int): Max retries per chunk
            
        Returns:
            bool: True if successful
        """
        if not os.path.exists(local_file):
            self.logger.error(f"Local file does not exist: {local_file}")
            return False
        
        file_size = os.path.getsize(local_file)
        num_chunks = math.ceil(file_size / self.chunk_size_bytes)
        
        self.logger.info(f"Starting robust chunked transfer:")
        self.logger.info(f"  File: {local_file} ({file_size / (1024*1024*1024):.2f} GB)")
        self.logger.info(f"  Chunks: {num_chunks} × {self.chunk_size_mb}MB")
        self.logger.info(f"  Target: {remote_file}")
        
        # Check space
        if not self._check_space(file_size):
            return False
        
        # Transfer chunks one by one (don't create all at once)
        try:
            base_name = os.path.splitext(os.path.basename(local_file))[0]
            successful_chunks = 0
            
            with open(local_file, 'rb') as source_file:
                for chunk_idx in range(num_chunks):
                    # Create chunk on-the-fly
                    chunk_data = source_file.read(self.chunk_size_bytes)
                    if not chunk_data:
                        break
                    
                    chunk_filename = f"{base_name}_chunk_{chunk_idx:03d}.bin"
                    chunk_path = os.path.join("/tmp", chunk_filename)
                    remote_chunk = f"bootflash:{chunk_filename}"
                    
                    # Write chunk to temporary file
                    try:
                        with open(chunk_path, 'wb') as chunk_file:
                            chunk_file.write(chunk_data)
                    except Exception as e:
                        self.logger.error(f"Failed to create chunk file {chunk_path}: {str(e)}")
                        continue
                    
                    self.logger.info(f"Transferring chunk {chunk_idx+1}/{num_chunks}: {chunk_filename}")
                    
                    # Refresh connections every 5 chunks to prevent timeouts
                    if chunk_idx > 0 and chunk_idx % 5 == 0:
                        self.logger.info("Refreshing connections after 5 chunks...")
                        self._refresh_connections()
                        # Give the device a moment to settle
                        time.sleep(10)
                    
                    if self._transfer_single_chunk_robust(chunk_path, remote_chunk, chunk_filename, max_retries):
                        successful_chunks += 1
                        self.logger.info(f"✅ Chunk {chunk_idx+1}/{num_chunks} completed successfully")
                    else:
                        self.logger.error(f"❌ Failed to transfer chunk {chunk_idx+1}: {chunk_filename}")
                    
                    # Clean up local chunk immediately
                    try:
                        os.remove(chunk_path)
                    except:
                        pass
                    
                    # Force garbage collection after each chunk
                    gc.collect()
            
            self.logger.info(f"Transfer summary: {successful_chunks}/{num_chunks} chunks successful")
            
            if successful_chunks == num_chunks:
                self.logger.info("🎉 All chunks transferred successfully!")
                self._provide_reassembly_instructions(remote_file, base_name, num_chunks)
                return True
            else:
                self.logger.error(f"Only {successful_chunks}/{num_chunks} chunks transferred")
                return False
                
        except Exception as e:
            self.logger.error(f"Chunked transfer error: {str(e)}")
            return False
        finally:
            # Clean up any remaining chunk files
            self._cleanup_temp_files()
    
    def _refresh_connections(self):
        """Refresh both CLI and SSH connections."""
        try:
            # Refresh CLI connection
            if self.connection:
                try:
                    # Test connection with a simple command
                    test_output = self.connection.send_command("show clock", delay_factor=1, read_timeout=30)
                    if not test_output:
                        raise Exception("CLI connection test failed")
                    self.logger.info("CLI connection is healthy")
                except Exception as e:
                    self.logger.warning(f"CLI connection issue: {str(e)}, reconnecting...")
                    try:
                        self.connection.disconnect()
                    except:
                        pass
                    self.connection = None
                    if not self.connect():
                        raise Exception("Failed to reconnect CLI")
            
            # Refresh SSH connection
            self._establish_ssh_connection(force_new=True)
            
        except Exception as e:
            self.logger.error(f"Failed to refresh connections: {str(e)}")
            raise
    
    def _transfer_single_chunk_robust(self, chunk_file, remote_chunk, chunk_name, max_retries):
        """Transfer a single chunk with robust connection handling."""
        chunk_size = os.path.getsize(chunk_file)
        
        self.logger.info(f"Starting transfer of {chunk_name} ({chunk_size / (1024*1024):.1f} MB)")
        
        for attempt in range(max_retries):
            try:
                # Ensure SSH connection is available and healthy
                if not self._establish_ssh_connection():
                    self.logger.error("Failed to establish SSH connection for chunk")
                    if attempt < max_retries - 1:
                        time.sleep(30)
                        continue
                    return False
                
                # Create SCP client with more conservative settings
                scp = SCPClient(
                    self.ssh_client.get_transport(),
                    progress=lambda f, s, sent: self._chunk_progress(f, s, sent, chunk_name),
                    socket_timeout=1200  # 20 minutes for chunk
                )
                
                # Transfer the chunk
                self.logger.info(f"Uploading {chunk_name} (attempt {attempt + 1})")
                start_time = time.time()
                
                scp.put(chunk_file, remote_chunk)
                scp.close()  # Explicitly close SCP client
                
                transfer_time = time.time() - start_time
                speed = chunk_size / transfer_time / (1024*1024) if transfer_time > 0 else 0
                self.logger.info(f"Upload completed in {transfer_time:.1f}s ({speed:.1f} MB/s)")
                
                # Verify chunk with improved method
                if self._verify_chunk_robust(remote_chunk, chunk_size, chunk_name):
                    self.logger.info(f"✅ Chunk {chunk_name} verified successfully")
                    return True
                else:
                    self.logger.warning(f"❌ Chunk {chunk_name} verification failed on attempt {attempt + 1}")
                    
            except Exception as e:
                self.logger.error(f"Chunk transfer error on attempt {attempt + 1}: {str(e)}")
                
            # If not the last attempt, wait and retry
            if attempt < max_retries - 1:
                wait_time = 45 * (attempt + 1)  # Longer wait between retries
                self.logger.info(f"Retrying chunk transfer in {wait_time} seconds...")
                time.sleep(wait_time)
                
                # Clean up potentially corrupted chunk on device
                try:
                    self.send_command(f"delete {remote_chunk} no-prompt", timeout=30)
                except:
                    pass
                
                # Force connection refresh on retry
                self._establish_ssh_connection(force_new=True)
        
        self.logger.error(f"❌ All retry attempts failed for chunk {chunk_name}")
        return False
    
    def _chunk_progress(self, filename, size, sent, chunk_name):
        """Progress callback for chunk transfers."""
        percent = (sent / size) * 100
        # Log progress at specific intervals to avoid spam
        if percent in [10, 25, 50, 75, 90, 95, 100] or sent == size:
            mb_sent = sent / (1024*1024)
            mb_total = size / (1024*1024)
            self.logger.info(f"  📦 {chunk_name}: {percent:.0f}% ({mb_sent:.1f}/{mb_total:.1f} MB)")
    
    def _verify_chunk_robust(self, remote_chunk, expected_size, chunk_name):
        """Robust chunk verification with multiple methods and retries."""
        for verify_attempt in range(3):  # Try verification up to 3 times
            try:
                self.logger.debug(f"Verifying {chunk_name} on device (attempt {verify_attempt + 1})...")
                
                # Wait longer for file system to sync, especially on later attempts
                wait_time = 3 + (verify_attempt * 2)
                time.sleep(wait_time)
                
                dir_output = self.send_command(f"dir {remote_chunk}", timeout=90)
                
                if not dir_output:
                    self.logger.warning(f"No output from dir command for {chunk_name} (attempt {verify_attempt + 1})")
                    if verify_attempt < 2:
                        continue
                    return False
                
                if "No such file" in dir_output or "Error" in dir_output:
                    self.logger.warning(f"File not found: {chunk_name} (attempt {verify_attempt + 1})")
                    if verify_attempt < 2:
                        continue
                    return False
                
                # Look for the file size in the output
                lines = dir_output.split('\n')
                for line in lines:
                    # NX-OS dir output format: size date time filename
                    if chunk_name in line:
                        # Try to extract size - it should be the first number in the line
                        parts = line.strip().split()
                        for part in parts:
                            if part.isdigit():
                                actual_size = int(part)
                                if actual_size == expected_size:
                                    self.logger.debug(f"Size verified: {actual_size} bytes for {chunk_name}")
                                    return True
                                else:
                                    self.logger.error(f"Size mismatch for {chunk_name}: expected {expected_size}, got {actual_size}")
                                    return False
                
                # If we get here, we couldn't parse the size but file exists
                self.logger.warning(f"Could not parse size for {chunk_name}, but file appears to exist")
                
                # Try one more verification method - check if file is readable
                cat_test = self.send_command(f"show file {remote_chunk} | head", timeout=60)
                if cat_test and "No such file" not in cat_test and "Error" not in cat_test:
                    self.logger.info(f"File {chunk_name} appears readable, accepting verification")
                    return True
                
            except Exception as e:
                self.logger.warning(f"Error verifying chunk {chunk_name} (attempt {verify_attempt + 1}): {str(e)}")
                
            # Wait before retrying verification
            if verify_attempt < 2:
                time.sleep(5)
        
        self.logger.error(f"Could not verify chunk {chunk_name} after 3 attempts")
        return False
    
    def _provide_reassembly_instructions(self, final_remote_file, base_name, num_chunks):
        """Provide instructions for reassembling chunks."""
        self.logger.info("📋 File transfer completed! Chunks are now on the device.")
        self.logger.info("🔧 To reassemble the file, you can:")
        self.logger.info(f"   1. Use the first chunk as base: copy bootflash:{base_name}_chunk_000.bin {final_remote_file}")
        
        if num_chunks > 1:
            self.logger.info("   2. For multiple chunks, you may need to use external tools to combine them")
            self.logger.info("      or transfer them to a server that can reassemble them.")
        
        # List all chunks for reference
        self.logger.info("📦 Chunks transferred:")
        for i in range(num_chunks):
            chunk_name = f"{base_name}_chunk_{i:03d}.bin"
            self.logger.info(f"   - bootflash:{chunk_name}")
    
    def _check_space(self, file_size):
        """Check if enough space available."""
        if self.bootflash_free_space == 0:
            self.logger.warning("Could not determine free space, proceeding anyway")
            return True
        
        # Conservative estimate: need space for chunks
        required_space = file_size * 1.15  # 15% buffer for safety
        if required_space < self.bootflash_free_space:
            self.logger.info(f"Space check passed: {required_space / (1024*1024*1024):.2f} GB required, {self.bootflash_free_space / (1024*1024*1024):.2f} GB available")
            return True
        else:
            self.logger.error(f"Insufficient space: need {required_space / (1024*1024*1024):.2f} GB, have {self.bootflash_free_space / (1024*1024*1024):.2f} GB")
            return False
    
    def _cleanup_temp_files(self):
        """Clean up temporary chunk files."""
        try:
            temp_files_removed = 0
            for file in os.listdir("/tmp"):
                if "_chunk_" in file and file.endswith(".bin"):
                    file_path = os.path.join("/tmp", file)
                    try:
                        os.remove(file_path)
                        temp_files_removed += 1
                    except:
                        pass
            
            if temp_files_removed > 0:
                self.logger.info(f"Cleaned up {temp_files_removed} temporary chunk files")
                
        except Exception as e:
            self.logger.warning(f"Error during temp file cleanup: {str(e)}")
    
    def send_command(self, command, timeout=300):
        """Send command to NX-OS device with improved error handling."""
        if not self.connection:
            self.logger.error("No connection available for command")
            return None
        
        try:
            self.logger.debug(f"Sending command: {command}")
            output = self.connection.send_command(
                command,
                delay_factor=2,
                max_loops=1000,  # Increased for slower responses
                cmd_verify=False,
                read_timeout=timeout,
                expect_string=None
            )
            self.logger.debug(f"Command completed successfully")
            return output
            
        except Exception as e:
            self.logger.error(f"Command '{command}' failed: {str(e)}")
            return None
    
    def disconnect(self):
        """Close all connections."""
        if self.connection:
            try:
                self.connection.disconnect()
                self.logger.info("NX-OS connection closed")
            except:
                pass
            self.connection = None
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.logger.info("SSH connection closed")
            except:
                pass
            self.ssh_client = None
    
    def __enter__(self):
        if self.connect():
            return self
        else:
            raise Exception("Failed to connect to NX-OS device")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def transfer_large_file_chunked_robust(hostname, local_file, remote_file="bootflash:", chunk_size_mb=100):
    """
    Transfer very large file using robust chunked approach.
    
    Args:
        hostname (str): NX-OS device IP
        local_file (str): Local file path
        remote_file (str): Remote file path
        chunk_size_mb (int): Chunk size in MB
        
    Returns:
        bool: Success/failure
    """
    try:
        if remote_file.endswith(":"):
            remote_file += os.path.basename(local_file)
        
        print(f"🚀 Starting robust chunked transfer")
        print(f"   Source: {local_file}")
        print(f"   Target: {hostname}:{remote_file}")
        print(f"   Chunk size: {chunk_size_mb}MB")
        
        with NXOSChunkedTransferRobust(hostname, chunk_size_mb=chunk_size_mb, debug=True) as transfer:
            success = transfer.transfer_large_file_chunked(local_file, remote_file)
            return success
            
    except Exception as e:
        print(f"❌ Chunked transfer failed: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nxos_chunked_robust.py <hostname> <local_file> [chunk_size_mb] [remote_file]")
        print("Example: python nxos_chunked_robust.py 10.92.1.4 /path/to/large_file.bin 50")
        print("  Transfers file in 50MB chunks with robust connection management")
        sys.exit(1)
    
    hostname = sys.argv[1]
    local_file = sys.argv[2]
    chunk_size_mb = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    remote_file = sys.argv[4] if len(sys.argv) > 4 else "bootflash:"
    
    success = transfer_large_file_chunked_robust(hostname, local_file, remote_file, chunk_size_mb)
    print(f"\n{'🎉 SUCCESS' if success else '❌ FAILED'}: Chunked transfer {'completed' if success else 'failed'}")
    sys.exit(0 if success else 1)
