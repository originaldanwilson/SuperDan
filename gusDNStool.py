#!/usr/bin/env python3
"""
DNS Performance Testing Tool for SD-WAN/Network Engineers

Features:
- Configurable requests per second (RPS) rate limiting
- Multi-threaded worker support
- Detailed timestamps and logging
- Support for local or remote domain lists
- Comprehensive error classification
- Real-time statistics display
- Portable - single Python file with minimal dependencies

Usage:
    python3 dns_perf_test.py --server 8.8.8.8 --rate 100 --duration 60 --threads 10
    python3 dns_perf_test.py --server 10.1.1.1 --domains domains.txt --rate 50 --threads 5
"""

import argparse
import dns.resolver
import dns.exception
import time
import threading
import queue
import sys
import urllib.request
import random
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path

# Default domain list for testing (Top Alexa domains)
DEFAULT_DOMAINS = [
    'google.com', 'youtube.com', 'facebook.com', 'baidu.com', 'wikipedia.org',
    'yahoo.com', 'reddit.com', 'amazon.com', 'twitter.com', 'instagram.com',
    'linkedin.com', 'netflix.com', 'microsoft.com', 'apple.com', 'ebay.com',
    'stackoverflow.com', 'github.com', 'wordpress.com', 'adobe.com', 'spotify.com',
    'cnn.com', 'bbc.com', 'nytimes.com', 'zoom.us', 'cloudflare.com',
    'paypal.com', 'salesforce.com', 'dropbox.com', 'office.com', 'bing.com',
    'imdb.com', 'craigslist.org', 'whatsapp.com', 'twitch.tv', 'pinterest.com',
    'etsy.com', 'quora.com', 'tumblr.com', 'yelp.com', 'medium.com',
    'cisco.com', 'oracle.com', 'ibm.com', 'intel.com', 'hp.com',
    'dell.com', 'samsung.com', 'huawei.com', 'aliexpress.com', 'booking.com'
]

