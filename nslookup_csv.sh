#!/bin/bash

INPUT_FILE="addresses.csv"

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: $INPUT_FILE not found."
    exit 1
fi

# Create temp file to store output
OUTPUT_FILE="addresses_with_lookup.csv"
> "$OUTPUT_FILE"

while IFS=',' read -r addr; do
    # Skip empty lines or header lines starting with #
    [[ -z "$addr" || "$addr" =~ ^# ]] && continue

    # Run nslookup and extract results
    result=$(nslookup "$addr" 2>/dev/null | awk '/^Address: / {print $2}' | paste -sd " " -)

    # If no result, mark as NOT_FOUND
    if [[ -z "$result" ]]; then
        result="NOT_FOUND"
    fi

    echo "$addr,$result" >> "$OUTPUT_FILE"
done < "$INPUT_FILE"

echo "Lookup complete. Results saved to $OUTPUT_FILE"
