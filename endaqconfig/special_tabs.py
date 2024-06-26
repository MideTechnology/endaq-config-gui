"""
Configuration "special" tabs: UI panels for showing recorder information and
calibration, not dynamically generated from ConfigUI data. Copied from the old
configuration system.

:todo: This still has cruft from the old configuration system. It needs a good
    cleaning.
"""
from __future__ import absolute_import, print_function

from datetime import datetime
import html
import os.path
import time
from math import factorial

import numpy as np

import wx
from wx.html import HtmlWindow
import wx.lib.wxpTag  # @UnusedImport - simply importing it does the work.

from .widgets.calibration_editor import PolyEditDialog

from .base import Tab, logger, registerTab


#===============================================================================
#
#===============================================================================

def n_choose_k(n, k):
    return factorial(n) // (factorial(k) * factorial(n - k))


def get_reduced_polynomial_coefficients(coefficients, references):
    """
    Reduces any univariate or bivariate polynomial to one where the references values are all zero.

    The guiding math used to calculate the coefficients can be given as the following LaTeX code,
    with occurrences of 0^0 being replaced by 1 (seen in the conditional statements within the code):

    For the univariate case, the desired formulation is:
    P = \sum\limits_{j=0}^{n} x^j \sum\limits_{i=j}^{n} a_i (-s)^{i-j} {i\choose j}

    For the bivariate case, the desired formulation is as follows (with C being the coefficient matrix to be returned):
    P = \sum\limits_{i=0}^{n} \sum\limits_{j=0}^{n} x^i y^j *C_{i,j}

    This coefficient matrix C is calculated using the following equation:
    C_{i,j} = \sum\limits_{k=i}^{n} \sum\limits_{g=j}^{n} a_{k,g} {g\choose j} {k\choose i} (-s)^{g-j} (-r)^{k-i}

    In the above math, A is the coefficient matrix of the
    unshifted polynomial, and s and r and the offsets of x and y
    respectively


    :param coefficients: The list of coefficients for the calibration polynomial
    :param references: The list of references (offsets) for the variables
    :return: The coefficients of the reduced polynomial.  This will represent the same polynomial as the one given,
    but with only zero reference values.
    """
    if len(references) == 1:
        out = np.zeros(len(coefficients))
        for j in range(len(coefficients)):
            for k in range(j, len(coefficients)):
                offset_power = (-references[0]) ** (k - j) if references[0] != 0 or k != j else 1

                out[j] += coefficients[k] * offset_power * n_choose_k(k, j)
    else:
        coeff_length = int(np.sqrt(len(coefficients)))
        out = np.zeros((coeff_length, coeff_length))
        coefficients = np.array(coefficients).reshape(coeff_length, coeff_length)[::-1, ::-1].T

        for j in range(coeff_length):
            for k in range(coeff_length):
                for m in range(j, coeff_length):
                    for n in range(k, coeff_length):
                        offset_power1 = (-references[0]) ** (n - k) if references[0] != 0 or n != k else 1
                        offset_power2 = (-references[1]) ** (m - j) if references[1] != 0 or m != j else 1

                        out[j, k] += coefficients[m, n] * n_choose_k(n, k) * n_choose_k(m, j) * offset_power1 * offset_power2

        out = out[::-1, ::-1].T
    return out


