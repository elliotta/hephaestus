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

import Adafruit_GPIO.SPI as SPI
import Adafruit_MAX31855.MAX31855 as MAX31855


# Raspberry Pi software SPI configuration.
# All sensors will share CLK and DO, with separate CS for each sensor
CLK = 24
DO  = 25
CS  = [23, 18]


def c_to_f(c):
    '''Convert Celcius temperature to Farenheit.
    '''
    return c * 9.0 / 5.0 + 32.0

def corrected_celsius(thermocouple_temp, internal_temp):
    ''''corrected temperature reading for a K-type thermocouple
    allowing accurate readings over an extended range
    http://forums.adafruit.com/viewtopic.php?f=19&t=32086&p=372992#p372992
    assuming global: Adafruit_MAX31855 thermocouple(CLK, CS, DO);

    Adapted from https://learn.adafruit.com/calibrating-sensors/maxim-31855-linearization
    '''
       
    # MAX31855 thermocouple voltage reading in mV
    thermocoupleVoltage = (thermocouple_temp - internal_temp) * 0.041276
       
    # MAX31855 cold junction voltage reading in mV
    coldJunctionTemperature = internal_temp
    coldJunctionVoltage = (-0.176004136860E-01 +
          0.389212049750E-01  * coldJunctionTemperature +
          0.185587700320E-04  * pow(coldJunctionTemperature, 2.0) +
          -0.994575928740E-07 * pow(coldJunctionTemperature, 3.0) +
          0.318409457190E-09  * pow(coldJunctionTemperature, 4.0) +
          -0.560728448890E-12 * pow(coldJunctionTemperature, 5.0) +
          0.560750590590E-15  * pow(coldJunctionTemperature, 6.0) +
          -0.320207200030E-18 * pow(coldJunctionTemperature, 7.0) +
          0.971511471520E-22  * pow(coldJunctionTemperature, 8.0) +
          -0.121047212750E-25 * pow(coldJunctionTemperature, 9.0) +
          0.118597600000E+00  * exp(-0.118343200000E-03 * 
                               pow((coldJunctionTemperature-0.126968600000E+03), 2.0) )
                            )
                            
                            
    # cold junction voltage + thermocouple voltage         
    voltageSum = thermocoupleVoltage + coldJunctionVoltage
       
    # calculate corrected temperature reading based on coefficients for 3 different ranges   
    if thermocoupleVoltage < 0:
       b0 = 0.0000000E+00
       b1 = 2.5173462E+01
       b2 = -1.1662878E+00
       b3 = -1.0833638E+00
       b4 = -8.9773540E-01
       b5 = -3.7342377E-01
       b6 = -8.6632643E-02
       b7 = -1.0450598E-02
       b8 = -5.1920577E-04
       b9 = 0.0000000E+00
       
    elif thermocoupleVoltage < 20.644:
       b0 = 0.000000E+00
       b1 = 2.508355E+01
       b2 = 7.860106E-02
       b3 = -2.503131E-01
       b4 = 8.315270E-02
       b5 = -1.228034E-02
       b6 = 9.804036E-04
       b7 = -4.413030E-05
       b8 = 1.057734E-06
       b9 = -1.052755E-08
       
    elif thermocoupleVoltage < 54.886:
        b0 = -1.318058E+02
        b1 = 4.830222E+01
        b2 = -1.646031E+00
        b3 = 5.464731E-02
        b4 = -9.650715E-04
        b5 = 8.802193E-06
        b6 = -3.110810E-08
        b7 = 0.000000E+00
        b8 = 0.000000E+00
        b9 = 0.000000E+00
       
    else:
        # TODO: handle error - out of range
        return 0
       
    return (b0 + 
        b1 * voltageSum +
        b2 * pow(voltageSum, 2.0) +
        b3 * pow(voltageSum, 3.0) +
        b4 * pow(voltageSum, 4.0) +
        b5 * pow(voltageSum, 5.0) +
        b6 * pow(voltageSum, 6.0) +
        b7 * pow(voltageSum, 7.0) +
        b8 * pow(voltageSum, 8.0) +
        b9 * pow(voltageSum, 9.0)
        )


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


def main(web_output_file, interval, verbose,
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
            temps = [sensor.readTempC() for sensor in sensors]
            internals = [sensor.readInternalC() for sensor in sensors]
            corrected_temps = [corrected_celsius(temp, internal) for temp, internal in zip(temps, internals)]
            now = datetime.datetime.now()

            # Stdout output
            if verbose:
                print(now.isoformat() + ' ' + '; '.join(['%f,%f,%f' % (c_to_f(t), c_to_f(i), c_to_f(c)) for t, i, c in zip(temps, internals, corrected_temps) ]))

            # Html output
            # Always overwrite current file
            with open(web_output_file, 'w') as web_file:
                web_file.write('<html><head><title>Current Temps</title></head><body>%s<br><%s></body></html>' % ('<br>'.join(['temp %i: %f' % (i, f) for i, f in enumerate(corrected_temps)]), now.isoformat()))

            # Log file output
            if not file_start_time:
                file_start_time = now
            if not interval_start_time:
                interval_start_time = now
            if log_short_interval:
                if not short_file_start_time:
                    short_file_start_time = now
                if not short_interval_start_time:
                    short_interval_start_time = now

            if now - interval_start_time > log_interval:
                # Assemble data dictionary
                data_dict = OrderedDict([('timestamp', interval_start_time.strftime('%H:%M:%S')), ('hours', format((interval_start_time-file_start_time).total_seconds()/3600.0, '06.3f'))])
                data_dict.update([('sensor %i' % (i+1), str(temp)) for i, temp in enumerate(corrected_temps)])
                # Write out the data
                if not output_file or now.date() != current_date:
                    if output_file:
                        output_file.close()
                    print('Opening new output file')
                    current_date = datetime.datetime.now().date()
                    output_file = get_output_file(current_date.strftime(log_file_pattern), data_dict, output_separator)
                output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')

            if log_short_interval:
                if now - short_interval_start_time > short_interval:
                    # Assemble data dictionary
                    data_dict = OrderedDict([('timestamp', short_interval_start_time.strftime('%H:%M:%S')), ('hours', format((short_interval_start_time-short_file_start_time).total_seconds()/3600.0, '07.4f'))])
                    data_dict.update([('sensor %i' % (i+1), str(temp)) for i, temp in enumerate(corrected_temps)])
                    # Write out the data
                    if not short_output_file or now.date() != current_date:
                        if short_output_file:
                            short_output_file.close()
                        print('Opening new short output file')
                        current_date = datetime.datetime.now().date()
                        short_output_file = get_output_file(current_date.strftime(short_log_file_pattern), data_dict, output_separator)
                    short_output_file.write(output_separator.join([str(x) for x in data_dict.values()]) + '\n')

        except KeyboardInterrupt:
            break

        time.sleep(interval - time.time() % interval) # corrects for drift


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read data from MAX31855 sensors', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-w', '--web_output_file', default='/dev/shm/current_temp.html', help='Html output file')
    parser.add_argument('-i', '--interval', default=1, help='Seconds at which to update the web_output_file')
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
