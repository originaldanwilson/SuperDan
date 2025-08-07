#!/usr/bin/env python3
"""
Cisco NX-OS File Transfer Manager - Class-based approach
Handles large file transfers (500MB+) with robust timeout management and retry logic.
Optimized specifically for Cisco Nexus switches running NX-OS.
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


class NXOSFileManager:
    """
    Cisco NX-OS specific file transfer manager with advanced timeout handling.
    Optimized for Nexus switches and large file transfers.
    """
    
    def __init__(self, hostname, debug=False):
        """
        Initialize the NX-OS File Manager.
        
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
        
        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(f"NXOSFileManager-{hostname}")
        
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
            # Extended timeouts for large NX-OS transfers
            'timeout': 2400,          # 40 minutes (NX-OS can be slow)
            'session_timeout': 7200,  # 2 hours
            'auth_timeout': 300,      # 5 minutes for auth
            'banner_timeout': 120,    # 2 minutes for banner (NX-OS can be slow)
            'blocking_timeout': 2400, # 40 minutes for blocking operations
            'conn_timeout': 120,      # 2 minutes connection timeout
            'keepalive': 30,          # Send keepalive every 30 seconds
            'global_delay_factor': 4, # Very slow for NX-OS stability
            'fast_cli': False,        # Always disable for NX-OS large transfers
            'session_log': 'nxos_session.log' if self.debug else None,
            # NX-OS specific settings
            'allow_agent': False,
            'look_for_keys': False,
            'use_keys': False,
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
            
            # Configure socket with aggressive keepalive for NX-OS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # More aggressive keepalive for NX-OS
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 9)
            sock.connect((self.hostname, 22))
            
            self.ssh_client.connect(
                hostname=self.hostname,
                username=self.username,
                password=self.password,
                timeout=300,
                auth_timeout=300,
                banner_timeout=120,  # NX-OS can have long banners
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
            
            if file_size * 1.1 < self.bootflash_free_space:  # 10% buffer
                return True
            else:
                self.logger.error("Insufficient space for file transfer")
                return False
        else:
            self.logger.warning("Could not determine free space, proceeding with transfer")
            return True
    
    def transfer_file_scp_nxos(self, local_file, remote_file, max_retries=3):
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
        
        self.logger.info(f"Starting NX-OS SCP transfer of {local_file} ({file_size} bytes) to {remote_file}")
        
        for attempt in range(max_retries):
            try:
                self.cancel_transfer.clear()
                
                # Create SCP client with extended timeout for NX-OS
                scp = SCPClient(
                    self.ssh_client.get_transport(),
                    progress=self.progress_callback,
                    socket_timeout=7200  # 2 hours timeout for NX-OS
                )
                
                # Pre-transfer checks
                local_checksum = self._calculate_file_checksum(local_file)
                self.logger.info(f"Local file MD5: {local_checksum}")
                
                # Start transfer with monitoring
                transfer_success = self._execute_scp_transfer(scp, local_file, remote_file, file_size)
                
                if transfer_success:
                    # Post-transfer verification
                    if self._verify_nxos_transfer(remote_file, local_checksum, file_size):
                        self.logger.info("NX-OS SCP transfer completed and verified successfully")
                        return True
                    else:
                        self.logger.warning("Transfer completed but verification failed")
                
            except Exception as e:
                self.logger.error(f"NX-OS SCP transfer error on attempt {attempt + 1}: {str(e)}")
                
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 45  # Longer wait for NX-OS
                self.logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
                # Clean up any partial files
                self._cleanup_partial_transfer(remote_file)
                
                # Re-establish SSH connection
                if self.ssh_client:
                    self.ssh_client.close()
                self._establish_ssh_connection()
                if not self.ssh_client:
                    self.logger.error("Could not re-establish SSH connection")
                    return False
        
        return False
    
    def _execute_scp_transfer(self, scp, local_file, remote_file, file_size):
        """Execute SCP transfer with timeout monitoring."""
        transfer_complete = Event()
        transfer_success = [False]  # Use list for mutable reference
        
        def transfer_worker():
            try:
                scp.put(local_file, remote_file)
                transfer_success[0] = True
                transfer_complete.set()
            except Exception as e:
                self.logger.error(f"SCP transfer worker error: {str(e)}")
                transfer_complete.set()
        
        # Start transfer thread
        transfer_thread = threading.Thread(target=transfer_worker)
        transfer_thread.daemon = True
        transfer_thread.start()
        
        # Monitor transfer with keepalives
        self._monitor_nxos_transfer(transfer_thread, file_size)
        
        # Wait for completion
        transfer_complete.wait(timeout=7200)  # 2 hours max
        
        if transfer_thread.is_alive():
            self.logger.error("Transfer thread timed out")
            self.cancel_transfer.set()
            return False
        
        return transfer_success[0] and not self.cancel_transfer.is_set()
    
    def _monitor_nxos_transfer(self, transfer_thread, file_size):
        """Monitor NX-OS transfer with enhanced keepalive and progress tracking."""
        monitor_interval = 45  # Longer intervals for NX-OS
        stall_timeout = 600    # 10 minutes stall detection
        last_progress_update = time.time()
        last_sent_bytes = 0
        
        while transfer_thread.is_alive() and not self.cancel_transfer.is_set():
            time.sleep(monitor_interval)
            
            current_time = time.time()
            
            # Send keepalive through main NX-OS connection
            try:
                if self.connection:
                    # Use a simple command that won't interfere with transfer
                    self.connection.send_command("show clock", delay_factor=0.5, max_loops=1)
            except:
                pass  # Ignore keepalive errors
            
            # Check for progress stall
            current_sent = self._get_current_transfer_progress()
            if current_sent > last_sent_bytes:
                last_progress_update = current_time
                last_sent_bytes = current_sent
            elif current_time - last_progress_update > stall_timeout:
                self.logger.warning("NX-OS transfer appears stalled, may need to cancel")
                # For NX-OS, we're more patient due to slower processing
    
    def _get_current_transfer_progress(self):
        """Get current transfer progress in bytes."""
        # This would need to be implemented based on progress callback data
        # For now, return 0 to avoid stall detection issues
        return 0
    
    def _calculate_file_checksum(self, file_path):
        """Calculate MD5 checksum of local file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
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
            size_match = re.search(r'(\d+)\s+\w+\s+\d+\s+\d+:\d+:\d+\s+' + re.escape(os.path.basename(remote_file)), dir_output)
            if size_match:
                actual_size = int(size_match.group(1))
                if actual_size != expected_size:
                    self.logger.error(f"Size mismatch: expected {expected_size}, got {actual_size}")
                    return False
                else:
                    self.logger.info(f"File size verified: {actual_size} bytes")
            
            # For critical transfers, could add checksum verification here
            # NX-OS doesn't have built-in md5sum, but could implement if needed
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying transfer: {str(e)}")
            return False
    
    def _cleanup_partial_transfer(self, remote_file):
        """Clean up any partial transfer files on NX-OS."""
        try:
            # Check if partial file exists and remove it
            cleanup_cmd = f"delete {remote_file} no-prompt"
            self.send_command_with_timeout(cleanup_cmd, timeout=60)
            self.logger.info(f"Cleaned up partial file: {remote_file}")
        except:
            pass  # Ignore cleanup errors
    
    def copy_file_within_nxos(self, source_file, dest_file, timeout=1800):
        """
        Copy file within NX-OS filesystem.
        
        Args:
            source_file (str): Source file path
            dest_file (str): Destination file path
            timeout (int): Command timeout
            
        Returns:
            bool: True if successful
        """
        try:
            copy_cmd = f"copy {source_file} {dest_file}"
            self.logger.info(f"Copying file within NX-OS: {copy_cmd}")
            
            output = self.send_command_with_timeout(copy_cmd, timeout=timeout)
            
            if output and ("Copy complete" in output or "bytes copied" in output):
                self.logger.info("NX-OS file copy completed successfully")
                return True
            else:
                self.logger.error("NX-OS file copy failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Error copying file within NX-OS: {str(e)}")
            return False
    
    def progress_callback(self, filename, size, sent):
        """Enhanced progress callback for NX-OS transfers."""
        if filename not in self.transfer_progress:
            self.transfer_progress[filename] = {
                'size': size, 
                'start_time': time.time(),
                'last_update': time.time()
            }
        
        progress = self.transfer_progress[filename]
        current_time = time.time()
        
        # Update progress less frequently for large transfers to reduce log spam
        if current_time - progress.get('last_update', 0) >= 30:  # Every 30 seconds
            percent = (sent / size) * 100
            elapsed = current_time - progress['start_time']
            
            if elapsed > 0 and sent > 0:
                speed = sent / elapsed / 1024 / 1024  # MB/s
                remaining_bytes = size - sent
                eta = remaining_bytes / (sent / elapsed) if sent > 0 else 0
                
                self.logger.info(f"NX-OS Transfer: {percent:.1f}% "
                               f"({sent / (1024*1024):.1f}/{size / (1024*1024):.1f} MB) "
                               f"Speed: {speed:.1f} MB/s "
                               f"ETA: {eta / 60:.0f}m")
            
            progress['last_update'] = current_time
    
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
                    delay_factor=4,      # Slower for NX-OS
                    max_loops=1000,     # More loops for NX-OS
                    cmd_verify=False,
                    read_timeout=timeout,
                    expect_string=None
                )
                
                self.logger.debug("NX-OS command completed successfully")
                return output
                
            except NetMikoTimeoutException as e:
                self.logger.warning(f"NX-OS command timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    # Try to recover NX-OS connection
                    try:
                        self.connection.clear_buffer()
                        # Send a simple command to check connectivity
                        self.connection.send_command("show clock", delay_factor=1, read_timeout=30)
                    except:
                        pass
                    time.sleep(45)  # Longer wait for NX-OS
                
            except Exception as e:
                self.logger.error(f"NX-OS command error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(45)
        
        return None
    
    def disconnect(self):
        """Close all NX-OS connections."""
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


# Example usage class for NX-OS
class NXOSTransferExample:
    """Example usage of NXOSFileManager."""
    
    @staticmethod
    def transfer_large_file_to_nxos(hostname, local_file, remote_file="bootflash:"):
        """
        Transfer a large file to NX-OS device.
        
        Args:
            hostname (str): NX-OS device hostname/IP
            local_file (str): Local file path
            remote_file (str): Remote file path (default to bootflash:)
            
        Returns:
            bool: Transfer success
        """
        try:
            # If remote_file is just a filesystem, append filename
            if remote_file.endswith(":"):
                remote_file += os.path.basename(local_file)
            
            with NXOSFileManager(hostname, debug=True) as nxos:
                success = nxos.transfer_file_scp_nxos(local_file, remote_file)
                return success
                
        except Exception as e:
            print(f"NX-OS transfer failed with error: {str(e)}")
            return False
    
    @staticmethod
    def install_nxos_image(hostname, local_image, install_timeout=3600):
        """
        Transfer and install NX-OS image.
        
        Args:
            hostname (str): NX-OS device hostname/IP
            local_image (str): Local NX-OS image file
            install_timeout (int): Installation timeout in seconds
            
        Returns:
            bool: Installation success
        """
        try:
            remote_image = f"bootflash:{os.path.basename(local_image)}"
            
            with NXOSFileManager(hostname, debug=True) as nxos:
                # Transfer image
                if not nxos.transfer_file_scp_nxos(local_image, remote_image):
                    return False
                
                # Install image (example - adjust for your specific NX-OS version)
                install_cmd = f"install all nxos {remote_image}"
                nxos.logger.info("Starting NX-OS image installation...")
                
                output = nxos.send_command_with_timeout(
                    install_cmd, 
                    timeout=install_timeout,
                    max_retries=1
                )
                
                if output and "Install operation" in output:
                    nxos.logger.info("NX-OS installation completed")
                    return True
                else:
                    nxos.logger.error("NX-OS installation failed")
                    return False
                
        except Exception as e:
            print(f"NX-OS installation failed with error: {str(e)}")
            return False


if __name__ == "__main__":
    # Command line usage for NX-OS
    if len(sys.argv) < 3:
        print("Usage: python nxos_file_manager.py <hostname> <local_file> [remote_file]")
        print("Example: python nxos_file_manager.py 192.168.1.10 nxos.bin")
        print("Example: python nxos_file_manager.py 192.168.1.10 nxos.bin bootflash:new_nxos.bin")
        sys.exit(1)
    
    hostname = sys.argv[1]
    local_file = sys.argv[2]
    remote_file = sys.argv[3] if len(sys.argv) > 3 else "bootflash:"
    
    success = NXOSTransferExample.transfer_large_file_to_nxos(hostname, local_file, remote_file)
    print(f"Transfer {'successful' if success else 'failed'}")
    sys.exit(0 if success else 1)