class InfoPanel(HtmlWindow):
    """ A generic configuration dialog page showing various read-only properties
        of a recorder. Displays HTML.

        :cvar field_types: A dictionary pairing field names with a function to
            prepare the value for display.
    """
    # Replacement, human-readable field names. Other names will be converted
    # from camel case.
    field_names = {'HwRev': 'Hardware Revision',
                   'FwRev': 'Firmware Revision',
                   'McuType': 'MCU Type',
                   'FwRevStr': 'Firmware Version',
                   'SerialCommandInterface': 'Has Serial Command Interface',
                   'FileCommandInterface': 'Has File Command Interface',
                   'HasEsp32': 'Has ESP32 Wi-Fi',
                   'NcpAppFwVer': 'Network Interface FW Version',
                   }

    # Formatters for specific fields. The keys should be the string as
    # displayed (de-camel-cased or replaced by field_names)
    field_types = {'Date of Manufacture': lambda x: datetime.fromtimestamp(x).date(),
                   'Hardware Revision': str,
                   'Firmware Revision': str,
                   'Config. Format Version': str,
                   'Recorder Serial': str,
                   'Calibration Date': str,
                   'Calibration Expiration Date': str,
                   'Calibration Serial Number': lambda x: "C%05d" % x,
                   'Has File Command Interface': lambda x: bool(x),
                   'Has Serial Command Interface': lambda x: 'True',
                   'Has ESP32 Wi-Fi': lambda x: 'True',
                   'Network Interface FW Version': str,
                   }

    excluded_fields = ('RecorderTypeUID', 'WispiApiLevel',)

    column_widths = (50, 50)


    def __init__(self, *args, **kwargs):
        """ Constructor. Takes standard `wx.html.HtmlWindow` arguments, plus:

            :keyword info: A dictionary of information to show.
            :keyword root: The 'root' viewer window.
        """
        self.tabIcon = -1
        self.info = kwargs.pop('info', {})
        self.root = kwargs.pop('root', None)
        super(InfoPanel, self).__init__(*args, **kwargs)
        self.data = {}
        self.html = []
        self._inTable = False
        self.buildUI()
        self.initUI()


    def addItem(self, k, v, escape=True):
        """ Append a labeled info item.
        """
        # Automatically create new table if not already in one.
        if not self._inTable:
            self.html.append("<table width='100%'>")
            self._inTable = True

        if escape:
            k = html.escape(str(k)).replace(' ', '&nbsp;')
            v = html.escape(str(v))

        self.html.append(f"<tr><td width='{self.column_widths[0]}%'>{k}</td>")
        self.html.append(f"<td width='{self.column_widths[1]}%'><b>{v}</b></td></tr>")


    def closeTable(self):
        """ Wrap up any open table, if any.
        """
        if self._inTable:
            self.html.append("</table>")
            self._inTable = False


    def addLabel(self, v, warning=False, escape=True):
        """ Append a label.
        """
        if escape:
            v = html.escape(v)

        if self._inTable:
            self.html.append("</table>")
            self._inTable = False
        if warning:
            v = f"<font color='#FF0000'>{v}</font>"
        self.html.append(f"<p>{v}</p>")


    @staticmethod
    def _fromCamelCase(s):
        """ break a 'camelCase' string into space-separated words.
        """
        result = []
        lastChar = ''
        for i in range(len(s)):
            c = s[i]
            if c.isupper() and lastChar.islower():
                result.append(' ')
            result.append(c)
            lastChar = c

        # Hack to fix certain acronyms. Should really be done by checking text.
        result = ''.join(result).replace("ID", "ID ").replace("EBML", "EBML ")
        return result.replace("UTC", "UTC ").replace(" Of ", " of ")


    def getDeviceData(self):
        """ Populate the `data` dictionary, using human-readable keys.
            This will get shown verbatim.
        """
        # Hack: This is ugly!
        if self.root.device is not None:
            self.info['RecorderSerial'] = self.root.device.serial

        # Hack: remove the integer FwRev if the string exists
        if 'FwRevStr' in self.info:
            self.info.pop('FwRev', None)

        items = []
        for k, v in self.info.items():
            if k in self.excluded_fields or str(k).startswith('Unknown'):
                continue

            items.append((self.field_names.get(k, self._fromCamelCase(k)), v))

        for k, v in sorted(items, key=lambda x: x[0]):
            self.data[k] = v


    def buildHeader(self):
        """ Called after the HTML document is started but before the dictionary
            items are written. Override to add custom stuff.
        """
        return


    def buildFooter(self):
        """ Called after the dictionary items are written but before the HTML
            document is closed. Override to add custom stuff.
        """
        return


    def buildUI(self):
        """ Create the UI elements within the page. Every subclass should
            implement this. Called after __init__() and before initUI().
        """
        self.getDeviceData()
        self.html = ["<html><body>"]
        self.buildHeader()

        if isinstance(self.data, dict):
            items = self.data.items()
        else:
            items = iter(self.data)
        for k, v in items:
            if k.startswith('_label'):
                # Treat this like a label
                self.addLabel(v)
                continue

            try:
                if k.startswith('_'):
                    continue
                elif k in self.field_types:
                    v = self.field_types[k](v)
                elif isinstance(v, int):
                    v = f"0x{v:08X}"
                elif isinstance(v, dict) and len(v) == 0:
                    v = "True"
            except TypeError:
                # Unlikely, but just in case. `v` remains the same.
                pass

            self.addItem(k, v)

        if self._inTable:
            self.html.append("</table>")

        self.buildFooter()

        self.html.append('</body></html>')
        self.SetPage(''.join(self.html))


    def initUI(self):
        pass


    def OnLinkClicked(self, linkinfo):
        """ Handle a link click. Ones starting with "viewer:" link to a
            channel, subchannel and time; ones starting with "http:" link to
            an external web page.

            :todo: Implement linking to a viewer position.
        """
        href = linkinfo.GetHref()
        if href.startswith("viewer:"):
            # Link to a channel at a specific time.
            # Not yet implemented!
            href = href.replace('viewer', '')
            base, t = href.split("@")
            chid, subchid = base.split('.')
            logger.debug(f"Viewer link: {chid!r} {subchid} {t}")
        elif href.startswith("http"):
            # Launch external web browser
            wx.LaunchDefaultBrowser(href)
        else:
            # Show in same window (file, etc.)
            super(InfoPanel, self).OnLinkClicked(linkinfo)


    def getData(self):
        return {}


