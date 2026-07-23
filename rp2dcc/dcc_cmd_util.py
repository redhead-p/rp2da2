"""DCC module utilities
    :author: Paul Redhead

This module contains classes for DCC command objects.


"""
"""        Copyright (C) 2023, 2024, 2025 Paul Redhead

        This program is free software: you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the Free Software Foundation, 
        either version 3 of the License, or (at your option) any later version.
        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
        See the GNU General Public License for more details.
        You should have received a copy of the GNU General Public License along with this program.
        If not, see <http://www.gnu.org/licenses/>.
"""

from micropython import const
import machine

import array



"""NMRA Standard S 9.2 (2004) Section C applies.
The time between packets addressed to the same decoder must exceed 5ms. This is the time the packet
end bit and the following packet start bit.

The period between complete packet transmission (start bit to start bit) must be less or equal to
30ms.
"""
_DCC_PREAMBLE =  const(0x0003FFFF)  # DCC preamble - 18 '1' bits (minumum 14 bits)
_DCC_PE1_CU =    const(0xC00001FF)  # packet end '1' bit & cutout (if used)

_SPD_128 = const(0x3f)              # 1st instruction byte for 128 speed packet
_F_GROUP_1 = const(0x80)            # instruction byte for Function group 1
_F_NUM_ENCODE = [0x10, 0x01, 0x02, 0x04, 0x08] # translate Group 1 function no. to mask

_IDLE_PACKET = bytes(b'\xff\x00')  # Address 255, instruction/data 0


