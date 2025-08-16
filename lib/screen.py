"""Screen Module
    :author: Paul Redhead

 
This is the screen application module.  It specifies the Screen class.

Generally it provides application specific access to the display. It knows about application objects and events etc.
and how they are managed on screen.


The OlED display is updated using blocked writes.
"""
"""       Copyright 2023, 2024  Paul Redhead

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
    Initial contents decode CV 8 values into manufacturer text."""
    

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
        if (Screen._scrn) != None and (Screen._scrn is not self):
            raise RuntimeError ('Only one Screen object possible')
        
        self._oled = OLED_0in91(I2C(0))
        self.clear_screen()
        self._just_started = True



    def clear_screen(self):
        """Clear the screen
        
        This clears the screen by filling it with black.
        """
        for pg in self._oled.page:
            pg.fill(0)
        self._oled.show()

    def show_screen(self, lines):
        """Show the screen with the given lines.

        This loads the screen with the given lines and then displays it.
        Each line is a tuple of (page number, text, x position).
        If the same page number appears multiple times in `lines`, only the last entry for that page will be displayed.

        Args:
            lines: A list of tuples, each containing (page number, text, x position).
        """
        for pgn, text, x in lines:
            self._oled.page[pgn].fill(0)
            self._oled.page[pgn].text(text, x, 0)
            self._oled.show_page(pgn)


    def show_event(self, report):
        """Show an event report
        
        This updates the screen with the event.  Other application actions on events are 
        dealt with elsewhere.

        Args:
            self:
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
        self._oled.scroll_write(f'{src.get_name()} empty')

    def _handle_blk_ch1(self,src, data):
        addr_t, address, orientation = data
        self._oled.scroll_write(f'{src.get_name()} {addr_t}{address} {orientation}')

    def _handle_blk_occ(self,src, _):
        self._oled.scroll_write(f'{src.get_name()} occupied')


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

    def _handle_mqtt_ready(self, src, data):
        """MQTT connection established
        (subscribption sent) - clear the screen if first time"""
        if self._just_started:
            # this is the first time
            self._just_started = False
            self.clear_screen()

    _event_handler = {Device.BLK_EMPTY: _handle_blk_empty,
                      Device.BLK_OCC:_handle_blk_occ,
                      Device.BLK_CH1: _handle_blk_ch1,
                      Device.POM_CV: _handle_cv_val,
                      Device.POM_TO: _handle_pom_to,
                      Device.POM_NAK: _handle_pom_nak,
                      Device.MC_READY: _handle_mqtt_ready}