#===============================================================================
#
#===============================================================================

class SSXInfoPanel(InfoPanel):
    """ Specialized InfoPanel that adds special formatting and content based
        on conditions of the recorder.
    """

    ICONS = ('resources/info.png', 'resources/warn.png', 'resources/error.png')


    def buildUI(self):
        self.life = None  # self.root.device.getEstLife() XXX: FIX
        self.lifeIcon = -1
        self.lifeMsg = None
        self.calExp = self.root.device.getCalExpiration()
        self.calIcon = -1
        self.calMsg = None

        # HACK: PyInstaller flattens the directory structure, so the
        # executable's path to RESOURCES is different than when running from
        # source. Insert ``..`` if running from source.
        curdir = os.path.dirname(__file__)
        if not os.path.exists(os.path.realpath(os.path.join(curdir, self.ICONS[0]))):
            curdir = os.path.join(curdir, '..')
        self.ICONS = [os.path.realpath(os.path.join(curdir, x)) for x in self.ICONS]

        if self.life is not None:
            if self.life < 0:
                self.lifeIcon = self.root.ICON_WARN
                self.lifeMsg = self.ICONS[self.lifeIcon], f"This devices is {self.root.device.getAge()} days old; battery life may be limited."

        if self.calExp is not None:
            calExpDate = self.calExp.date()
            if self.calExp < time.time():
                self.calIcon = self.root.ICON_ERROR
                self.calMsg = self.ICONS[self.calIcon], f"This device's calibration expired on {calExpDate}; it may require recalibration."
            elif self.calExp < time.time() - 8035200:
                self.calIcon = self.root.ICON_WARN
                self.calMsg = self.ICONS[self.calIcon], f"This device's calibration will expire on {calExpDate}."

        self.tabIcon = max(self.calIcon or -1, self.lifeIcon or -1, self.tabIcon or -1)
        # self.tabIcon = None if self.tabIcon == -1 else self.tabIcon
        super(SSXInfoPanel, self).buildUI()


    def addItem(self, k, v, escape=True):
        """ Custom adder that highlights problem items.
        """
        if ((k == 'Date of Manufacture' and self.lifeIcon > 0) or
            (k == 'Calibration Expiration Date' and self.calIcon > 0)):
            k = f"<font color='red'>{k}</font>"
            v = f"<font color='red'>{v}</font>"

        super(SSXInfoPanel, self).addItem(k, v, escape=escape)


    def buildFooter(self):
        warnings = list(filter(None, (self.lifeMsg, self.calMsg)))
        if len(warnings) > 0:
            warnings = [f"<tr valign=center><td><img src='{w[0]}'></td><td><font color='red'>{w[1]}</font></td></tr>" for w in warnings]
            warnings.insert(0, "<hr><center><table>")
            warnings.append('</table>')
            if self.root.device.homepage is not None:
                warnings.append(f"<p>Please visit the <a href='{self.root.device.homepage}'>product's home page</a> for more information.</p>")
            warnings.append('</center>')
            self.html.extend(warnings)


#===============================================================================
#
#===============================================================================

