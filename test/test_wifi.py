""" Wi-Fi Connection Initial Confidence Check

To be run as part of commissioning a newly constructed board as a check on Wi-fi
configuration file contents and wi-fi operability.

"""
"""        Copyright (C) 2026 Paul Redhead

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

wlan = None
ssidd_set = set()

def get_config():
    """ read wi-fi configuration from json file"""
    global credentials, conf
    with open('/conf/wifi.json', 'r') as fd:
        conf = json.load(fd)
        network.country(conf['country'])
        network.hostname(conf['hostname'])
        credentials = (conf['ssid'], conf['password'])
    for key, content in conf.items():
        filler = ' ' * (9 - len(key))
        print(f"{key}{filler}:{content}")

def print_ifconfig():
        ip, subnet, gateway, dns = wlan.ifconfig()
        print(f" ip      {ip}")
        print(f" subnet  {subnet}")
        print(f" gateway {gateway}")
        print(f" dns     {dns}")
        
def chk_wifi():
    global wlan
    global ssid_set
    ssid_set = set()
    print("Access points")
    print()
    for ssid, bssid, channel, rssi, sec, hidden in wlan.scan():
        ssid_set.add(ssid.decode())
        print(f"ssid : {ssid.decode()}")
        bssid_out = ''
        for b in bssid:
            bssid_out = bssid_out + hex(b)[2:4] + ':'
        print(f" bssid   : {bssid_out[:-1]}")
        print(f' channel : {channel}')
        print(f' rssi    : {rssi}')
        print(f' security: {sec}')
        print(f' hidden  : {hidden}')
        print()
    if conf['ssid'] not in ssid_set:
        print(f'** Warning {conf["ssid"]} not in range.')

    if wlan.isconnected():
        print(f"wi-fi connected to {wlan.config('ssid')}")
        print_ifconfig()
    else:
        print("wi-fi not connected")

def do_connect():
    state_lu = {network.STAT_IDLE: 'Idle',
            network.STAT_CONNECTING: 'Still connecting - timeout!',
            network.STAT_WRONG_PASSWORD: 'Password wrong',
            network.STAT_NO_AP_FOUND: 'Access point not found',
            network.STAT_CONNECT_FAIL: 'Connect fail',
            network.STAT_GOT_IP: 'Connected OK'}
    global wlan, conf, credentials
    if wlan.isconnected():
        print(f"wi-fi connected to {wlan.config('ssid')}")
    else:
        print(f'Connecting to {conf['ssid']}')
        wlan.connect(*credentials)
        status = network.STAT_CONNECTING
        count = 0
        while status == network.STAT_CONNECTING:
            time.sleep(1)
            count += 1
            if count > 10:
                break # authentication error doesn't seem to get reported!
            status  = wlan.status()
        if status == network.STAT_GOT_IP:
            print(f"wi-fi connected to {wlan.config('ssid')}")
            print_ifconfig()
        else:
            print(state_lu[status])
    
def disconnect():
    wlan.disconnect()


tests = {
            0:("Load and review Wi-Fi configuration", get_config,()),
            1:("Check Wi-Fi State", chk_wifi, ()),
            2:("Connect", do_connect, ()),
            3:("Disconnect", disconnect, ())
        }
    
def do_test(tn = None):
    global test_num
    if tn is not None:
        test_num = tn
    descrip, test_fn , param = tests[test_num]
    print(f"** {descrip} **")
    test_fn(*param)


if __name__ == '__main__':
    print()
    print("Wi-Fi Commissioning Tests")
    print()
    if wlan is None:
        # get wlan and activate
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    nxt_tst = 0

    test_keys = sorted(tests.keys())
    # list tests
    for k in test_keys:
        print(k, tests[k][0])
    # stop when last test done
    while nxt_tst < len(test_keys):
        print()
        ip = input('>')
        print(ip)
        if ip:
            nxt_tst = int(ip)
        do_test(nxt_tst)
        nxt_tst += 1
    
