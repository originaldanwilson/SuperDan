import socket
import time
import argparse
import random
import string

def generate_payload(size):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size)).encode()

def send_udp_traffic(target_ip, target_port, duration, pps, payload_size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = generate_payload(payload_size)
    end_time = time.time() + duration
    delay = 1 / pps

    print(f"Sending UDP traffic to {target_ip}:{target_port} for {duration}s at {pps} packets/sec")
    while time.time() < end_time:
        sock.sendto(payload, (target_ip, target_port))
        time.sleep(delay)

def send_tcp_traffic(target_ip, target_port, duration, pps, payload_size):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((target_ip, target_port))
        payload = generate_payload(payload_size)
        end_time = time.time() + duration
        delay = 1 / pps

        print(f"Sending TCP traffic to {target_ip}:{target_port} for {duration}s at {pps} packets/sec")
        while time.time() < end_time:
            sock.send(payload)
            time.sleep(delay)

        sock.close()
    except Exception as e:
        print(f"TCP connection failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate network traffic")
    parser.add_argument("target_ip", help="Target IP address")
    parser.add_argument("target_port", type=int, help="Target port")
    parser.add_argument("--protocol", choices=["udp", "tcp"], default="udp", help="Protocol to use")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    parser.add_argument("--pps", type=int, default=10, help="Packets per second")
    parser.add_argument("--payload", type=int, default=100, help="Payload size in bytes")

    args = parser.parse_args()

    if args.protocol == "udp":
        send_udp_traffic(args.target_ip, args.target_port, args.duration, args.pps, args.payload)
    else:
        send_tcp_traffic(args.target_ip, args.target_port, args.duration, args.pps, args.payload)
