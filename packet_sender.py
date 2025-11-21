#!/usr/bin/env python3
"""
Network Packet Sender Tool
Sends UDP packets with configurable parameters for network testing.
Compatible with Python 3.12.7 on Windows and Linux.
"""

import socket
import time
import threading
import argparse
import sys
import struct


class PacketSender:
    def __init__(self, target_ip, target_port, packet_size, duration, 
                 pps, num_threads, size_mode='fixed', source_ip=None, bind_ip=None):
        """
        Initialize packet sender.
        
        Args:
            target_ip: Target IP address
            target_port: Target port number
            packet_size: Packet size in bytes (for fixed mode)
            duration: Duration in seconds
            pps: Packets per second
            num_threads: Number of threads
            size_mode: 'fixed', 'increasing', or 'decreasing'
            source_ip: Optional source IP for spoofing (requires raw sockets)
            bind_ip: Optional local IP to bind to (no root required)
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.packet_size = packet_size
        self.duration = duration
        self.pps = pps
        self.num_threads = num_threads
        self.size_mode = size_mode
        self.source_ip = source_ip
        self.bind_ip = bind_ip
        
        # Statistics
        self.packets_sent = 0
        self.bytes_sent = 0
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        
        # Size range for variable modes
        self.min_size = 100
        self.max_size = 1500
        
        # Pre-create payloads for performance
        self.payloads = self._create_payloads()

    def _create_payloads(self):
        """Pre-create payloads for better performance."""
        if self.size_mode == 'fixed':
            return {self.packet_size: bytes(self.packet_size)}
        elif self.size_mode in ['increasing', 'decreasing']:
            # Pre-create payloads for common sizes
            payloads = {}
            for size in range(self.min_size, self.max_size + 1, 10):
                payloads[size] = bytes(size)
            return payloads
        else:
            return {self.packet_size: bytes(self.packet_size)}
    
    def get_payload(self, packet_count):
        """Get pre-created payload based on mode."""
        if self.size_mode == 'fixed':
            return self.payloads[self.packet_size]
        elif self.size_mode == 'increasing':
            size_range = self.max_size - self.min_size
            offset = (packet_count * 10) % size_range
            size = self.min_size + offset
            return self.payloads.get(size, bytes(size))
        elif self.size_mode == 'decreasing':
            size_range = self.max_size - self.min_size
            offset = (packet_count * 10) % size_range
            size = self.max_size - offset
            return self.payloads.get(size, bytes(size))
        else:
            return self.payloads[self.packet_size]

    def create_socket(self):
        """Create appropriate socket based on configuration."""
        if self.source_ip:
            print(f"WARNING: Source IP spoofing enabled. This requires root/admin privileges.")
            print(f"WARNING: May be blocked by network infrastructure and could be illegal.")
            try:
                # Raw socket for IP spoofing (requires privileges)
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
                return sock
            except PermissionError:
                print("ERROR: Raw socket creation failed. Run with administrator/root privileges.")
                sys.exit(1)
        else:
            # Standard UDP socket with performance optimizations
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Increase socket buffer sizes for better throughput
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB send buffer
            except OSError:
                pass  # Ignore if system doesn't support
            
            # Bind to specific local IP if requested (no root required)
            if self.bind_ip:
                try:
                    sock.bind((self.bind_ip, 0))  # 0 = any available port
                except OSError as e:
                    print(f"ERROR: Cannot bind to {self.bind_ip}: {e}")
                    sock.close()
                    sys.exit(1)
            
            return sock

    def send_packets(self, thread_id):
        """Send packets from a single thread with optimized timing."""
        sock = self.create_socket()
        local_packet_count = 0
        local_bytes_sent = 0
        
        # Pre-resolve target address once
        target = (self.target_ip, self.target_port)
        
        # Calculate timing for rate limiting
        pps_per_thread = self.pps / self.num_threads
        batch_size = max(1, int(pps_per_thread / 100))  # Send in small batches
        sleep_time = batch_size / pps_per_thread if pps_per_thread > 0 else 0
        
        end_time = time.time() + self.duration
        
        try:
            while time.time() < end_time and not self.stop_flag.is_set():
                # Send packets in batches without checking time each iteration
                batch_start = time.time()
                
                for _ in range(batch_size):
                    # Get pre-created payload
                    payload = self.get_payload(local_packet_count)
                    
                    try:
                        sock.sendto(payload, target)
                        local_packet_count += 1
                        local_bytes_sent += len(payload)
                    except socket.error as e:
                        print(f"\nThread {thread_id}: Socket error - {e}")
                        self.stop_flag.set()
                        break
                
                # Rate limiting with better precision
                if sleep_time > 0:
                    elapsed = time.time() - batch_start
                    sleep_needed = sleep_time - elapsed
                    if sleep_needed > 0:
                        time.sleep(sleep_needed)
        
        finally:
            sock.close()
            
            # Update global statistics
            with self.lock:
                self.packets_sent += local_packet_count
                self.bytes_sent += local_bytes_sent

    def run(self):
        """Start packet sending with multiple threads."""
        print(f"\n{'='*60}")
        print(f"Packet Sender Starting")
        print(f"{'='*60}")
        print(f"Target: {self.target_ip}:{self.target_port}")
        print(f"Packet Size: {self.packet_size} bytes ({'mode: ' + self.size_mode})")
        if self.size_mode != 'fixed':
            print(f"Size Range: {self.min_size}-{self.max_size} bytes")
        print(f"Duration: {self.duration} seconds")
        print(f"Rate: {self.pps} packets/second")
        print(f"Threads: {self.num_threads}")
        if self.source_ip:
            print(f"Source IP (SPOOFED): {self.source_ip}")
        if self.bind_ip:
            print(f"Bound to local IP: {self.bind_ip}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        threads = []
        
        # Start threads
        for i in range(self.num_threads):
            thread = threading.Thread(target=self.send_packets, args=(i,))
            thread.daemon = True
            threads.append(thread)
            thread.start()
        
        # Monitor progress
        try:
            while any(t.is_alive() for t in threads):
                time.sleep(1)
                elapsed = time.time() - start_time
                with self.lock:
                    current_pps = self.packets_sent / elapsed if elapsed > 0 else 0
                    print(f"\rElapsed: {elapsed:.1f}s | Packets: {self.packets_sent} | "
                          f"Bytes: {self.bytes_sent:,} | Rate: {current_pps:.1f} pps", 
                          end='', flush=True)
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Stopping...")
            self.stop_flag.set()
        
        # Wait for all threads to finish
        for thread in threads:
            thread.join()
        
        # Final statistics
        elapsed_time = time.time() - start_time
        print(f"\n\n{'='*60}")
        print(f"Packet Sender Complete")
        print(f"{'='*60}")
        print(f"Duration: {elapsed_time:.2f} seconds")
        print(f"Packets Sent: {self.packets_sent:,}")
        print(f"Bytes Sent: {self.bytes_sent:,} ({self.bytes_sent/1024/1024:.2f} MB)")
        print(f"Average Rate: {self.packets_sent/elapsed_time:.2f} packets/second")
        print(f"Average Throughput: {self.bytes_sent/elapsed_time/1024/1024:.2f} MB/s")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Network Packet Sender Tool - Send UDP packets for network testing',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('target_ip', help='Target IP address')
    parser.add_argument('-p', '--port', type=int, default=9999,
                        help='Target port (default: 9999)')
    parser.add_argument('-s', '--size', type=int, default=64,
                        help='Packet size in bytes (default: 64)')
    parser.add_argument('-d', '--duration', type=int, default=60,
                        help='Duration in seconds (default: 60)')
    parser.add_argument('-r', '--rate', type=int, default=100,
                        help='Packets per second (default: 100)')
    parser.add_argument('-t', '--threads', type=int, default=1,
                        help='Number of threads (default: 1)')
    parser.add_argument('-m', '--mode', choices=['fixed', 'increasing', 'decreasing'],
                        default='fixed',
                        help='Packet size mode: fixed, increasing (100-1500), or decreasing (1500-100)')
    parser.add_argument('--source-ip', type=str, default=None,
                        help='Source IP address for spoofing (requires root/admin, may be illegal)')
    parser.add_argument('--bind-ip', type=str, default=None,
                        help='Local IP address to bind to (for multi-interface machines, no root required)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.size < 1 or args.size > 65507:
        print("Error: Packet size must be between 1 and 65507 bytes")
        sys.exit(1)
    
    if args.duration < 1:
        print("Error: Duration must be at least 1 second")
        sys.exit(1)
    
    if args.rate < 1:
        print("Error: Rate must be at least 1 packet per second")
        sys.exit(1)
    
    if args.threads < 1:
        print("Error: Must have at least 1 thread")
        sys.exit(1)
    
    # Create and run sender
    sender = PacketSender(
        target_ip=args.target_ip,
        target_port=args.port,
        packet_size=args.size,
        duration=args.duration,
        pps=args.rate,
        num_threads=args.threads,
        size_mode=args.mode,
        source_ip=args.source_ip,
        bind_ip=args.bind_ip
    )
    
    sender.run()


if __name__ == '__main__':
    main()
