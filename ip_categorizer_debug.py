#!/usr/bin/env python3
"""
IP Address Categorizer - DEBUG VERSION
This version provides detailed diagnostics to troubleshoot data loading issues
"""

import pandas as pd
import ipaddress
import sys
from pathlib import Path

def debug_xlsx_file(xlsx_file):
    """
    Debug XLSX file structure and content
    """
    print("=== XLSX FILE DEBUG INFO ===")
    try:
        # Read all sheets
        all_sheets = pd.read_excel(xlsx_file, sheet_name=None)
        print(f"Total sheets found: {len(all_sheets)}")
        
        total_raw_rows = 0
        total_processed_ips = 0
        
        for sheet_name, df in all_sheets.items():
            print(f"\n--- Sheet: '{sheet_name}' ---")
            print(f"Raw rows: {len(df)}")
            print(f"Columns: {list(df.columns)}")
            
            total_raw_rows += len(df)
            
            # Show first few rows
            print("First 5 rows:")
            print(df.head())
            
            # Find IP column
            ip_col = None
            for col in df.columns:
                sample_values = df[col].dropna().astype(str).head(20)  # Check more samples
                ip_matches = sample_values.str.match(r'^\d+\.\d+\.\d+\.\d+$').sum()
                print(f"Column '{col}': {ip_matches} IP-like values in first 20 samples")
                
                if ip_matches >= 5:  # If at least 5 look like IPs
                    ip_col = col
                    break
            
            if ip_col:
                print(f"Selected IP column: '{ip_col}'")
                
                # Debug IP extraction
                valid_ips = []
                invalid_count = 0
                skipped_count = 0
                
                for idx, ip_str in enumerate(df[ip_col].dropna()):
                    ip_str_clean = str(ip_str).strip()
                    
                    # Debug first 10 entries
                    if idx < 10:
                        print(f"  Row {idx}: '{ip_str_clean}'", end="")
                    
                    # Skip obvious non-IP values
                    if (ip_str_clean.lower() in ['zscaler', 'zsscaler', 'microsoft', 'msft', 'nan', 'null', ''] 
                        or not ip_str_clean
                        or ip_str_clean.isalpha()):
                        skipped_count += 1
                        if idx < 10:
                            print(" -> SKIPPED (non-IP text)")
                        continue
                    
                    try:
                        ip = ipaddress.ip_address(ip_str_clean)
                        valid_ips.append(str(ip))
                        if idx < 10:
                            print(" -> VALID IP")
                    except Exception as e:
                        invalid_count += 1
                        if idx < 10:
                            print(f" -> INVALID ({e})")
                        elif '.' in ip_str_clean and not ip_str_clean.isalpha():
                            print(f"Invalid IP-like value at row {idx}: '{ip_str_clean}' -> {e}")
                
                print(f"Sheet summary:")
                print(f"  - Valid IPs: {len(valid_ips)}")
                print(f"  - Invalid entries: {invalid_count}")
                print(f"  - Skipped entries: {skipped_count}")
                print(f"  - Total processed: {len(valid_ips) + invalid_count + skipped_count}")
                
                total_processed_ips += len(valid_ips)
                
            else:
                print("No IP column identified!")
                
        print(f"\n=== OVERALL SUMMARY ===")
        print(f"Total raw rows across all sheets: {total_raw_rows}")
        print(f"Total valid IPs found: {total_processed_ips}")
        
    except Exception as e:
        print(f"Error reading XLSX file: {e}")

def debug_csv_file(csv_file):
    """
    Debug CSV file structure
    """
    print("\n=== CSV FILE DEBUG INFO ===")
    try:
        df = pd.read_csv(csv_file)
        print(f"CSV rows: {len(df)}")
        print(f"CSV columns: {list(df.columns)}")
        print("First 5 rows:")
        print(df.head())
        print("Last 5 rows:")
        print(df.tail())
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python ip_categorizer_debug.py <network_ranges.csv> <ip_addresses.xlsx>")
        print("This debug version will analyze your files without processing them")
        sys.exit(1)
    
    network_csv = Path(sys.argv[1])
    ip_xlsx = Path(sys.argv[2])
    
    # Validate input files
    if not network_csv.exists():
        print(f"Error: Network ranges file not found: {network_csv}")
        sys.exit(1)
    
    if not ip_xlsx.exists():
        print(f"Error: IP addresses file not found: {ip_xlsx}")
        sys.exit(1)
    
    print("=== FILE DEBUG ANALYSIS ===")
    print(f"Network ranges file: {network_csv}")
    print(f"IP addresses file: {ip_xlsx}")
    
    # Debug both files
    debug_csv_file(network_csv)
    debug_xlsx_file(ip_xlsx)

if __name__ == "__main__":
    main()
