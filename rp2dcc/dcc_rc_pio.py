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

from machine import mem32, disable_irq, enable_irq

from micropython import const, schedule
import array
import rp2

from device import Device

# module constants - not for importing elsewhere
_PIO_CU_FREQ = const(250_000)           # 250 kHz - 4 micro sec. tick period for command stn. cutout timing
_PIO_CU_D_FREQ = const(500_000)         # 500 kHz - 2 micro sec. tick period for block detect cu timing
_PIO_RX_FREQ = const(4_000_000)         # 4MHz - 16 * 250kHz bps rx clock rate for async. rx


class RailComRead(Device):
    """ The RailCom Reader class
    
    This class schedules and executes RailCom datagram read activities during the cutout period. During
    the cutout period, the DCC power signal is ceased and the two DCC lines are short circuited allowing the 
    RailCom current signal to be generated and detected. On the command station the cutout is instigated by the
    enable signal to the DRV8874 being set low. This cutout signal being low is used directly when detecting
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
    RailCom message receiver. Both state machines need to be on the same PIO block for RP2040 and
    are assigned to consecutive state machine numbers.
    
    A PIO block has 4 state machines and can run two readers. The 
    The cutout timers will be on the state machine numbers 0 & 2 of the PIO block and the associated receivers on state machine
    numbers 1 & 3. (Note that MicroPython numbers all state machines sequentially from 0 - e.g. it refers to the first 
    state machine on the second PIO as no. 4.)

    The cutout state machine starts the RailCom receiver using an IRQ. Relative IRQ numbering 
    is used. The first is no 5 which will be used by sm 0. The sm 2 will use IRQ 7.

    At the end of the channel window the PIO raises an application interrupt to initate reading the state machine
    FIFO buffer.


    Attributes:
        ACK: acknowledgement from decoder (may be used as padding)
        RES:  reserved
        NAK: negative acknowledgement from decoder (may follow ACK!)
        IMP_ACK: no explicit ACK but datagram received (implicit ACK)
        ERR_WH: raw data byte not valid Hamming 4 weight - weight high
        ERR_WL: raw data byte not valid Hamming 4 weight - weight low
        ERR_OE: Overrun error (no valid stop bit)
        ERR_CB: Unexpected Control Byte (within datagram body)
        ERR_ID: Invalid datagram id
        ERR_FE: datagram format error (incomplete)
        ERR_PL: Payload content validation error
        ERR_RESP: unable to associate ch2 response with command
        DG_RESP: internally generated datagram containing protocol control byte
        LCL_DEVICE_TYPE: Local block detector device type
        GBL_DEVICE_TYPE: Global detector device type
    """
    # class constant

    # protocol bytes - only applicable to Channel 2
    # these are internal values post Hamming W4 translation
    # bit 7 set to differentiate from datagram value 6 bit translation
    ACK =  const(0x80)
    RES =  const(0x82)
    NAK =  const(0x83)
    # locally interpreted responses
    ERR_WH = const(0x84)
    ERR_OE = const(0x85)
    ERR_WL = const(0x86)
    # other available response codes (used elsewhere)
    IMP_ACK = const(0x87)
    ERR_RESP = const(0x88)
    ERR_CB = const(0x89)
    ERR_ID = const(0x8A)
    ERR_FE = const(0x8B)
    ERR_PL = const(0x8C)

    PROT_BYTE = (ACK, NAK, RES)

    LCL_DEVICE_TYPE = const('l')
    GBL_DEVICE_TYPE = const('g')
    
    # datagram IDs (incomplete at present) - ID's are 6 bits 
    # IDs >= 64 are internally generated datagrams
    DG_RESP = const(0x40) # protocol control byte

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
    0x0F:ACK, 0xF0:ACK, 0xE1:RES, 0xC3:RES, 0x87:RES, 0x3C:NAK
    }
    """ Hamming Look Up Table

    This translates the received Hamming 4 weighted byte back to the six bit group from
    the original datagram or one of the 6 special values. Applicable to Ch1 & Ch2.
    N.B. the 6 special values are not valid for Ch1.

    See RCN-217 2.5.
    """

    @staticmethod
    def hw4_2_6b(rawd):
        """Translate Hamming weight 4 byte to 6 bit

        This translates the raw data byte as deserialised back to the
        6 bit datagram component value or protocol control character.
        Two errors are possible. The raw value signifies an overrun error
        or the Hamming weight is not 4.
        
        args:
            rawd: Hamming Weight 4 byte input

        returns:
            the translated 6 bit value, control byte or error code.
        """
        try:
            # is the byte value in the Hamming 4 weight look up table?
            return(RailComRead._H4LU[rawd & 0xff])
        except KeyError:
            # no it's not! overrun or Hamming W != 4
            if rawd & 0x200:
                return(RailComRead.ERR_OE)
        
            # work out if Hamming weight is high or low
            if bin(rawd & 0xff).count('1') > 4:
                return(RailComRead.ERR_WH)
                    
            return(RailComRead.ERR_WL)    

    def __init__(self, dev_name, cu_sm_num, rc_rx_pin, *, cu_pin = None, dcc_pin = None):
        """ RailCom class constructor

        Constructs a reader for Channel 1 (local block detector) or Channel 2 (global detector) using two PIO state machines.

        The cutout monitor state machine runs on the supplied state machine number.  The receive state machine
        runs on the number + 1.

        1 and only 1 of cu_pin or dcc_pin must be specified. If dcc_pin is specified, this is the DCC sense pin on a local
        detector. If cu_pin is specified this is the DRV8874 enable pin. Depending on which pin is specified a local or
        global detector is constructed.

        N.B the pins work in opposite senses. DRV8874 enable is low during the cutout.
        The DCC power on pin is high during the cutout!

        args:
            dev_name: for channel 1 this will be the block name
            cu_sm_num: state machine number for cut out scheduling - 4 or 6 if using the second PIO block
            rc_rx_pin: the detector output pin (pin + 1 is the orientation detect pin)
            cu_pin: cutout indicator (global detector)
            dcc_pin: DCC sense (track power on or off - local detector)
        """
        assert cu_pin is not None or dcc_pin is not None, "cu or dcc pin must be provided"
        # set up cutout detect PIO state machine 
        if dcc_pin is not None:
            # channel 1 - local block detection
            self._max_buf = 2
            self._sm = rp2.StateMachine(cu_sm_num, self._cut_out1_bd,
                                            freq = _PIO_CU_D_FREQ,
                                            in_base = dcc_pin,
                                            jmp_pin = dcc_pin)
            self._rx = self._rx_lcl
        else:
            # Channel 2 on command station
            self._max_buf = 6
            self._sm = rp2.StateMachine(cu_sm_num, self._cut_out2,
                                        freq = _PIO_CU_FREQ,
                                        in_base = cu_pin)
            self._rx = self._rx_gbl
        
        self._sm.irq(self._read_isr, hard = True) # read from the state machine at the end of the cutout

        # set up RailCom read PIO state machine
        self._smrx = rp2.StateMachine(cu_sm_num + 1, self._rx,
                                      freq = _PIO_RX_FREQ,
                                      in_base = rc_rx_pin,
                                      jmp_pin = rc_rx_pin)
        
        self._read_ref = self._read_soft # set up reference for use by hard isr

        self._rx_buff = bytearray(6) # translated buffer - max is 6 bytes for channel 2
        self._rx_raw = array.array('H', range(8)) # raw buffer for PIO - 8 words to match FIFO
        self._gash = array.array('H', (0,))
        self._ql = False            # queue lock - to protect against race
        # soft reset might not do this so:
        while self._smrx.rx_fifo() > 0:
            self._smrx.get(self._gash)
        self._smrx.restart()
        self._sm.active(True)       # start both state machines
        self._smrx.active(True)
        super().__init__(dev_name,
                       RailComRead.LCL_DEVICE_TYPE if cu_pin is None else RailComRead.GBL_DEVICE_TYPE)

    def _rail_com_msg(self, buffer):
        """ Process the RailCom Response
        
        This must be overriden by a bound method in the inheriting class.
        
        Raises:
            NotImplemented error if not overriden
        """
        raise NotImplementedError # must be overriden
        

    @rp2.asm_pio() 
    def _cut_out1_bd():
        """ The Cutout state machine monitor program (channel1 / block detect)

        This version is for use on a pico in use as an RailCom block detector.
        The cutout is detected by monitoring the DCC power on the track. This
        enables reading during the channel 1 window. The cutout timings in µs:

        0 - Packet end trailing edge
        28 - cutout start (monitored here)
        28 + 47  = 75  - enable receiver for ch1
        28 + 152 = 180 - disable receiver for ch1 (ch1 end @ 177, ch2 start 193)
        28 + 446 = 474 cutout ends (timed in DCCGen)

        The clock is 500 kHz. 2 µs per tick
        7 instructions

        Once the read ISR is triggered the program freezes until reset and restarted by
        the parent application.
        """
        wait(0, pin, 0)     [0]        # if power off wait for power on to ensure clean start
        wrap_target()
        wait(1, pin, 0)     [22]       # wait power off then reconfirm
        jmp(pin, "cu_conf") [1]        # power still off + 2 µs
        wrap()                         # reverted back to power_on if < 44µs (too short for cutout)

        # cutout start confirmed
        label("cu_conf")
        # break > 44 µs - potential cutout start - treat as such
        # now 46 µs after cu start - PEB + 72 to + 78 µs
        irq(rel(5))         [31] # start of ch1 window - release the datagram receiver 
        nop()               [20] # ch1 end 
        # PEB + 178 to 184 µs - ch1 end is PEB +177
        irq(rel(0))         [0] # end of channel 1 window - initiate read
        label("freeze")
        jmp("freeze")       [0]  # wait to be restarted to avoid race
    
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

        7 instructions used -   main loop 117 ticks total
        """
        
        wrap_target()
        # wait for cutout - enable pin false!
        wait(0, pin, 0)     [31] # then delay 38 ticks from cutout start (152µs)
        nop()               [5]
        irq(rel(5))         [31] # start of ch2 window - release the datagram receiver
        nop()               [31] # delay 70 ticks (280µs, 460µs so far from PE trailing edge)
        nop()               [5]
        # raise application interrupt to read what's there
        irq(rel(0))         [7]  # and then wait to allow enable pin to be asserted (>488µs)
        wait(1, pin, 0)     [0]
        wrap()                 

    @rp2.asm_pio(
                 in_shiftdir = rp2.PIO.SHIFT_RIGHT,           # lsb first so shift right
                 out_shiftdir = rp2.PIO.SHIFT_RIGHT,
                 fifo_join = rp2.PIO.JOIN_RX)                # no tx so both fifos for rx
    def _rx_lcl():
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

        The osr is used as an additional register.  It's not in use for transmission.

        The state machine clock is set at 16 x the bit rate. (4 MHz)

        There's no programatic way back to the first instruction within the PIO program.  The
        state machine is restarted by the controlling application externally forcing a reset.

        Reading is stopped if an overrun error occurs.

        17 instructions
        """
        wait(1, irq, rel(4))    [0] # wait to be enabled
        wrap_target()               # restart calculated on basis that this labels 2nd instruction

        label("await_start")
        # we want a confirmed start bit to be at least 3/4 bit time 
        # so we sample it 6 times following the initial edge
        set(y,5)                [0]       
        wait(0, pin, 0)         [0] # wait for start bit leading edge - 2 ticks between samples
        mov(osr, pins)          [0] # get start bit ('0') and orientation
        label("spin")
        jmp(pin,"await_start")  [0] # back to '1', not long enough for start bit
        jmp(y_dec, "spin")      [0] # spin for next sample

        label("start_ok")
        out(y,1)                [0] # shift out start bit  & discard leaving orientation in osr
        set(y, 7)               [8] # 11 ticks in total from last sample to mid 1st bit.
                                    # y set to count 8 bits
        label("next_bit")
        in_(pins,1)             [0] # read next bit into isr
        jmp(y_dec,"next_bit")   [14] # wait 15 more ticks - 16 ticks in total  
        jmp(pin,"stop_ok")      [0] # if all data bits read check stop bit
        mov(isr, invert(null))  [0] # clear the isr - to all '1's for overrun
        push(noblock)           [0] # and save isr to rx FIFO
        label("freeze")
        jmp("freeze")           [0] # lock after overrun pending external reset

        label("stop_ok")            # stop bit OK
        in_(osr,1)              [0] # shift orientation bit into isr
        in_(null, 23)           [0] # shift all bits to l.s. end of isr
        push(noblock)           [0] # and save isr to rx FIFO - data lost if FIFO overrun
        wrap()                      # wait for next start bit


    @rp2.asm_pio(
                 in_shiftdir = rp2.PIO.SHIFT_RIGHT,           # lsb first so shift right
                 out_shiftdir = rp2.PIO.SHIFT_RIGHT,
                 fifo_join = rp2.PIO.JOIN_RX)                # no tx so both fifos for rx
    def _rx_gbl():
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
        
        A second input pin is not  used to determine the orientation and the code
        does not process it, thereby saving 3 instructions when compared with the local
        version. In other respects the code is identical.

        The state machine clock is set at 16 x the bit rate. (4 MHz)

        There's no programatic way back to the first instruction within the PIO program.  The
        state machine is restarted by the controlling application externally forcing execution
        of a jump to the first instruction.

        Reading is stopped if an overrun error occurs.

        14 instructions
        """
        wait(1, irq, rel(4))    [0] # wait to be enabled
        wrap_target()               # restart calculated on basis that this labels 2nd instruction

        label("await_start")
        # we want a confirmed start bit to be at least 3/4 bit time 
        # so we sample it 6 times following the initial edge
        set(y,5)                [0]       
        wait(0, pin, 0)         [0] # wait for start bit leading edge - 2 ticks between samples
        label("spin")
        jmp(pin,"await_start")  [0] # back to '1', not long enough for start bit
        jmp(y_dec, "spin")      [0] # spin for next sample

        label("start_ok")
        set(y, 7)               [8] # 11 ticks in total from last sample to mid 1st bit.

        label("next_bit")
        in_(pins,1)             [0] # read next bit into isr
        jmp(y_dec,"next_bit")   [14] # wait 15 more ticks - 16 ticks in total  
        jmp(pin,"stop_ok")      [0] # if all data bits read check stop bit
        mov(isr, invert(null))  [0] # clear the isr - to all '1's for overrun
        push(noblock)           [0] # and save isr to rx FIFO
        label("freeze")
        jmp("freeze")           [0] # lock after overrun pending external reset

        label("stop_ok")            # stop bit OK
        in_(null, 24)           [0] # shift all bits to l.s. end of isr
        push(noblock)           [0] # and save isr to rx FIFO - data lost if FIFO overrun
        wrap()                      # wait for next start bit

    def _read_isr(self, _):
        """Hard ISR to ensure restart asap after window end"""
        self._smrx.active(0)    # stop the sm reading any stray bytes
        self._sm.active(0)      # stop the cutout monitor (it's frozen)
        self._sm.restart()      # and reset it to unfreeze
        rc = self._smrx.rx_fifo()      # get the count
        if rc and not self._ql: # not blank read and not locked
            self._ql = True  # set lock to stop race condition
            schedule(self._read_ref,(rc)) # use preset indirection to avoid new heap usage
            return
        # blank read or locked (previous read still being processed)
        while self._smrx.rx_fifo() > 0:
            self._smrx.get(self._gash) # flush buffer
        self._smrx.restart()    # reset sm including instruction pointer
        self._smrx.active(1)    # restart - it will wait for interrupt
        self._sm.active(1)      # and restart the monitor
        
    def _read_soft(self, rxc):
        """Soft PIO read ISR
        
        Read PIO FIFO into buffer.  Needs to be soft for memoryviews to  work
        Common to both channel 1 & 2.

        The raw buffer is in words - bits 0 - 7 data byte as received
        bit 8 (the orientation bit)
        overrun error is reported as all '1's

        There must be at least 1 entry in the buffer.
        
        args:
            rxc: received buffer count 
        """
        # set raw_buff limit to amount in fifo otherwise read will hang
        raw_buff = memoryview(self._rx_raw)[:rxc]
        self._smrx.get(raw_buff)  # read data into raw buffer
        self._smrx.restart() # reset internals (inc. IP)
        self._smrx.active(1)    # restart sm (it's now been reset)
        self._sm.active(1)      # and restart monitor

        if rxc > self._max_buf:
            # quietly truncate the buffer if over channel len
            raw_buff = raw_buff[:self._max_buf]
        # call channel specific code
        self._rail_com_msg(raw_buff)
        m = disable_irq()
        self._ql = False # allow next read to be decoded
        enable_irq(m)
        return