class CalibrationPanel(InfoPanel):
    """ Panel for displaying calibration polynomials. Read-only.
    """
    ID_CREATE_CAL = wx.NewIdRef()

    def __init__(self, parent, id_, calSerial=None, calDate=None,
                 calExpiry=None, channels=None, editable=False,
                 hideUnused=True, **kwargs):
        self.editable = editable
        self.calSerial = calSerial
        self.calDate = calDate
        self.calExpiry = calExpiry
        self.channels = channels
        self.hideUnused = hideUnused
        self.initialized = False

        # dictionaries to map calibration IDs to/from the Edit/Revert buttons
        self.calIds = {}
        self.calWxIds = {}
        self.revertIds = {}
        self.revertWxIds = {}
        super(CalibrationPanel, self).__init__(parent, id_, **kwargs)


    def getDeviceData(self):
        if isinstance(self.info, dict):
            self.info = list(self.info.values())
        else:
            self.info = []
#             polys = self.root.device.getCalPolynomials()
#             if polys is not None:
#                 self.info = self.root.device.getCalPolynomials().values()
#                 self.calSerial = self.root.device.getCalExpiration()
#                 self.calDate = self.root.device.getCalSerial()
#             else:
#                 self.info = []

        if self.channels is None:
            self.channels = self.root.device.getChannels()

        self.info.sort(key=lambda x: x.id)


    @classmethod
    def cleanFloat(cls, f, places=6):
        s = (('%%.%df' % places) % f).rstrip('0')
        if s.endswith('.'):
            return '%s0' % s
        return s


    def addEditButton(self, cal):
        """ Helper method to embed wxPython Buttons in the HTML display (the
            widget does not support forms, so it can't be done in HTML).
        """
        if cal.id in self.calWxIds:
            wxid = self.calWxIds[cal.id]
        else:
            wxid = self.calWxIds.setdefault(cal.id, wx.NewIdRef())

        if cal.id in self.revertWxIds:
            wxrevid = self.revertWxIds[cal.id]
        else:
            wxrevid = self.revertWxIds.setdefault(cal.id, wx.NewIdRef())

        self.calIds[wxid] = cal
        self.revertIds[wxrevid] = cal
        return ('<wxp module="wx" class="Button" width="60" height="20">'
                '<param name="label" value="Edit">'
                f'<param name="id" value="{int(wxid)}">'
                '</wxp>'
                '<wxp module="wx" class="Button" width="60" height="20">'
                '<param name="label" value="Revert">'
                f'<param name="id" value="{int(wxrevid)}">'
                '</wxp>')


    def buildUI(self):
        """ Create the UI elements within the page. Every subclass should
            implement this. Called after __init__() and before initUI().
        """

        def _usesCal(cal, ch):
            # Helper function to determine users of a transform
            try:
                return ch.transform == cal.id or ch.transform.id == cal.id
            except AttributeError:  # as err:
                return False

        def _chName(ch):
            # Helper function to pretty-print (Sub)Channel names
            if hasattr(ch, 'subchannels'):
                return f"Channel {ch.id}: <i>{ch.displayName}</i>"
            return f"Channel {ch.parent.id}.{ch.id}: <i>{ch.displayName}</i>"

        # HACK: other panels assume they will only have their contents generated
        # once, but this one will redraw if its contents were edited.
        if not self.initialized:
            self.getDeviceData()
            self.initialized = True

        self.html = ["<html><body>"]

        if self.calSerial:
            self.html.append(f"<p><b>Calibration Serial: C{self.calSerial:03d}</b></p>")
        if self.calDate or self.calExpiry:
            self.html.append("<p>")
            if self.calDate:
                self.html.append(f"<b>Calibration Date:</b> {self.calDate.date()}")
            if self.calExpiry:
                self.html.append(f" <b>Expires:</b> {self.calExpiry.date()}")
            self.html.append("</p>")

        if len(self.info) == 0:
            self.html.append("Device has no calibration data.")
            if self.editable:
                self.html.append('<br><wxp module="wx" class="Button">'
                                 '<param name="label" value="Create User Calibration">'
                                 f'<param name="id" value="{int(self.ID_CREATE_CAL)}">'
                                 '</wxp>')

        for cal in self.info:
            if cal.id is None:
                # HACK: This shouldn't happen.
                continue

            # Collect the users of the calibration polynomial
            users = []
            for ch in self.channels.values():
                if _usesCal(cal, ch):
                    users.append(_chName(ch))
                users.extend([_chName(subch) for subch in ch.subchannels if _usesCal(cal, subch)])

            if len(users) == 0:
                # Only show polynomials used by channels if explicitly told to.
                if self.hideUnused:
                    continue
                else:
                    users = ["None"]

            t = (f"<p><b>Calibration ID {cal.id} (Used by {'; '.join(users)})</b>")
            if self.editable:
                t += "<br>"+self.addEditButton(cal)
            self.html.append(t)

            calType = cal.__class__.__name__
            if hasattr(cal, 'channelId'):
                try:
                    if hasattr(cal, 'subchannelId'):
                        ref = _chName(self.channels[cal.channelId][cal.subchannelId])
                    else:
                        ref = _chName(self.channels[cal.channelId])
                    calType = f"{calType}; references {ref}"
                except (IndexError, AttributeError, KeyError) as err:
                    logger.debug(f'Ignored error formatting polynomial reference: {err!r}')

            self.html.append('<ul>')
            self.html.append(f'<li>{calType}</li>')
            if hasattr(cal, 'coefficients'):
                coeffs = ', '.join(map(self.cleanFloat, cal.coefficients))
                refs = ', '.join(map(self.cleanFloat, cal.references))
                self.html.append(f'<li>Coefficients: <tt>{coeffs}</tt></li>')
                self.html.append(f'<li>Reference(s): <tt>{refs}</tt></li>')

            reduced_polynomial_coeffs = get_reduced_polynomial_coefficients(cal.coefficients, cal.references).flatten()

            poly = cal.__class__(reduced_polynomial_coeffs, channelId=-1, subchannelId=-1).source.split()[-1]
            self.html.append(f'<li>Polynomial: <tt>{cal!s}</tt></li>')
            if str(cal) != poly:
                self.html.append(f'<li>Polynomial, Reduced: <tt>{poly}</tt></li>')
            self.html.append('</ul></p>')

        self.html.append("</body></html>")
        self.SetPage(''.join(self.html))


