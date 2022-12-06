"""
Configuration import/export functionality.

Created on Jan 29, 2020

:author: dstokes

TODO: Refactor and move into `endaq.device.config`. A good chunk has already
    been reimplemented.
"""

from fnmatch import filter as fnfilter
import os.path

from ebmlite import loadSchema, Element
# from endaq.device import getDevices
import wx

from .base import logger, ConfigBase, Group


# ===========================================================================
#
# ===========================================================================

def makeExpression(exp, configId=None, label=None):
    """ Helper method for compiling an expression in a string into a code
        object that can later be used with `eval()`.
    """
    name = "displayFormat"
    if exp is None:
        # No expression defined: value is returned unmodified (it matches
        # the config item's type)
        return None  # ConfigBase.noEffect
    elif exp == '':
        # Empty string expression: always returns `None` (e.g. the field is
        # used to calculate another config item, not a config item itself)
        return ConfigBase.noValue
    elif not isinstance(exp, str):
        # Probably won't occur, but just in case...
        logger.debug("Bad value for %s: %r (%s)" % (name, exp, type(exp)))
        return

    # Create a nicely formatted, informative string for the compiled
    # expression's "filename" and for display if the expression is bad.
    idstr = ("(ID 0x%0X) " % configId) if configId else ""
    msg = "%r %s%s" % (label, idstr, name)

    try:
        return compile(exp, "<%s>" % msg, "eval")
    except SyntaxError as err:
        logger.error("Ignoring bad expression (%s) for %s: %r" %
                     (err.msg, msg, err.text))
        return ConfigBase.noValue


def makeGainOffsetFormat(gain=1.0, offset=0.0, configId=None, label=None):
    """ Helper method for generating `displayFormat` expressions using a
        field's `gain` and `offset`.
    """
    gain = 1.0 if gain is None else gain
    offset = 0.0 if offset is None else offset
    # Create a nicely formatted, informative string for the compiled
    # expression's "filename" and for display if the expression is bad.
    idstr = (" (ID 0x%0X)" % configId) if configId else ""
    msg = "%r%s" % (label, idstr)

    displayFormat = compile("(x+%.8f)*%.8f" % (offset, gain),
                            "%s displayFormat" % msg, "eval")

    return displayFormat


# ===========================================================================
#
# ===========================================================================

def getConverters(configUi, data=None):
    """ Recursively get "DisplayFormat" expressions from dumped CONFIG.UI
        data. Fields without a conversion expression or display gain/offset
        are ignored.

        :param configUi: A dictionary generated by calling the `dump()` method
            on a CONFIG.UI EBML element, or an undumped EBML element.
        :return: A dictionary of compiled `eval` code objects, keyed by
            the field's `ConfigID`.
    """
    if data is None:
        data = {}

    if isinstance(configUi, Element):
        configUi = configUi.dump()

    if isinstance(configUi, list):
        for el in configUi:
            getConverters(el, data)
        return data
    elif not isinstance(configUi, dict):
        return data

    configId = configUi.get('ConfigID', None)
    if configId is not None:
        label = configUi.get('Label', None)
        displayFormat = configUi.get('DisplayFormat', None)
        gain = fnfilter(configUi, '*Gain')
        offset = fnfilter(configUi, '*Offset')

        gain = configUi[gain[0]] if gain else None
        offset = configUi[offset[0]] if offset else None

        if gain or offset:
            data[configId] = makeGainOffsetFormat(gain, offset, configId, label)
        elif displayFormat:
            data[configId] = makeExpression(displayFormat, configId, label)

    for v in configUi.values():
        if isinstance(v, (list, dict)):
            getConverters(v, data)

    return data


# ===========================================================================
#
# ===========================================================================

def checkCompatibility(dev, configUi, devprops):
    """ Score the compatibility of imported config data with a given device.

        :param dev: A `devices.Recorder` instance.
        :param configUi: The imported ``ConfigUI`` EBML element used to
            generate the configuration data.
        :param devprops: The imported ``RecordingProperties`` EBML element,
            from the device that exported it.
        :return: A ranking of compatibility.
                * 5: Totally compatible (same device).
                * 4: Probably compatible, with no problems.
                * 3: Probably compatible, but some things might be wrong.
                * 2: May or may not be compatible.
                * 1: Probably incompatible.
                * 0: Totally incompatible.
            4-5 can probably be imported with no user warning. The user should
            be prompted before importing files ranking 1-3, with warnings of
            inversely proportional strength. 0 should probably be prohibited
            from being imported.
    """
    result = 2

    props = devprops.dump()

    if props == dev.getProperties():
        # Same device. Totally compatible, return highest rank.
        return 5

    devInfo = dev.getInfo()
    info = props['RecorderInfo']

    if devInfo.get('ProductName', None) == info.get('ProductName'):
        fwRev = info.get('FwRevStr', None)
        if fwRev and fwRev == devInfo.get('FwRevStr', None):
            result += 1

    return result


