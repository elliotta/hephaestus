#!/usr/bin/env python
"""Read data in Innovate Serial Protocol version 2 (ISP2).

For data format specifications, see
http://www.innovatemotorsports.com/support/downloads/Seriallog-2.pdf
"""
import struct
import threading

import serial

import packet


class Isp2Serial(serial.Serial):
    def __init__(self, device):
        serial.Serial.__init__(self, device, baudrate=19200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=5)
        self.reply_lock = threading.Lock()
        self.reply = None

    def read_packet(self):
        '''Read a packet from the serial device.
        '''
        # Get the header first to determine the length of the packet
        p = packet.InnovatePacket(self.read(2))
        # Packet length is in words, and each word is 2 bytes
        p.data = self.read(p.packet_length * 2)
        return p

    def start_recording(self):
        '''Tell devices to start recording.

        There is no reply packet.
        '''
        self.send(b'R')

    def end_recording(self):
        '''Tell devices to stop recording.

        There is no reply packet.
        '''
        self.send(b'r')

    def erase_recording(self):
        '''Tell devices to erase recordings.

        There is no reply packet.
        '''
        self.send(b'e')

    def calibrate(self):
        '''Tell devices to run calibration, if applicable.

        There is no reply packet.
        '''
        self.send(b'c')

    def listen(self, device_name):
        '''Tell a particular device to list.

        The device will send a reply packet that contains the device name.
        '''
        if len(device_name) > 8:
            raise Exception('Device name cannot be longer than 8 characters')
        self.send(struct.pack('>H', 0xCC) + device_name.ljust(8, '0'))

    def unlisten(self):
        '''Stop listening.

        The device that was listening will send a reply packet that contains the command.
        '''
        self.send(struct.pack('>H', 0xEC))

    def namelist(self):
        '''Request a list of device names.

        Response will contain a list of names.
        '''
        self.send(struct.pack('>H', 0xCE))

    def typelist(self):
        '''Request a list of device types.

        Response will contain a list of types, 8 bytes per device.
        '''
        self.send(struct.pack('>H', 0xCE))