class EditableCalibrationPanel(wx.Panel):
    """ Wrapper for CalibrationPanel, in order to receive button press events
        generated by the embedded widgets (they are sent to parent, not the
        HtmlWindow containing them).
    """
    # TODO: Refactor this as the only Calibration panel and use only it.
    # Having them separate is a hack done for expedience.
    def __init__(self, parent, id_, calSerial=None, calDate=None,
                 calExpiry=None, editable=True, root=None,
                 factoryCal=None, channels=None, **kwargs):

        info = kwargs.pop('info', {})

        self.editable = editable
        self.calSerial = calSerial
        self.calDate = calDate
        self.calExpiry = calExpiry
        self.channels = channels

        self.tabIcon = -1
        self.originalCal = info
        self.info = info.copy() if isinstance(info, dict) else None
        self.factoryCal = factoryCal
        self.root = root
        super(EditableCalibrationPanel, self).__init__(parent, id_, **kwargs)
        self.data = {}
        self.buildUI()
        self.initUI()


    def buildUI(self):
        sizer = wx.BoxSizer()
        self.SetSizer(sizer)
        self.html = CalibrationPanel(self, -1, calSerial=self.calSerial,
                                     calDate=self.calDate, calExpiry=None,
                                     editable=self.editable, info=self.info,
                                     root=self.root, channels=self.channels)
        sizer.Add(self.html, 1, wx.EXPAND | wx.ALL)
        self.Bind(wx.EVT_BUTTON, self.OnButtonEvt)


    def initUI(self):
        self.enableRevertButtons()


    def updateCalDisplay(self):
        """ Update the displayed polynomials.
        """
        if self.info is None:
            return
        self.html.info = sorted(self.info.values(), key=lambda x: x.id)
        self.html.buildUI()
        self.enableRevertButtons()


    def enableRevertButtons(self):
        """ Disable the 'Revert' button if the user polynomial is the same as
            the factory's.
        """
        if self.info is None:
            return
        for calid, wxid in self.html.revertWxIds.items():
            but = self.FindWindowById(wxid)
            try:
                but.Enable(not self.info[calid] == self.factoryCal[calid])
            except AttributeError:
                pass
            except Exception as err:
                logger.debug(f'Ignored error in enableRevertButtons: {err!r}')
                but.Enable(False)


    def OnButtonEvt(self, evt):
        """ Handle a button press in the HTML widget.
        """
        evtId = evt.GetId()
        if evtId == self.html.ID_CREATE_CAL:
            # Duplicate factory calibration data.
            self.info = self.factoryCal.copy()
            self.updateCalDisplay()
        elif evtId in self.html.calIds:
            # Edit a polynomial
            cal = self.html.calIds[evtId]
            savedCal = self.factoryCal[cal.id]
            dlg = PolyEditDialog(self, -1, transforms=self.info,
                                 channels=self.html.channels, cal=cal,
                                 changeSource=False, changeType=False,
                                 savedCal=savedCal)
            if dlg.ShowModal() == wx.ID_OK:
                self.info[dlg.cal.id] = dlg.cal
                self.updateCalDisplay()
            dlg.Destroy()
        elif evtId in self.html.revertIds:
            # Revert a polynomial to factory settings
            cal = self.html.revertIds[evtId]
            self.info[cal.id] = self.factoryCal[cal.id]
            self.updateCalDisplay()
        else:
            logger.debug(f"Unknown button ID: {evtId}")
            evt.Skip()


    def getData(self):
        return {}