class DNSStats:
    """Thread-safe statistics collector"""
    def __init__(self):
        self.lock = threading.Lock()
        self.total_queries = 0
        self.successful = 0
        self.failed = 0
        self.timeout = 0
        self.nxdomain = 0
        self.servfail = 0
        self.refused = 0
        self.nodata = 0
        self.network_error = 0
        self.other_errors = 0
        self.response_times = []
        self.error_details = Counter()
        self.start_time = None
        self.end_time = None
        
    def record_success(self, response_time):
        with self.lock:
            self.total_queries += 1
            self.successful += 1
            self.response_times.append(response_time)
    
    def record_failure(self, error_type, error_detail):
        with self.lock:
            self.total_queries += 1
            self.failed += 1
            
            if error_type == 'TIMEOUT':
                self.timeout += 1
            elif error_type == 'NXDOMAIN':
                self.nxdomain += 1
            elif error_type == 'SERVFAIL':
                self.servfail += 1
            elif error_type == 'REFUSED':
                self.refused += 1
            elif error_type == 'NODATA':
                self.nodata += 1
            elif error_type == 'NETWORK':
                self.network_error += 1
            else:
                self.other_errors += 1
            
            self.error_details[f"{error_type}: {error_detail}"] += 1
    
    def get_stats(self):
        with self.lock:
            if self.response_times:
                sorted_times = sorted(self.response_times)
                avg_time = sum(self.response_times) / len(self.response_times)
                min_time = min(self.response_times)
                max_time = max(self.response_times)
                p50 = sorted_times[len(sorted_times) // 2]
                p95 = sorted_times[int(len(sorted_times) * 0.95)]
                p99 = sorted_times[int(len(sorted_times) * 0.99)]
            else:
                avg_time = min_time = max_time = p50 = p95 = p99 = 0
            
            elapsed = (self.end_time or time.time()) - (self.start_time or time.time())
            qps = self.total_queries / elapsed if elapsed > 0 else 0
            
            return {
                'total': self.total_queries,
                'successful': self.successful,
                'failed': self.failed,
                'success_rate': (self.successful / self.total_queries * 100) if self.total_queries > 0 else 0,
                'timeout': self.timeout,
                'nxdomain': self.nxdomain,
                'servfail': self.servfail,
                'refused': self.refused,
                'nodata': self.nodata,
                'network': self.network_error,
                'other': self.other_errors,
                'avg_time': avg_time,
                'min_time': min_time,
                'max_time': max_time,
                'p50_time': p50,
                'p95_time': p95,
                'p99_time': p99,
                'elapsed': elapsed,
                'qps': qps,
                'error_details': dict(self.error_details.most_common(10))
            }

class DNSWorker(threading.Thread):
    """Worker thread for DNS queries"""
    def __init__(self, worker_id, work_queue, stats, dns_server, timeout, log_file):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.work_queue = work_queue
        self.stats = stats
        self.dns_server = dns_server
        self.timeout = timeout
        self.log_file = log_file
        self.resolver = None
        self.running = True
        
    def setup_resolver(self):
        """Setup DNS resolver for this worker"""
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = [self.dns_server]
        self.resolver.timeout = self.timeout
        self.resolver.lifetime = self.timeout
        
    def run(self):
        self.setup_resolver()
        
        while self.running:
            try:
                domain = self.work_queue.get(timeout=0.1)
                if domain is None:  # Poison pill to stop worker
                    break
                
                self.query_domain(domain)
                self.work_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
    
    def query_domain(self, domain):
        """Perform DNS query and record results"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        start_time = time.time()
        
        try:
            answer = self.resolver.resolve(domain, 'A')
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            ip_addresses = [str(rdata) for rdata in answer]
            result = 'SUCCESS'
            detail = f"Resolved to {', '.join(ip_addresses)}"
            
            self.stats.record_success(response_time)
            
            # Log success
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except dns.resolver.NXDOMAIN as e:
            response_time = (time.time() - start_time) * 1000
            result = 'NXDOMAIN'
            detail = 'Domain not found'
            self.stats.record_failure('NXDOMAIN', detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except dns.resolver.Timeout as e:
            response_time = (time.time() - start_time) * 1000
            result = 'TIMEOUT'
            detail = f'Query timeout after {self.timeout}s'
            self.stats.record_failure('TIMEOUT', detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except dns.resolver.NoAnswer as e:
            response_time = (time.time() - start_time) * 1000
            result = 'NODATA'
            detail = 'No A records found'
            self.stats.record_failure('NODATA', detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except dns.resolver.NoNameservers as e:
            response_time = (time.time() - start_time) * 1000
            result = 'SERVFAIL'
            detail = 'All nameservers failed (SERVFAIL or network issue)'
            self.stats.record_failure('SERVFAIL', detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except dns.exception.DNSException as e:
            response_time = (time.time() - start_time) * 1000
            result = 'DNS_ERROR'
            detail = str(e)
            
            # Classify DNS errors
            if 'REFUSED' in str(e).upper():
                error_type = 'REFUSED'
            elif 'SERVFAIL' in str(e).upper():
                error_type = 'SERVFAIL'
            else:
                error_type = 'OTHER'
            
            self.stats.record_failure(error_type, detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = 'ERROR'
            detail = str(e)
            self.stats.record_failure('NETWORK', detail)
            log_line = f"{timestamp} | Worker-{self.worker_id:02d} | {domain:40s} | {result:10s} | {response_time:7.2f}ms | {detail}\n"
        
        # Write to log file and stdout
        if self.log_file:
            self.log_file.write(log_line)
            self.log_file.flush()
        
        # Print to console (with less verbosity for high rates)
        if self.stats.total_queries % 100 == 0 or result != 'SUCCESS':
            print(log_line.rstrip())

def load_domains(domains_source):
    """Load domains from file or URL"""
    domains = []
    
    # Check if it's a URL
    if domains_source.startswith('http://') or domains_source.startswith('https://'):
        try:
            print(f"Downloading domain list from {domains_source}...")
            response = urllib.request.urlopen(domains_source, timeout=30)
            content = response.read().decode('utf-8')
            domains = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(domains)} domains from URL")
        except Exception as e:
            print(f"Error downloading domain list: {e}")
            print("Using default domain list instead")
            domains = DEFAULT_DOMAINS.copy()
    
    # Check if it's a file
    elif Path(domains_source).is_file():
        try:
            print(f"Loading domain list from {domains_source}...")
            with open(domains_source, 'r') as f:
                domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(domains)} domains from file")
        except Exception as e:
            print(f"Error reading domain file: {e}")
            print("Using default domain list instead")
            domains = DEFAULT_DOMAINS.copy()
    
    # Use default if empty
    if not domains:
        print("Using default domain list")
        domains = DEFAULT_DOMAINS.copy()
    
    return domains

def rate_limited_feeder(work_queue, domains, target_rate, duration):
    """Feed work queue at specified rate"""
    interval = 1.0 / target_rate  # Time between queries
    end_time = time.time() + duration
    query_count = 0
    
    print(f"Starting DNS queries at {target_rate} requests/second for {duration} seconds")
    
    while time.time() < end_time:
        domain = random.choice(domains)  # Random selection from domain list
        work_queue.put(domain)
        query_count += 1
        
        # Sleep to maintain rate
        time.sleep(interval)
    
    print(f"\nQueued {query_count} total queries")

def print_stats_header():
    """Print statistics header"""
    print("\n" + "=" * 120)
    print(f"{'Timestamp':<20} | {'Total':>8} | {'Success':>8} | {'Failed':>8} | {'Rate %':>7} | {'QPS':>7} | {'Avg(ms)':>8} | {'P95(ms)':>8}")
    print("=" * 120)

def print_live_stats(stats):
    """Print live statistics"""
    s = stats.get_stats()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp:<20} | {s['total']:>8} | {s['successful']:>8} | {s['failed']:>8} | {s['success_rate']:>6.1f}% | {s['qps']:>7.1f} | {s['avg_time']:>7.2f} | {s['p95_time']:>7.2f}")

def print_final_report(stats, args, log_filename):
    """Print comprehensive final report"""
    s = stats.get_stats()
    
    print("\n" + "=" * 120)
    print("DNS PERFORMANCE TEST RESULTS")
    print("=" * 120)
    
    print("\nTest Configuration:")
    print(f"  DNS Server:        {args.server}")
    print(f"  Target Rate:       {args.rate} queries/second")
    print(f"  Duration:          {args.duration} seconds")
    print(f"  Worker Threads:    {args.threads}")
    print(f"  Query Timeout:     {args.timeout} seconds")
    print(f"  Domain Source:     {args.domains}")
    
    print("\nOverall Results:")
    print(f"  Total Queries:     {s['total']}")
    print(f"  Successful:        {s['successful']} ({s['success_rate']:.2f}%)")
    print(f"  Failed:            {s['failed']}")
    print(f"  Actual QPS:        {s['qps']:.2f}")
    print(f"  Test Duration:     {s['elapsed']:.2f} seconds")
    
    print("\nResponse Times (milliseconds):")
    print(f"  Average:           {s['avg_time']:.2f} ms")
    print(f"  Minimum:           {s['min_time']:.2f} ms")
    print(f"  Maximum:           {s['max_time']:.2f} ms")
    print(f"  50th Percentile:   {s['p50_time']:.2f} ms")
    print(f"  95th Percentile:   {s['p95_time']:.2f} ms")
    print(f"  99th Percentile:   {s['p99_time']:.2f} ms")
    
    print("\nError Breakdown:")
    print(f"  Timeouts:          {s['timeout']}")
    print(f"  NXDOMAIN:          {s['nxdomain']}")
    print(f"  SERVFAIL:          {s['servfail']}")
    print(f"  REFUSED:           {s['refused']}")
    print(f"  NODATA:            {s['nodata']}")
    print(f"  Network Errors:    {s['network']}")
    print(f"  Other Errors:      {s['other']}")
    
    if s['error_details']:
        print("\nTop Error Details:")
        for error, count in list(s['error_details'].items())[:10]:
            print(f"  {error}: {count}")
    
    print("\nInterpretation Guide:")
    if s['timeout'] == s['failed'] and s['failed'] > 0:
        print("  → All queries timing out: DNS server unreachable or overloaded")
    if s['servfail'] > s['failed'] * 0.5:
        print("  → High SERVFAIL rate: DNS misconfiguration or upstream issues")
    if s['nxdomain'] > s['failed'] * 0.5:
        print("  → High NXDOMAIN rate: Check domain list validity")
    if s['avg_time'] > 100:
        print("  → High average latency: DNS server may be slow or overloaded")
    if s['success_rate'] < 90:
        print("  → Low success rate: Investigate DNS infrastructure")
    
    print(f"\nDetailed log saved to: {log_filename}")
    print("=" * 120)

def main():
    parser = argparse.ArgumentParser(
        description='DNS Performance Testing Tool for Network Engineers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Test local DNS server at 100 QPS for 60 seconds:
    %(prog)s --server 10.1.1.1 --rate 100 --duration 60 --threads 10

  Test Google DNS with custom domain list:
    %(prog)s --server 8.8.8.8 --domains domains.txt --rate 50 --threads 5

  Download domain list from URL:
    %(prog)s --server 1.1.1.1 --domains https://example.com/domains.txt --rate 200

  Quick 10-second test:
    %(prog)s --server 8.8.8.8 --rate 50 --duration 10
        """
    )
    
    parser.add_argument('--server', '-s', required=True,
                        help='DNS server IP address to test')
    parser.add_argument('--rate', '-r', type=int, default=10,
                        help='Target queries per second (default: 10)')
    parser.add_argument('--duration', '-d', type=int, default=60,
                        help='Test duration in seconds (default: 60)')
    parser.add_argument('--threads', '-t', type=int, default=5,
                        help='Number of worker threads (default: 5)')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='DNS query timeout in seconds (default: 5.0)')
    parser.add_argument('--domains', default=None,
                        help='Domain list file or URL (default: built-in list)')
    parser.add_argument('--output', '-o', default=None,
                        help='Output log filename (default: dns_test_TIMESTAMP.log)')
    
    args = parser.parse_args()
    
    # Generate log filename if not specified
    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f'dns_test_{timestamp}.log'
    
    # Load domains
    if args.domains:
        domains = load_domains(args.domains)
    else:
        domains = DEFAULT_DOMAINS.copy()
        print(f"Using built-in domain list ({len(domains)} domains)")
    
    if not domains:
        print("ERROR: No domains available for testing")
        sys.exit(1)
    
    # Setup
    stats = DNSStats()
    stats.start_time = time.time()
    work_queue = queue.Queue(maxsize=args.rate * 10)  # Buffer
    
    print("\n" + "=" * 120)
    print("DNS PERFORMANCE TEST")
    print("=" * 120)
    print(f"Server: {args.server} | Rate: {args.rate} QPS | Duration: {args.duration}s | Workers: {args.threads}")
    print("=" * 120)
    
    # Open log file
    try:
        log_file = open(args.output, 'w')
        log_file.write(f"DNS Performance Test Log\n")
        log_file.write(f"Server: {args.server}\n")
        log_file.write(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"Target Rate: {args.rate} QPS\n")
        log_file.write(f"Duration: {args.duration} seconds\n")
        log_file.write(f"Workers: {args.threads}\n")
        log_file.write("=" * 120 + "\n")
        log_file.write(f"{'Timestamp':<26} | {'Worker':<10} | {'Domain':<40} | {'Result':<10} | {'Time':<10} | Details\n")
        log_file.write("=" * 120 + "\n")
    except Exception as e:
        print(f"ERROR: Could not open log file {args.output}: {e}")
        sys.exit(1)
    
    # Start workers
    workers = []
    for i in range(args.threads):
        worker = DNSWorker(i, work_queue, stats, args.server, args.timeout, log_file)
        worker.start()
        workers.append(worker)
    
    print(f"Started {args.threads} worker threads")
    
    # Start feeder thread
    feeder = threading.Thread(target=rate_limited_feeder, 
                             args=(work_queue, domains, args.rate, args.duration),
                             daemon=True)
    feeder.start()
    
    # Monitor progress
    print_stats_header()
    
    last_print = time.time()
    while feeder.is_alive() or not work_queue.empty():
        if time.time() - last_print >= 5:  # Print stats every 5 seconds
            print_live_stats(stats)
            last_print = time.time()
        time.sleep(0.5)
    
    # Wait for queue to drain
    print("\nWaiting for remaining queries to complete...")
    work_queue.join()
    
    # Stop workers
    for _ in workers:
        work_queue.put(None)  # Poison pill
    
    for worker in workers:
        worker.join(timeout=2)
    
    stats.end_time = time.time()
    
    # Print final stats
    print_live_stats(stats)
    
    # Close log file
    log_file.close()
    
    # Print final report
    print_final_report(stats, args, args.output)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
