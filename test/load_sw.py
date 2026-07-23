""" Load Software

This installs the software packages and relevant main.py for the command station or local
detector board. The latest version of softare as available on the GitHub repository is installed.

To be run as part of commissioning a newly constructed board or to maintain the sofware.

The target Pico must be a wireless capbable version. There must be W-Fi connectivity to the 
Internet.

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
import mip

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
        if key != 'password':
            print(f"{key}{filler}:{content}")
        else:
            print(f"{key}{filler}:{'*' * len(content)}")

def print_ifconfig():
        ip, subnet, gateway, dns = wlan.ifconfig()
        print(f" ip      {ip}")
        print(f" subnet  {subnet}")
        print(f" gateway {gateway}")
        print(f" dns     {dns}")
        

def do_connect():
    state_lu = {network.STAT_IDLE: 'Idle',
            network.STAT_CONNECTING: 'Still connecting - timeout!',
            network.STAT_WRONG_PASSWORD: 'Password wrong',
            network.STAT_NO_AP_FOUND: 'Access point not found',
            network.STAT_CONNECT_FAIL: 'Connect fail',
            network.STAT_GOT_IP: 'Connected OK',
            2: 'Connected - No IP yet'
            }
    global wlan, conf, credentials
    if wlan.isconnected():
        print(f"Wi-Fi already connected to {wlan.config('ssid')}")
        return True
    else:
        print(f'Connecting to {conf['ssid']}')
        wlan.connect(*credentials)
        status = network.STAT_CONNECTING
        count = 0
        while status == network.STAT_CONNECTING:
            time.sleep(1)
            count += 1
            if count > 20:
                break # authentication error doesn't seem to get reported!
            status  = wlan.status()
        if status == network.STAT_GOT_IP:
            print(f"Wi-Fi connected to {wlan.config('ssid')}")
            print_ifconfig()
            print()
            return True
        else:
            print(state_lu[status])
            return False
        
def select_option():
    ip = '?'
    print('Select Option')
    while ip not in 'pcl':
        print('enter "p" for packages only')
        print('      "c" for packages + command station "main.py"')
        print('      "l" for packages + local detector  "main.py"')
        ip = input('>')
        print(ip)
    return ip

        
def load_packages():
    # other packages depend on mqtt
    mip.install("github:redhead-p/rp2da2/mqtt")


def load_main(ip):
    if ip == 'c':
        mip.install("github:redhead-p/rp2da2/examples/command/main.py", target = '/')
    if ip == 'l':
        mip.install("github:redhead-p/rp2da2/examples/quad_local_detect/main.py", target = '/')    

    
def disconnect():
    wlan.disconnect()





if __name__ == '__main__':
    print()
    print("Load RP2DA2 Software")
    print()
    print("Activating Wi-Fi")
    if wlan is None:
        # get wlan and activate
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    print("Reading Configuration from /conf/wifi.json")
    get_config()
    print("Connecting......")
    if not do_connect():
        print("Connection failed")
    else:
        opt = select_option()
        load_packages()
        if opt in 'cl':
            load_main(opt)
        print("Check preceeding REPL log for errors")


    
