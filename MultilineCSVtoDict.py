import csv
import json

def process_switch_data_multi_interface(csv_file, output_file="switch_data.json"):
    """
    Reads switch interface data from a CSV file where each row contains a switch
    and multiple interface-description pairs, and structures it into a Python dictionary,
    then writes the dictionary to a JSON file.

    Args:
        csv_file (str): Path to the CSV file containing switch data.
                        The CSV is expected to have a repeating pattern on each row:
                        switch_name, interface1, description1, interface2, description2, ...
        output_file (str, optional): Path to the output JSON file.
                                      Defaults to "switch_data.json".
    """
    switch_data = {}
    with open(csv_file, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure the row is not empty
                switch_name = row[0].strip()
                switch_data[switch_name] = {}
                # Iterate through the rest of the row in pairs of interface and description
                for i in range(1, len(row), 2):
                    if i + 1 < len(row):
                        interface = row[i].strip()
                        description = row[i + 1].strip()
                        switch_data[switch_name][interface] = description
                    else:
                        print(f"Warning: Incomplete interface-description pair at the end of row: {row}")
                        break  # Stop processing this row if an interface has no corresponding description

    with open(output_file, 'w') as file:
        json.dump(switch_data, file, indent=4)

    print(f"Data processed and saved to {output_file}")

if __name__ == "__main__":
    csv_file_path = input("Enter the path to your CSV file: ")
    process_switch_data_multi_interface(csv_file_path)
