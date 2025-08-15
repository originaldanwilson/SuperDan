#!/usr/bin/env python3
"""
Enhanced Cisco NX-OS File Transfer Manager - Version 2
Improved handling for very large file transfers with better timeout management.
Specifically addresses the Netmiko connection drop issue during long SCP transfers.
"""

import time
import os
import sys
import logging
import threading
import hashlib
from threading import Event, Timer
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
from tools import get_netmiko_creds
import paramiko
from scp import SCPClient
import socket
import re


class NXOSFileManagerV2:
    """
    Enhanced Cisco NX-OS specific file transfer manager.
    Version 2 with improved timeout handling for very large transfers.
    """
    
    def __init__(self, hostname, debug=False):
        """
        Initialize the Enhanced NX-OS File Manager.
        
        Args:
            hostname (str): Target NX-OS switch hostname/IP
            debug (bool): Enable debug logging
        """
        self.hostname = hostname
        self.device_type = "cisco_nxos"
        self.debug = debug
        self.connection = None
        self.ssh_client = None
        self.transfer_progress = {}
        self.cancel_transfer = Event()
        self.bootflash_free_space = 0
        self.keepalive_thread = None
        self.keepalive_running = False
        
        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"NXOSFileManagerV2-{hostname}")
        
        # Get credentials
        self.username, self.password = get_netmiko_creds()
        
        # NX-OS specific connection parameters
        self.connection_params = self._get_nxos_connection_params()
        
    def _get_nxos_connection_params(self):
        """Get NX-OS optimized connection parameters for large file transfers."""
        return {
            'device_type': self.device_type,
            'host': self.hostname,
            'username': self.username,
            'password': self.password,
            # Very extended timeouts for large NX-OS transfers
            'timeout': 3600,          # 1 hour 
            'session_timeout': 14400, # 4 hours
            'auth_timeout': 300,      # 5 minutes for auth
            'banner_timeout': 120,    # 2 minutes for banner
            'blocking_timeout': 3600, # 1 hour for blocking operations
            'conn_timeout': 120,      # 2 minutes connection timeout
            'keepalive': 20,          # More frequent keepalive
            'global_delay_factor': 2, # Balanced for stability and speed
            'fast_cli': False,        # Always disable for NX-OS large transfers
            'session_log': 'nxos_session_v2.log' if self.debug else None,
        }
    
    def connect(self, max_retries=3):
        """
        Establish connection to NX-OS device with retry logic.
        
        Args:
            max_retries (int): Maximum connection attempts
            
        Returns:
            bool: True if connected successfully
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"NX-OS connection attempt {attempt + 1}/{max_retries} to {self.hostname}")
                
                # Connect to NX-OS switch
                self.connection = ConnectHandler(**self.connection_params)
                self.logger.info("NX-OS Netmiko connection established successfully")
                
                # Verify it's actually NX-OS
                version_output = self.connection.send_command("show version", delay_factor=2)
                if "NX-OS" not in version_output and "Nexus" not in version_output:
                    self.logger.warning("Device may not be running NX-OS")
                
                # Get system information
                self._get_system_info()
                
                # Establish SSH connection for SCP
                self._establish_ssh_connection()
                
                # Start keepalive thread for long transfers
                self._start_keepalive_thread()
                
                return True
                
            except NetMikoAuthenticationException as e:
                self.logger.error(f"Authentication failed: {str(e)}")
                return False
                
            except NetMikoTimeoutException as e:
                self.logger.warning(f"Connection timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 20
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                
            except Exception as e:
                self.logger.error(f"Connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 20
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        self.logger.error("All NX-OS connection attempts failed")
        return False
    
    def _start_keepalive_thread(self):
        """Start a dedicated keepalive thread for long transfers."""
        self.keepalive_running = True
        self.keepalive_thread = threading.Thread(target=self._keepalive_worker)
        self.keepalive_thread.daemon = True
        self.keepalive_thread.start()
        self.logger.info("Keepalive thread started")
    
    def _keepalive_worker(self):
        """Worker thread to send periodic keepalives."""
        keepalive_interval = 30  # Send keepalive every 30 seconds
        
        while self.keepalive_running and self.connection:
            try:
                time.sleep(keepalive_interval)
                if self.keepalive_running and self.connection:
                    # Send a very lightweight command
                    self.connection.send_command("", expect_string="", delay_factor=0.1, max_loops=1)
                    self.logger.debug("Keepalive sent")
            except Exception as e:
                self.logger.debug(f"Keepalive failed (normal during transfers): {str(e)}")
                # Don't stop on keepalive errors, they're common during transfers
    
    def _stop_keepalive_thread(self):
        """Stop the keepalive thread."""
        self.keepalive_running = False
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            self.keepalive_thread.join(timeout=5)
            self.logger.info("Keepalive thread stopped")
    
    def _get_system_info(self):
        """Get NX-OS system information including free space."""
        try:
            # Get bootflash filesystem info
            df_output = self.send_command_with_timeout("dir bootflash: | include free", timeout=60)
            if df_output:
                # Parse free space from output like "12345678912 bytes free"
                match = re.search(r'(\d+)\s+bytes\s+free', df_output)
                if match:
                    self.bootflash_free_space = int(match.group(1))
                    self.logger.info(f"Bootflash free space: {self.bootflash_free_space / (1024*1024*1024):.2f} GB")
            
            # Get hostname for logging
            hostname_output = self.send_command_with_timeout("show hostname", timeout=30)
            if hostname_output:
                self.logger.info(f"Connected to NX-OS device: {hostname_output.strip()}")
                
        except Exception as e:
            self.logger.warning(f"Could not get system info: {str(e)}")
    
    def _establish_ssh_connection(self):
        """Establish direct SSH connection optimized for NX-OS SCP transfers."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Configure socket with very aggressive keepalive for NX-OS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Very aggressive keepalive for long transfers
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)   # Start after 30s
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)  # Interval 15s
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 20)    # 20 attempts
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
            
            self.logger.info("Direct SSH connection established for NX-OS SCP")
            
        except Exception as e:
            self.logger.warning(f"Could not establish SSH connection for SCP: {str(e)}")
            self.ssh_client = None
    
    def check_file_space(self, file_size, filesystem="bootflash:"):
        """
        Check if there's enough space for the file on NX-OS filesystem.
        
        Args:
            file_size (int): Size of file in bytes
            filesystem (str): NX-OS filesystem to check
            
        Returns:
            bool: True if enough space available
        """
        if self.bootflash_free_space == 0:
            self._get_system_info()
        
        if self.bootflash_free_space > 0:
            free_space_gb = self.bootflash_free_space / (1024*1024*1024)
            file_size_gb = file_size / (1024*1024*1024)
            
            self.logger.info(f"File size: {file_size_gb:.2f} GB, Free space: {free_space_gb:.2f} GB")
            
            if file_size * 1.2 < self.bootflash_free_space:  # 20% buffer for safety
                return True
            else:
                self.logger.error("Insufficient space for file transfer")
                return False
        else:
            self.logger.warning("Could not determine free space, proceeding with transfer")
            return True
    
    def transfer_file_scp_nxos(self, local_file, remote_file, max_retries=2):
        """
        Transfer file to NX-OS using SCP with enhanced retry logic.
        
        Args:
            local_file (str): Path to local file
            remote_file (str): Path to remote file (e.g., "bootflash:myfile.bin")
            max_retries (int): Maximum retry attempts
            
        Returns:
            bool: True if transfer successful
        """
        if not self.ssh_client:
            self.logger.error("No SSH connection available for SCP transfer")
            return False
        
        if not os.path.exists(local_file):
            self.logger.error(f"Local file does not exist: {local_file}")
            return False
        
        file_size = os.path.getsize(local_file)
        
        # Check available space
        if not self.check_file_space(file_size):
            return False
        
        self.logger.info(f"Starting NX-OS SCP transfer of {local_file} ({file_size / (1024*1024):.1f} MB) to {remote_file}")
        
        for attempt in range(max_retries):
            try:
                self.cancel_transfer.clear()
                
                # Clean up any partial files first
                if attempt > 0:
                    self._cleanup_partial_transfer(remote_file)
                
                # Pre-transfer checks
                local_checksum = self._calculate_file_checksum(local_file)
                self.logger.info(f"Local file MD5: {local_checksum}")
                
                # Create SCP client with very long timeout for NX-OS
                scp = SCPClient(
                    self.ssh_client.get_transport(),
                    progress=self.progress_callback,
                    socket_timeout=14400  # 4 hours timeout
                )
                
                # Execute transfer
                self.logger.info("Starting SCP transfer...")
                start_time = time.time()
                
                try:
                    scp.put(local_file, remote_file)
                    transfer_time = time.time() - start_time
                    avg_speed = file_size / transfer_time / (1024*1024)  # MB/s
                    self.logger.info(f"SCP transfer completed in {transfer_time:.1f}s (avg: {avg_speed:.1f} MB/s)")
                    
                    # Post-transfer verification
                    if self._verify_nxos_transfer(remote_file, local_checksum, file_size):
                        self.logger.info("NX-OS SCP transfer completed and verified successfully")
                        return True
                    else:
                        self.logger.warning("Transfer completed but verification failed")
                        
                except Exception as scp_error:
                    self.logger.error(f"SCP transfer failed: {str(scp_error)}")
                    raise
                
            except Exception as e:
                self.logger.error(f"NX-OS SCP transfer error on attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 60  # Wait longer between retries
                    self.logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    
                    # Re-establish SSH connection
                    if self.ssh_client:
                        self.ssh_client.close()
                    self._establish_ssh_connection()
                    if not self.ssh_client:
                        self.logger.error("Could not re-establish SSH connection")
                        return False
        
        return False
    
    def _calculate_file_checksum(self, file_path):
        """Calculate MD5 checksum of local file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):  # 64KB chunks
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating checksum: {str(e)}")
            return None
    
    def _verify_nxos_transfer(self, remote_file, expected_checksum, expected_size):
        """Verify file transfer on NX-OS device."""
        try:
            # Check file existence and size
            dir_output = self.send_command_with_timeout(f"dir {remote_file}", timeout=120)
            if not dir_output or "No such file" in dir_output:
                self.logger.error("Transferred file not found on NX-OS device")
                return False
            
            # Parse file size from dir output
            filename = os.path.basename(remote_file)
            size_match = re.search(r'(\d+)\s+\w+\s+\d+\s+\d+:\d+:\d+\s+' + re.escape(filename), dir_output)
            if size_match:
                actual_size = int(size_match.group(1))
                if actual_size != expected_size:
                    self.logger.error(f"Size mismatch: expected {expected_size}, got {actual_size}")
                    return False
                else:
                    self.logger.info(f"File size verified: {actual_size} bytes")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying transfer: {str(e)}")
            return False
    
    def _cleanup_partial_transfer(self, remote_file):
        """Clean up any partial transfer files on NX-OS."""
        try:
            # Check if file exists and remove it
            cleanup_cmd = f"delete {remote_file} no-prompt"
            self.send_command_with_timeout(cleanup_cmd, timeout=60)
            self.logger.info(f"Cleaned up partial file: {remote_file}")
        except:
            pass  # Ignore cleanup errors
    
    def progress_callback(self, filename, size, sent):
        """Enhanced progress callback for NX-OS transfers."""
        if filename not in self.transfer_progress:
            self.transfer_progress[filename] = {
                'size': size, 
                'start_time': time.time(),
                'last_update': time.time(),
                'last_sent': 0
            }
        
        progress = self.transfer_progress[filename]
        current_time = time.time()
        
        # Update progress every 30 seconds
        if current_time - progress.get('last_update', 0) >= 30:
            percent = (sent / size) * 100
            elapsed = current_time - progress['start_time']
            
            if elapsed > 0 and sent > 0:
                # Calculate current speed (last 30 seconds)
                time_diff = current_time - progress['last_update']
                bytes_diff = sent - progress.get('last_sent', 0)
                current_speed = bytes_diff / time_diff / (1024*1024) if time_diff > 0 else 0
                
                # Calculate overall speed
                overall_speed = sent / elapsed / (1024*1024)
                
                # Calculate ETA
                remaining_bytes = size - sent
                eta_seconds = remaining_bytes / (sent / elapsed) if sent > 0 else 0
                eta_minutes = eta_seconds / 60
                
                self.logger.info(f"NX-OS Transfer: {percent:.1f}% "
                               f"({sent / (1024*1024):.1f}/{size / (1024*1024):.1f} MB) "
                               f"Current: {current_speed:.1f} MB/s "
                               f"Overall: {overall_speed:.1f} MB/s "
                               f"ETA: {eta_minutes:.0f}m")
            
            progress['last_update'] = current_time
            progress['last_sent'] = sent
    
    def send_command_with_timeout(self, command, timeout=300, max_retries=2):
        """
        Send command to NX-OS with extended timeout handling.
        
        Args:
            command (str): Command to send
            timeout (int): Command timeout in seconds
            max_retries (int): Maximum retry attempts
            
        Returns:
            str: Command output or None if failed
        """
        if not self.connection:
            self.logger.error("No NX-OS connection available")
            return None
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Sending NX-OS command (attempt {attempt + 1}): {command}")
                
                output = self.connection.send_command(
                    command,
                    delay_factor=2,
                    max_loops=1000,
                    cmd_verify=False,
                    read_timeout=timeout,
                    expect_string=None
                )
                
                self.logger.debug("NX-OS command completed successfully")
                return output
                
            except NetMikoTimeoutException as e:
                self.logger.warning(f"NX-OS command timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"NX-OS command error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(30)
        
        return None
    
    def disconnect(self):
        """Close all NX-OS connections."""
        # Stop keepalive thread first
        self._stop_keepalive_thread()
        
        if self.connection:
            try:
                self.connection.disconnect()
                self.logger.info("NX-OS Netmiko connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing NX-OS connection: {str(e)}")
            finally:
                self.connection = None
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.logger.info("NX-OS SSH connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing NX-OS SSH connection: {str(e)}")
            finally:
                self.ssh_client = None
    
    def __enter__(self):
        """Context manager entry."""
        if self.connect():
            return self
        else:
            raise Exception("Failed to establish NX-OS connection")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Simplified usage example
def transfer_large_file_nxos_v2(hostname, local_file, remote_file="bootflash:"):
    """
    Simple function to transfer large files to NX-OS with improved timeout handling.
    
    Args:
        hostname (str): NX-OS device IP
        local_file (str): Local file path  
        remote_file (str): Remote file path
        
    Returns:
        bool: Success/failure
    """
    try:
        # If remote_file is just filesystem, add filename
        if remote_file.endswith(":"):
            remote_file += os.path.basename(local_file)
        
        print(f"Starting transfer of {local_file} to {hostname}:{remote_file}")
        
        with NXOSFileManagerV2(hostname, debug=True) as nxos:
            success = nxos.transfer_file_scp_nxos(local_file, remote_file)
            return success
            
    except Exception as e:
        print(f"Transfer failed: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python nxos_file_manager_v2.py <hostname> <local_file> [remote_file]")
        print("Example: python nxos_file_manager_v2.py 10.92.1.4 /path/to/large_file.bin")
        sys.exit(1)
    
    hostname = sys.argv[1]
    local_file = sys.argv[2]
    remote_file = sys.argv[3] if len(sys.argv) > 3 else "bootflash:"
    
    success = transfer_large_file_nxos_v2(hostname, local_file, remote_file)
    print(f"Transfer {'successful' if success else 'failed'}")
    sys.exit(0 if success else 1)
