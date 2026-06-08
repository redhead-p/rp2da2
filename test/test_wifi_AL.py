# ============================================================
# WiFi Connection Test — Raspberry Pi Pico W
""" To be run as part of commissioning a newly constructed board as a check on
    WiFi network connectivity and the validaty of the \conf\wifi.json config file.

Includes Verbose logging to the Thonny REPL console output.
 - reads credentials from conf\wifi.json
 - scans for available networks
 - reports if configuraton matches an available network
 - continues logging in using the provided credentials
 - reports success by reporting the assigned details (IP address for example)
 - adapted from an earlier version by Paul Redhead with assistance from Claude.AI
"""
"""     Copyright (C) 2026 Paul Redhead
        Copyright (C) 2026 Alan Lomax

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""
#
# ============================================================

import network
import time
import json
import sys

# ── Helper ──────────────────────────────────────────────────
def log(msg):
    """Timestamped print to REPL/shell."""
    print(f"[{time.ticks_ms():>8}ms] {msg}")

def scan_networks(wlan):
    """Scan for visible networks and print a formatted report."""
    log("--- Scanning for visible WiFi networks ---")
    try:
        nets = wlan.scan()
    except Exception as e:
        log(f"  Scan failed: {e}")
        return

    if not nets:
        log("  No networks found at all — check antenna / distance to router")
        return

    log(f"  Found {len(nets)} network(s):")
    log(f"  {'SSID':<32} {'Chan':>4}  {'RSSI':>5}  {'Security'}")
    log(f"  {'-'*32} {'-'*4}  {'-'*5}  {'-'*10}")

    AUTH = {0: "Open", 1: "WEP", 2: "WPA", 3: "WPA2", 4: "WPA/WPA2", 5: "WPA3"}

    for n in sorted(nets, key=lambda x: x[3], reverse=True):
        try:
            ssid = n[0].decode("utf-8")
        except:
            ssid = repr(n[0])
        channel  = n[2]
        rssi     = n[3]
        security = AUTH.get(n[4], f"Unknown({n[4]})")
        hidden   = " [hidden]" if not ssid else ""
        log(f"  {ssid:<32} {channel:>4}  {rssi:>5}  {security}{hidden}")

    log("--- End of scan ---")

# ── 1. Load config file ──────────────────────────────────────
CONFIG_FILE = "conf/wifi.json"

log("=== WiFi Test Starting ===")
log(f"Attempting to open config file: {CONFIG_FILE}")

try:
    with open(CONFIG_FILE, "r") as f:
        log("File opened successfully")
        raw = f.read()
        log(f"Raw read: {len(raw)} bytes")          # length only — no contents echoed
except OSError as e:
    log(f"ERROR: Could not open {CONFIG_FILE} — {e}")
    log("Check the file exists on the Pico (not just your PC).")
    sys.exit()

# ── 2. Parse JSON ────────────────────────────────────────────
log("Attempting to parse JSON...")

try:
    config = json.loads(raw)
    log("JSON parsed successfully")
except ValueError as e:
    log(f"ERROR: JSON parse failed — {e}")
    log("Check the file is valid JSON (no trailing commas, proper quotes).")
    sys.exit()

# ── 3. Validate expected keys & log redacted config ─────────
log("Validating config keys...")

required_keys = ["country", "ssid", "password", "hostname"]
missing = [k for k in required_keys if k not in config]

if missing:
    log(f"ERROR: Missing keys in config: {missing}")
    sys.exit()

log(f"  country  : {config['country']}")
log(f"  ssid     : {config['ssid']}")
log(f"  password : {'*' * len(config['password'])}  ({len(config['password'])} chars)")
log(f"  hostname : {config['hostname']}")
log("All required keys present")

# ── 4. Initialise WiFi interface ─────────────────────────────
log("Initialising WLAN interface (STA mode)...")

try:
    wlan = network.WLAN(network.STA_IF)
    log(f"WLAN object created: {wlan}")
except Exception as e:
    log(f"ERROR: Failed to create WLAN object — {e}")
    sys.exit()

# ── 5. Set country & hostname ────────────────────────────────
log(f"Setting WiFi country to: {config['country']}")
try:
    rp2 = __import__("rp2")
    rp2.country(config["country"])
    log("Country set successfully")
except Exception as e:
    log(f"WARNING: Could not set country — {e}")

log(f"Setting hostname to: {config['hostname']}")
try:
    network.hostname(config["hostname"])
    log("Hostname set successfully")
except Exception as e:
    log(f"WARNING: Could not set hostname — {e}")

# ── 6. Activate interface & connect ─────────────────────────
log("Activating WLAN interface...")
wlan.active(True)
log(f"WLAN active: {wlan.active()}")

# ── 7. Pre-connection scan ───────────────────────────────────
log("Running pre-connection network scan...")
scan_networks(wlan)

# Check the target SSID is actually visible before attempting connect
visible_ssids = []
try:
    visible_ssids = [n[0].decode("utf-8") for n in wlan.scan()]
except:
    pass

if config["ssid"] not in visible_ssids:
    log(f"WARNING: Target SSID '{config['ssid']}' not found in scan results!")
    log("Attempting connection anyway (network may be hidden), but expect failure.")
else:
    log(f"Target SSID '{config['ssid']}' confirmed visible — proceeding to connect")

# ── 8. Connect ───────────────────────────────────────────────
log(f"Connecting to SSID: {config['ssid']} ...")
wlan.connect(config["ssid"], config["password"])

# ── 9. Wait for connection (with timeout) ───────────────────
TIMEOUT_SECONDS = 20
log(f"Waiting for connection (timeout: {TIMEOUT_SECONDS}s)...")

start = time.time()

while not wlan.isconnected():
    elapsed = time.time() - start
    if elapsed >= TIMEOUT_SECONDS:
        log(f"ERROR: Connection timed out after {TIMEOUT_SECONDS}s")
        status = wlan.status()
        log(f"Final wlan.status() = {status}")

        advice = {
             0: "STAT_IDLE — interface inactive, try restarting",
             1: "STAT_CONNECTING — still trying but timed out",
            -1: "STAT_CONNECT_FAIL — general failure, check password",
            -2: "STAT_NO_AP_FOUND — SSID not visible (wrong name/case, or out of range)",
            -3: "STAT_WRONG_PASSWORD — SSID found but password rejected",
        }
        log(f"  Status meaning: {advice.get(status, f'Unknown status code {status}')}")

        if status == -2:
            log("Running post-failure scan to help diagnose...")
            scan_networks(wlan)
            log(f"HINT: Compare your configured SSID  '{config['ssid']}'")
            log( "      against the scan results above (check case, spaces, spelling)")
        elif status == -3:
            log(f"HINT: SSID '{config['ssid']}' was found but password was rejected")
            log( "      Check the password in your conf/wifi.json")

        sys.exit()

    print(f"  ... still connecting  elapsed={elapsed:.1f}s  status={wlan.status()}", end="\r")
    time.sleep(0.5)

print()  # newline after the spinning status line

# ── 10. Report success ───────────────────────────────────────
elapsed = time.time() - start
log(f"Connected! Took {elapsed:.1f}s")

ifconfig = wlan.ifconfig()
log(f"  IP address : {ifconfig[0]}")
log(f"  Subnet mask: {ifconfig[1]}")
log(f"  Gateway    : {ifconfig[2]}")
log(f"  DNS server : {ifconfig[3]}")
log(f"  RSSI (signal strength): {wlan.status('rssi')} dBm")
log("=== WiFi Test Complete — All Good! ===")