"""
CDP Network Topology Mapper
Connects to Cisco NX-OS and IOS-XE devices, collects CDP neighbor data,
and generates a network topology diagram.

Supports recursive discovery to automatically crawl multiple hops.

Requirements:
    pip install netmiko networkx matplotlib
"""

import re
import argparse
from dataclasses import dataclass, field
from typing import Optional
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import networkx as nx
import matplotlib.pyplot as plt


@dataclass
class CDPNeighbor:
    """Represents a CDP neighbor entry."""
    local_device: str
    local_port: str
    remote_device: str
    remote_port: str
    platform: str
    ip_address: Optional[str] = None


@dataclass
class Device:
    """Represents a network device to query."""
    hostname: str
    ip: str
    device_type: str  # 'cisco_nxos' or 'cisco_xe'
    username: str
    password: str


def parse_cdp_neighbors(output: str, local_device: str) -> list[CDPNeighbor]:
    """
    Parse 'show cdp neighbors detail' output from NX-OS or IOS-XE.
    Returns a list of CDPNeighbor objects.
    """
    neighbors = []
    
    # Split output into neighbor blocks
    blocks = re.split(r'-{5,}', output)
    
    for block in blocks:
        if not block.strip():
            continue
            
        # Extract device ID (hostname)
        device_match = re.search(
            r'Device ID[:\s]+([^\s\n]+)', block, re.IGNORECASE
        )
        if not device_match:
            continue
        remote_device = device_match.group(1).split('.')[0]  # Remove domain
        
        # Extract IP address
        ip_match = re.search(
            r'(?:IP address|IPv4 Address)[:\s]+(\d+\.\d+\.\d+\.\d+)', 
            block, re.IGNORECASE
        )
        ip_address = ip_match.group(1) if ip_match else None
        
        # Extract platform
        platform_match = re.search(
            r'Platform[:\s]+([^,\n]+)', block, re.IGNORECASE
        )
        platform = platform_match.group(1).strip() if platform_match else "Unknown"
        
        # Extract local interface
        local_port_match = re.search(
            r'Interface[:\s]+([^\s,\n]+)', block, re.IGNORECASE
        )
        local_port = local_port_match.group(1) if local_port_match else "Unknown"
        
        # Extract remote port
        remote_port_match = re.search(
            r'Port ID \(outgoing port\)[:\s]+([^\s\n]+)', block, re.IGNORECASE
        )
        remote_port = remote_port_match.group(1) if remote_port_match else "Unknown"
        
        neighbors.append(CDPNeighbor(
            local_device=local_device,
            local_port=local_port,
            remote_device=remote_device,
            remote_port=remote_port,
            platform=platform,
            ip_address=ip_address
        ))
    
    return neighbors


def get_cdp_neighbors(device: Device) -> list[CDPNeighbor]:
    """Connect to a device and retrieve CDP neighbor information."""
    connection_params = {
        'device_type': device.device_type,
        'host': device.ip,
        'username': device.username,
        'password': device.password,
    }
    
    try:
        print(f"Connecting to {device.hostname} ({device.ip})...")
        with ConnectHandler(**connection_params) as conn:
            output = conn.send_command('show cdp neighbors detail')
            neighbors = parse_cdp_neighbors(output, device.hostname)
            print(f"  Found {len(neighbors)} CDP neighbors")
            return neighbors
    except NetmikoTimeoutException:
        print(f"  ERROR: Timeout connecting to {device.hostname}")
        return []
    except NetmikoAuthenticationException:
        print(f"  ERROR: Authentication failed for {device.hostname}")
        return []
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def guess_device_type(platform: str) -> str:
    """
    Guess the Netmiko device_type based on CDP platform string.
    Returns best guess for the device type.
    """
    platform_lower = platform.lower()
    
    if 'nexus' in platform_lower or 'n9k' in platform_lower or 'n7k' in platform_lower or 'n5k' in platform_lower:
        return 'cisco_nxos'
    elif 'ios-xe' in platform_lower or 'cat9' in platform_lower or 'c9' in platform_lower:
        return 'cisco_xe'
    elif 'isr' in platform_lower or 'asr' in platform_lower or 'csr' in platform_lower:
        return 'cisco_xe'
    elif 'catalyst' in platform_lower or 'ws-c' in platform_lower:
        return 'cisco_ios'  # Older Catalyst
    else:
        return 'cisco_ios'  # Default fallback


