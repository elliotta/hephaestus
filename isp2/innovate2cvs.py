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


def main(device, output_directory=None, output_file_name=None, output_separator='\t', interval=1,
         log_short_interval=False, short_output_file=None, short_output_directory='/dev/shm', short_interval=60):
    '''Interval is in minutes. Short_interval is seconds.
    '''

    # Setup
    output_file = None
    if output_file_name and output_directory:
        output_file_name = os.path.join(output_directory, output_file_name)

    interval = datetime.timedelta(minutes=interval)
    short_interval = datetime.timedelta(seconds=short_interval)

    # Main function
    current_date = datetime.datetime.now().date()
    file_start_time = None # For logging hours since start of file
    interval_start_time = None
    short_interval_start_time = None
    averaged_data = None

    print('About to connect to serial device %s' % device)
    with isp2_serial.Isp2Serial(device) as ser:
        while True:
            try:
                p = ser.read_packet()
                if p.is_sensor_data():
                    # Note the time - this is a new entry
                    now = datetime.datetime.now()

                    # Parse the packet into a dictionary. Assume only a TC-4
                    aux_data = [p.aux_word2aux_channel(word) for word in p.data]

                    if not file_start_time:
                        file_start_time = now
                    if not interval_start_time:
                        interval_start_time = now
                    if not short_interval_start_time:
                        short_interval_start_time = now

                    if now - interval_start_time > interval:
                        # Write out old data
                        data_dict = OrderedDict([('timestamp', interval_start_time.strftime('%H:%M:%S')), ('hours', (interval_start_time-file_start_time).total_second()/3600.0)])
                        data_dict.update([('avg %i' % i, str(avg)) for i, avg in enumerate(averaged_data)])
                        data_dict.update([('aux %i b2' % i, format(aux, '016b')) for i, aux in enumerate(aux_data)])
                        data_dict.update([('aux %i b10' % i, str(aux)) for i, aux in enumerate(aux_data)])
                        # Write out the data
                        if not output_file or now.date() != current_date:
                            if output_file:
                                output_file.close()
                            print('Opening new output file')
                            current_date = datetime.datetime.now().date()
                            if not output_file_name:
                                output_file = get_output_file(get_output_filename(current_date, output_directory, output_separator), data_dict)
                            else:
                                output_file = get_output_file(output_file_name, data_dict)
                        output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')
                        # Set up for next loop
                        interval_start_time = now
                        averaged_data = aux_data
                        n_in_average = 1
                    else:
                        # Update the running average
                        if not averaged_data:
                            # This should only happen the first time through the loop
                            averaged_data = aux_data
                            n_in_average = 1
                        else:
                            averaged_data = [avg + (new - avg)/n_in_average  for avg, new in zip(averaged_data, aux_data)]

            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read an Innovate serial data sream')
    parser.add_argument('device', help='The USB device')
    parser.add_argument('-o', '--output_file', dest='output_file_name', help='File to write to. If no file is given, base on date.')
    parser.add_argument('-u', '--output_directory', help='Directory to write output to.')
    parser.add_argument('-n', '--interval', type=int, default=1, help='Interval to log, in minutes')
    parser.add_argument('-s', '--output_separator', default='\t', help='Separator for output file')
    group = parser.add_argument_group('short interval logging')
    group.add_argument('--log_short_interval', action='store_true', help='Additional log at shorter interval')
    group.add_argument('--short_output_file', help='File to write shorter intervales to')
    group.add_argument('--short_output_directory', default='/dev/shm', help='Directory to write short interval output to.')
    group.add_argument('--short_interval', type=int, default=60, help='Interval to log, in seconds')
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
                print('Pid from %s already running' % pidfile)
                sys.exit()
        # Create pid file
        f = open(pidfile, 'w')
        f.write('%i\n' % mypid)
        f.close()

    kwargs = vars(args)
    del kwargs['daemon']
    main( **kwargs)
