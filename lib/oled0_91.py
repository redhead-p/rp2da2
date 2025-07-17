"""Device driver module for 0.91 inch OLED on i2c

128 columns by 32 lines

Mono chrome using SSD1306 controller

Display is organised as 4 full width pages. Each may contain 1 line of text 


"""

from micropython import const
from machine import Pin, I2C
import time
from framebuf import FrameBuffer, MONO_VLSB


_OLED_WIDTH   = const(128)  #OLED width
_OLED_HEIGHT  = const(32)  #OLED height
_PAGE_HEIGHT = const(8)  # page height is same as font height 

_I2C_CMD = const(0X00)
_I2C_RAM = const(0X40)
_I2C_ADDR = const(0x3c)





class Page(FrameBuffer):
    """Display Page Class
    
    The display is organised into 4 pages.
    It is based on the FrameBuffer class.
    
    If using the default Framebuffer text each page holds 1 line of text.
    """
    def __init__(self):
        """Construct a page.
        
        This allocates creates a framebuffer with the buffer allocated here.
        
        Args:
            self:
            
        """
        self._data_buff = bytearray(_OLED_WIDTH + 1)  # monochrome eight pixels per byte
        self._data_buff[0] = _I2C_RAM # it will always hold data for ram
        self._data_buff_mv = memoryview(self._data_buff)
        super().__init__(self._data_buff_mv[1:], _OLED_WIDTH, _PAGE_HEIGHT, MONO_VLSB)

    def data_buff(self):
        """Get the data buffer

        This returns a memory view of the buffer. 
        
        Returns:
            Data buffer
            """
        return self._data_buff_mv





class OLED_0in91:
    """0.91" OLED Display using SSD1306
    
    """
    def __init__(self, i2c):
        """Construct the OLED driver
        
        Check to see if OLED is on I2C bus and initialise the SSD1306.
        
        args:
            self:
            i2c: I2C driver.
            """
        #self.width = _OLED_WIDTH
        #self.height = _OLED_HEIGHT
        #Initialize DC RST pin
        # not using reset!

        self._i2c = i2c
        self._addr = _I2C_ADDR       # address is fixed

        assert self._addr in self._i2c.scan(), print ('oled not found')
        



        self._cmdBuff = bytearray(2)  # buffer for commands - fixed size
        self._cmdBuff[0] = _I2C_CMD    # it will always hold a command
        #self._pageBuff = memoryview(self._dataBuff[1:len(self._dataBuff)]) 
        #super().__init__(self._frmBuff, _OLED_WIDTH, _OLED_HEIGHT, MONO_VLSB)
        self._init_display()

        self.page = [Page(), Page(), Page(), Page()]




    def _write_cmd(self, cmd):
        self._cmdBuff[1] = cmd
        l = self._i2c.writeto(self._addr, self._cmdBuff)
        assert l == len(self._cmdBuff), 'i2c write cmd NACK'


    def _write_data(self, buf):

        l = self._i2c.writeto(self._addr, buf)
        assert l == len(buf), f'i2c write data NACK l {l}'

    def _init_display(self):
        """Initialize display""" 
        self._write_cmd(0xAE)

        self._write_cmd(0x40) # set low column address
        self._write_cmd(0xB0) # set high column address

        self._write_cmd(0xC8) # not offset

        self._write_cmd(0x81) # set contrast
        self._write_cmd(0x7f) # to 50%

        self._write_cmd(0xa1) # map col 127 to SEG0

        self._write_cmd(0xa6) # set normal display

        self._write_cmd(0xa8) # set multiplex ratio 
        self._write_cmd(0x1f) # to 31

        self._write_cmd(0xd3) # set display offset   
        self._write_cmd(0x00) # to zero

        self._write_cmd(0xd5) # set clock divide ratio
        self._write_cmd(0xf0) # and oscillator freq

        self._write_cmd(0xd9) # set pre charge period
        self._write_cmd(0x22) 

        self._write_cmd(0xda) # set pins config
        self._write_cmd(0x02)

        self._write_cmd(0xdb) # set desel level
        self._write_cmd(0x49) #

        self._write_cmd(0x8d) # enable charge pump
        self._write_cmd(0x14) # on

        time.sleep_ms(200)
        self._write_cmd(0xAF)  #--turn on oled panel


    def show_page(self, pg_n):
        self._write_cmd(0xB0 + pg_n) # set page address
        self._write_cmd(0x00) # set low column address
        self._write_cmd(0x10) # set high column address
           

        #print(f'Written {self._i2c.writeto(self._addr, self._dataBuff)}')
        self._write_data(self.page[pg_n].data_buff())
        

    def show(self):
        for pg in range(0, _OLED_HEIGHT//_PAGE_HEIGHT):
            self.show_page(pg)
           

if __name__ == '__main__':
    o = OLED_0in91(I2C(0))
    o.page[0].text('Hello World', 0, 0)
    o.page[1].text('Line 2', 0, 0)
    o.page[2].text('Indented line 3', 8, 0)
    o.page[3].text('Last line', 8, 0)
    x = time.ticks_us()
    o.show()
    print(time.ticks_us() -  x)