#!/usr/bin/env python3
import csv, ipaddress, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver, dns.reversename

INPUT = "combinedSD.csv"
OUTPUT = "combinedSD_with_lookup.csv"

DNS_SERVERS = ["8.8.8.8"]  # your resolver(s)
TIMEOUT = 2.0              # per query
MAX_WORKERS = 32

resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = DNS_SERVERS
resolver.timeout = TIMEOUT
resolver.lifetime = TIMEOUT

def resolve_one(addr: str) -> str:
    addr = addr.strip()
    if not addr or addr.startswith("#"):
        return ""
    try:
        # IP -> PTR
        ipaddress.ip_address(addr)
        rev = dns.reversename.from_address(addr)
        ans = resolver.resolve(rev, "PTR", raise_on_no_answer=False)
        names = []
        if ans.rrset:
            for r in ans:
                names.append(str(r.target).rstrip("."))
        return " ".join(sorted(set(names))) if names else "NOT_FOUND"
    except ValueError:
        # Hostname -> A/AAAA
        addrs = set()
        for rrtype in ("A", "AAAA"):
            try:
                ans = resolver.resolve(addr, rrtype, raise_on_no_answer=False)
                if ans.rrset:
                    for r in ans:
                        addrs.add(r.address)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout):
                pass
        return " ".join(sorted(addrs)) if addrs else "NOT_FOUND"

def main():
    rows = []
    with open(INPUT, newline="") as f:
        # strip CR if present and parse single-column CSV
        lines = [line.rstrip("\r\n") for line in f]
    addrs = [line.split(",")[0].strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(resolve_one, a): a for a in addrs}
        for fut in as_completed(futs):
            a = futs[fut]
            try:
                results[a] = fut.result()
            except Exception as e:
                results[a] = "NOT_FOUND"

    with open(OUTPUT, "w", newline="") as f:
        w = csv.writer(f)
        for a in addrs:
            w.writerow([a, results.get(a, "NOT_FOUND")])

    print(f"Results -> {OUTPUT}")

if __name__ == "__main__":
    main()
