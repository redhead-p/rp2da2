# ============================================================
""" MQTT Connection Initial Confidence Check

    To be run as part of commissioning a newly constructed board as a check on
    MQTT broker connectivity, publish and subscribe operability.

NOTE:
A passing result confirms the MQTT broker is reachable and anonymous access is
working correctly, which is a prerequisite for the main application.

This test uses the 'umqtt.simple' library
(install via Thonny: Tools > Manage Packages > umqtt.simple)
It is an independent infrastructure check and NOT a test of Paul Redhead's mqtt_client.py library. 

Includes Verbose logging to the Thonny REPL console output.
 - reads wifi configuration details from conf\wifi.json
 - proceeds to log into the wifi network
 - reads mqtt configuration details from conf\mqtt.json
 - contacts the broker and subscribes to a test topic.
 - publishes a 'ping' test to that test topic. (send and receive)
 - reports as pass or fail to the REPL console in Thonny
 - prepared with assistance from Claude.AI
"""
"""     Copyright (C) 2026 Alan Lomax

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""
import network
import time
import json
import sys
from umqtt.simple import MQTTClient

# ── Helpers ──────────────────────────────────────────────────
def log_brief(msg):
    """Minimal single-line output for WiFi phase."""
    print(msg)

def log(msg):
    """Timestamped detailed output for MQTT phase."""
    print(f"[{time.ticks_ms():>8}ms] {msg}")

# ── PHASE 1: WiFi — minimal output ───────────────────────────

print()
print("=== MQTT Commissioning Test ===")
print()

# 1. Load WiFi config
print("1) Reading WiFi Configuration...")
try:
    with open("conf/wifi.json", "r") as f:
        wifi = json.loads(f.read())
except OSError:
    print("   ERROR: conf/wifi.json not found on Pico")
    sys.exit()
except ValueError:
    print("   ERROR: conf/wifi.json is not valid JSON")
    sys.exit()

required = ["country", "ssid", "password", "hostname"]
missing = [k for k in required if k not in wifi]
if missing:
    print(f"   ERROR: Missing keys: {missing}")
    sys.exit()

# 2. Validate
print("2) WiFi Configuration Valid")

# Set country and hostname
try:
    import rp2
    rp2.country(wifi["country"])
except:
    pass
try:
    network.hostname(wifi["hostname"])
except:
    pass

# 3. Connect
print(f"3) Connecting to WiFi...")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(wifi["ssid"], wifi["password"])

TIMEOUT = 20
start = time.time()
while not wlan.isconnected():
    if time.time() - start >= TIMEOUT:
        print(f"   ERROR: WiFi connection timed out after {TIMEOUT}s")
        print(f"   Last status: {wlan.status()}")
        sys.exit()
    time.sleep(0.5)

# 4. Connected
ip = wlan.ifconfig()[0]
print(f"4) Connected to '{wifi['ssid']}' with IP address: {ip}")
print()

# ── PHASE 2: MQTT — detailed output ──────────────────────────

log("=== MQTT Phase Starting ===")

# 5. Load MQTT config
log("Loading MQTT configuration from conf/mqtt.json...")
try:
    with open("conf/mqtt.json", "r") as f:
        raw = f.read()
        log(f"  File read: {len(raw)} bytes")
except OSError as e:
    log(f"ERROR: Could not open conf/mqtt.json — {e}")
    sys.exit()

try:
    mqtt_conf = json.loads(raw)
    log("  JSON parsed successfully")
except ValueError as e:
    log(f"ERROR: JSON parse failed — {e}")
    sys.exit()

required_mqtt = ["broker", "clientId"]
missing = [k for k in required_mqtt if k not in mqtt_conf]
if missing:
    log(f"ERROR: Missing keys in mqtt.json: {missing}")
    sys.exit()

broker   = mqtt_conf["broker"]
clientId = mqtt_conf["clientId"]
port     = mqtt_conf.get("port", 1883)

log(f"  broker  : {broker}")
log(f"  clientId: {clientId}")
log(f"  port    : {port}")

# 6. Define test topic and message
TEST_TOPIC   = b"pico/test"
TEST_PAYLOAD = b"ping"
received_msg = []

log(f"  test topic  : {TEST_TOPIC.decode()}")
log(f"  test payload: {TEST_PAYLOAD.decode()}")

# 7. Define subscription callback
def on_message(topic, msg):
    log(f"  <<< Message received!")
    log(f"      topic  : {topic.decode()}")
    log(f"      payload: {msg.decode()}")
    received_msg.append((topic, msg))

# 8. Create MQTT client
log("Creating MQTT client object...")
try:
    client = MQTTClient(
        client_id = clientId,
        server    = broker,
        port      = port,
        keepalive = 30
    )
    client.set_callback(on_message)
    log("  Client object created successfully")
except Exception as e:
    log(f"ERROR: Failed to create MQTT client — {e}")
    sys.exit()

# 9. Connect to broker
log(f"Connecting to MQTT broker at {broker}:{port}...")
try:
    client.connect()
    log("  Connected to broker successfully")
except OSError as e:
    log(f"ERROR: Connection to broker failed — {e}")
    log("  Check broker address, port, and that broker is running")
    log("  Check WiFi firewall / router is not blocking port 1883")
    sys.exit()
except Exception as e:
    log(f"ERROR: Unexpected error connecting to broker — {e}")
    sys.exit()

# 10. Subscribe to test topic
log(f"Subscribing to topic: {TEST_TOPIC.decode()} ...")
try:
    client.subscribe(TEST_TOPIC)
    log("  Subscribed successfully")
except Exception as e:
    log(f"ERROR: Subscribe failed — {e}")
    client.disconnect()
    sys.exit()

# 11. Brief pause to let subscription establish
log("Waiting 1s for subscription to establish...")
time.sleep(1)

# 12. Publish test message
log(f"Publishing '{TEST_PAYLOAD.decode()}' to topic '{TEST_TOPIC.decode()}' ...")
try:
    client.publish(TEST_TOPIC, TEST_PAYLOAD)
    log("  Publish sent successfully")
except Exception as e:
    log(f"ERROR: Publish failed — {e}")
    client.disconnect()
    sys.exit()

# 13. Wait for loopback message
log("Waiting for loopback message (up to 5s)...")
LOOPBACK_TIMEOUT = 5
start = time.ticks_ms()

while not received_msg:
    try:
        client.check_msg()
    except Exception as e:
        log(f"ERROR: check_msg() failed — {e}")
        break
    if time.ticks_diff(time.ticks_ms(), start) > LOOPBACK_TIMEOUT * 1000:
        log("WARNING: No loopback message received within timeout")
        log("  Possible causes:")
        log("  - Broker not forwarding messages back to subscriber")
        log("  - check_msg() not being called frequently enough")
        log("  - Topic mismatch between publish and subscribe")
        break
    time.sleep(0.1)

# 14. Report outcome
print()
if received_msg:
    topic, msg = received_msg[0]
    if msg == TEST_PAYLOAD:
        log("=== MQTT Test PASSED ===")
        log(f"  Sent    : '{TEST_PAYLOAD.decode()}'")
        log(f"  Received: '{msg.decode()}'")
        log("  Publish → Subscribe loopback confirmed working")
    else:
        log("WARNING: Message received but payload mismatch")
        log(f"  Expected: '{TEST_PAYLOAD.decode()}'")
        log(f"  Received: '{msg.decode()}'")
else:
    log("=== MQTT Test INCOMPLETE ===")
    log("  Connected and published successfully but no loopback received")
    log("  MQTT broker connectivity is working; subscriber callback is the issue")

# 15. Disconnect cleanly
log("Disconnecting from broker...")
try:
    client.disconnect()
    log("  Disconnected cleanly")
except:
    log("  WARNING: Clean disconnect failed (non-critical)")

log("=== MQTT Test Complete ===")