# ===========================================================================
#
# ===========================================================================

def loadExport(filename):
    """ Load data from an exported configuration file.

        :param filename: The name of the exported file.
        :return: A 3-item tuple containing EBML elements (or `None`):
            * ``'ConfigUI'``
            * ``'RecorderConfigurationList'``
            * ``'RecordingProperties'``
    """
    mideSchema = loadSchema('mide_ide.xml')
    uiSchema = loadSchema('mide_config_ui.xml')

    doc = mideSchema.load(filename)
    result = {el.name: el for el in doc[0]}

    config = result.get('RecorderConfigurationList', None)
    configUi = result.get('ConfigUI', None)
    props = result.get('RecordingProperties', None)

    if configUi is not None:
        configUi = uiSchema.loads(configUi.value)

    return config, configUi, props


# def loadRecording(filename):
#     """ Import configuration data from an IDE file.
#
#         :param filename: The name of the IDE file from which to import.
#         :return: A 3-item tuple containing EBML elements (or `None`):
#             * ``'ConfigUI'``
#             * ``'RecorderConfigurationList'``
#             * ``'RecordingProperties'``
#     """
#     raise NotImplementedError("Importing from IDE not yet implemented!")
#
#
# def loadRecorder(path):
#     """ Import configuration data directly from another recorder.
#
#         :param dev: The path to a `Recorder` or a file on it (e.g. its config
#             file).
#         :return: A 3-item tuple containing EBML elements (or `None`):
#             * ``'ConfigUI'``
#             * ``'RecorderConfigurationList'``
#             * ``'RecordingProperties'``
#     """
#     raise NotImplementedError("Importing directly from another recorder TBD!")

#     mideSchema = loadSchema('mide_ide.xml')
#     uiSchema = loadSchema('mide_config_ui.xml')
#
#     try:
#         dev = getDevices(path)[0]
#     except IndexError:
#         # TODO: Report that the device wasn't found
#         return
#
#     if dev.configFile and os.path.exists(dev.configFile):
#         con = dev.getConfigItems()
#         if con:
#             config = mideSchema.load(dev.configFile)
#         else:
#             config = legacy.loadConfigData(dev)
#     else:
#         # TODO: Report no config data
#         return
#
#     if dev.configUIFile and os.path.exists(dev.configUIFile):
#         configUi = uiSchema.load(dev.configUIFile)
#     else:
#         configUi = legacy.loadConfigUI(dev)
#
#     props = dev.getProperties()
#
#     return (config, configUi, props)


# ===========================================================================
#
# ===========================================================================

def applyImportedConfig(dlg, config, configUi, props=None,
                        exclude=(0x8ff7f, 0x9ff7f), reset=True):
    """ Populate the dialog with imported configuration data.

        :param dlg: The parent `ConfigDialog`.
        :param config: The imported EBML configuration data.
        :param configUi: The imported CONFIG.UI data.
        :param props: The imported recorder properties.
        :param exclude: A list of configIDs to exclude from import. Defaults
            to the recorder name (0x8ff7f) and recorder description (0x9ff7f).
        :param reset: If `True`, dialog configuration values will be reset
            to defaults before the imported configuration is applied.
    """
    exclude = list(exclude)
    exclude.append(None)

    if reset:
        for cid, c in dlg.configItems.items():
            if cid not in exclude and not isinstance(c.group, Group):
                c.setToDefault()

    expressionVariables = dlg.expressionVariables.copy()
    converters = getConverters(configUi)

    for el in config:
        cid = value = None
        if el.name != "RecorderConfigurationItem":
            continue
        for c in el:
            if c.name == "ConfigID":
                cid = c.value
            elif c.name.endswith("Value"):
                value = c.value

        if cid not in exclude and cid in dlg.configItems:
            if cid in converters:
                expressionVariables['x'] = value
                value = eval(converters[cid], expressionVariables)
            dlg.configItems[cid].setDisplayValue(value)


# ============================================================================
#
# ============================================================================

