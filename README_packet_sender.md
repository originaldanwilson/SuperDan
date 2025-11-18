# Network Packet Sender Tool

A Python-based UDP packet generator for network testing and WAN link stress testing. Designed for white-hat network engineers testing connections with configurable packet sizes, rates, and threading.

## Features

- **Variable packet rates**: Configure packets per second (PPS)
- **Multi-threaded**: Distribute load across multiple threads
- **Flexible packet sizes**: Fixed, increasing (100-1500), or decreasing (1500-100) byte patterns
- **Duration control**: Set test duration in seconds
- **Interface binding**: Bind to specific local IPs on multi-interface machines (no root required)
- **Real-time statistics**: Live monitoring of packets sent, throughput, and rate
- **Cross-platform**: Compatible with Python 3.12.7 on Windows and Linux

## Requirements

- Python 3.12.7 (or compatible version)
- No additional dependencies (uses standard library only)
- No root/admin privileges required (for standard operation)


## Basic Usage

```bash
# Basic test with defaults (64 bytes, 100 pps, 60 seconds)
python packet_sender.py 192.168.1.100

# Custom packet size and rate
python packet_sender.py 192.168.1.100 -s 1400 -r 1000

# Multi-threaded with custom duration
python packet_sender.py 192.168.1.100 -t 8 -d 300 -r 5000

# Variable packet sizes (MTU testing)
python packet_sender.py 192.168.1.100 -m increasing
python packet_sender.py 192.168.1.100 -m decreasing

# Bind to specific interface (multi-homed machines)
python packet_sender.py 192.168.1.100 --bind-ip 10.0.50.5
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `target_ip` | Target IP address (required) | - |
| `-p, --port` | Target UDP port | 9999 |
| `-s, --size` | Packet size in bytes | 64 |
| `-d, --duration` | Test duration in seconds | 60 |
| `-r, --rate` | Packets per second | 100 |
| `-t, --threads` | Number of threads | 1 |
| `-m, --mode` | Packet size mode: `fixed`, `increasing`, `decreasing` | fixed |
| `--bind-ip` | Local IP to bind to (no root required) | - |
| `--source-ip` | Spoof source IP (requires root/admin) | - |

## WAN Link Stress Testing

### Single Machine Example

Saturate a 100 Mbps link:

```bash
# ~90 Mbps: 1400 bytes × 8000 pps × 8 bits/byte
python packet_sender.py <wan-target> -s 1400 -r 8000 -t 4 -d 300
```

### Multi-Machine Distributed Testing

To stress test a WAN link with multiple source machines:

**Machine 1:**
```bash
python packet_sender.py <wan-target> -s 1400 -r 5000 -t 8 -d 300
```

**Machine 2:**
```bash
python packet_sender.py <wan-target> -s 1400 -r 5000 -t 8 -d 300
```

**Machine 3:**
```bash
python packet_sender.py <wan-target> -s 1400 -r 5000 -t 8 -d 300
```

**Result:** ~200 Mbps aggregate traffic across the WAN link

### Bandwidth Planning

Calculate required rate for target bandwidth:

```
Throughput (Mbps) = (Packet Size × PPS × 8) / 1,000,000

Example:
- 1400 bytes × 5000 pps × 8 = 56 Mbps per machine
- 1400 bytes × 10000 pps × 8 = 112 Mbps per machine
```

### Testing Tips

1. **MTU/Fragmentation Testing**: Use `-m increasing` to cycle through packet sizes from 100-1500 bytes
2. **Stagger Starts**: Start machines a few seconds apart to avoid synchronized bursts
3. **Monitor Traffic**: Use `iftop`, `nload`, or similar tools to verify actual throughput
4. **Target Selection**: Point all senders at a single target IP beyond the WAN link you're testing
5. **Corporate Machines**: Use `--bind-ip` to select specific interfaces without root privileges
6. **Baseline First**: Test with low rates first, then scale up incrementally

## Example Scenarios

### Test 1: Basic Connectivity Test
```bash
# Low-rate, small packets for 30 seconds
python packet_sender.py 10.1.1.1 -s 64 -r 100 -d 30
```

### Test 2: MTU Discovery
```bash
# Increasing packet sizes to find fragmentation point
python packet_sender.py 10.1.1.1 -m increasing -r 500 -d 120
```

### Test 3: High-Throughput Stress Test
```bash
# Large packets, high rate, multiple threads
python packet_sender.py 10.1.1.1 -s 1400 -r 10000 -t 16 -d 600
```

### Test 4: Multi-Interface Testing
```bash
# Send from specific source IP on multi-homed machine
python packet_sender.py 10.1.1.1 --bind-ip 192.168.50.10 -r 1000
```

## Output Example

```
============================================================
Packet Sender Starting
============================================================
Target: 192.168.1.100:9999
Packet Size: 1400 bytes (mode: fixed)
Duration: 60 seconds
Rate: 5000 packets/second
Threads: 4
============================================================

Elapsed: 60.0s | Packets: 300,000 | Bytes: 420,000,000 | Rate: 5000.0 pps

============================================================
Packet Sender Complete
============================================================
Duration: 60.02 seconds
Packets Sent: 300,012
Bytes Sent: 420,016,800 (400.63 MB)
Average Rate: 4999.80 packets/second
Average Throughput: 6.68 MB/s
============================================================
```

## Advanced Features

### Source IP Spoofing (Requires Root)

**Warning:** IP spoofing requires root/admin privileges and may be blocked by network infrastructure (BCP 38 egress filtering). Only use in controlled lab environments.

```bash
sudo python packet_sender.py 192.168.1.100 --source-ip 10.0.0.5
```

### Multi-Interface Binding (No Root Required)

For machines with multiple network interfaces, bind to a specific local IP:

```bash
# List available interfaces
ip addr show  # Linux
ipconfig      # Windows

# Bind to specific interface
python packet_sender.py 192.168.1.100 --bind-ip 10.0.50.5
```

## Safety and Legal Considerations

- **Authorization Required**: Only test networks you own or have explicit permission to test
- **White Hat Use**: This tool is designed for legitimate network engineering and testing
- **Avoid Production Impact**: Test during maintenance windows or on non-production networks
- **Resource Limits**: High rates/thread counts can saturate local CPU and network resources
- **Target Capacity**: Ensure target systems can handle the expected load

## Troubleshooting

### "Permission denied" error with --source-ip
- Solution: Run with `sudo` (Linux) or Administrator privileges (Windows)
- Alternative: Remove `--source-ip` flag to use standard sockets

### Cannot bind to specified IP
- Verify the IP exists on a local interface: `ip addr show` (Linux) or `ipconfig` (Windows)
- Check for typos in the IP address
- Ensure no other process is exclusively using that IP

### Actual rate lower than requested
- CPU limitations: Reduce threads or rate
- Network interface saturation: Lower packet size or rate
- OS socket buffer limits: May need to adjust system parameters

### "Connection refused" or "Network unreachable"
- Verify target IP is reachable: `ping <target>`
- Check firewall rules on sender and receiver
- Verify routing table: `ip route` (Linux) or `route print` (Windows)

## License

MIT License - See repository for details

## Author

Network Engineering Team - SuperDan Project

## Contributing

Contributions welcome! Please submit pull requests or open issues on GitHub.
