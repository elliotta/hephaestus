#!/usr/bin/env python
"""Read data in Innovate Serial Protocol version 2 (ISP2).

For data format specifications, see
http://www.innovatemotorsports.com/support/downloads/Seriallog-2.pdf
"""

import os
import sys
import datetime
from sys import stderr
import struct

import serial

# Define some constants for the ISP2
# Packets are organized by 16-bit words

START_MARKER = 0b1000000000000000
# If this is a header, bits 13, 9, and 7 will be 1. It will also be a (one word) section.
HEADER_WORD        = START_MARKER | 0b0010001010000000
RECORDING_TO_FLASH = 0b0100000000000000 # In header. 1 is is recording.
SENSOR_DATA        = 0b0001000000000000 # In header. 1 if data, 0 if reply to command.
DATA_HEADER_WORD   = HEADER_WORD | SENSOR_DATA # The stuff we want to log to a file.
CAN_LOG            = 0b0000100000000000 # In header. 1 if originating device can do internal logging.

LC1_HIGH           = 0b0100001000000000 # First of two words from an LC-1, bits always high
LC1_LOW            = 0b1010000010000000 # First of two words from an LC-1, bits always low

def get_packet_length(header_word):
    """Get the packet length from an ISP2 header word.

    Packet length is the number of data words after the header.
    Note that each word is 2 bytes long.
    """
    # Packet length is encoded in bit 8 and bits 6-0
    # First, get bits 6-0
    packet_length = header_word & 0b0000000001111111
    # Bit 8 is the 7th (zero-indexed) bit in the length
    if header_word & 0b0000000100000000:
        packet_length += 0b10000000 # 128
    return packet_length


def get_output_filename(current_date, output_directory):
    """Return the current file name based on the current_date.
    """
    return os.path.join(output_directory, current_date.strftime('%Y%m%d-postbox.tsv'))


def get_output_file(filename, data_dict, sep):
    """Create or open the output file.

    If a new file is being created, add a header line.
    """
    header_line = sep.join(data_dict.keys())
    if os.path.exists(filename) and not os.stat(filename).st_size == 0:
        # Check for a header line
        f_check = open(filename)
        if f_check.readline().strip() == header_line:
            # Headers match, we're good to go
            f_check.close()
            return open(filename, 'a', 1) # line buffered
        else:
            stderr.write('File %s has unexpected header line' % filename)
            sys.exit(1)
    else:
        # Is safe to overwrite an empty file
        f = open(filename, 'w', 1)  # line buffered
        f.write(header_line + '\n')
        return f


def main(output_directory=None, output_file_name=None):
    # Device Setup
    device = '/dev/tty.UC-232AC'
    baudrate = 19200
    parity=serial.PARITY_NONE
    stopbits=serial.STOPBITS_ONE

    # Output setup
    sep = '\t'

    # Setup
    data_dict = {} # This will get trashed; don't worry that it's not ordered
    output_file = None
    if output_file_name and output_directory:
        output_file_name = os.path.join(output_directory, output_file_name)

    # Main function
    current_date = datetime.datetime.now().date()

    print('About to connect to serial device %s' % device)
    with serial.Serial(device, baudrate=baudrate, parity=parity, stopbits=stopbits) as ser:
        while True:
            # First two Byes are the header word
            header = struct.unpack(">H", ser.read(2))[0] # Example string is '\xb2\x82'

            if not header & DATA_HEADER_WORD == DATA_HEADER_WORD:
                print('Expected header, got other data.')
                continue

            packet_length = get_packet_length(header) * 2 # Words are 2 bytes long

            data_packet = ser.read(packet_length) # Example is 'C\x13\x0b3', with 2 words

        """
        while True:
            try:
                line = ser.readline().strip()
                if line:
                    if line.startswith('V'):
                        # Note the time - this is a new entry
                        now = datetime.datetime.now()
                        # Write out the old data
                        if 'date' in data_dict:
                            if not output_file or now.date() != current_date:
                                if output_file:
                                    output_file.close()
                                print 'Opening new output file'
                                current_date = datetime.datetime.now().date()
                                if not output_file_name:
                                    output_file = get_output_file(get_output_filename(current_date, output_directory, sep), data_dict)
                                else:
                                    output_file = get_output_file(output_file_name, data_dict)
                            output_file.write(sep.join([str(x) for x in data_dict.values()]) + '\n')
                        # Start a new dict
                        data_dict = OrderedDict((('date', now.date()), ('time', now.time())))
                    try:
                        key, value = line.split()
                    except Exception:
                        if line.startswith('Checksum'):
                            # stderr.write('Error splitting checksum line\n')
                            pass
                        else:
                            stderr.write("Cannot split line\n")
                            stderr.write(line)
                        continue
                    data_dict[key] = value
            except KeyboardInterrupt:
                break
        """


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read an Innovate serial data sream')
    parser.add_argument('-o', '--output_file', help='File to write to')
    parser.add_argument('-u', '--output_directory', help='Directory to write output to. If no file is given, base on date')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    args = parser.parse_args()

    if args.daemon:
        # Pid file check
        pidfile = '/var/run/innovate.pid'
        mypid = os.getpid()
        if os.path.exists(pidfile):
            f = open(pidfile)
            old_pid = int(f.readline().strip())
            f.close()
            if os.path.exists('/proc/%i' % old_pid):
                print 'Pid from %s already running' % pidfile
                sys.exit()
        # Create pid file
        f = open(pidfile, 'w')
        f.write('%i\n' % mypid)
        f.close()

    main(output_file_name=args.output_file, output_directory=args.output_directory)
