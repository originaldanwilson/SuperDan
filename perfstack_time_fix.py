#!/usr/bin/env python3
"""
Quick fix for time window issue in PerfStack URLs
Test different time formats to see which works
"""

from datetime import datetime, timedelta, timezone
import urllib.parse

def test_time_formats(hours=168):
    """Test different time formats for SolarWinds"""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    
    formats = [
        # Format 1: ISO with Z suffix
        (start.strftime("%Y-%m-%dT%H:%M:%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")),
        
        # Format 2: ISO with milliseconds
        (start.strftime("%Y-%m-%dT%H:%M:%S.000Z"), now.strftime("%Y-%m-%dT%H:%M:%S.000Z")),
        
        # Format 3: URL encoded ISO
        (urllib.parse.quote(start.strftime("%Y-%m-%dT%H:%M:%SZ")), 
         urllib.parse.quote(now.strftime("%Y-%m-%dT%H:%M:%SZ"))),
        
        # Format 4: Epoch timestamps (if SolarWinds uses them)
        (str(int(start.timestamp() * 1000)), str(int(now.timestamp() * 1000))),
        
        # Format 5: Simple format without T
        (start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")),
    ]
    
    print(f"Testing time formats for {hours} hour window:")
    print(f"Current time: {now}")
    print(f"Start time:   {start}")
    print(f"Difference:   {now - start}")
    print()
    
    for i, (start_fmt, end_fmt) in enumerate(formats, 1):
        print(f"Format {i}:")
        print(f"  Start: {start_fmt}")
        print(f"  End:   {end_fmt}")
        print(f"  Same:  {start_fmt == end_fmt}")
        
        # Build sample URL
        params = {
            "timeFrom": start_fmt,
            "timeTo": end_fmt,
            "charts": "0_test;"
        }
        
        query_string = urllib.parse.urlencode(params)
        sample_url = f"https://orion.company.com/apps/perfstack/?{query_string}"
        print(f"  URL: {sample_url}")
        print()

if __name__ == "__main__":
    test_time_formats(168)  # Test 7-day window
    print("=" * 50)
    test_time_formats(24)   # Test 24-hour window
