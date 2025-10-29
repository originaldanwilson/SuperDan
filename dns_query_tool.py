#!/usr/bin/env python3
"""
DNS Query Tool with Rate Limiting and Multiprocessing
Queries DNS domains from a file with adjustable query rate.
"""

import dns.resolver
import time
import argparse
from pathlib import Path
from multiprocessing import Pool, Manager, Lock
from typing import List, Dict, Any
from datetime import datetime


class DNSQueryTool:
    """DNS query tool with rate limiting and multiprocessing support."""
    
    def __init__(self, domains_file: str, output_file: str, queries_per_second: float = 10, workers: int = 4):
        """
        Initialize DNS Query Tool.
        
        Args:
            domains_file: Path to file containing domain names (one per line)
            output_file: Path to output file for results
            queries_per_second: Number of queries per second across all workers
            workers: Number of worker processes
        """
        self.domains_file = Path(domains_file)
        self.output_file = Path(output_file)
        self.queries_per_second = queries_per_second
        self.workers = workers
        self.delay_per_query = 1.0 / queries_per_second if queries_per_second > 0 else 0
        
    def load_domains(self) -> List[str]:
        """Load domains from input file."""
        with open(self.domains_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
        return domains
    
    @staticmethod
    def query_domain(args: tuple) -> Dict[str, Any]:
        """
        Query a single domain and return results.
        
        Args:
            args: Tuple of (domain, delay, lock, counter)
            
        Returns:
            Dictionary with query results
        """
        domain, delay, lock, counter = args
        result = {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'ips': [],
            'error': None
        }
        
        try:
            # Perform DNS query
            answers = dns.resolver.resolve(domain, 'A')
            result['ips'] = [str(rdata) for rdata in answers]
            
        except dns.resolver.NXDOMAIN:
            result['status'] = 'failed'
            result['error'] = 'NXDOMAIN'
        except dns.resolver.NoAnswer:
            result['status'] = 'failed'
            result['error'] = 'NoAnswer'
        except dns.resolver.Timeout:
            result['status'] = 'failed'
            result['error'] = 'Timeout'
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
        
        # Rate limiting
        if delay > 0:
            time.sleep(delay)
        
        # Update counter
        with lock:
            counter.value += 1
            
        return result
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """Format a result for display and file output."""
        if result['status'] == 'success':
            ips = ', '.join(result['ips'])
            return f"[{result['timestamp']}] {result['domain']} -> {ips}"
        else:
            return f"[{result['timestamp']}] {result['domain']} -> ERROR: {result['error']}"
    
    def run(self):
        """Execute DNS queries with multiprocessing."""
        print(f"Loading domains from {self.domains_file}...")
        domains = self.load_domains()
        total_domains = len(domains)
        
        print(f"Loaded {total_domains} domains")
        print(f"Query rate: {self.queries_per_second} queries/second")
        print(f"Workers: {self.workers}")
        print(f"Starting queries...\n")
        
        # Shared counter and lock for progress tracking
        manager = Manager()
        counter = manager.Value('i', 0)
        lock = manager.Lock()
        
        # Prepare arguments for workers
        query_args = [(domain, self.delay_per_query, lock, counter) for domain in domains]
        
        # Open output file
        with open(self.output_file, 'w') as out_file:
            out_file.write(f"DNS Query Results - Started: {datetime.now().isoformat()}\n")
            out_file.write(f"Total domains: {total_domains}\n")
            out_file.write(f"Query rate: {self.queries_per_second} queries/second\n")
            out_file.write("-" * 80 + "\n\n")
            
            start_time = time.time()
            
            # Process queries with multiprocessing pool
            with Pool(processes=self.workers) as pool:
                for result in pool.imap_unordered(self.query_domain, query_args):
                    # Format and display result
                    formatted = self.format_result(result)
                    print(formatted)
                    
                    # Write to output file
                    out_file.write(formatted + "\n")
                    out_file.flush()
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # Summary
            summary = (
                f"\n{'-' * 80}\n"
                f"Completed: {total_domains} queries in {elapsed:.2f} seconds\n"
                f"Average rate: {total_domains / elapsed:.2f} queries/second\n"
            )
            print(summary)
            out_file.write(summary)
        
        print(f"\nResults written to {self.output_file}")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='DNS Query Tool with rate limiting and multiprocessing'
    )
    parser.add_argument(
        'domains_file',
        help='Path to file containing domain names (one per line)'
    )
    parser.add_argument(
        '-o', '--output',
        default='dns_results.txt',
        help='Output file path (default: dns_results.txt)'
    )
    parser.add_argument(
        '-r', '--rate',
        type=float,
        default=10.0,
        help='Queries per second (default: 10)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='Number of worker processes (default: 4)'
    )
    
    args = parser.parse_args()
    
    # Create and run DNS query tool
    tool = DNSQueryTool(
        domains_file=args.domains_file,
        output_file=args.output,
        queries_per_second=args.rate,
        workers=args.workers
    )
    
    tool.run()


if __name__ == '__main__':
    main()
