#!/usr/bin/env python3
"""
Simple HTTPS file server (no root required — uses port 8443 by default).

Usage:
    # 1. Generate a self-signed cert (one-time):
    #    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'
    #
    # 2. Run:
    #    python3 https_server.py --file /path/to/file.txt
"""

import argparse
import os
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_handler(filepath: str):
    filename = os.path.basename(filepath)

    class FileHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                with open(filepath, "rb") as f:
                    data = f.read()
            except FileNotFoundError:
                self.send_error(404, "File not found")
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            print(f"[{self.address_string()}] {fmt % args}")

    return FileHandler


def main():
    parser = argparse.ArgumentParser(description="Serve a single file over HTTPS.")
    parser.add_argument("--file",  required=True,          help="Path to the file to serve")
    parser.add_argument("--port",  type=int, default=8443, help="Port to listen on (default: 8443)")
    parser.add_argument("--cert",  default="cert.pem",     help="TLS certificate file (default: cert.pem)")
    parser.add_argument("--key",   default="key.pem",      help="TLS key file (default: key.pem)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        raise SystemExit(f"Error: file not found: {args.file}")
    if not os.path.isfile(args.cert) or not os.path.isfile(args.key):
        raise SystemExit(
            "Error: cert/key not found.\n"
            "Generate them with:\n"
            "  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem "
            "-days 365 -nodes -subj '/CN=localhost'"
        )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.cert, keyfile=args.key)

    server = HTTPServer(("0.0.0.0", args.port), make_handler(args.file))
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"Serving '{args.file}' on https://0.0.0.0:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
