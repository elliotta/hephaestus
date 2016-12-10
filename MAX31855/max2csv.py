#!/usr/bin/env python
"""Read data from an Adafruit MAX31855.
After a testing reading out at 10Hz, it was determined that the temperatures
  returned by this board are stable enough that the current data point is
  sufficient, and averaging multiple data points is unnecessary.

This code requires https://github.com/adafruit/Adafruit_Python_MAX31855

Other documentation:
https://learn.adafruit.com/max31855-thermocouple-python-library?view=all
https://learn.adafruit.com/calibrating-sensors/maxim-31855-linearization
https://learn.adafruit.com/thermocouple/f-dot-a-q
"""

import os
import sys
import datetime
from sys import stderr
from collections import OrderedDict
from math import exp
import time
import subprocess

import Adafruit_GPIO.SPI as SPI
import Adafruit_MAX31855.MAX31855 as MAX31855


# Raspberry Pi software SPI configuration.
# All sensors will share CLK and DO, with separate CS for each sensor
CLK = 24
DO  = 25
CS  = [23, 18, 22, 17]
SENSOR_NAMES = ['Firebox', 'Cat', 'Stove Top', 'Flue']


def c_to_f(c):
    '''Convert Celcius temperature to Farenheit.
    '''
    return c * 9.0 / 5.0 + 32.0


def get_output_file(filename, data_dict, sep):
    """Create or open the output file.

    If a new file is being created, add a header line.
    """
    header_line = sep.join(data_dict.keys())
    x = 1
    while True:
        # Loop will break at a return statement
        if os.path.exists(filename) and not os.stat(filename).st_size == 0:
            # Check for a header line
            f_check = open(filename)
            if f_check.readline().strip() == header_line:
                # Headers match, we're good to go
                f_check.close()
                return open(filename, 'a', 1) # line buffered
            else:
                stderr.write('File %s has unexpected header line\n' % filename)
                x += 1
                if x == 2:
                    # only do this the first time, otherwise file will be foo-2-3-4.log!
                    base, extension = os.path.splitext(filename) 
                filename = base + '-' + str(x) + extension
                # The next loop will try with this new filename
        else:
            # Is safe to overwrite an empty file
            f = open(filename, 'w', 1)  # line buffered
            f.write(header_line + '\n')
            return f


