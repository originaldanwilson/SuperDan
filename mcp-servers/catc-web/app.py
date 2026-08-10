#!/usr/bin/env python3
"""
Catalyst Center Device Inventory Web UI
Run: python3 app.py
Browse: http://localhost:8080
"""

import os
import requests
import urllib3
from flask import Flask, render_template, jsonify

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CATC_HOST     = os.environ.get("CATALYST_CENTER_HOST", "")
CATC_USER     = os.environ.get("CATALYST_CENTER_USERNAME", "")
CATC_PASS     = os.environ.get("CATALYST_CENTER_PASSWORD", "")
CATC_VERIFY   = os.environ.get("CATALYST_CENTER_VERIFY_SSL", "false").lower() == "true"


def get_token():
    url = f"{CATC_HOST}/dna/system/api/v1/auth/token"
    resp = requests.post(url, auth=(CATC_USER, CATC_PASS), verify=CATC_VERIFY, timeout=10)
    resp.raise_for_status()
    return resp.json()["Token"]


def get_devices(token):
    url = f"{CATC_HOST}/dna/intent/api/v1/network-device"
    headers = {"X-Auth-Token": token}
    devices = []
    offset = 1
    while True:
        resp = requests.get(url, headers=headers, verify=CATC_VERIFY,
                            params={"offset": offset, "limit": 500}, timeout=15)
        resp.raise_for_status()
        batch = resp.json().get("response", [])
        if not batch:
            break
        devices.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return devices


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices")
def api_devices():
    try:
        token   = get_token()
        devices = get_devices(token)
        rows = []
        for d in devices:
            rows.append({
                "hostname":      d.get("hostname", "—"),
                "ip":            d.get("managementIpAddress", "—"),
                "platform":      d.get("platformId", "—"),
                "software":      d.get("softwareVersion", "—"),
                "role":          d.get("role", "—").replace("_", " ").title(),
                "reachability":  d.get("reachabilityStatus", "—"),
                "series":        d.get("series", "—"),
                "site":          d.get("locationName") or "—",
                "uptime":        d.get("uptimeSeconds", None),
            })
        return jsonify({"ok": True, "devices": rows, "total": len(rows)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    if not CATC_HOST:
        print("ERROR: Set CATALYST_CENTER_HOST, CATALYST_CENTER_USERNAME, CATALYST_CENTER_PASSWORD")
        raise SystemExit(1)
    print(f"Starting CatC Web UI → http://0.0.0.0:8080  (target: {CATC_HOST})")
    app.run(host="0.0.0.0", port=8080, debug=False)
