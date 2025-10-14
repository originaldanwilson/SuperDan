# DNS Query Tool

A cross-platform Python tool that identifies which DNS server responds to your queries. Works on Windows, Linux (including Ubuntu with systemd-resolved), macOS, and RedHat systems without requiring sudo privileges.

## Features

- **Cross-platform**: Works on Windows, Linux, macOS
- **Smart DNS detection**: Handles systemd-resolved, NetworkManager, traditional resolv.conf
- **Query specific DNS servers** or automatically detect system DNS servers
- **Multiple record types**: A, AAAA, MX, CNAME
- **Load balancer detection**: Shows actual responding IP vs queried server
- **Reverse DNS lookup**: Shows server hostnames when available
- **Response time measurement**: Performance testing capabilities
- **No external dependencies**: Uses only Python standard library
- **No privileges required**: Works without sudo/admin rights

## Requirements

- Python 3.6+
- Standard Python libraries only (socket, struct, sys, argparse, time, platform, subprocess, re)
- No sudo/administrator privileges required

## Usage

### Linux/macOS Examples

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

# Use as executable script
./dns_query_tool.py google.com -s 8.8.8.8
```

### Windows Examples

```cmd
REM Query system DNS servers
python dns_query_tool.py google.com

REM Query specific DNS server
python dns_query_tool.py google.com -s 8.8.8.8

REM Use the batch file wrapper
dns_query_tool.bat google.com -s 1.1.1.1

REM Query multiple servers with verbose output
python dns_query_tool.py google.com -s 8.8.8.8,1.1.1.1 -v
```

### Advanced Usage

```bash
# Verbose mode shows platform and DNS detection method
python3 dns_query_tool.py google.com -v

# Set custom timeout (useful for slow networks)
python3 dns_query_tool.py example.com --timeout 5.0

# Test multiple record types
python3 dns_query_tool.py example.com -t MX -v
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

## Platform Compatibility

### Linux (including RedHat, Ubuntu, CentOS)
- **Traditional systems**: Reads `/etc/resolv.conf`
- **Ubuntu 18.04+**: Automatically detects systemd-resolved DNS servers
- **NetworkManager**: Uses `nmcli` to detect DNS configuration
- **systemd-resolved**: Uses `resolvectl` or `systemd-resolve` commands
- Works without sudo privileges
- Compatible with enterprise firewalls

### Windows (Windows 10, 11, Server)
- **Detection methods**: Uses `nslookup` and `ipconfig /all`
- **Batch wrapper**: Included `dns_query_tool.bat` for easy Windows usage
- Works without administrator privileges
- Compatible with Windows Defender and corporate antivirus

### macOS
- Uses `scutil --dns` to detect system DNS servers
- Works with both Wi-Fi and Ethernet configurations
- No sudo privileges required

## Troubleshooting

### General Issues
- If you get "No DNS servers found", specify servers manually with `-s`
- If queries timeout, try increasing timeout with `--timeout 10`
- If reverse DNS lookup fails, the tool will still show the IP address
- Use `-v` (verbose) mode to see platform detection details

### Ubuntu with systemd-resolved
- The tool automatically detects real DNS servers (not 127.0.0.53)
- Uses multiple detection methods: `resolvectl`, `systemd-resolve`, `nmcli`
- If detection fails, manually specify servers with `-s`

### Windows-specific
- Ensure Python is in your PATH
- Use `dns_query_tool.bat` for easier Windows usage
- If `nslookup` fails, the tool falls back to `ipconfig /all`
- Corporate networks may have additional DNS servers not detected automatically

### Enterprise/Corporate Networks
- Tool works through most corporate firewalls (uses standard DNS port 53)
- May detect internal DNS servers in corporate environments
- If behind a proxy, DNS queries should still work normally
- For additional security, tool never modifies system settings
