enDAQ&trade; Data Recorder Configuration GUI
============================================

This is a Python script is a standalone version of the configuration dialog in enDAQ Lab, for performing 
configuration of enDAQ (and legacy SlamStick X, C, and S) data recorders via a user-friendly GUI.

> **Note**
> As of 2022-11-30, Python **3.9** or **3.10** is required. Some required libraries (including wxPython) 
> have issues with Python 3.11. Python versions 3.7 to 3.8 may work, but have not been thoroughly tested.

Installing
----------

On the command line (bash, PowerShell, cmd, etc.):

    python -m pip install "endaqconfig @ git+https://github.com/MideTechnology/endaq-config-gui"

Note: using a virtual environment is recommended.

Running
-------
Here are two ways, both from the command line:

    python -m endaqconfig

Or simply:

    endaqconfig.exe
