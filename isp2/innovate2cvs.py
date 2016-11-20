#!/usr/bin/env python
"""Read data in Innovate Serial Protocol version 2 (ISP2).

For data format specifications, see
http://www.innovatemotorsports.com/support/downloads/Seriallog-2.pdf
"""

import os
import sys
import datetime
from sys import stderr
from collections import OrderedDict
import isp2_serial 


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


def main(device, output_directory=None, output_file_name=None, output_separator='\t'):
    # Setup
    output_file = None
    if output_file_name and output_directory:
        output_file_name = os.path.join(output_directory, output_file_name)

    # Main function
    current_date = datetime.datetime.now().date()

    print('About to connect to serial device %s' % device)
    with isp2_serial.Isp2Socket(device) as ser:
        while True:
            try:
                p = ser.read_packet()
                if p.is_sensor_data():
                    # Note the time - this is a new entry
                    now = datetime.datetime.now()
                    # Parse the packet into a dictionary. Assume only a TC-4
                    data_dict = OrderedDict([('word %i' % i, word) for i, word in enumerate(p.data)])
                    # Write out the data
                    if not output_file or now.date() != current_date:
                        if output_file:
                            output_file.close()
                        print 'Opening new output file'
                        current_date = datetime.datetime.now().date()
                        if not output_file_name:
                            output_file = get_output_file(get_output_filename(current_date, output_directory, output_separator), data_dict)
                        else:
                            output_file = get_output_file(output_file_name, data_dict)
                    output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')
            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read an Innovate serial data sream')
    parser.add_argument('device', help='The USB device')
    parser.add_argument('-o', '--output_file', help='File to write to')
    parser.add_argument('-u', '--output_directory', help='Directory to write output to. If no file is given, base on date')
    parser.add_argument('-s', '--output_separator', default='\t', help='Separator for output file')
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

    main(args.device, output_file_name=args.output_file, output_directory=args.output_directory, output_separator=args.output_separator)
