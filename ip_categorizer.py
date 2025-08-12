#!/usr/bin/env python3
"""
IP Address Categorizer
Matches individual IP addresses against network ranges and categorizes them as 'msft' or 'zx'
"""

import pandas as pd
import ipaddress
import sys
from pathlib import Path

def load_network_ranges(csv_file):
    """
    Load network ranges from CSV file
    Expected format: network column with CIDR notation, category column with 'msft' or 'zx'
    """
    try:
        df = pd.read_csv(csv_file)
        print(f"Loaded network ranges CSV with columns: {list(df.columns)}")
        
        # Try to identify the correct columns
        network_col = None
        category_col = None
        
        # Look for network column (containing CIDR notation)
        for col in df.columns:
            if any(df[col].astype(str).str.contains(r'\d+\.\d+\.\d+\.\d+/', na=False)):
                network_col = col
                break
        
        # Look for category column (containing msft/zx/zsscaler)
        for col in df.columns:
            if any(df[col].astype(str).str.contains('msft|zx|zsscaler', case=False, na=False)):
                category_col = col
                break
        
        if network_col is None:
            print("Available columns:", list(df.columns))
            print("Sample data:")
            print(df.head())
            raise ValueError("Could not find network column with CIDR notation")
        
        if category_col is None:
            print("Available columns:", list(df.columns))
            print("Sample data:")
            print(df.head())
            raise ValueError("Could not find category column with 'msft' or 'zx'")
        
        print(f"Using network column: '{network_col}', category column: '{category_col}'")
        
        networks = {}
        for _, row in df.iterrows():
            try:
                network = ipaddress.ip_network(row[network_col].strip(), strict=False)
                category = row[category_col].strip().lower()
                networks[network] = category
            except Exception as e:
                print(f"Warning: Could not parse network '{row[network_col]}': {e}")
        
        print(f"Loaded {len(networks)} valid network ranges")
        return networks
        
    except Exception as e:
        print(f"Error loading network ranges: {e}")
        sys.exit(1)

def load_ip_addresses(xlsx_file):
    """
    Load IP addresses from all sheets in XLSX file
    """
    try:
        # Read all sheets
        all_sheets = pd.read_excel(xlsx_file, sheet_name=None)
        print(f"Found {len(all_sheets)} sheets in XLSX file")
        
        all_ips = []
        for sheet_name, df in all_sheets.items():
            print(f"Processing sheet '{sheet_name}' with {len(df)} rows")
            
            # Find the column containing IP addresses
            ip_col = None
            for col in df.columns:
                # Check if column contains IP-like data
                sample_values = df[col].dropna().astype(str).head(10)
                if any(sample_values.str.match(r'^\d+\.\d+\.\d+\.\d+$')):
                    ip_col = col
                    break
            
            if ip_col is None:
                print(f"Warning: No IP address column found in sheet '{sheet_name}'")
                print(f"Columns: {list(df.columns)}")
                print("Sample data:")
                print(df.head())
                continue
            
            # Extract valid IP addresses
            sheet_ips = []
            for ip_str in df[ip_col].dropna():
                ip_str_clean = str(ip_str).strip()
                
                # Skip obvious non-IP values
                if (ip_str_clean.lower() in ['zscaler', 'zsscaler', 'microsoft', 'msft', 'nan', 'null', ''] 
                    or not ip_str_clean
                    or ip_str_clean.isalpha()):
                    continue
                
                try:
                    ip = ipaddress.ip_address(ip_str_clean)
                    sheet_ips.append(str(ip))
                except Exception as e:
                    # Only show warning for values that look like they might be IPs
                    if '.' in ip_str_clean and not ip_str_clean.isalpha():
                        print(f"Warning: Could not parse as IP: '{ip_str_clean}'")
            
            all_ips.extend(sheet_ips)
            print(f"Extracted {len(sheet_ips)} valid IPs from sheet '{sheet_name}'")
        
        # Remove duplicates while preserving order
        unique_ips = list(dict.fromkeys(all_ips))
        print(f"Total unique IP addresses: {len(unique_ips)}")
        return unique_ips
        
    except Exception as e:
        print(f"Error loading IP addresses: {e}")
        sys.exit(1)

def categorize_ips(ip_addresses, networks):
    """
    Categorize IP addresses based on network ranges
    """
    results = []
    categorized_count = {'microsoft': 0, 'zsscaler': 0, 'msft': 0, 'zx': 0, 'uncategorized': 0}
    
    print("Categorizing IP addresses...")
    for i, ip_str in enumerate(ip_addresses):
        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1}/{len(ip_addresses)} IPs")
        
        try:
            ip = ipaddress.ip_address(ip_str)
            category = 'uncategorized'
            
            # Check against all networks
            for network, net_category in networks.items():
                if ip in network:
                    category = net_category
                    break
            
            results.append({'ip_address': ip_str, 'category': category})
            categorized_count[category] += 1
            
        except Exception as e:
            print(f"Warning: Could not process IP '{ip_str}': {e}")
    
    print(f"\nCategorization results:")
    for category, count in categorized_count.items():
        if count > 0:
            print(f"{category.upper()}: {count}")
    
    return results

def save_results(results, output_file):
    """
    Save results to CSV or XLSX file
    """
    df = pd.DataFrame(results)
    
    if output_file.suffix.lower() == '.xlsx':
        df.to_excel(output_file, index=False)
    else:
        df.to_csv(output_file, index=False)
    
    print(f"Results saved to: {output_file}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python ip_categorizer.py <network_ranges.csv> <ip_addresses.xlsx> <output_file>")
        print("Example: python ip_categorizer.py networks.csv addresses.xlsx results.csv")
        sys.exit(1)
    
    network_csv = Path(sys.argv[1])
    ip_xlsx = Path(sys.argv[2])
    output_file = Path(sys.argv[3])
    
    # Validate input files
    if not network_csv.exists():
        print(f"Error: Network ranges file not found: {network_csv}")
        sys.exit(1)
    
    if not ip_xlsx.exists():
        print(f"Error: IP addresses file not found: {ip_xlsx}")
        sys.exit(1)
    
    print("Starting IP address categorization...")
    print(f"Network ranges file: {network_csv}")
    print(f"IP addresses file: {ip_xlsx}")
    print(f"Output file: {output_file}")
    
    # Load data
    networks = load_network_ranges(network_csv)
    ip_addresses = load_ip_addresses(ip_xlsx)
    
    # Categorize IPs
    results = categorize_ips(ip_addresses, networks)
    
    # Save results
    save_results(results, output_file)
    
    print("Processing complete!")

if __name__ == "__main__":
    main()
