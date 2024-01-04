enDAQ&trade; Data Recorder Configuration GUI
============================================

This is a Python script is a standalone version of the configuration dialog in enDAQ Lab, for performing 
configuration of enDAQ (and legacy SlamStick X, C, and S) data recorders via a user-friendly GUI. It can
also be imported in another script for device selection and/or configuration.

Python 3.9 or later required. It is known to work in Windows 10 and up; it *may* work in Linux and
MacOS, but it has not been significantly tested in an OS other than Windows.


Installing
----------

On the command line (bash, PowerShell, cmd, etc.):

    python -m pip install "endaqconfig @ git+https://github.com/MideTechnology/endaq-config-gui"

Note: using a virtual environment is recommended (but not required).

Running
-------
Here are two ways, both from the command line:

    python -m endaqconfig

Or simply:

    endaqconfig
