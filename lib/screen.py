"""Screen Module
    :author: Paul Redhead

 
This is the screen application module.  It specifies the Screen class.

Generally it provides application specific access to the display. It knows about application objects and events etc.
and how they are managed on screen.


The OLED display is updated using blocked writes.
"""
"""       Copyright 2023, 2024, 2025, 2026 Paul Redhead

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
from machine import I2C

from oled0_91 import OLED_0in91

from hw_conf import HwConf

from device import Device


class Screen():
    """This class provides the screen application.
    
    It deals with the application events that
    require display on the screen or other actions (e.g. UI menu/data)

    It's a singleton.
    """

    _scrn = None # this will be set to the singleton object on instantiation

    _CV_LU = {(8, 151):"ESU", (8, 145):"ZIMO", (8, 78):"TOM"}
    """Translation table for CV number, value tuples into text.
    Initial contents decode CV 8 values into manufacturer text.
    """
    
    @classmethod
    def get_instance(cls):
        """Return the singleton instance

        The singleton is created on the first call.
        
        args:
            cls:
        """
        if cls._scrn is None:
            cls._scrn = Screen()
        return cls._scrn

    def __init__(self):
        """Screen Initialiser
        
        Initialise the oled and clear screen.
        """
        assert Screen._scrn is None, 'Only one Screen object possible'
        hc = HwConf.get_instance()
        self._oled = OLED_0in91(I2C(hc.OLED_I2C))
        self.clear_screen()
        self.show_line(0,hc.name, 0)

    def clear_screen(self):
        """Clear the screen
        
        This clears the screen by filling it with black.
        """
        for pg in self._oled.page:
            pg.fill(0)
        self._oled.show()

    def show_line(self, pgn, text, x):
        """Show a screen line.

        This loads the screen page with the given line and then displays it.
        Each line is described by page number, text and x position.

        args:
            pgn: page number (1 page per line)
            text: text to be displayed
            x:  horizontal offset
        """
        self._oled.page[pgn].fill(0)
        self._oled.page[pgn].text(text, x, 0)
        self._oled.show_page(pgn)

    def show_screen(self, lines):
        """Show the screen with the given lines.

        This loads the screen with the given lines and then displays it.
        Each line is a tuple of (page number, text, x position).
        If the same page number appears multiple times in *lines*, only the last entry for that page
        will be displayed.

        args:
            lines: A list of tuples, each containing (page number, text, x position).
        """
        for line in lines:
            self.show_line(*line)

    def show_event(self, report):
        """Show an event report
        
        This updates the screen with the event.  Other application actions on events are 
        dealt with elsewhere.

        Args:
            report: a tuple containing the reference to the source object, the unique event code see: display
                and additional information - format and content event specific
        """
        (source, event, data) = report
        try:
            self._event_handler[event](self, source, data)
        except KeyError:
            # assume intended for a different event processor
            pass

    def _handle_blk_empty(self,src, _):
        txt = (f'{src.name}')
        self.show_line(src.index, txt, 0)

    def _handle_blk_ch1(self,src, data):
        if data:
            addr_t, address, orientation = data
            txt = (f'{src.name} {addr_t}{address} {orientation}')
        else:
            txt = (f'{src.name}')
        self.show_line(src.index, txt, 0)

    def _handle_cv_val(self,src, data):
        address, cv_num, value = data
        try:
            self._oled.scroll_write(f'a:{address} {Screen._CV_LU[(cv_num, value)]}')
        except KeyError:
            self._oled.scroll_write(f'a:{address} c:{cv_num} v:{value}')

    def _handle_pom_to(self,src, data):
        address, cv_num = data
        self._oled.scroll_write(f'a:{address} c:{cv_num} timeout')
        self._oled.show_page(1)

    def _handle_pom_nak(self,src, data):
        address, cv_num = data
        self._oled.scroll_write(f'a:{address} c:{cv_num} NAK')

    def _handle_un_enc(self,src, data):
        si , v = data
        self._oled.scroll_write(f'!ID7 i:{si} v:{v}')

    def _handle_wifi_discon(self,src, data):
        self.show_line(1,f'wifi discon:{data}',0)

    def _handle_wifi_start(self, src, data):
        ssid, host = data
        self.show_line(1,f'{ssid}:{host}', 0)

    def _handle_wifi_connected(self, src, data):
        self.show_line(2,data,0)

    def _handle_mqtt_connected(self, src, data):
        broker, port = data
        self.show_line(3,f'{broker}:{port}', 0)

    def _handle_mqtt_closed(self, src, data):
        self.show_line(3, f'Closed:{data}',0)

    def _handle_mqtt_os_err(self, src, data):
        rw, oserr = data
        self.show_line(3,f'Er {rw}:{str(oserr)}', 0)

    _event_handler = {Device.BLK_EMPTY: _handle_blk_empty,
                      Device.BLK_CH1: _handle_blk_ch1,
                      Device.POM_CV: _handle_cv_val,
                      Device.POM_TO: _handle_pom_to,
                      Device.POM_NAK: _handle_pom_nak,
                      Device.WF_START: _handle_wifi_start,
                      Device.WF_CONNECTING: _handle_wifi_start,
                      Device.WF_CONNECTED: _handle_wifi_connected,
                      Device.WF_DISCON: _handle_wifi_discon,
                      Device.MC_CONNECTED: _handle_mqtt_connected,
                      Device.MC_CLOSED: _handle_mqtt_closed,
                      Device.MC_OS_ERR: _handle_mqtt_os_err,
                      Device.MC_U_ID7: _handle_un_enc}