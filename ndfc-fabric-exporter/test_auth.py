#!/usr/bin/env python3
"""
NDFC Authentication Tester
Tests different authentication methods to find the correct one for your NDFC version.
"""

import requests
import json
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def test_auth():
    ndfc_ip = input("Enter NDFC IP/hostname: ")
    username = input("Enter username: ")
    password = input("Enter password: ")
    
    print("\n" + "="*60)
    print("Testing NDFC Authentication Methods")
    print("="*60)
    
    # Test 1: Standard NDFC login with tacacs domain
    print("\n=== Test 1: Standard NDFC login with 'tacacs' domain ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/login", 
            json={"userName": username, "userPasswd": password, "domain": "tacacs"},
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Standard NDFC login with 'local' domain
    print("\n=== Test 2: Standard NDFC login with 'local' domain ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/login", 
            json={"userName": username, "userPasswd": password, "domain": "local"},
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: NDFC login with 'DefaultAuth' domain
    print("\n=== Test 3: Standard NDFC login with 'DefaultAuth' domain ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/login", 
            json={"userName": username, "userPasswd": password, "domain": "DefaultAuth"},
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: NDFC login without domain field
    print("\n=== Test 4: NDFC login without domain field ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/login", 
            json={"userName": username, "userPasswd": password},
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 5: Alternative API v1 endpoint
    print("\n=== Test 5: Alternative /api/v1/login endpoint ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/api/v1/login", 
            json={"userName": username, "userPasswd": password, "domain": "tacacs"},
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 6: DCNM-style /rest/logon with Basic Auth
    print("\n=== Test 6: DCNM-style /rest/logon endpoint ===")
    try:
        r = requests.post(
            f"https://{ndfc_ip}/rest/logon", 
            json={"expirationTime": 10000000},
            auth=(username, password),
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            print(f"✓ SUCCESS! Response: {r.text[:200]}")
            return
        else:
            print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 7: Check NDFC version/about
    print("\n=== Test 7: Checking NDFC version ===")
    try:
        r = requests.get(
            f"https://{ndfc_ip}/appcenter/cisco/ndfc/api/about",
            verify=False, 
            timeout=10
        )
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*60)
    print("All tests completed. If none succeeded, please check:")
    print("1. NDFC is accessible and running")
    print("2. Credentials are correct")
    print("3. User has API access permissions")
    print("="*60)

if __name__ == "__main__":
    test_auth()
