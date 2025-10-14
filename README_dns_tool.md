# DNS Query Tool

A Python tool that identifies which DNS server responds to your queries. Perfect for environments without sudo privileges, using only standard Python libraries.

## Features

- Query specific DNS servers or use system default DNS servers
- Support for multiple record types (A, AAAA, MX, CNAME)
- Shows actual responding IP address (useful for load-balanced DNS servers)
- Performs reverse DNS lookup to show server hostnames
- Measures response times
- No external dependencies - uses only Python standard library

## Requirements

- Python 3.6+
- Standard Python libraries only (socket, struct, sys, argparse, time)
- No sudo privileges required

## Usage

### Basic Examples

```bash
# Query system DNS servers for google.com
python3 dns_query_tool.py google.com

# Query a specific DNS server
python3 dns_query_tool.py google.com -s 8.8.8.8

# Query multiple DNS servers
python3 dns_query_tool.py google.com -s 8.8.8.8,1.1.1.1,208.67.222.222

# Query for different record types
python3 dns_query_tool.py google.com -t AAAA          # IPv6 records
python3 dns_query_tool.py google.com -t MX            # Mail exchange records
python3 dns_query_tool.py google.com -t CNAME        # Canonical name records
```

### Advanced Usage

```bash
# Set custom timeout (useful for slow networks)
python3 dns_query_tool.py example.com --timeout 5.0

# Use as executable script
./dns_query_tool.py google.com -s 8.8.8.8
```

## Sample Output

```
Querying for google.com (A record)
------------------------------------------------------------
Querying DNS server: 8.8.8.8
  ✓ Response received from: 8.8.8.8
  ✓ Response time: 41.03 ms
  ✓ DNS server hostname: dns.google

Querying DNS server: 1.1.1.1
  ✓ Response received from: 1.1.1.1
  ✓ Response time: 23.45 ms
  ✓ DNS server hostname: one.one.one.one
```

## Common Use Cases

1. **Troubleshooting DNS Issues**: Identify which server is actually responding
2. **Network Analysis**: Check if DNS requests are being intercepted or redirected
3. **Performance Testing**: Compare response times between different DNS servers
4. **Load Balancer Detection**: See if DNS servers use load balancing (responding IP differs from queried IP)
5. **DNS Monitoring**: Automated scripts to monitor DNS server availability

## Popular DNS Servers to Test

- **Google DNS**: 8.8.8.8, 8.8.4.4
- **Cloudflare DNS**: 1.1.1.1, 1.0.0.1
- **OpenDNS**: 208.67.222.222, 208.67.220.220
- **Quad9**: 9.9.9.9, 149.112.112.112

## RedHat/Enterprise Environment Notes

- Works without sudo privileges
- Uses only standard Python libraries available on most systems
- Queries port 53 using UDP (standard DNS protocol)
- Reads system DNS servers from `/etc/resolv.conf`
- Compatible with enterprise firewalls (uses standard DNS queries)

## Troubleshooting

- If you get "No DNS servers found", specify servers manually with `-s`
- If queries timeout, try increasing timeout with `--timeout`
- If reverse DNS lookup fails, the tool will still show the IP address
- For systems without `/etc/resolv.conf` access, always use `-s` option