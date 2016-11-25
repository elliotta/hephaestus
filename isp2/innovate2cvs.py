#!/usr/bin/env python
import os
import sys
import datetime
from sys import stderr
from collections import OrderedDict
import isp2_serial 


class Tc4DataWriter(object):
    """Write data to disk, and manage file rollover and cleanup.
    """

    def __init__(self, filename_format='%Y%m%d-tc4.tsv', output_directory='', separator='/t'):
        self.filename_format = filename_format
        self.output_directory = output_directory
        self.separator = separator
        self.current_file = None
        self.current_file_time = None

    def get_output_file(self, timestamp, header):
        """Create or open the output file.

        If a new file is being created, add a header line.
        """
        filename = os.path.join(self.output_directory, data_dict['timestamp'].strftime(self.filename_format))
        header_line = self.separator.join(data_dict.keys())
        if os.path.exists(filename) and not os.stat(filename).st_size == 0:
            # Check for a header line
            f_check = open(filename) # read only
            if f_check.readline().strip() == header_line:
                # Headers match, we're good to go
                f_check.close()
                self.current_file = open(filename, 'a', 1) # line buffered
            else:
                stderr.write('File %s has unexpected header line' % filename)
                sys.exit(1)
        else:
            # Is safe to overwrite an empty file
            self.current_file = open(filename, 'w', 1)  # line buffered
            self.current_file.write(header_line + '\n')
        self.output_file_time = timestamp

    def rollover(self, timestamp):
        """Check if this data needs to go into a new file.
        """
        return self.output_file_time.date() != timestamp.date()

    def write(self, timestamp, data_dict):
        if not self.output_file or self.rollover(timestamp):
            self.get_output_file(timestamp, self.assemble_line(timestamp, data_dict, header=True))
        self.output_file.write(self.assemble_line(timestamp, data_dict))

    def assemble_line(self, timestamp, data_dict, header=False):
        '''Do the data cruching here.
        '''
        line_elements = []
        if header:
            line_elements.append('timestamp')
            line_elements.append('hours')
        else:
            line_elements.append(timestamp.strftime('%H:%M:%S'))
            line_elements.append(format((timestamp-self.output_file_time).total_seconds()/3600.0, '06.3f'))
        if header:
            line_elements += [str(x) for x in data_dict.keys()]
        else:
            line_elements += [str(x) for x in data_dict.values()]
        return self.separator.join(line_elements) + '\n'


class ShortIntervalDataWriter(Tc4DataWriter):
    '''Short interval files have a slightly different data format.
    '''

    def __init__(self, filename_format='%Y%m%d-short_interval_tc4.tsv', *args, **kwargs):
        Tc4DataWriter.__init__(self, filename_format=filename_format, *args, **kwargs)

    def rollover(self, timestamp):
        """Check if this data needs to go into a new file.
        """
        return self.output_file_time.date() != timestamp.date()

    def assemble_line(self, timestamp, data_dict, header=False):
        '''Do the data cruching here.
        '''
        line_elements = []
        if header:
            line_elements.append('timestamp')
            line_elements.append('hours')
        else:
            line_elements.append(timestamp.strftime('%H:%M:%S'))
            line_elements.append(format((timestamp-self.output_file_time).total_seconds()/3600.0, '07.4f'))
        if header:
            line_elements += [str(x) for x in data_dict.keys()]
        else:
            line_elements += [str(x) for x in data_dict.values()]
        return self.separator.join(line_elements) + '\n'

def main(device, output_directory=None, output_separator='\t', interval=1,
         log_short_interval=False, short_output_directory='/dev/shm', short_interval=60, verbose=False):
    '''Interval is in minutes. Short_interval is seconds.
    '''

    # Setup
    output_file =  Tc4DataWriter(output_directory=output_directory, separator=output_separator)
    short_output_file = ShortIntervalDataWriter(output_directory=short_output_directory, separator=output_separator)

    interval = datetime.timedelta(minutes=interval)
    short_interval = datetime.timedelta(seconds=short_interval)

    # Main function
    interval_start_time = None
    short_interval_start_time = None
    averaged_data = None
    short_interval_averaged_data = None

    print('About to connect to serial device %s' % device)
    with isp2_serial.Isp2Serial(device) as ser:
        while True:
            try:
                p = ser.read_packet()
                if p.is_sensor_data:
                    # Note the time - this is a new entry
                    now = datetime.datetime.now()

                    # Parse the packet into a dictionary. Assume only a TC-4
                    aux_data = [p.aux_word2aux_channel(word) for word in p.data]
                    if verbose:
                        print(now.isoformat() + ' ' + ', '.join([str(x) for x in aux_data]))

                    if not interval_start_time:
                        interval_start_time = now
                    if not short_interval_start_time:
                        short_interval_start_time = now

                    if now - interval_start_time > interval:
                        # Write out old data
                        data_dict = OrderedDict([('chan %i' % (i+1), str(avg)) for i, avg in enumerate(averaged_data)])
                        output_file.write(interval_start_time, data_dict)
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

                    if log_short_interval:
                        if now - short_interval_start_time > short_interval:
                            # Write out old data
                            data_dict = OrderedDict([('chan %i' % (i+1), str(avg)) for i, avg in enumerate(short_interval_averaged_data)])
                            short_output_file.write(short_interval_start_time, data_dict)
                            # Set up for next loop
                            short_interval_start_time = now
                            short_interval_averaged_data = aux_data
                            n_in_short_interval_average = 1
                        else:
                            # Update the running average
                            if not short_interval_averaged_data:
                                # This should only happen the first time through the loop
                                short_interval_averaged_data = aux_data
                                short_interval_n_in_average = 1
                            else:
                                short_interval_averaged_data = [avg + (new - avg)/short_interval_n_in_average  for avg, new in zip(short_interval_averaged_data, aux_data)]

            except KeyboardInterrupt:
                break


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read an Innovate serial data sream')
    parser.add_argument('device', help='The USB device')
    parser.add_argument('-u', '--output_directory', help='Directory to write output to.')
    parser.add_argument('-n', '--interval', type=int, default=1, help='Interval to log, in integer minutes')
    parser.add_argument('-s', '--output_separator', default='\t', help='Separator for output file')
    group = parser.add_argument_group('short interval logging')
    group.add_argument('--log_short_interval', action='store_true', help='Additional log at shorter interval')
    group.add_argument('--short_output_directory', default='/dev/shm', help='Directory to write short interval output to.')
    group.add_argument('--short_interval', type=int, default=15, help='Interval to log, in integer seconds')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each data point to stdout')
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