def cleanProps(el: dict):
    """ Recursively emove unknown elements from a dictionary of device
        properties.
    """
    if isinstance(el, list):
        return [cleanProps(x) for x in el]
    elif not isinstance(el, dict):
        return el

    return {k: cleanProps(v) for k, v in el.items() if k != "UnknownElement"}


def exportConfig(device, filename, config=None, configUi=None, props=None):
    """ Generate a configuration export file. Writes the device's current
        information and configuration data by default.

        :param filename: The name of the file to write.
        :param device: The device from which to export the config.
        :param config: Configuration data to write, as nested dictionaries
            as generated by calling `dump()` on a `RecorderConfigurationList`
            element. If `None`, the data will be read from the device.
        :param configUi: The device's configuration UI, as an
            `ebmlite.Document`. If `None`, the data will be read from the
            device. Note: this is required if the recorder has old firmware
            without a CONFIG.UI file!
        :param props: The device's properties, as nested dictionaries
            as generated by calling `dump()` on a `RecordingProperties`
            element or calling the device's `Recorder.getProperties()`. If
            `None`, the data will be read from the device.
    """
    mideSchema = loadSchema('mide_ide.xml')

    # Get and/or prepare CONFIG.UI data
    configUi = configUi or device.config.configUi
    config = config or device.config.getConfig().dump()

    # Get and/or prepare configuration data
    if config is None:
        # No data provided. Read from device.
        logger.debug('Loading config data from %s' % device.configFile)
        ebml = device.config.getConfig()
        config = ebml.dump() if ebml else {}
        config = mideSchema.load(device.configFile).dump()
    else:
        logger.debug('Using provided config data')

    if 'RecorderConfigurationList' in config:
        # Get contents; the outer element is added on encoding.
        config = config['RecorderConfigurationList']

    # Get and/or prepare `RecordingProperties` data
    if props is None:
        props = device.getProperties()
    if 'RecordingProperties' in props:
        # Get contents; the outer element is added on encoding.
        props = props['RecordingProperties']

    # Encode and write
    data = {'RecorderConfigurationList': config,
            'RecordingProperties': cleanProps(props),
            'ConfigUI': configUi.getRaw()}

    with open(filename, 'wb') as f:
        mideSchema.encode(f, {'ExportedConfigurationData': data})

    return data


# ===============================================================================
#
# ===============================================================================

def importConfig(dlg):
    """ Import configuration data.

        :param dlg: The config dialog from which import was called.
    """
    # FUTURE: Implement other types of import.
    types = "Exported configuration data (*.xcg)|*.xcg"  # + \
    #             "|Device configuration file (*.cfg)|*.cfg" + \
    #             "|enDAQ recording file (*.ide)|*.ide"

    config = configUi = props = None

    fd = wx.FileDialog(dlg, message="Import Configuration Data",
                       wildcard=types, style=wx.FD_OPEN)

    while True:
        filename = None
        if fd.ShowModal() == wx.ID_OK:
            filename = fd.GetPath()
            ext = os.path.splitext(filename)[1].lower()

            if ext == ".xcg":
                config, configUi, props = loadExport(filename)
                break
            #             elif ext == ".ide":
            #                 config, configUi, props = loadRecording(filename)
            #                 break
            #             elif ext == ".cfg":
            #                 config, configUi, props = loadRecorder(filename)
            #                 break
            else:
                wx.MessageBox(("Configuration data could not be read.\n\n"
                               "The file type '%s' is unknown." % ext),
                              "Import Configuration Data",
                              wx.OK | wx.ICON_ERROR, dlg)
                continue
        break

    fd.Destroy()
    if config is None:
        return None

    compat = checkCompatibility(dlg.device, configUi, props)
    if compat <= 0:
        # Not compatible!
        wx.MessageBox("This device is not compatible with the imported "
                      "configuration data.\n\nThe imported data was generated "
                      "by an incompatible device, or is missing required "
                      "information.", "Import Configuration Data",
                      wx.OK | wx.ICON_ERROR, dlg)
        return None
    elif compat < 3:
        # Possibly compatible
        q = wx.MessageBox("The imported data may contain incompatibilities.\n\n"
                          "Some configuration values may not be imported, or "
                          "may be invalid for this device.\n\n"
                          "Continue with import?", "Import Configuration Data",
                          wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION, dlg)
        if q == wx.ID_NO:
            return None

    applyImportedConfig(dlg, config, configUi[0], props)
