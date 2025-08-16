"""DCC RailCom PIO module
    :author: Paul Redhead

This module contains the functions and classes for low level RailCom datagram reading.
It's applicable for block occupancy detection on Channel 1 and central dcc command decoder
responses on Channel 2. 

The module makes use of the RP2xx0 PIO. A command station can support two detectors - one on channel 1
(e.g. for a block close to the command station) and one 
on channel 2 . These must be on the same PIO block and will use all four state machines. On the command station
different PIO block is used for DCC signal encoding.

For block detection only, a single PIO block can run two detectors.

Memory mapped addresses and offsets are as defined in the RP2040 datasheet.

"""
"""
        Copyright (C) 2023, 2024, 2025 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""


# stop pylance reporting undefined variables for PIO code
# pyright: reportUndefinedVariable=false

from machine import Pin, mem32

from micropython import const
import array
import rp2

from device import Device


# module constants - not for importing elsewhere
_PIO_CU_FREQ = const(250_000)           # 250 kHz - 4 micro sec. tick period for command stn. cutout timing
_PIO_CU_D_FREQ = const(500_000)         # 500 kHz - 2 micro sec. tick period for block detect cu timing
_PIO_RX_FREQ = const(4_000_000)         # 4MHz - 16 * 250kHz bps rx clock rate for async. rx

_CH_SIZE = [2, 6]                       # Channel 1: 2 chars max - Channel 2: 6 chars max     

# memory mapped addresses and offsets of PIO registers (as defined the RP2040 datasheet)
PIO0_BASE = const(0x50200000)
""" PIO  0 base address"""
PIO1_BASE = const(0x50300000)
""" PIO 1 base address """
SM1_EXECCTRL = const(0xe4)
""" State machine 1 exec control offset """
SM3_EXECCTRL = const(0x114)
""" State machine 3 exec control offset """


class RailComRead:
    """ The RailComm Reader class
    
    This class schedules and executes RailComm datagram read activities during the cutout period. During
    the cutout period, the DCC power signal is ceased and the two DCC lines are short circuited allowing the 
    RailCom current signal to be generated and detected. On the command station the cutout is instigated by the
    enable signal to the DRV8874 being set low. This cutout siganl being low is used directly when detecting
    on the command station. A remote block detector uses the RailCom detector output to detect the cutout.

    A RailCom reader object works on either on Channel 1 (block) or Channel 2 (central/global) but not both. 

    Channel 1 is used for block occupancy detection and the detector may run on the commamd station or a remote
    detector. Channel 2 is used for command responses and other decoder specific information.  It only runs
    on the command station.

    On the command station, as far as this class is concerned, the cutout (DRV8874 enable pin) is used as an input.
    
    The RailCom detector output is high for no current detected and low for current detected. During normal DCC
    energisation it will be high for an unoccupied block / no load. For an occupied block it will low except for 
    short periods (<2.5µs) during DCC polarity change. During the cutout period it will be high except when
    a RailCom encoder (e.g. DCC decoder) is actively transmitting.

    Each RailCom reader uses two PIO state machines.  One times the cutout and the second is the serial
    RailCom message receiver. Both state machines need to be on the same PIO for RP2040 and are assigned to
    consecutive state machine numbers. A PIO block has 4 state machines and can run two readers. The 
    The cutout timers will be on the state machine numbers 0 & 2 of the PIO block and the associated receivers on state machine
    numbers 1 & 3. (Note that MicroPython numbers all state machines sequentially from 0 - e.g. it refers to the first 
    state machine on the second PIO as no. 4.)

    The cutout state machine starts the RailCom receiver using an IRQ. Relative IRQ numbering 
    is used. The first is no 5 which will be used by sm 0. The sm 2 will use IRQ 7.

    At the end of the channel window the PIO raises an application interrupt to initate reading the state machine
    FIFO buffer.


    Attributes:
        ACK: acknowledgement from decoder (may be used as padding)
        BUSY: busy response from decoder
        RES:  reserved
        NAK: negative acknowledgement from decoder (may follow ACK!)
        IMP_ACK: no explicit ACK but datagram received (implicit ACK)
        ERR_WH: raw data byte not valid Hamming 4 weight - weight high
        ERR_WL: raw data byte not valid Hamming 4 weight - weight low
        ERR_OE: Overrun error (no valid stop bit)
        DG_RESP: internally generated datagram containing protocol control byte
    """
    # class constant

    # protocol bytes - only applicable to Channel 2
    # decoder responses
    # bit 7 set to differentiate from datagram value 6 bit translation
    ACK =  const(0x80)
    BUSY = const(0x81)
    RES =  const(0x82)
    NAK =  const(0x83)
    # locally interpreted responses
    ERR_WH = const(0x84)
    ERR_OE = const(0x85)
    ERR_WL = const(0x86)
    # other available response codes (used elsewhere)
    IMP_ACK = const(0x87)
    ERR_RESP = const(0x88)


    # datagram IDs (incomplete at present) - ID's are 6 bits 
    # IDs >= 64 are internally generated datagrams
    DG_RESP = const(0x40) # protocol control byte
    # DG_SIDE = const(0x41) # side - originating decoder orientation

    _RESTART_MEM = {0:PIO0_BASE + SM1_EXECCTRL,
                    2:PIO0_BASE + SM3_EXECCTRL,
                    4:PIO1_BASE + SM1_EXECCTRL,
                    6:PIO1_BASE + SM3_EXECCTRL}
    """Memory locations for restart calculation by MP state machine number
    """

    _H4LU = {
    0xAC:0x00, 0xAA:0x01, 0xA9:0x02, 0xA5:0x03,
    0xA3:0x04, 0xA6:0x05, 0x9C:0x06, 0x9A:0x07,
    0x99:0x08, 0x95:0x09, 0x93:0x0A, 0x96:0x0B,
    0x8E:0x0C, 0x8D:0x0D, 0x8B:0x0E, 0xB1:0x0F,
    0xB2:0x10, 0xB4:0x11, 0xB8:0x12, 0x74:0x13,
    0x72:0x14, 0x6C:0x15, 0x6A:0x16, 0x69:0x17,
    0x65:0x18, 0x63:0x19, 0x66:0x1A, 0x5C:0x1B,
    0x5A:0x1C, 0x59:0x1D, 0x55:0x1E, 0x53:0x1F,
    0x56:0x20, 0x4E:0x21, 0x4D:0x22, 0x4B:0x23,
    0x47:0x24, 0x71:0x25, 0xE8:0x26, 0xE4:0x27,
    0xE2:0x28, 0xD1:0x29, 0xC9:0x2A, 0xC5:0x2B,
    0xD8:0x2C, 0xD4:0x2D, 0xD2:0x2E, 0xCA:0x2F,
    0xC6:0x30, 0xCC:0x31, 0x78:0x32, 0x17:0x33,
    0x1B:0x34, 0x1D:0x35, 0x1E:0x36, 0x2E:0x37,
    0x36:0x38, 0x3A:0x39, 0x27:0x3A, 0x2B:0x3B,
    0x2D:0x3C, 0x35:0x3D, 0x39:0x3E, 0x33:0x3F,
    0x0F:ACK, 0xF0:ACK, 0xE1:BUSY, 0xC3:RES, 0x87:RES, 0x3C:NAK
    }
    """ Hamming Look Up Table

    This translates the received Hamming 4 weighted byte back to the six bit group from
    the original datagram or one of the 6 special values. Applicable to Ch1 & Ch2.
    N.B. the 6 special values are not valid for Ch1.

    See RCN-217 2.5.
    """


    def __init__(self, cu_sm_num, rc_rx_pin, cb, channel = 1, cu_pin = None):
        """ RailCom class constructor

        Constructs a reader for Channel 1 (block detector) or Channel 2 (central detector) using two PIO state machines.

        The cutout monitor state machine runs on the supplied state machine number.  The receive statemachine
        runs on the number + 1.

        If no cutout pin is supplied for channel 1 then it's assumed we are on an accessory controller and
        the cutout is to be detected by monitoring the inputs. The cutout pin must be supplied
        for Channel 2 operation.

        
        args:
            self:
            cu_sm_num: state machine number for cut out scheduling - 4 or 6 if using the second PIO block
            rc_rx_pin: the detector output pin (pin + 1 is the orientation detect pin)
            cb: read complete callback
            channel: RailCom channel to be monitored
            cu_pin: the DRV8874 enable pin (command station usage only)
        """


        # set up cutout detect PIO state machine 
        if channel == 2:
            if cu_pin is None:
                raise RuntimeError("No cutout pin")
            # Channel 2 on command station
            self._sm = rp2.StateMachine(cu_sm_num, self._cut_out2, freq = _PIO_CU_FREQ,
                                        in_base = cu_pin)
            self._sm.irq(self._read_isr) # read from the state machine at the end of the cutout
        else:
            # channel 1 - either command station or block detect
            if cu_pin is None:
                self._sm = rp2.StateMachine(cu_sm_num, self._cut_out1_bd, freq = _PIO_CU_D_FREQ,
                                            in_base = rc_rx_pin, jmp_pin = rc_rx_pin)
            else:
                self._sm = rp2.StateMachine(cu_sm_num, self._cut_out1_com, freq = _PIO_CU_FREQ,
                                            in_base = cu_pin)
            self._sm.irq(self._read_isr) # read from the state machine at the end of the cutout

        # set up RailCom read PIO state machine
        self._smrx = rp2.StateMachine(cu_sm_num + 1, self._rx, freq = _PIO_RX_FREQ,
                                      in_base = rc_rx_pin, jmp_pin = rc_rx_pin)
        


        self._restart = ((mem32[RailComRead._RESTART_MEM[cu_sm_num]] & 0xf80) >> 7) - 1      
        """PIO restart instruction

        This generates the PIO op code required to restart the rx state machine which must run in
        sm 1, 3, 5 or 7
        corresponding to PIO state machines 1 or 3 on the PIO.
        
        Read the wrap address from the PIO exec control register and subtract 1
        for the first PIO instruction of state machine 1, 3, 5 or 7 (the rx program).
        Unconditional 'jmp' opcode is 0 so the address is the jump instruction!

        Raises KeyError if state machine number invalid. 
        
        """

        self._sm.active(True)       # start both state machines
        self._smrx.active(True)
        self._rx_buff = bytearray(6) # translated buffer - max is 6 bytes for channel 2
        self._rx_raw = array.array('I', range(8)) # raw buffer for PIO - 8 words to match FIFO
        self._callback = cb
        self._channel = channel


    @rp2.asm_pio() 
    def _cut_out1_com():
        """ The Cutout state machine monitor program (channel1/cmd stn)

        This version is for use on the same pico as is being used for DCC generation.
        I.e. command station usage for an detection on an adjacent block.
        The cutout is generated by the DCCGen state machine. This
        enables reading during the channel 1 window. The cutout timings in µs:

        0 - Packet end trailing edge
        28 - cutout start (timed in DCCGen - monitored here)
        28 + 47  = 75  - enable receiver for ch1
        28 + 152 = 180 - disable receiver for ch1 (ch1 end @ 177, ch2 start 193)
        28 + 152 + 280 = 460 application start read (ch2 end 454)
        28 + 446 = 474 cutout ends (timed in DCCGen)
        28 + 152 + 280 + 20 = 480 repeat wait for enable going low.
        
        The clock is 250 kHz. 4 µs per tick

        4 instructions used - main loop 39 ticks total
        """

        wrap_target()
        # wait for cutout pin to be asserted (enable off)!
        wait(0, pin, 0)     [11] # delay 12 ticks from cutout start (48µs, 76µs from PE) 
        irq(rel(5))         [24] # start of ch1 window - release the datagram receiver
        irq(rel(0))         [0]  # end of window - raise application interrupt to initiate read
        wait(1, pin, 0)     [0]  # wait for end of cutout (enable on again)
        wrap()                   
    

    @rp2.asm_pio() 
    def _cut_out1_bd():
        """ The Cutout state machine monitor program (channel1 / block detect)

        This version is for use on a pico in use as an railcom block detector.
        The cutout is detected by analysis of the current monitor output. This
        enables reading during the channel 1 window. The cutout timings in µs:

        0 - Packet end trailing edge
        28 - cutout start (monitored here)
        28 + 47  = 75  - enable receiver for ch1
        28 + 152 = 180 - disable receiver for ch1 (ch1 end @ 177, ch2 start 193)
        28 + 152 + 280 = 460 application start read (ch2 end 454)
        28 + 446 = 474 cutout ends (timed in DCCGen)
        28 + 152 + 280 + 20 = 480 repeat wait for enable going low.
        

        The clock is 500 kHz. 2 µs per tick
        14 instructions
        """

        # assumed start state is block unoccupied - current 0 - (rx pin high)
        label("unoccupied")
        wait(0, pin, 0)     [31]       # wait until current detected/block occupied then pause to reconfirm
        jmp(pin, "unoccupied")          # reverted back to unoccupied if < 64µs
        # block now occupied
        label("occupied")
        # filter out any short breaks in occupancy (DCC crossover etc)

        set(y, 9)                       # take ten consecutive samples
        label("spin")
        jmp(pin,"spin2")                
        jmp("occupied")
        label("spin2")
        jmp(y_dec, "spin")      # count not exhausted yet
        
        # break > 40 µs - potential cutout start - treat as such
        # wait another 2µs
        nop()   
        irq(rel(5))         [31] # start of ch1 window - release the datagram receiver 
        nop()               [15] #
        irq(rel(0))         [14] # end of channel 1 window - initiate read
        nop()               [31] # skip channel 2 window 
        nop()               [31] # 
        nop()               [31] #
        nop()               [31]
        # delay for cut out end - implicit wrap back to start
    
 
    @rp2.asm_pio() 
    def _cut_out2():
        """ The Cutout state machine monitor program (channel2)

        This runs at the command station and the cutout is generated by the DCCGen state machine. This
        enables reading during the channel 2 window. The cutout timings in µs:

        0 - Packet end trailing edge
        28 - cutout start (timed in DCCGen - monitored here)
        28 + 152 = 180 - enable reciever (ch1 end @ 177, ch2 start 193)
        28 + 152 + 280 = 460 application start read (ch2 end 454)
        28 + 446 = 474 cutout ends (timed in DCCGen)
        28 + 152 + 280 + 20 = 480 repeat wait for enable going low.
        
        The clock is 250 kHz. 4 µs per tick

        6 instructions used -   main loop 116 ticks total
        """
        
        wrap_target()
        # wait for cutout pin to be asserted !
        wait(0, pin, 0)     [31] # then delay 38 ticks from cutout start (152µs)
        nop()               [5]
        irq(rel(5))         [31] # start of ch2 window - release the datagram receiver
        nop()               [31] # delay 70 ticks (280µs, 460µs so far from PE trailing edge)
        nop()               [5]
        # raise application interrupt to read whats there
        irq(rel(0))         [7]  # and then wait to allow enable pin to be asserted (>488µs)
        wait(1, pin, 0)     [0]
        wrap()                 


    @rp2.asm_pio(
                 in_shiftdir = rp2.PIO.SHIFT_RIGHT,           # lsb first so shift right
                 out_shiftdir = rp2.PIO.SHIFT_RIGHT,
                 fifo_join = rp2.PIO.JOIN_RX)                # no tx so both fifos for rx
    def _rx():
        """ The RailCom data receiver state machine program
        
        This implements a simplified version of an asynchronous communications receiver as
        typically employed in a UART. There's no transmission function.

        The receiver is enabled at the start of the channel window
        by another state machine setting the interrupt flag. It is disabled once the data has
        been read by the application, which restarts the state machine.

        The first input pin is the 'or' of the two sides of the detector circuit. One side detects
        +ve going RailCom pulses and the second -ve going pulses. A RailCom pulse indicates a logic '0',
        the line idle (no RailCom current) is a logic '1'.
        Low indicates logic '0' and vice versa.
        
        The second input pin is the first comparator side.  This may be used to determine which side is
        active, thus indicating which way the locomotive is facing relative to the track DCC.

        The second pin may be NC or used for other purposes, in which case the indication of the
        active side will be indeterminate.

        The osr is used as an additional register.  It's not in use for transmission.

        The state machine clock is set at 16 x the bit rate. (4MHz)

        There's no programatic way back to the first instruction within the PIO program.  The
        state machine is restarted by the controlling application externally forcing execution
        of a jump to the first instruction.

        17 instructions
        """

        wait(1, irq, rel(4))    [0] # wait to be enabled
        wrap_target()
        # each bit is sampled at 16 tick intervals

        label("await_start")
        # we want a confirmed start bit to be at least 3/4 bit time 
        # so we sample it 6 times following the initial edge
        set(y,5)                [0]       
        wait(0, pin, 0)         [0] # wait for start bit leading edge - 2 ticks between samples
        mov(osr, pins)          [0] # get start bit ('0') and orientation (can't get orientation only!)
        label("spin")
        jmp(pin,"await_start")  [0] # back to '1', not long enough for start bit
        jmp(y_dec, "spin")      [0] # spin for next sample

        label("start_ok")
        out(y,1)                [0] # shift out start bit  & discard leaving orientation in osr
        set(y, 7)               [8] # 11 ticks in total from last sample to mid 1st bit.

        label("next_bit")
        in_(pins,1)             [0] # read next bit into isr
        jmp(y_dec,"next_bit")   [14] # wait 15 more ticks - 16 ticks in total  
        jmp(pin,"stop_ok")      [0] # if all data bits read check stop bit
        wait(1, pin, 0)         [0] # overrun error - wait for line idle
        mov(isr, invert(null))  [0] # clear the isr - to all '1's for overrun
        jmp("push")             [0]

        label("stop_ok")            # stop bit OK
        in_(osr,1)              [0] # shift orientation bit into isr
        in_(null, 23)           [0] # shift all bits to l.s. end of isr
        label("push")
        push(noblock)           [0] # and save isr to rx FIFO - data lost if FIFO overrun

        wrap()                      # wait for next start bit


    def _read_isr(self, _):
        """Soft PIO read ISR
        
        Read PIO FIFO into buffer.  Needs to be soft for memory views to  work
        Common to both channel 1 & 2

        N.B the second parameter is the state machine that raised the IRQ.  It is not
        the state machine that has data available!
        
        args:
            self:
            _: state machine raising IRQ - discard
        """
        #Device.check_core0()
        # reset PIO back to first instruction to wait for next trigger.
        # N.B StateMachine.restart() resets everything but the program counter.
        # although documentation and code suggests it should reset it
        self._smrx.exec(self._restart)

        # set raw_buff limit to amount in fifo otherwise read will hang
        raw_buff = memoryview(self._rx_raw)[:self._smrx.rx_fifo()]

        if len(raw_buff) == 0:
            # report no data - and no orientation
            self._callback(self._rx_buff[0:0], 0)
            return

        self._smrx.get(raw_buff)  # read data into raw buffer
       
        # side is saved as 1 or -1 e.g. s * 2 - 1
        # this is the orienation of the decoder wrt the DCC signal
        # orienatation is invalid in case of character overrun
        detector_side = ((raw_buff[0] & 0x100) >> 7) - 1

        max_buf = _CH_SIZE[self._channel - 1] # max number of bytes for this channel
        if len(raw_buff) > max_buf:
            # quietly truncate the buffer
            raw_buff = raw_buff[:max_buf]
        # the raw buffer is in words - bits 0 - 7 data byte as received
        # bit 8 (the orientation bit) is ignored on all but first byte
        # character overrun error is reported as all '1's
        x = 0
        for rxd in raw_buff:
            try:
                # is the byte value in the Hamming 4 weight look up table?
                self._rx_buff[x] =  RailComRead._H4LU[rxd & 0xff]
                x += 1
            except KeyError:
                # no it's not!
                if (rxd & 0x200) != 0:
                    self._rx_buff[x] = RailComRead.ERR_OE
                else:
                    # work out if Hamming weight is high or low
                    self._rx_buff[x] = RailComRead.ERR_WH if bin(self._rx_buff[x & 0xff]).count('1') > 4 \
                        else RailComRead.ERR_WL
                x += 1
        # buffer now translated - parsing for channel specific info done in callback
        self._callback(memoryview(self._rx_buff)[:x], detector_side)
        return
