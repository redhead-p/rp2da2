# Configuration

## RP Pico

Configuration files hold information required at runtime by the Pico MicroPython application.  The files use the JSON format.
They are held in the repository's conf directory.
They must be copied to a top level directory on the
target machine called conf. The configuration files in the repository
should be taken as examples.
They need to be modified outside the repository to reflect local requirements. The Thonny editor
may be used to update them as required once they have been copied to the target machine.

### Wi-Fi - '/conf/wifi.json'

The configuration file specifies:

- Network country code
- SSID - your Wi-Fi network name
- password - the network password
- host name - the name to be used by local machine. This needs to be changed
from the MicroPython default to avoid duplicates.

```json
{"country": "myCountry", "password": "myPassword", "ssid": "mySSID", "hostname":"myHostName"}
```

### MQTT -  '/conf/mqtt.json'

The config file specifies:

- the MQTT broker's host name
- the local machine client ID.  The client id is required as by default Mosquitto will not permit access without it. However if not specified here the client id will be set to the network host name.
- port - the MQTT port number. By default this is set to 1883 and this setting may be ommitted.

```json
{"broker": "myBroker", "clientId": "myClientName", "port": 1883}
```

On the command station the MQTT connection supports track power and cabs.
On the local detector the MQTT connection supports sensor updates and reporters.
The MQTT connection may be used to communicate with JMRI.
Generally topics match those used by JMRI but some modifications are required to JMRI defaults
as configured on the MQTT connections settings.

## MQTT Broker - Mosquitto Configuration

The Mosquitto MQTT broker configuration file is held in mosquitto.conf on the machine running the broker.
The location of the file is OS dependent.
For Raspberry Pi OS it's

```text
/etc/mosquitto/mosquitto.conf
```

A couple of lines will need to be added if not already there.

```text
allow_anonymous true

listener 1883
```

Note that connections to Mosquitto will not be authenticated.
Do not do this unless inward connections to your network are blocked
(or you don't mind aliens hacking your model railway).

## JMRI MQTT Configuration

The JMRI MQTT Configuration is maintained as part of the JMRI MQTT connection settings.
An MQTT connection needs to be created within JMRI preferences -> connections.  

Set the IP Address/Host Name to that of your broker. I.e. the same as set for "broker" in
the mqtt.json configuration file above.

Check 'Additional Connection Settings' under
Preferences->Connections for the MQTT connection to access the JMRI MQTT configuration.

|Setting|Value|
|---|---|
|Sensor send topic:|track/sensor/{0}/set|
|Sensor receive topic:|track/sensor/{0}/event|
|Power send topic:|track/power/set|
|Power receive topic:|track/power/event|
