Hephaestus
==========

Purpose
-------

This code will monitor temperatures on a wood burning stove, and provide
analysis of the data. It will provide current temperature display near the
stove, and a web interface with history and analysis.

This code was developed for reading temerature data from an Innovate TC-4,
with initial protocol testing occuring with an Innovate LC-1. Development and
testing occured on OSX with plans to eventually run on a raspberry pi. Since OSX
at the time this was developed ships with python2.7 installed, this code is
designed to run under python2.7.

Installation
------------

### pyserial

Assuming you already have a python2.7 install, all you need to run this code is
the pyserial module.

Python2.7 and pyserial come installed on some versions of raspbian.

To get this on OSX, either use your favorite package
manager, or a virtual environment, or install it in the system area. This last
is the simplest way to set it up, but is not the recommended method becasue this
may need repeated after a system update. This also requires root access:

~~~~
sudo easy_install pip
sudo pip install pyserial
~~~~

### Timezone

Default file names are based on the date, and the logs have timestamps. To avoid
confusion, be sure the operating system's timezone is set to the timezone you
wish to see in the log files. Local time is probably better for a home stove
than UTC would be.
