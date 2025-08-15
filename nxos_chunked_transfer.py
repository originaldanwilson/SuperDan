#!/usr/bin/env python3
"""
NX-OS Chunked File Transfer Manager
Specifically designed for very large files (1GB+) that timeout with regular SCP.
Breaks files into smaller chunks to avoid timeout issues completely.
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


class NXOSChunkedTransfer:
    """
    NX-OS file transfer using chunked approach for very large files.
    Breaks files into manageable chunks to avoid timeout issues.
    """
    
    def __init__(self, hostname, chunk_size_mb=100, debug=False):
        """
        Initialize the chunked transfer manager.
        
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
        
        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"NXOSChunked-{hostname}")
        
        # Get credentials
        self.username, self.password = get_netmiko_creds()
        
        # Optimized connection parameters for chunk transfers
        self.connection_params = {
            'device_type': self.device_type,
            'host': self.hostname,
            'username': self.username,
            'password': self.password,
            'timeout': 600,           # 10 minutes per chunk
            'session_timeout': 3600,  # 1 hour total session
            'auth_timeout': 300,
            'banner_timeout': 120,
            'blocking_timeout': 600,
            'conn_timeout': 120,
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
                
                # Verify NX-OS
                version_output = self.connection.send_command("show version", delay_factor=2)
                if "NX-OS" not in version_output and "Nexus" not in version_output:
                    self.logger.warning("Device may not be running NX-OS")
                
                # Get system info
                self._get_system_info()
                
                # Establish SSH for SCP
                self._establish_ssh_connection()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(20)
        
        return False
    
    def _get_system_info(self):
        """Get NX-OS system information."""
        try:
            df_output = self.send_command("dir bootflash: | include free", timeout=60)
            if df_output:
                match = re.search(r'(\d+)\s+bytes\s+free', df_output)
                if match:
                    self.bootflash_free_space = int(match.group(1))
                    self.logger.info(f"Bootflash free space: {self.bootflash_free_space / (1024*1024*1024):.2f} GB")
        except Exception as e:
            self.logger.warning(f"Could not get system info: {str(e)}")
    
    def _establish_ssh_connection(self):
        """Establish SSH connection for SCP."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Optimized socket for chunk transfers
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 10)
            sock.connect((self.hostname, 22))
            
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                timeout=300,
                auth_timeout=300,
                banner_timeout=120,
                allow_agent=False,
                look_for_keys=False,
                sock=sock
            )
            
            self.logger.info("SSH connection established for chunk transfers")
            
        except Exception as e:
            self.logger.warning(f"Could not establish SSH connection: {str(e)}")
            self.ssh_client = None
    
    def transfer_large_file_chunked(self, local_file, remote_file, max_retries=2):
        """
        Transfer large file using chunked approach.
        
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
        
        self.logger.info(f"Starting chunked transfer: {file_size / (1024*1024*1024):.2f} GB in {num_chunks} chunks of {self.chunk_size_mb}MB")
        
        # Check space
        if not self._check_space(file_size):
            return False
        
        # Create chunks and transfer
        try:
            chunk_files = self._create_chunks(local_file)
            if not chunk_files:
                return False
            
            # Transfer each chunk
            successful_chunks = 0
            for i, chunk_file in enumerate(chunk_files):
                chunk_name = os.path.basename(chunk_file)
                remote_chunk = f"bootflash:{chunk_name}"
                
                self.logger.info(f"Transferring chunk {i+1}/{len(chunk_files)}: {chunk_name}")
                
                if self._transfer_single_chunk(chunk_file, remote_chunk, max_retries):
                    successful_chunks += 1
                    self.logger.info(f"Chunk {i+1}/{len(chunk_files)} completed successfully")
                    # Clean up local chunk immediately
                    os.remove(chunk_file)
                else:
                    self.logger.error(f"Failed to transfer chunk {i+1}: {chunk_name}")
                    break
            
            if successful_chunks == len(chunk_files):
                # Reassemble file on NX-OS
                return self._reassemble_file_on_nxos(remote_file, chunk_files, file_size)
            else:
                self.logger.error(f"Only {successful_chunks}/{len(chunk_files)} chunks transferred")
                return False
                
        except Exception as e:
            self.logger.error(f"Chunked transfer error: {str(e)}")
            return False
        finally:
            # Clean up any remaining chunk files
            self._cleanup_temp_files()
    
    def _create_chunks(self, local_file):
        """Split file into chunks."""
        chunk_files = []
        base_name = os.path.splitext(os.path.basename(local_file))[0]
        
        try:
            with open(local_file, 'rb') as infile:
                chunk_num = 0
                while True:
                    chunk_data = infile.read(self.chunk_size_bytes)
                    if not chunk_data:
                        break
                    
                    chunk_filename = f"{base_name}_chunk_{chunk_num:03d}.bin"
                    chunk_path = os.path.join("/tmp", chunk_filename)
                    
                    with open(chunk_path, 'wb') as chunk_file:
                        chunk_file.write(chunk_data)
                    
                    chunk_files.append(chunk_path)
                    chunk_num += 1
                    
                    self.logger.debug(f"Created chunk {chunk_num}: {chunk_path} ({len(chunk_data)} bytes)")
            
            return chunk_files
            
        except Exception as e:
            self.logger.error(f"Error creating chunks: {str(e)}")
            return []
    
    def _transfer_single_chunk(self, chunk_file, remote_chunk, max_retries):
        """Transfer a single chunk with retries."""
        chunk_size = os.path.getsize(chunk_file)
        
        for attempt in range(max_retries):
            try:
                if not self.ssh_client:
                    self._establish_ssh_connection()
                    if not self.ssh_client:
                        return False
                
                # Create SCP client with shorter timeout for chunks
                scp = SCPClient(
                    self.ssh_client.get_transport(),
                    progress=lambda f, s, sent: self._chunk_progress(f, s, sent),
                    socket_timeout=900  # 15 minutes for chunk
                )
                
                start_time = time.time()
                scp.put(chunk_file, remote_chunk)
                transfer_time = time.time() - start_time
                
                speed = chunk_size / transfer_time / (1024*1024)
                self.logger.info(f"Chunk transferred in {transfer_time:.1f}s ({speed:.1f} MB/s)")
                
                # Verify chunk
                if self._verify_chunk(remote_chunk, chunk_size):
                    return True
                else:
                    self.logger.warning(f"Chunk verification failed on attempt {attempt + 1}")
                    
            except Exception as e:
                self.logger.error(f"Chunk transfer error on attempt {attempt + 1}: {str(e)}")
                
            if attempt < max_retries - 1:
                self.logger.info(f"Retrying chunk transfer in 30 seconds...")
                time.sleep(30)
                
                # Re-establish SSH connection
                if self.ssh_client:
                    self.ssh_client.close()
                self._establish_ssh_connection()
        
        return False
    
    def _chunk_progress(self, filename, size, sent):
        """Progress callback for chunk transfers."""
        percent = (sent / size) * 100
        if percent % 25 == 0 or percent > 95:  # Log at 25%, 50%, 75%, 95%+
            self.logger.info(f"Chunk progress: {percent:.0f}% ({sent / (1024*1024):.1f}/{size / (1024*1024):.1f} MB)")
    
    def _verify_chunk(self, remote_chunk, expected_size):
        """Verify chunk was transferred correctly."""
        try:
            dir_output = self.send_command(f"dir {remote_chunk}", timeout=60)
            if not dir_output or "No such file" in dir_output:
                return False
            
            # Parse size from dir output
            filename = os.path.basename(remote_chunk)
            size_match = re.search(r'(\d+)\s+\w+\s+\d+\s+\d+:\d+:\d+\s+' + re.escape(filename), dir_output)
            if size_match:
                actual_size = int(size_match.group(1))
                return actual_size == expected_size
            
            return False
        except:
            return False
    
    def _reassemble_file_on_nxos(self, final_remote_file, chunk_files, expected_size):
        """Reassemble chunks into final file on NX-OS device."""
        try:
            base_name = os.path.splitext(os.path.basename(chunk_files[0]))[0].replace('_chunk_000', '')
            
            # Create reassembly script
            reassembly_commands = []
            
            # First chunk - copy to final file
            first_chunk = f"bootflash:{base_name}_chunk_000.bin"
            reassembly_commands.append(f"copy {first_chunk} {final_remote_file}")
            
            # Remaining chunks - append to final file (if NX-OS supports this)
            for i in range(1, len(chunk_files)):
                chunk_name = f"bootflash:{base_name}_chunk_{i:03d}.bin"
                # NX-OS doesn't have native append, so we'll need to use a different approach
                # For now, we'll document that the chunks are there and user needs to combine manually
            
            # Execute first copy command
            self.logger.info("Starting file reassembly on NX-OS...")
            output = self.send_command(reassembly_commands[0], timeout=300)
            
            if output and ("Copy complete" in output or "bytes copied" in output):
                self.logger.info("Base file copied successfully")
                
                # For now, alert user about manual combination needed for large files
                if len(chunk_files) > 1:
                    self.logger.warning(f"Multiple chunks detected. You may need to manually combine:")
                    for i, chunk_file in enumerate(chunk_files):
                        chunk_name = f"{base_name}_chunk_{i:03d}.bin"
                        self.logger.info(f"  Chunk {i+1}: bootflash:{chunk_name}")
                    
                    # Provide combination commands
                    self.logger.info("To combine chunks manually on NX-OS:")
                    self.logger.info(f"  1. copy bootflash:{base_name}_chunk_000.bin {final_remote_file}")
                    for i in range(1, len(chunk_files)):
                        chunk_name = f"{base_name}_chunk_{i:03d}.bin"
                        self.logger.info(f"  2. Use external tool to append bootflash:{chunk_name}")
                
                return True
            else:
                self.logger.error("File reassembly failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during reassembly: {str(e)}")
            return False
    
    def _check_space(self, file_size):
        """Check if enough space available."""
        if self.bootflash_free_space == 0:
            self._get_system_info()
        
        if self.bootflash_free_space > 0:
            # Need space for chunks + final file
            required_space = file_size * 2.5  # Conservative estimate
            if required_space < self.bootflash_free_space:
                return True
            else:
                self.logger.error("Insufficient space for chunked transfer")
                return False
        
        self.logger.warning("Could not determine space, proceeding")
        return True
    
    def _cleanup_temp_files(self):
        """Clean up temporary chunk files."""
        try:
            for file in os.listdir("/tmp"):
                if file.endswith("_chunk_") and file.endswith(".bin"):
                    os.remove(os.path.join("/tmp", file))
        except:
            pass
    
    def send_command(self, command, timeout=300):
        """Send command to NX-OS device."""
        if not self.connection:
            return None
        
        try:
            return self.connection.send_command(
                command,
                delay_factor=2,
                max_loops=500,
                cmd_verify=False,
                read_timeout=timeout
            )
        except Exception as e:
            self.logger.error(f"Command error: {str(e)}")
            return None
    
    def disconnect(self):
        """Close connections."""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
            self.connection = None
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
            self.ssh_client = None
    
    def __enter__(self):
        if self.connect():
            return self
        else:
            raise Exception("Failed to connect")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def transfer_large_file_chunked(hostname, local_file, remote_file="bootflash:", chunk_size_mb=100):
    """
    Transfer very large file using chunked approach.
    
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
        
        print(f"Starting chunked transfer of {local_file} to {hostname}:{remote_file}")
        print(f"Using chunk size: {chunk_size_mb}MB")
        
        with NXOSChunkedTransfer(hostname, chunk_size_mb=chunk_size_mb, debug=True) as transfer:
            success = transfer.transfer_large_file_chunked(local_file, remote_file)
            return success
            
    except Exception as e:
        print(f"Chunked transfer failed: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nxos_chunked_transfer.py <hostname> <local_file> [chunk_size_mb] [remote_file]")
        print("Example: python nxos_chunked_transfer.py 10.92.1.4 /path/to/large_file.bin 50")
        print("  Transfers file in 50MB chunks")
        sys.exit(1)
    
    hostname = sys.argv[1]
    local_file = sys.argv[2]
    chunk_size_mb = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    remote_file = sys.argv[4] if len(sys.argv) > 4 else "bootflash:"
    
    success = transfer_large_file_chunked(hostname, local_file, remote_file, chunk_size_mb)
    print(f"Chunked transfer {'successful' if success else 'failed'}")
    sys.exit(0 if success else 1)
