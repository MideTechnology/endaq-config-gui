enDAQ&trade; Data Recorder Configuration GUI
============================================

This is a Python script is a standalone version of the configuration dialog in enDAQ Lab, for performing 
configuration of enDAQ (and legacy SlamStick X, C, and S) data recorders via a user-friendly GUI.

The configuration UI is not (currently) a _pip_-installable Python package.

> **Note**
> As of 2022-11-30, Python **3.9** or **3.10** is required. Some required libraries (including wxPython) 
> have issues with Python 3.11. Python versions 3.6 to 3.8 may work, but have not been thoroughly tested.

Installing
----------
1. Clone the repository:
   * Via the command line with `git clone https://github.com/MideTechnology/endaq-config-gui.git` in 
     the directory of your choice, or
   * Use your favorite git client.
2. In the repo directory, install the requirements:
    * `python -m pip install -r requirements.txt`

Running
-------
* In the repo directory, `python run.py`