def recursive_cdp_discovery(
    seed_devices: list[Device],
    max_depth: int,
    username: str,
    password: str
) -> list[CDPNeighbor]:
    """
    Recursively discover CDP neighbors up to max_depth hops.
    
    Args:
        seed_devices: Initial devices to start discovery from
        max_depth: Maximum number of hops to traverse (0 = unlimited)
        username: SSH username for discovered devices
        password: SSH password for discovered devices
    
    Returns:
        List of all discovered CDP neighbor relationships
    """
    all_neighbors: list[CDPNeighbor] = []
    visited_ips: set[str] = set()
    visited_hostnames: set[str] = set()
    
    # Queue: (device, current_depth)
    queue: list[tuple[Device, int]] = [(d, 1) for d in seed_devices]
    
    while queue:
        device, depth = queue.pop(0)
        
        # Skip if already visited
        if device.ip in visited_ips or device.hostname.lower() in visited_hostnames:
            continue
        
        visited_ips.add(device.ip)
        visited_hostnames.add(device.hostname.lower())
        
        print(f"[Depth {depth}] ", end="")
        neighbors = get_cdp_neighbors(device)
        all_neighbors.extend(neighbors)
        
        # If we haven't reached max depth, queue discovered neighbors
        if max_depth == 0 or depth < max_depth:
            for neighbor in neighbors:
                # Skip if no IP or already visited
                if not neighbor.ip_address:
                    print(f"    Skipping {neighbor.remote_device}: No IP address in CDP")
                    continue
                if neighbor.ip_address in visited_ips:
                    continue
                if neighbor.remote_device.lower() in visited_hostnames:
                    continue
                
                # Create device entry for discovered neighbor
                guessed_type = guess_device_type(neighbor.platform)
                new_device = Device(
                    hostname=neighbor.remote_device,
                    ip=neighbor.ip_address,
                    device_type=guessed_type,
                    username=username,
                    password=password
                )
                queue.append((new_device, depth + 1))
                print(f"    Queued {neighbor.remote_device} ({neighbor.ip_address}) as {guessed_type}")
    
    return all_neighbors


def build_topology_graph(all_neighbors: list[CDPNeighbor]) -> nx.Graph:
    """Build a NetworkX graph from CDP neighbor data."""
    G = nx.Graph()
    
    # Track unique devices and their platforms
    device_platforms = {}
    
    for neighbor in all_neighbors:
        device_platforms[neighbor.local_device] = "Queried Device"
        if neighbor.remote_device not in device_platforms:
            device_platforms[neighbor.remote_device] = neighbor.platform
    
    # Add nodes
    for device, platform in device_platforms.items():
        G.add_node(device, platform=platform)
    
    # Add edges (links between devices)
    for neighbor in all_neighbors:
        edge_label = f"{neighbor.local_port} <-> {neighbor.remote_port}"
        
        # Check if edge already exists (avoid duplicates)
        if G.has_edge(neighbor.local_device, neighbor.remote_device):
            # Append to existing label if different ports
            existing = G[neighbor.local_device][neighbor.remote_device].get('label', '')
            if edge_label not in existing:
                G[neighbor.local_device][neighbor.remote_device]['label'] = \
                    f"{existing}\n{edge_label}"
        else:
            G.add_edge(
                neighbor.local_device, 
                neighbor.remote_device,
                label=edge_label
            )
    
    return G