def main(web_output_file, interval, web_server_port, verbose,
         log_interval, output_file_pattern, output_separator,
         log_short_interval, short_interval, short_output_file_pattern):
    '''Interval is in minutes. Short_interval is seconds.
    '''

    # Hardware configuration is set at top of file
    global CLK, DO, CS

    # Setup
    output_file = None
    log_interval = datetime.timedelta(minutes=log_interval)
    file_start_time = None # For logging hours since start of file
    interval_start_time = None
    web_server = subprocess.Popen(['python', '-m', 'SimpleHTTPServer', str(web_server_port)], cwd=os.path.dirname(web_output_file))

    if log_short_interval:
	    short_output_file = None
	    short_interval = datetime.timedelta(seconds=short_interval)
	    short_file_start_time = None # For logging hours since start of file
	    short_interval_start_time = None

    print('About to connect to %i sensors' % len(CS))
    sensors = [MAX31855.MAX31855(CLK, this_CS, DO) for this_CS in CS]
    print('Sensors connected')
    while True:
        try:
            # Collect the data
            temps = [sensor.readAll() for sensor in sensors]
            for t in temps:
                for k in t.keys():
                    if k != 'state':
                        t[k] = c_to_f(t[k])
            now = datetime.datetime.now()

            # Stdout output
            if verbose:
                print(now.isoformat() + ' ' + '; '.join(['%.2f,%.2f,%.2f' % (t['temp'], t['internal'], t['linearized']) for t in temps]))

            # Html output
            # Always overwrite current file
            with open(web_output_file, 'w') as web_file:
                web_file.write('<html><head><meta http-equiv="refresh" content="1"><title>Current Temps</title></head><body><h1>%s<br><<%s></h1></body></html>' % ('<br>'.join(['%s: %.1f F (%.1f sensor, %.1f internal)' % (name, t['linearized'], t['temp'], t['internal']) for name, t in zip(SENSOR_NAMES, temps)]), now.isoformat()))

            # Log file output
            if not interval_start_time:
                interval_start_time = now
            if log_short_interval:
                if not short_interval_start_time:
                    short_interval_start_time = now

            if (not file_start_time) or (now - interval_start_time >= log_interval):
                if not file_start_time:
                    file_start_time = now
                # Assemble data dictionary
                data_dict = OrderedDict([('timestamp', now.strftime('%H:%M:%S')), ('hours', format((now-file_start_time).total_seconds()/3600.0, '06.3f'))])
                data_dict.update([('%s F' % name, format(t['linearized'], '.2f')) for name, t in zip(SENSOR_NAMES, temps)])
                data_dict.update([('raw %s F' % name, format(t['temp'], '.2f')) for name, t in zip(SENSOR_NAMES, temps)])
                data_dict.update([('internal %s F' % name, format(t['internal'], '.2f')) for name, t in zip(SENSOR_NAMES, temps)])
                # Write out the data
                if not output_file or now.date() != current_date:
                    if output_file:
                        output_file.close()
                    print('Opening new output file')
                    current_date = datetime.datetime.now().date()
                    output_file = get_output_file(current_date.strftime(output_file_pattern), data_dict, output_separator)
                output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')
                interval_start_time = now

            if log_short_interval:
                if (not short_file_start_time) or (now - short_interval_start_time >=short_interval):
                    if not short_file_start_time:
                        short_file_start_time = now
                    # Assemble data dictionary
                    data_dict = OrderedDict([('timestamp', now.strftime('%H:%M:%S')), ('hours', format((now-short_file_start_time).total_seconds()/3600.0, '07.4f'))])
                    data_dict.update([('%s F' % name, format(t['linearized'], '.2f')) for name, t in zip(SENSOR_NAMES, temps)])
                    # Write out the data
                    if not short_output_file or now.date() != current_date:
                        if short_output_file:
                            short_output_file.close()
                        print('Opening new short output file')
                        current_date = datetime.datetime.now().date()
                        short_output_file = get_output_file(current_date.strftime(short_log_file_pattern), data_dict, output_separator)
                    short_output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')
                    short_interval_start_time = now

            time.sleep(interval - time.time() % interval) # corrects for drift

        except KeyboardInterrupt:
            break

    web_server.terminate() # Cleanup


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read data from MAX31855 sensors', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-w', '--web_output_file', default='/dev/shm/current_temp.html', help='Html output file')
    parser.add_argument('-i', '--interval', default=1, help='Seconds at which to update the web_output_file')
    parser.add_argument('-p', '--web_server_port', default=8080, type=int, help='Web server port for displaying web_output_file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each data point to stdout')
    parser.add_argument('-o', '--output_file_pattern', default='%Y%m%d-temps.tsv', help='Output file name based on date')
    parser.add_argument('-l', '--log_interval', type=int, default=1, help='Interval to log, in integer minutes')
    parser.add_argument('-s', '--output_separator', default='\t', help='Separator for output file(s)')
    group = parser.add_argument_group('short interval logging')
    group.add_argument('--log_short_interval', action='store_true', help='Additional log at shorter interval')
    group.add_argument('--short_output_file_pattern', default='/dev/shm/%Y%m%d-short_interval.tsv', help='File to write shorter intervales to')
    group.add_argument('--short_interval', type=int, default=15, help='Interval to log, in integer seconds')
    parser.add_argument('-d', '--daemon', action='store_true', help='Run as a daemon')
    args = parser.parse_args()

    if args.daemon:
        # Pid file check
        #pidfile = '/var/run/max2csv.pid'
        pidfile = '/dev/shm/max2csv.pid'
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
