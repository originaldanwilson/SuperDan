# gusDNStool.py - DNS Performance Testing Tool

A professional DNS performance testing tool designed for network engineers testing SD-WAN boxes and DNS infrastructure.

## Features

- **Rate Control**: Specify exact queries per second (QPS)
- **Multi-threaded**: Configurable worker threads for high load
- **Timestamps**: Millisecond-precision timestamps in logs and console
- **Flexible Domain Lists**: Use built-in domains, local files, or download from URLs
- **Detailed Error Classification**: Comprehensive failure analysis including:
  - TIMEOUT - DNS server not responding
  - NXDOMAIN - Domain not found
  - SERVFAIL - Server failure or misconfiguration
  - REFUSED - Query refused by server
  - NODATA - No A records
  - Network errors
- **Real-time Stats**: Live statistics every 5 seconds
- **Portable**: Single Python file, minimal dependencies

## Requirements

```bash
pip install dnspython
```

Or from your project requirements:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Examples

Test a DNS server at 10 QPS for 60 seconds (default):
```bash
python3 gusDNStool.py --server 8.8.8.8
```

Test your SD-WAN box at 100 QPS for 60 seconds with 10 workers:
```bash
python3 gusDNStool.py --server 10.1.1.1 --rate 100 --duration 60 --threads 10
```

Quick 10-second test:
```bash
python3 gusDNStool.py --server 8.8.8.8 --rate 50 --duration 10
```

### Custom Domain Lists

Use a local domain list file:
```bash
python3 gusDNStool.py --server 10.1.1.1 --domains domains.txt --rate 50
```

Download domain list from URL:
```bash
python3 gusDNStool.py --server 8.8.8.8 --domains https://example.com/domains.txt --rate 100
```

### Advanced Options

Specify output file and timeout:
```bash
python3 gusDNStool.py --server 10.1.1.1 \
    --rate 200 \
    --duration 120 \
    --threads 20 \
    --timeout 3.0 \
    --output my_test.log
```

## Command Line Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--server` | `-s` | *required* | DNS server IP address to test |
| `--rate` | `-r` | 10 | Target queries per second |
| `--duration` | `-d` | 60 | Test duration in seconds |
| `--threads` | `-t` | 5 | Number of worker threads |
| `--timeout` | | 5.0 | DNS query timeout in seconds |
| `--domains` | | Built-in | Domain list file or URL |
| `--output` | `-o` | `dns_test_TIMESTAMP.log` | Output log filename |

## Output

### Console Output

Real-time statistics table showing:
- Total queries
- Successful queries
- Failed queries
- Success rate percentage
- Actual QPS achieved
- Average response time (ms)
- 95th percentile response time (ms)

### Log File

Detailed per-query log with:
- Timestamp (millisecond precision)
- Worker thread ID
- Domain queried
- Result status
- Response time
- IP addresses resolved or error details

### Final Report

Comprehensive summary including:
- Test configuration
- Overall results and success rate
- Response time statistics (avg, min, max, P50, P95, P99)
- Error breakdown by type
- Top 10 error details
- Interpretation guide

## Error Interpretation Guide

### Common Scenarios

**All resolvers time out**
- Domain/NS unreachable
- DNSSEC break
- Network filter blocking DNS

**Only your resolver times out**
- Local caching server issue
- SD-WAN box overloaded

**Public resolvers answer but slow**
- Upstream authoritative delay
- Network congestion

**UDP fails, TCP works**
- EDNS/fragmentation issue
- Firewall blocking large UDP packets

**SERVFAIL**
- DNS misconfiguration
- DNSSEC issue
- Upstream resolver problem

**NXDOMAIN**
- Domain not registered
- Check domain list validity

## Domain List Format

Create a text file with one domain per line:

```
# Comments start with #
google.com
microsoft.com
cisco.com
github.com
```

## Testing Your SD-WAN Box

### Recommended Test Strategy

1. **Baseline Test** (10 QPS, 60s):
   ```bash
   python3 gusDNStool.py --server YOUR_SDWAN_IP --rate 10 --duration 60
   ```

2. **Load Test** (100 QPS, 120s):
   ```bash
   python3 gusDNStool.py --server YOUR_SDWAN_IP --rate 100 --duration 120 --threads 10
   ```

3. **Stress Test** (500 QPS, 300s):
   ```bash
   python3 gusDNStool.py --server YOUR_SDWAN_IP --rate 500 --duration 300 --threads 20
   ```

4. **Peak Capacity Test** (gradually increase rate):
   ```bash
   for rate in 100 200 500 1000 2000; do
       echo "Testing at $rate QPS"
       python3 gusDNStool.py --server YOUR_SDWAN_IP --rate $rate --duration 60 --threads 20
       sleep 10
   done
   ```

### What to Look For

- **Success Rate**: Should be >99% for healthy DNS
- **Response Time**: 
  - P50 < 50ms: Excellent
  - P95 < 100ms: Good
  - P99 < 200ms: Acceptable
- **Actual QPS vs Target**: Should match within 10%
- **Error Types**: High TIMEOUT = capacity issue, High SERVFAIL = config issue

## Distributed Testing

To test from multiple locations, distribute this single Python file to other engineers:

```bash
# Share the tool
scp gusDNStool.py engineer@remote-host:/tmp/

# They can run it immediately
ssh engineer@remote-host "python3 /tmp/gusDNStool.py --server YOUR_SDWAN_IP --rate 50 --duration 30"
```

## Tips

- Start with low rates (10-50 QPS) to establish baseline
- Increase worker threads for rates >200 QPS
- Monitor SD-WAN box CPU/memory during tests
- Compare results against public DNS (8.8.8.8) for reference
- Save logs for different scenarios (peak hours, different locations)
- Use shorter timeouts (2-3s) for responsive testing

## Troubleshooting

**ImportError: No module named 'dns'**
```bash
pip install dnspython
```

**Permission denied**
```bash
chmod +x gusDNStool.py
```

**Low QPS achieved**
- Increase worker threads
- Check network latency
- Verify DNS server isn't rate limiting

**All timeouts**
- Verify DNS server IP is correct
- Check firewall rules
- Test with known good DNS (8.8.8.8) first

## Author

Created for network engineers testing SD-WAN and DNS infrastructure.

## License

Use freely for testing your networks.
