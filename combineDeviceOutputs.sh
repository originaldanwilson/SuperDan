#!/bin/bash
# combineDeviceOutputs.sh - Combine all command outputs for each device into one file

# Check if directory argument provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <check_results_directory>"
    echo "Example: $0 precheck_20240911_142530"
    exit 1
fi

CHECK_DIR="$1"

if [ ! -d "$CHECK_DIR" ]; then
    echo "Error: Directory '$CHECK_DIR' not found"
    exit 1
fi

echo "Combining device outputs from: $CHECK_DIR"

# Create combined output directory
COMBINED_DIR="${CHECK_DIR}/combined"
mkdir -p "$COMBINED_DIR"

# Get list of unique devices
DEVICES=$(ls "$CHECK_DIR"/*.txt 2>/dev/null | sed 's/.*\///' | cut -d'_' -f1 | sort -u)

if [ -z "$DEVICES" ]; then
    echo "No device output files found in $CHECK_DIR"
    exit 1
fi

echo "Found devices: $DEVICES"

# Process each device
for device in $DEVICES; do
    echo "Processing device: $device"
    
    combined_file="$COMBINED_DIR/${device}_all_commands.txt"
    
    # Create header for combined file
    cat > "$combined_file" << EOF
================================================================================
COMBINED DEVICE OUTPUT: $device
Generated: $(date)
Source Directory: $CHECK_DIR
================================================================================

EOF
    
    # Find all files for this device and sort them
    device_files=$(ls "$CHECK_DIR"/${device}_*.txt 2>/dev/null | sort)
    
    if [ -n "$device_files" ]; then
        # Combine all files for this device
        for file in $device_files; do
            echo "  Adding: $(basename $file)"
            echo "" >> "$combined_file"
            echo "################################################################################" >> "$combined_file"
            echo "FILE: $(basename $file)" >> "$combined_file"
            echo "################################################################################" >> "$combined_file"
            cat "$file" >> "$combined_file"
            echo "" >> "$combined_file"
        done
        
        echo "  Created: $combined_file"
    else
        echo "  No files found for device: $device"
    fi
done

echo ""
echo "Combined files created in: $COMBINED_DIR"
echo "Files created:"
ls -la "$COMBINED_DIR"