#===============================================================================
#--- Special-case tabs
#===============================================================================

@registerTab
class DeviceInfoTab(Tab):
    """ Special-case Tab for showing device info. The tab's default behavior
        shows the appropriate info for Slam Stick recorders, no child fields
        required.

        TODO: Refactor and clean up DeviceInfoTab, removing dependency on old
            system.
    """

    def __init__(self, *args, **kwargs):
        self.setAttribDefault("label", "Recorder Info")
        super(DeviceInfoTab, self).__init__(*args, **kwargs)


    def initUI(self):
        dev = self.root.device

        if dev is None:
            # Should only happen during debugging
            return

        info = dev.getInfo()

        info['CalibrationSerialNumber'] = dev.getCalSerial()
        info['CalibrationDate'] = dev.getCalDate()
        info['CalibrationExpirationDate'] = dev.getCalExpiration()

        info['HwRev'] = dev.hardwareVersion
        if info.pop('UniqueChipIDLong', None):
            info['UniqueChipID'] = dev.chipId

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.field = InfoPanel(self, -1,
                                  root=self.root,
                                  info=info)
        self.sizer.Add(self.field, 1, wx.EXPAND)
        self.SetSizer(self.sizer)


@registerTab
class FactoryCalibrationTab(DeviceInfoTab):
    """ Special-case Tab for showing recorder's factory-set calibration
        polynomials. The tab's default behavior shows the appropriate info for
        Slam Stick recorders, no child fields required.

        TODO: Refactor and clean up FactoryCalibrationTab, removing dependency
            on old system.
    """
    def __init__(self, *args, **kwargs):
        self.setAttribDefault('label', 'Factory Calibration')
        super(FactoryCalibrationTab, self).__init__(*args, **kwargs)


    def initUI(self):
        dev = self.root.device

        if dev is None:
            # Should only happen during debugging
            return

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.field = CalibrationPanel(self, -1,
                                      root=self.root,
                                      info=dev.getCalPolynomials(user=False),
                                      calSerial=dev.getCalSerial(),
                                      calDate=dev.getCalDate(),
                                      calExpiry=dev.getCalExpiration())
        self.sizer.Add(self.field, 1, wx.EXPAND)
        self.SetSizer(self.sizer)


@registerTab
class UserCalibrationTab(FactoryCalibrationTab):
    """ Special-case Tab for showing recorder's user-defined calibration
        polynomials. The tab's default behavior shows the appropriate info for
        Slam Stick recorders, no child fields required.

        TODO: Refactor and clean up UserCalibrationTab, removing dependency on
            old system.
    """
    def __init__(self, *args, **kwargs):
        self.setAttribDefault('label', 'User Calibration')
        super(UserCalibrationTab, self).__init__(*args, **kwargs)


    def initUI(self):
        dev = self.root.device

        if dev is None:
            # Should only happen during debugging
            return

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.field = EditableCalibrationPanel(
                self, -1,
                root=self.root,
                info=dev.getUserCalPolynomials(),
                factoryCal=dev.getCalPolynomials(user=False),
                editable=True
        )
        self.sizer.Add(self.field, 1, wx.EXPAND)
        self.SetSizer(self.sizer)


    def save(self):
        """ Save the user calibration, if any. Called when main dialog saves
            prior to closing.
        """
        if self.field.info and self.root.device is not None:
            self.root.device.writeUserCal(self.field.info)
