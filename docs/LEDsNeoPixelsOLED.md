# Using the LEDs and OLED to monitor status

The LEDs provide quick clues about whether a board is running, communicating track status and block status. The OLED gives more detail, such as the DCC address of the loco in a block, network status or a programming response.

Use both together: an LED is a quick status cue, while the OLED can help identify what changed or where to investigate. The indicators report what the software has detected rather than directly reporting status.

There is a built in mono-colour LED on the Pico. This flashes with a 1 Hz frequency in normal operation. There are 'NeoPixel' LEDS chanined on a single data line. The first NeoPixel on the chain shows the communications status. On the command station the second NeoPixel shows the track status. On the RailCom block detector, the other four NeoPixels show the status of each of the monitored blocks. The NeoPixels' silkscreen annotations are in the chaining order. In addition the RailCom detector has a power on LED.

## Quick checks

| What you see | What it suggests | What to check |
| --- | --- | --- |
| The Pico's built-in LED flashes | The application is running its heartbeat task. | If not flashing this indicates a softare problem or possibly no power. A flashing heartbeat does not confirm that Wi-Fi, MQTT or track detection is working. |
| The communications NeoPixel is red | Wi-Fi is disconnected, or an MQTT communication error has been reported. | Look for a matching Wi-Fi or MQTT message on the OLED, if one is shown. Check the configured network, signal, broker address and broker availability; not every MQTT error has a matching OLED message. |
| The communications NeoPixel shows orange | The board is trying to connect to Wi-Fi. | Allow time for connection. If it stays in this state, check the Wi-Fi configuration and access point. |
| The communications NeoPixel is blue, then goes dark | An MQTT message was sent; the dark state follows when the client reports ready. | This is activity, not an error indication. The device will ping the MQTT broker periodically which will result in a flash. |
| The communications NeoPixel is green, then goes dark | An MQTT publication was received; the indication may be brief. | If data is not reaching the application, check that the publisher is sending to the expected broker/topic and that the client is connected. |
| The communications NeoPixel is unlit | This is the quiescent state. | This not indicative of a problem unless it persists for more than a minute. |
| A block NeoPixel is green | Current-based detection reports the block occupied, but no DCC decoder is providing a RailCom response. | If there's nothing or RailCom decoder in the block inspect the detector and track wiring. |
| A block NeoPixel is blue | RailCom Channel 1 reports occupancy for that block. | Check the locomotive's RailCom response and the block's RailCom detector if the report is unexpected. |
| Block NeoPixels are dim red | Internal I2C bus problem. | If all four NeoPixels are the same, this is typically the result of no track power. Check the DCC supply, booster/output and block feed. If not all four NeoPixals are red, this indicates a board fault. |
| A block NeoPixel is unlit | The software currently indicates the block is empty, or has not received an indication that lights it. | If a vehicle is present, check track power and both current and RailCom detection. Dark alone does not identify which part of the detection path needs attention. |
| The command station track monitor NeoPixel is dark | Booster power is off. | If booster power should be on (e.g. it's on at JMRI) check software configuration. |
| The command station track monitor NeoPixel is green | Booster power is on. | If booster power is off (e.g. at JMRI) check software configuration. |
| The command station track monitor NeoPixel is orange | High track load - not a fault. | If not consistent with expected load check for partial track short or loco mechanism problem. |
| The command station track monitor NeoPixel is red | DRV8874 fault detected. | Typically track short circuit or DRV8874 over temperature. **Warning** DRV8874 may be hot. |
| The command station track monitor NeoPixel is purple | DRV8874 fault detected. | Typically the firmware has the booster power on, but there is no DC supply to the booster. E.g the Pico has USB power but 12V is not connected. |

## Reading the OLED

The OLED is a small event display rather than a continuously refreshed dashboard. A new event can replace text on the same line. An earlier message may no longer be visible. Treat the text as a clue to the latest reported event, not as a complete history.

### Network and MQTT messages

The display can show:

- **Wi-Fi name and host** while the board starts or tries to connect. If Wi-Fi disconnects, a `wifi discon:` message includes the reported disconnect information.
- **Wi-Fi connection details** after connection.
- **MQTT broker and port** when MQTT connects.
- **`Closed:` or `Er ...`** when the MQTT connection closes or reports an operating-system error.

Following normal connection the board shows:

- board type details
- SSID / host name
- ip address
- broker:port

If Wi-Fi is disconnected, investigate the Wi-Fi configuration or access point first. If Wi-Fi details appear but the MQTT line reports a close or error, focus on broker reachability, address/port configuration and broker operation. A green or blue communications flash only indicates a received or sent publication; it is not by itself confirmation that the intended recipient processed it.

### Block and RailCom messages

The display identifies blocks by their configured names. When RailCom data is reported, the line includes the locomotive address type, address and orientation. This can help distinguish a real RailCom report from occupancy indicated only by current detection.

If a block LED indicates occupancy but there is no locomotive information on the OLED, the system may have detected current without receiving usable RailCom identification. If the block should be empty but remains indicated as occupied, compare the LED colour with the OLED and check the corresponding track section and detector.

### Programming messages

During Programming on Main (POM), the OLED can show the locomotive address and CV (configuration variable) involved:

- A CV result is shown with its value, either as `c:<CV> v:<value>` or, for a few known manufacturer values, CV8 is interpreted as a manufacturer name.
- **`timeout`** means no response was received before the operation timed out.
- **`NAK`** means the command was refused (e.g the addressed CV doesn't exist or is read-only).

For a timeout check that the locomotive is on the layout and that its address is correct. For a NAK check that the decoder supports the requested operation. The display reports the outcome. It does not distinguish by itself between a decoder, track, power or communication problem.

## A practical troubleshooting sequence

1. **Check the heartbeat.** If the built-in LED is not flashing, first confirm that the board is powered and the expected application has started.
2. **Check communications.** Use the first NeoPixel and the OLED's Wi-Fi/MQTT messages to decide whether to investigate Wi-Fi or the broker.
3. **Check the affected block.** Note which block LED is lit and its colour, then compare it with the block name and any RailCom details on the OLED.
4. **Check the physical section.** Confirm track power and wiring, then consider current detection and RailCom separately. A green indication is current-based; a blue indication is RailCom occupancy.
5. **For POM problems,** note the displayed address, CV and result (`timeout` or `NAK`) before checking the locomotive, decoder and powered track section.

The precise messages and available block indicators depend on the board and application. The hardware documentation describes the supported board configurations and detector connections.