class CommandPacket:
    """ DCC Commmand
    
    Base class for a DCC Command packet. This is created for a new command and updated when changed.
    It holds the raw command as required for serialisation by the PIO. The command can be upto 11 bytes
    inclusive of address bytes but not counting preamble, error check or packet end.

    The device driver for the PIO is a singleton class and it's assumed here that any variables held here
    specific to the PIO device driver may be held as class variables.
    

    Attributes:
        MAX_LONG_ADDR:  DCC long address upper limit (inclusive)
        MIN_LONG_ADDR:  DCC long address lower limit (inclusive)
        BASE_LONG_ADDR: DCC long mobile address range base
        NOT_SENT:   Return value for command not sent (command being updated)
        SENT:       Return value for command serialised
        SENT_POM:   Return valued for Program on Main second send
    """

    # class constants
    MAX_LONG_ADDR = const(0x27FF)      # DCC long address upper limit (inclusive)
    MIN_LONG_ADDR = const(128)         # DCC long address lower limit (inclusive)
    BASE_LONG_ADDR = const(0xc000)     # DCC long mobile address range base

    def __init__(self, byte_list = None):
        """ Contruct the DCC Command

        This method is not called automatically on object instantiation and is called
        explicitly by __init__ in the inheriting object.

        This builds the DCC Command. The supplied byte list is used to create the raw
        command as serialised by the PIO state machine. It is saved in a word
        array of sufficient size (max 8 32 bit words). The reference to 
        the PIO state machine is obtained when the first command object is built.

        Mobile traction commands etc. are created from the supplied byte list.

        POM commands are built as empty templates without a byte list.

        args:
            byte_list: a list of the component bytes.
        """

        # max buffer is 8 words - 2 (pre-amb + pe) - 1 byte (chksum) => command 11 bytes

        if byte_list is None:
            # set buffer to PIO FIFO max size
            # FIFO buffer is 8 32 bit words but 'I' not 'L'
            self._packet_buff = array.array('I', range(8))
        else:
            # set buffer according to supplied byte list
            buff_len = ((len(byte_list) + 2) // 2) + 2  # compute buffer length required
            if buff_len > 8:
                raise RuntimeError ('DCC command too long')
            self._packet_buff = array.array('I', range(buff_len))
            self.set_buffer(byte_list)

    def set_buffer(self, byte_list):
        """Set buffer contents

        This builds the raw command content as required by the PIO state machine. The preamble is
        prepended.  The checksum is calculated and appended, as is the packet end bit. The function
        is called by the constructor. It may also be called to update the command.
        
        It's not assumed that writing 0 to a word in the buffer is atomic. So setting the first word 
        (the preamble) to 0 is used as an indicator that the buffer is being updated and shouldn't be sent.
        Word 0 is reset to the preamble to indicate update over. IRQs are disabled when writing to word 0.

        We build the buffer here in 'slow time' rather than in ISR 'critical time'.

        args:
            byte_list: a list of the component bytes.
        """
        magic_no = machine.disable_irq()
        self._packet_buff[0] = 0 # flag buffer being updated to stop soft ISR sending it
        machine.enable_irq(magic_no)
        err_detect = 0  # initialise error detection checksum
        count = 2
        for b in byte_list:
            if (count & 1) == 0:
                self._packet_buff[count//2] = b << 9
            else:
                self._packet_buff[count//2] |= b
            err_detect ^= b
            count += 1
        if (count & 1) == 1:
            self._packet_buff[count//2] |= err_detect
        else:
            count += 1
            self._packet_buff[count//2] = err_detect | 0x80000000 # set single byte marker
        count += 1
        self._packet_buff[count//2] = _DCC_PE1_CU
        magic_no = machine.disable_irq()
        self._packet_buff[0] = _DCC_PREAMBLE    # release buffer for timer ISR
        machine.enable_irq(magic_no)

    def is_locked(self):
        """Is Locked

        Check to see if the command is locked by looking at the first
        word.  This will be pre-amble if unlocked or 0 if locked.
        
        returns: True if command is locked for editing"""
        return(not self._packet_buff[0])
    
    @property
    def packet_buffer(self):
        """Get the Packet Buffer
        
        This returns the packet as prepared for serialisation.
        It may be written as is to the PIO state machine FIFO."""
        return self._packet_buff
    
    @property
    def type(self):
        """Get the command type
        
        This returns the command type.  The type is set by the class object inheriting from 
        CommandPacket

        returns:
            command type
        """
        return self._type
    
    @property
    def address(self):
        """ Get Address
        
        This returns the decoder address targeted by the command

        returns:
            The decoder address as an integer
        """
        return self._address


class IdlePacket(CommandPacket):
    """ DCC Idle Packet 
    
    This requires no parameters to construct so only one is ever needed!

    Attributes:
        TYPE:   I - Idle Packet
    """
    TYPE = 'I'
    
    def __init__(self):
        """Construct the Idle Packet

        This constructs the Idle Packet. It calls __init__ in the base class. It sets
        the type and address. The address is the DCC broadcast address.
        """
        super().__init__(_IDLE_PACKET)
        self._type = IdlePacket.TYPE
        self._address = 255 # broadcast address
    
    
class SpeedCommand(CommandPacket):
    """ DCC Speed Command Packet
    
    Speed commands are built for specific DCC addresses and are retained on the packet list for 
    periodic transmission.  The speed and direction may be updated and this will rebuild the 
    packet, recalculating the checksum.
    
    attributes:
        TYPE:   S - Speed Command Packet
    """
    TYPE = 'S'

    def __init__(self, address, dir, speed):
        """Construct a  speed command

        This constructs a speed command. It calls __init__ in the base class. It sets
        the type, address, direction and speed. Direction and speed may be updated later.
        note:
            Parameters not validated here.

        args:
            address: DCC address of target decoder
            dir:    Direction (1:forward  or 0:reverse)
            speed:  Speed
        """
        inst_2 = (0x80 if dir == 1 else 0) | (speed & 0x7f)
        self._type = SpeedCommand.TYPE
        self._address = address

        if address < CommandPacket.MIN_LONG_ADDR:
            # short address - 1 byte, instruction 1, instruction 2
            self._byte_list = bytearray((address, _SPD_128, inst_2))
        else:
            # long address - 2 bytes, instruction 1, instruction 2
            msb_address = (CommandPacket.BASE_LONG_ADDR | address) >> 8
            self._byte_list = bytearray((msb_address, address & 0xff, _SPD_128, inst_2))

        super().__init__(self._byte_list)

    def update(self, dir, speed):
        """Update Speed Command
        
        This updates the speed command.  Speed and direction may be changed.

        note:
            Parameters not validated here.

        args:
            dir:    New direction (forward or reverse)
            speed:  New speed
        """
        # update last byte with new dir/speed 
        self._byte_list[-1] = (0x80 if dir == 1 else 0) | (speed & 0x7f)
        self.set_buffer(self._byte_list)


class FGrp1Command(CommandPacket):
    """ Function Group 1 Packet

    Function group 1 commands are built for specific DCC addresses and are retained on the packet list for 
    periodic transmission.  The function number and state may be updated.
    
    Attributes:
        TYPE:   F - Function Group 1 Command
    """
    TYPE = 'F'

    def __init__(self, address, f_num, state):
        """Construct a  Function Group 1 Command

        This constructs a function group one command. It calls __init__ in the base class. It sets
        the type, address, function number and function state. Function numbers and associated states 
        may be updated later.
        
        note:
            Parameters not validated here.

        args:
            address: DCC address of target decoder
            f_num:   The group 1 function number to be set or unset
            state:  may be set or unset (1 or 0)
        """
        self._address = address
        self._type = FGrp1Command.TYPE
        mask = _F_NUM_ENCODE[f_num]
        inst_1 = _F_GROUP_1 | (mask if state == 1 else 0)
        if address < CommandPacket.MIN_LONG_ADDR:
            # short address - 1 byte, instruction 1
            self._byte_list = bytearray((address, inst_1))
        else:
            # long address - 2 bytes, instruction 1
            msb_address = (CommandPacket.BASE_LONG_ADDR | address) >> 8
            self._byte_list = bytearray((msb_address, address & 0xff, inst_1))

        super().__init__(self._byte_list)

    def update(self, f_num, state):
        """Update Function Group 1 command
        
        Allows a function number in group 1 to be set or unset.

        args:
            f_num:   The group 1 function number to be set or unset
            state:  may be set or unset (1 or 0)
        """
        mask = _F_NUM_ENCODE[f_num]
        # get current intruction byte (it's at the end)
        inst_1 = self._byte_list[-1]
        # set or clear function bit
        self._byte_list[-1] = (inst_1 | mask) if state == 1 else  (inst_1 &  ~mask)
        self.set_buffer(self._byte_list)


class CV_Access(CommandPacket):
    """CV access - POM
    
    This is the CV Access Command - long form RCN-214 Section 2.
    Only one CV access conversation may take place concurrently.
    RailCom only - not service track or simplex Programming on Main.

    To read a single CV we can execute either of the check operations. In RailCom POM
    these both return the entire CV rather than the simple boolean service mode
    response. In practice we will use byte check for cv read.

    Objects in this class are single use.  I.e once the CV access is complete they may
    dropped for garbage collection.

    **TODO** Do we need to look at accessory CVs too?

    Attributes:
        BYTE_CHK: As specified in RCN-217 for read cv byte
        BYTE_WRT: As specified in RCN-217 for write cv byte
        BIT_MANIP: As specified in RCN-217 for write cv bit

        BIT_WRT: CV Bit Write
        BIT_CHK: CV BIT Check

        TYPE:   P - Programme on Main
    """
    BYTE_CHK = const(0xe4)  # As specified in RCN-217 for read cv byte
    BYTE_WRT = const(0xec)  # As specified in RCN-217 for write cv byte
    BIT_MANIP = const(0xe8) # As specified in RCN-217 for write cv bit

    BIT_WRT = const(0xf0)   # 1 << 4 | 0xe0
    BIT_CHK = const(0xe0)   # 0 << 4 | 0xe0


    TYPE = 'P'

    _CMD = {'r': BYTE_CHK,
            'w': BYTE_WRT}
    
    NOT_SENT = const(0)     # command not sent yet
    SENT_W1     = const(1)     # 1st POM write command sent
    SENT_POM = const(2)     # POM send complete (rd 1, write 2) - OK to delete.

    def __init__(self, address, cv, *, operation = 'r', value = 0):
        """Construct a  Program on Main Command

        This constructs a POM command. It calls __init__ in the base class. It sets the decoder address, 
        the CV number, the operation (read or write), and the new value.
        At the moment only single byte CV operations are supported.
        
        note:
            Parameters not validated here.

        args:
            address: DCC address of target decoder
            cv: CV number to read or write
            operation: read(r) or write(w)
            value:  new value for CV
        """        
        self._address = address
        self._type = CV_Access.TYPE
        self._operation = operation
        self._state = CV_Access.NOT_SENT
        self._cv = cv

        inst1 = CV_Access._CMD[operation] | ((cv >> 8) & 0x3)
        inst2 = cv & 0xff
        inst3 = value & 0xff

        if address < CommandPacket.MIN_LONG_ADDR:
            # short address - 1 byte, instruction 1, instruction 2
            self._byte_list = bytearray((address, inst1, inst2, inst3))
        else:
            # long address - 2 bytes, instruction 1, instruction 2
            msb_address = (CommandPacket.BASE_LONG_ADDR | address) >> 8
            self._byte_list = bytearray((msb_address, address & 0xff, inst1, inst2, inst3 ))

        super().__init__(self._byte_list)


    def all_sent(self):
        """ Update State after Send
        
        Process state according to operation (r or w)

        Should only need to send read once but TOM appears to need it twice!
        
        returns True if all POM sends done"""
        if self._state == CV_Access.NOT_SENT:
            self._state = CV_Access.SENT_W1
            return False
        if self._state == CV_Access.SENT_W1:
            self._state = CV_Access.SENT_POM
        return True



    def get_state(self):
        """Get the command state
        
        This returns the state of the most recent send or NOT_SENT.

        todo:
            Confirm that this is required. 

        returns:
            The send state of the command
        """
        return self._state
    
    def get_cv(self):
        """Get the CV number

        
        This returns the number of the CV being accessed. The primary purpose is
        allow the  Channel 2 response processor to determine which CV a returned 
        CV value relates to. 

        returns:
            The CV numver being accessed.
        """
        return self._cv
    