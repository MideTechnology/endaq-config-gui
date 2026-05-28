"""
Animated 'busy' image, like `wx.lib.throbber.Throbber` but transparent
and auto-hides when inactive.
"""
from itertools import cycle

import wx
from wx.lib.embeddedimage import PyEmbeddedImage

_FRAMES = (
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAfZJREFUOI2VlLGK20AQ'
        b'hv+VV7ZkmwMrGC5pDhHS7alZCfmq2KWvvObeIg+QlIE8QPp0aVKFPEKaIxAvagRJcaAqcGCw'
        b'jLmcZEvWpDjbKLKtkB8Glpmdj9mZ3WVEhDq5rvsKACaTyfu6fVpdcDQacQBnAM4266PaBV3X'
        b'fQrgPE3TmzAM7+uSHMfptVqtq6IoviqlbqsVnQNwTNO8FkJ0j0GEEFaz2XxDRCNN017uHS1N'
        b'0xvGWExEvWMwIYRlGMZrAKcA7pIk+bwHCsPwPkmST2XYcrnUAcwBzKfTqVGGpGn6LgzD2Taf'
        b'VacmhOiapnlNRD1N0z7GcRwDQLvdfqbr+ttDEAAAEe3ZeDxueZ53WvU7jmNLKduHcrjneZdE'
        b'1C/DGWO/iehLtUedTudutVp9kFJW9/+ovUf/pUNlDodD7vv+SdUvpdSx6WvV9iqybdtYLBYX'
        b'WZZdDAaDE8aYxhjTXNfVOeeWlPIJY6xRzftrarZtG5ZleQDaAB4YY9+KongBAEEQ/JRSWpzz'
        b'Rp7na6VUTETrba52DDKbzb4rpXIA+sZIKRXneb7mnDeklL1yZTtQv99/XoZEUZQe6Oe6DPN9'
        b'v7ON7R5tlmW/dF1HHMe3URQta4azZozNfN/v5nme7IGCIJjj8Tn8U0RUAFiUfbX3iB71sLHa'
        b'H/APxUA5QeIRQWAAAAAASUVORK5CYII='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAeFJREFUOI2V0s9rE0EU'
        b'B/Dve5NMcJEEamopRQKx9pLAQnbIj1tu+QuyFxG8KgiC/SvEm4j/gJ5ylSKem0NkNtBz48FD'
        b'L1YFE6ORDPu8tLJsNgs+WBhm3vvw9s2QiCAvgiC4DwBRFL3Ny+O8wzAMFRHtE9F+GIYqL7dw'
        b'vWi1WrsADpn5zFr7K6+o2+2WnXODOI4/TqfTz+mODpn5SEQGxhhvG2KMqTjnHgPoMnN749eY'
        b'+UxE5kRU3oYZYyoAHgHYBXAJ4MP1GSWHbYzxRGRwhc3n8/lJuVx+CADOuTfFYvFJAnltrf2R'
        b'CaUxpdS75XK5AAAi2iuVSk+zEACAiGx8jUZDt9vtW+n9ZrN5p9fr3ciqKQRB0AVQSeJa61Wt'
        b'VjtNz6harV4uFovnxpidVDOz3Hf0X5HV5nA4VEEQeOl93/eP+v3+zayarGEXAdyN47jEzOdR'
        b'FP0GAN/37ymlXhHRBYBja+3XZF36+pPIn3q9fj6bzXYAwPO81Wq1eikiB1kYb0MAfBqNRrHW'
        b'mrXWPB6PfwI4JqILETkA8MIYU92ACoXCXhKx1q7T87zq4B9GRA82IOfcd631t21IElNKPWPm'
        b'kziO32fOKB1ERJ1O5zYATCaTL5KTnPuORESYec3M6zwEAP4CvB0tsEXUP28AAAAASUVORK5C'
        b'YII='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAeFJREFUOI2Vk8+K01AU'
        b'xr/T5naSWtqZyEBh3GTRXSwtlxiYVbd1IbgSxOdw4Vact+gD+AC6FTeKNKFQAzNQXbiagUqz'
        b'sZO/zXHTlpimAQ9cuHz3nN899+NcYmZUhWVZTwFgOp1+rMqrVR0SUZ2Zz5n5nIjqVbnKbjMc'
        b'Dk+FEBe+7/9YLBZRVZFpmi1VVS8BfHcc5/afjoQQF5vN5lG73X5iGIZaBdE07QWAPoDHB09b'
        b'Lpc/AdwDaOq6bpXBdhBmPiMiPwzDL3sb8mYbhqHqum4BaAK4j6Lom6Zpz7Ydf0iS5OUOEgTB'
        b'e8/z/pSCijAhxNc0TQMAqNVqD7Mse1UGAQAw88EajUaKbdvtom5ZVnc8Hp+U1dBgMOgRUbNg'
        b'RzKbzW6YOcuLvV7vpNPpvAZwWsj/VTlH/xVlbQIgKaUo6v1+35BSNkufVjSbiOpSyjNFUepp'
        b'mq4ajYYCAOv1uiuEeAvgLgzDK8/zVvm6WgVk47oux3E8ieN4EkXRbwB3ALqqqr4xTVMvBZVA'
        b'fCkl7f5aq9UKwzC8Ogbbg2zbfpCHMPOm6Kfneas8TNO05weg7eAFruuuyiB5WBzH74joU5Zl'
        b'n3f6/vc7jpMASI4B8jGfz30Ak7xWOUeO4yREdE1E19uLjsZfxtU3ytOPemEAAAAASUVORK5C'
        b'YII='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAdFJREFUOI2V1EGL00AU'
        b'B/D/m46bWmxrs+5JvHRlLw30kKEYvPSkIF579OBRvAj6KRbP7ofwLvoNgkxa9rQHe6kgUjYg'
        b'3YGFZpN5XtqSTZOIDwLDm7wfbx6TEDOjLnzffwIAURSFde+Juk0iEgC6ALqbdWXI7UIp1ZJS'
        b'ummaLrXWN3VFSqmWtXYIYD6dTi9vdSSldJMkOQRwrJS6U4cw83MhxAmAx3tHS9N0KYRYW2ud'
        b'KmyLEFGHma+EEOe7MeSHvSk+ttY6Qoh1u92er1arpwBgjAk7nc6LLUJE37TW16VQCfaj3++v'
        b'AWCxWNzPsuxlGQIAYOa9ZzKZNHzfbxXzo9HocDAYHJTVUBAErrX21jySJLGz2SzmQrue5x04'
        b'jvOaiNqFZn7X3o3/irI2x+PxveFweFLMe573KAiCu6VHKxn2AwAfmflhlmVve73eTwCI4/jI'
        b'cZx3AC4BnGmtV/k6UYUQ0S8p5dIYc2qMOWXmPxvkCMAbpVS3FCoiAD4AuAbgAnCbzeYawFkV'
        b'toOI6FUe0VrHxXlujpPHnu1B1tqvQogvjUbjfRmSx6SUnwCE1trv2/zu64+i6ALARRWQjzAM'
        b'rwB8zudq75HW+oaZ58w8/9ev5S/2BDMml1QxkwAAAABJRU5ErkJggg=='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAeFJREFUOI2Vk7GK20AQ'
        b'hv85ryzJOaKTwXCtIS4CwmBGRiSVW1fHVWnS5R2uCKRMHiBvca+QxqQxiCAEibpcMFdcCAjs'
        b'CziW8UraFLGNTicJMjAw/DvzMbM7S0opNNloNBoAQBiG35vyTpoO6Z919k5NueIQuK6rCSFM'
        b'3/fXSqm8qWgwGOi2bT+TUt6FYXj/ACSEMAGYzNwmopVSKquC9Pt9o9vtjrMs62iaBgD3D0bz'
        b'ff9PmqaZEKLFzDYRteogADoANnEc/zicHUFKqSwIglURBoAASACSmUURslwuvywWi+2hnsqv'
        b'RkQtZraFEK00TZdBEGQA4HneqZTyRRXk0MkjB0DMrJV1z/OeTiYTUVVDzPxRKfW81FXcbrff'
        b'zOfzpKi7rqsR0YVS6kk5v3GP/suq2mTmznA47Jf18Xh8Pp1O9crRypftOE7XMIy3AM6llO82'
        b'm81PALBt287z/DURrZIkuY6iaF2sO6mDAPiVZVlsWdaVZVlXQojf+0W1TdN85TjOaSWoDNlu'
        b'tx96vd4WwBmAM13XZZIk13WwI8g0zcsiJIqiZfk+oyhaF2GGYbx8BMrz/DMRzXa73fsqSBkG'
        b'4CuAbwf9+GmDILgBcFMHKMMAfCpqjXs0m81SALcAbvdxrf0F938w2g8HAsIAAAAASUVORK5C'
        b'YII='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAdRJREFUOI2Vk89rE0EU'
        b'x79vnLjbxihpFQ/FS0wNkkAIswQSPOSkRbzm5KlHEa+e/QMqeNK74h/RfyA1MgnkqjHQQw9F'
        b'XKjIYuLue16yJU42Cz4YGN6PD+995w2JCPKs2+3uAMBgMAjz8lRekIiImQvMXCAiysvV6cUY'
        b'c18pdaCUej8cDn/kFQVBUNBa347jOLTWRv90pJQ6YObHSZK8DoLgZh4EwN3FYrGrtd5ZG01E'
        b'PhDRmYjsATjKgqUQZvaUUvM4js8vZVgVe1l8JCJ7RHTm+/6LKIp8AKhWq+FsNttPIQC+WWv/'
        b'ZIJcWJIkzyeTydelhlvMvJ8FSUdaO71e71qz2bzn+o0x2/1+/0pWjTbGvCKiqiNHWC6XX7oa'
        b'VSqV+XQ6fWCM8Z3QRe4e/ZdltdnpdLYajcYd199ut3fr9frVrJossW8AeAbg1nw+fyMi5wBQ'
        b'LBZLSZI8EZGfRHScLmJqahMEwHelVOh53qHneYdhGP5aQq6LyKMgCLYzQS4EwLtarfabiEpE'
        b'VGq1WjERHW+CrXb0cBVirb1w9bTWRqswZm6ugZj5M4BPWuu3WRAXxsxfAExT/+XvH4/HpwBO'
        b'NwFcGICTVd/aq7lmjHkKAKPR6GNe3l+osy5XWbAeqQAAAABJRU5ErkJggg=='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAd5JREFUOI2Vk79r21AQ'
        b'x7/v6dl5ikIhAoO3YtqhAWEwT0a0S5zRU8b+F/kDUrp26Ni/oUuX9s8wbqTFlScPWhoSCJVr'
        b'o1qyJfu6xEaRZZUeHDyOu8/9eHeMiFAltm1/AgDXda+q/Pg/IDUiOiOiM9u2a1W+YvtQSr3k'
        b'nJ8vl8uvo9FoWhXEGOOO45xkWRa7rps+qYhzfk5EF/V6/Z1lWWYFRFNKmQB0IYS+11ocx98A'
        b'3ANoSimvy2CPkFMhhJZl2Xo4HP7ZA/m+HyZJ8iEPi6JIMsYeGGMPnudRHuJ53pSI1rskxV+z'
        b'LMuUUl4DaKZp+t4wjHsAWK1WmRDCLIMAAIhoT5VSx+12u1Vir22TF5Uppa4APC+M4/dsNvs4'
        b'mUyWhRnxTqfzCsCTVSCiReUe/ZeUldnv94+63W6zaHcc51mv1xOlrZUM+0TX9bdEdMo5/7zZ'
        b'bH4BgBBCT9P0NYBFGIY3QRAk+Th+CMIYmwohZoyxS8bYZRRFCYAFgGPTNLutVkuWgoqQOI6/'
        b'DAaDFREZRGSMx+N1GIY3h2A7kJTyTR7i+35UnGcQBEke1mg0XpS19gPA6BAkD5vP5981TfuZ'
        b'punt1r67ftd17wDcHQLk5XG/xnlb5R4R0Xp7a3snUZC/WiBFydxdUzUAAAAASUVORK5CYII='),
    PyEmbeddedImage(
        b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAPYAAAD2AFuR2M1'
        b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAeJJREFUOI2VkzGLE0EU'
        b'x/9vdm9zBmOK20NENIXRJoGQ3WFz6dIp9qkE+7P2A9wHULARSwu/gohnleYgxWyqgCC5VFpF'
        b'L2YDkjWbNxZuwmazWfHBwPCfeT/+b+Y90lojL1zXPQMA3/fP8u6JvEMp5QERVYmoKqU8yLtr'
        b'rjeO41SEEJ5pmuf9fj/IS2q1WkfM/JSZP/q+/3nLkRDCA3ASRdEzKWU5x6W9Wq1eMvNjIcSj'
        b'rNI+AZgAOAZwmgWTUtoAXmitbxPRN631ux2QUmoG4E0StlgsCgCu4lVMQgA8V0p9X+dT+tdi'
        b'J6cAjsMwfGXb9gQAptPpXcMwXmdBAABa653Vbrev1ev1O2m90Wg86HQ617NyyHGcJ0R0KwWf'
        b'h2H4djgc/k7qRETNZtO2LGurbYQQy9w++q/Islmr1SzP847Suuu6xW63a2SWlvHYRa31QyK6'
        b'YRjG+0ql8hMAxuNxgZnvCyFCAJdKqeVW2UlQEqK1DoIg+FAqlU4AoFwuX8zn8yozF7JgYh+E'
        b'iM5Ho9GSiA6J6LDX6zGASyFEyMwFAPeS87cBMXMjCVFK/Uq/Z+xgAzNN8+YOCMCImb/sg6Rh'
        b'lmX9iKLoaq1vpn8wGEzwdzz+GTHsa1LL7SOtNQOYAZjF+73xBw9DNz4btMFjAAAAAElFTkSu'
        b'QmCC')
)


class Spinner(wx.Panel):
    """
    Animated 'busy' image, like `wx.lib.throbber.Throbber` but transparent
    and auto-hides when inactive.
    """

    def __init__(self, parent, id=wx.ID_ANY, frameDelay=100, **kwargs):
        self.frameDelay = frameDelay
        super().__init__(parent, id, **kwargs)

        bitmaps = [frame.GetBitmap() for frame in _FRAMES]
        self.cycle = cycle(bitmaps)

        self.empty = wx.Bitmap(bitmaps[0].GetSize())
        self.empty.SetMaskColour(wx.BLACK)

        self.image = wx.StaticBitmap(self, -1, bitmap=self.empty)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.image, 0)
        self.SetSizer(sizer)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)


    def Start(self):
        """ Start the animation. """
        self.timer.Start(self.frameDelay)


    def Stop(self):
        """ Stop the animation. """
        self.timer.Stop()
        self.image.SetBitmap(self.empty)


    def IsRunning(self):
        """ Is the spinner spinning? """
        return self.timer.IsRunning()


    def OnTimer(self, _event):
        self.image.SetBitmap(next(self.cycle))
