"""One data packet in Innovate Serial Protocol version 2 (ISP2).

For data format specifications, see
http://www.innovatemotorsports.com/support/downloads/Seriallog-2.pdf
"""

import struct


class InnovatePacket(object):
    """An packet in the Innovate Serial Protocol version 2 (ISP2).

    ISP2 packets are composed of 16 bit words.
    """
    # Define some bitmasks
    START_MARKER_MASK = 0b1000000000000000
    # In a header word, bits 13, 9, and 7 will be 1.
    HEADER_MASK             = START_MARKER_MASK | 0b0010001010000000
    RECORDING_TO_FLASH_MASK = 0b0100000000000000 # In header. 1 is is recording.
    SENSOR_DATA_MASK        = 0b0001000000000000 # In header. 1 if data, 0 if reply to command.
    CAN_LOG_MASK            = 0b0000100000000000 # In header. 1 if originating device can do internal logging.

    LC1_HIGH_MASK           = 0b0100001000000000 # First of two words from an LC-1, bits always high
    LC1_LOW_MASK            = 0b1010000010000000 # First of two words from an LC-1, bits always low

    def __init__(self, header=None, data=None):
        self.header = header
        self.data = data

    def _to_words(self, bytestring):
        """Convert a byte string to a list of words.

        Each word is an integer.
        """
        if bytestring is None:
            return None
        # Each word is two bytes long
        n_words = len(bytestring)/2
        # ISP2 words are big endian, indicated by ">"
        # ISP2 words are unsigned short, indicated by "H"
        return struct.unpack(">%dH" % n_words, bytestring)

    @property
    def header(self):
        return self._header

    @header.setter
    def header(self, header):
        """Input header as a bytestring.
        """
        header = self._to_words(header)
        if len(header) != 1:
            raise Exception('Header must be exactly one word long.')
        header = header[0]
        if not header & self.HEADER_MASK == self.HEADER_MASK:
            raise Exception('Invalid header')
        self._header = header

    ## Data stored in the header ##

    @property
    def packet_length(self):
        """Get the packet length from the header.

        Packet length is the number of data words after the header.
        Note that each word is 2 bytes long.
        """
        if not self._header:
            return None
        # Packet length is encoded in bit 8 and bits 6-0
        # First, get bits 6-0
        packet_length = self._header[0] & 0b0000000001111111
        # Bit 8 is the 7th (zero-indexed) bit in the length
        if self._headeri[0] & 0b0000000100000000:
            packet_length += 0b10000000 # 128
        return packet_length

    @property
    def is_recording_to_flash(self):
        """Return boolean indicating whether the data is being recorded to flash.
        """
        if not self._header:
            return None
        return self.header & self.RECORDING_TO_FLASH_MASK == self.RECORDING_TO_FLASH_MASK

    @property
    def is_sensor_data(self):
        """Return True if the packet contains sensor data, False if it is a reply to a command.
        """
        if not self._header:
            return None
        return self.header & self.SENSOR_DATA_MASK == self.SENSOR_DATA_MASK

    @property
    def can_log(self):
        """Return boolean indicating whether the originating device can do internal logging.
        """
        if not self._header:
            return None
        return self.header & self.CAN_LOG_MASK == self.CAN_LOG_MASK

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        """Input data as a bytestring.
        """
        self._data = self._to_words(data)