def draw_topology(G: nx.Graph, output_file: str = "network_topology.png"):
    """Draw the network topology and save to file."""
    if len(G.nodes()) == 0:
        print("No topology data to draw.")
        return
    
    plt.figure(figsize=(14, 10))
    
    # Use spring layout for automatic positioning
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Color nodes based on platform type
    node_colors = []
    for node in G.nodes():
        platform = G.nodes[node].get('platform', '').lower()
        if 'nexus' in platform or 'nxos' in platform:
            node_colors.append('#00BCEB')  # Cisco blue for Nexus
        elif 'switch' in platform or 'catalyst' in platform:
            node_colors.append('#6CC24A')  # Green for switches
        elif 'router' in platform or 'isr' in platform or 'asr' in platform:
            node_colors.append('#FF6B6B')  # Red for routers
        else:
            node_colors.append('#9E9E9E')  # Gray for unknown
    
    # Draw the graph
    nx.draw_networkx_nodes(
        G, pos, 
        node_color=node_colors,
        node_size=2000,
        alpha=0.9
    )
    
    nx.draw_networkx_labels(
        G, pos,
        font_size=9,
        font_weight='bold'
    )
    
    nx.draw_networkx_edges(
        G, pos,
        edge_color='#666666',
        width=2,
        alpha=0.7
    )
    
    # Draw edge labels (interface connections)
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(
        G, pos,
        edge_labels=edge_labels,
        font_size=7,
        alpha=0.8
    )
    
    plt.title("Network Topology (CDP Discovery)", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\nTopology map saved to: {output_file}")


def load_devices_from_file(filepath: str, username: str, password: str) -> list[Device]:
    """
    Load devices from a simple text file.
    Format: hostname,ip,device_type (one per line)
    Example: switch1,192.168.1.1,cisco_nxos
    """
    devices = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) >= 3:
                devices.append(Device(
                    hostname=parts[0].strip(),
                    ip=parts[1].strip(),
                    device_type=parts[2].strip(),
                    username=username,
                    password=password
                ))
    return devices


def main():
    parser = argparse.ArgumentParser(
        description='Discover CDP neighbors and generate network topology map'
    )
    parser.add_argument(
        '-f', '--file',
        help='File containing device list (hostname,ip,device_type per line)'
    )
    parser.add_argument(
        '-d', '--device',
        action='append',
        nargs=3,
        metavar=('HOSTNAME', 'IP', 'TYPE'),
        help='Single device: hostname ip device_type (cisco_nxos or cisco_xe)'
    )
    parser.add_argument('-u', '--username', required=True, help='SSH username')
    parser.add_argument('-p', '--password', required=True, help='SSH password')
    parser.add_argument(
        '-o', '--output',
        default='network_topology.png',
        help='Output image filename (default: network_topology.png)'
    )
    parser.add_argument(
        '-l', '--layers',
        type=int,
        default=1,
        help='Max discovery depth/hops (default: 1, use 0 for unlimited)'
    )
    
    args = parser.parse_args()
    
    devices = []
    
    # Load from file
    if args.file:
        devices.extend(load_devices_from_file(args.file, args.username, args.password))
    
    # Add individual devices from command line
    if args.device:
        for hostname, ip, dtype in args.device:
            devices.append(Device(
                hostname=hostname,
                ip=ip,
                device_type=dtype,
                username=args.username,
                password=args.password
            ))
    
    if not devices:
        print("No devices specified. Use -f or -d to specify devices.")
        parser.print_help()
        return
    
    depth_str = "unlimited" if args.layers == 0 else str(args.layers)
    print(f"Starting CDP discovery on {len(devices)} seed device(s), max depth: {depth_str}\n")
    
    # Recursive CDP discovery
    all_neighbors = recursive_cdp_discovery(
        seed_devices=devices,
        max_depth=args.layers,
        username=args.username,
        password=args.password
    )
    
    print(f"\nTotal CDP neighbor relationships discovered: {len(all_neighbors)}")
    
    # Build and draw topology
    G = build_topology_graph(all_neighbors)
    print(f"Topology contains {len(G.nodes())} devices and {len(G.edges())} links")
    
    draw_topology(G, args.output)


if __name__ == '__main__':
    main()
