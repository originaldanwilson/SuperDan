#!/usr/bin/env python3
"""
Convert network CSV from separate columns to single format
Converts from format with separate msft/zx columns to single network,category format
"""

import pandas as pd
import sys
from pathlib import Path

def convert_networks_csv(input_file, output_file):
    """
    Convert CSV with separate msft/zx columns to network,category format
    """
    try:
        # Read the input CSV
        df = pd.read_csv(input_file)
        print(f"Input file columns: {list(df.columns)}")
        print("Sample of input data:")
        print(df.head())
        
        # Create output data
        output_data = []
        
        # Process each column
        for col_name in df.columns:
            col_name_lower = col_name.lower()
            
            # Determine category based on column name
            if 'msft' in col_name_lower or 'microsoft' in col_name_lower:
                category = 'microsoft'
            elif 'zx' in col_name_lower or 'zsscaler' in col_name_lower or 'zscaler' in col_name_lower:
                category = 'zsscaler'
            else:
                # Ask user which category this column should be
                print(f"\nColumn '{col_name}' - what category should this be?")
                print("Enter 'msft', 'zx', or 'skip' to ignore this column:")
                user_input = input().strip().lower()
                if user_input in ['msft', 'zx']:
                    category = user_input
                else:
                    print(f"Skipping column '{col_name}'")
                    continue
            
            # Add all non-empty networks from this column
            for network in df[col_name].dropna():
                network_str = str(network).strip()
                if network_str and network_str != 'nan':
                    # Check if it looks like a network (contains . and optionally /)
                    if '.' in network_str:
                        output_data.append({'network': network_str, 'category': category})
        
        # Create output DataFrame
        output_df = pd.DataFrame(output_data)
        
        if len(output_df) == 0:
            print("Error: No valid network data found!")
            return False
        
        # Save to output file
        output_df.to_csv(output_file, index=False)
        
        print(f"\nConversion complete!")
        print(f"Input file: {input_file}")
        print(f"Output file: {output_file}")
        print(f"Total networks converted: {len(output_df)}")
        print(f"Microsoft networks: {len(output_df[output_df['category'] == 'microsoft'])}")
        print(f"ZsScaler networks: {len(output_df[output_df['category'] == 'zsscaler'])}")
        
        print(f"\nSample of converted data:")
        print(output_df.head(10))
        
        return True
        
    except Exception as e:
        print(f"Error converting file: {e}")
        return False

def main():
    if len(sys.argv) != 3:
        print("Usage: python convert_networks.py <input.csv> <output.csv>")
        print("Example: python convert_networks.py original_networks.csv converted_networks.csv")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    success = convert_networks_csv(input_file, output_file)
    
    if success:
        print(f"\nNow you can use the converted file with the IP categorizer:")
        print(f"python ip_categorizer.py {output_file} addresses.xlsx results.csv")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
