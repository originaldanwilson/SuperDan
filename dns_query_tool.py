#!/usr/bin/env python3
"""
DNS Query Tool - Identifies which DNS server responds to queries
Works without sudo privileges using standard Python libraries
"""

import socket
import struct
import sys
import argparse
import time
from typing import Optional, Tuple, List


class DNSQuery:
    def __init__(self):
        self.query_id = 0x1234  # Query ID
        
    def build_query(self, domain: str, query_type: str = 'A') -> bytes:
        """Build a DNS query packet"""
        # DNS Header (12 bytes)
        # ID (2 bytes) + Flags (2 bytes) + Questions (2 bytes) + 
        # Answer RRs (2 bytes) + Authority RRs (2 bytes) + Additional RRs (2 bytes)
        header = struct.pack('>HHHHHH', 
                           self.query_id,  # Query ID
                           0x0100,         # Flags: standard query, recursion desired
                           1,              # Questions: 1
                           0,              # Answer RRs: 0
                           0,              # Authority RRs: 0
                           0)              # Additional RRs: 0
        
        # Question section
        question = self._encode_domain(domain)
        
        # Query type and class
        if query_type.upper() == 'A':
            qtype = 1
        elif query_type.upper() == 'AAAA':
            qtype = 28
        elif query_type.upper() == 'MX':
            qtype = 15
        elif query_type.upper() == 'CNAME':
            qtype = 5
        else:
            qtype = 1  # Default to A record
            
        question += struct.pack('>HH', qtype, 1)  # Type A, Class IN
        
        return header + question
    
    def _encode_domain(self, domain: str) -> bytes:
        """Encode domain name for DNS query"""
        encoded = b''
        for part in domain.split('.'):
            encoded += struct.pack('B', len(part)) + part.encode('ascii')
        encoded += b'\x00'  # End of domain name
        return encoded
    
    def query_dns_server(self, dns_server: str, domain: str, query_type: str = 'A', 
                        timeout: float = 3.0) -> Tuple[Optional[str], float, bool]:
        """
        Query a specific DNS server
        Returns: (server_ip, response_time, success)
        """
        try:
            start_time = time.time()
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # Build and send query
            query = self.build_query(domain, query_type)
            sock.sendto(query, (dns_server, 53))
            
            # Receive response
            response, server_addr = sock.recvfrom(1024)
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            sock.close()
            
            # Return the actual IP that responded
            return server_addr[0], response_time, True
            
        except socket.timeout:
            return None, 0.0, False
        except socket.gaierror as e:
            print(f"Error resolving DNS server {dns_server}: {e}")
            return None, 0.0, False
        except Exception as e:
            print(f"Error querying DNS server {dns_server}: {e}")
            return None, 0.0, False
    
    def get_system_dns_servers(self) -> List[str]:
        """Get DNS servers from system configuration"""
        dns_servers = []
        
        try:
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('nameserver'):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns_servers.append(parts[1])
        except FileNotFoundError:
            print("Could not read /etc/resolv.conf")
        except PermissionError:
            print("No permission to read /etc/resolv.conf")
        
        return dns_servers
    
    def reverse_dns_lookup(self, ip: str) -> Optional[str]:
        """Perform reverse DNS lookup to get hostname"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror):
            return None


def main():
    parser = argparse.ArgumentParser(
        description='DNS Query Tool - Identify which DNS server responds to queries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s google.com                    # Query system DNS servers for google.com
  %(prog)s google.com -s 8.8.8.8        # Query specific DNS server
  %(prog)s google.com -t AAAA           # Query for AAAA record
  %(prog)s google.com -s 8.8.8.8,1.1.1.1 # Query multiple DNS servers
        """
    )
    
    parser.add_argument('domain', help='Domain name to query')
    parser.add_argument('-s', '--servers', 
                       help='DNS server(s) to query (comma-separated). If not specified, uses system DNS servers')
    parser.add_argument('-t', '--type', default='A', 
                       choices=['A', 'AAAA', 'MX', 'CNAME'],
                       help='Query type (default: A)')
    parser.add_argument('--timeout', type=float, default=3.0,
                       help='Timeout in seconds (default: 3.0)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    dns_query = DNSQuery()
    
    # Determine which DNS servers to query
    if args.servers:
        dns_servers = [s.strip() for s in args.servers.split(',')]
    else:
        dns_servers = dns_query.get_system_dns_servers()
        if not dns_servers:
            print("No DNS servers found. Please specify with -s option.")
            sys.exit(1)
    
    print(f"Querying for {args.domain} ({args.type} record)")
    print("-" * 60)
    
    for dns_server in dns_servers:
        print(f"Querying DNS server: {dns_server}")
        
        # Query the DNS server
        responding_ip, response_time, success = dns_query.query_dns_server(
            dns_server, args.domain, args.type, args.timeout
        )
        
        if success:
            print(f"  ✓ Response received from: {responding_ip}")
            print(f"  ✓ Response time: {response_time:.2f} ms")
            
            # Try to get hostname for the responding IP
            hostname = dns_query.reverse_dns_lookup(responding_ip)
            if hostname:
                print(f"  ✓ DNS server hostname: {hostname}")
            else:
                print(f"  ✓ DNS server hostname: (reverse lookup failed)")
            
            # Check if responding IP matches queried server
            if responding_ip != dns_server:
                print(f"  ! Note: Queried {dns_server} but {responding_ip} responded")
                print(f"    This could indicate load balancing or DNS forwarding")
        else:
            print(f"  ✗ No response (timeout after {args.timeout}s)")
        
        print()


if __name__ == '__main__':
    main()