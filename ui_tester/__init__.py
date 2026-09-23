"""
This is a rough little utility for rendering CONFIG.UI dialogs, primarily
intended to assist firmware development work.

Usage: `python -m ui_tester [--path <RECORDER PATH] <CONFIG.UI>`

    CONFIG.UI Rendering Tester

    positional arguments:
        configUi              CONFIG.UI data, either XML or EBML. 'default' to use the fake recorder's CONFIG.UI file.

    options:
        -h, --help            show this help message and exit
        -p PATH, --path PATH  Path to a base fake recorder directory. Defaults to ``endaq-config-gui/ui_tester/_W5-D40_STM32_FwRev3.1.8/``
"""
