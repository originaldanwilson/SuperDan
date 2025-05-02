import csv
import json

def process_switch_data(csv_file, output_file="switch_data.json"):
    """
    Reads switch interface data from a CSV file and structures it into a Python dictionary,
    then writes the dictionary to a JSON file.

    Args:
        csv_file (str): Path to the CSV file containing switch data.
                        The CSV is expected to have a repeating pattern of:
                        switch_name, interface, description.
        output_file (str, optional): Path to the output JSON file.
                                      Defaults to "switch_data.json".
    """
    switch_data = {}
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        row = next(reader, None)  # Get the first row
        while row:
            if len(row) >= 3:
                switch_name = row[0].strip()
                interface = row[1].strip()
                description = row[2].strip()

                if switch_name not in switch_data:
                    switch_data[switch_name] = {}
                switch_data[switch_name][interface] = description
                row = next(reader, None) # Move to the next set of data
            else:
                print(f"Warning: Skipping incomplete row: {row}")
                row = next(reader, None) # Move to the next row even if incomplete

    with open(output_file, 'w') as file:
        json.dump(switch_data, file, indent=4)

    print(f"Data processed and saved to {output_file}")

if __name__ == "__main__":
    csv_file_path = input("Enter the path to your CSV file: ")
    process_switch_data(csv_file_path)
