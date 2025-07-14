import socket
import csv

# Replace this list with your actual hostnames
deviceNames = [
    "switch01.example.com",
    "router01.example.com",
    "nxos-core1.lab.local"
]

def resolveHostnames(hostnames):
    results = []
    for name in hostnames:
        try:
            ip = socket.gethostbyname(name)
            results.append((name, ip))
            print(f"{name} -> {ip}")
        except socket.gaierror:
            results.append((name, "Resolution failed"))
            print(f"{name} -> Resolution failed")
    return results

def writeToCsv(data, filename="resolved_devices.csv"):
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Device Name", "IP Address"])
        writer.writerows(data)
    print(f"\nResults written to {filename}")

if __name__ == "__main__":
    results = resolveHostnames(deviceNames)
    writeToCsv(results)
