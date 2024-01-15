from math import ceil
from typing import Any, Optional

from wx.lib.embeddedimage import PyEmbeddedImage


def batStat2name(status: dict[str, Any],
                 theme: str = "dk") -> tuple[Optional[str], str]:
    """ Turn the output of `getBatteryStatus()` into the name of an icon.

        :param status: The dictionary produced by `getBatteryStatus()`, or `None`.
        :param theme: The GUI theme (for future use; only "dk" is supported).
        :returns: A tuple containing the name of the icon and a human-readable
            description of the battery state.
    """
    # {'hasBattery': True, 'charging': True, 'percentage': False, 'level': 255}
    if not status or not status.get('hasBattery'):
        return None, ''
    if status.get('externalPower', False):
        return None, "Externally powered"

    percentage = status.get('percentage')
    charging = '_charging' if status.get('charging') else ''
    level = int(status.get('level', 128) * 0.39216 + .5)

    desc = ""
    if level < 20:
        lev = 0
    elif not percentage:
        lev = "unknown"
        desc = "Partially charged"
    else:
        lev = max(0, min(100, int((level + 15) // 20) * 20))

    return (f"battery_{lev}{charging}_{theme}",
            f'{desc or f"{level}%"}{" (charging)" if charging else ""}')


battery_0_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAWNJREFUOI2l1L1LHFEU'
    b'BfDfuCoiKmhhoVYS7QQbkxRisLWxWCz9SCNWtnZG0NY2hb0QsLAIJH+AmBBES7sUESxEFNZC'
    b'UZFN8WZlkJ15k3iGy7x59+ucN3cmEUc/PkRizvCrRK1CrKJeYI94GyvSmt4H0NHE/wdTkRpb'
    b'OMFwTv5T42E6h+kN2nBRoOY4jdnK8X/OKuqTeHKkAhZMOXWLO4wI76gZ7rEoHN0e9pso7ctu'
    b'VCUe1Z+vroxvpUDNBnrRk0NkF9c4xGhLTlADRdP2CVeYzfF/xQ7eYyym6LxAUR3rEaLwgGpM'
    b'0SCS1LZf+L5gs0QjEGuURfYYD7AkqCqF1ngI6MZ4uv6NqjB1RVjFJGGayyqaTEldYQaXJXLe'
    b'CYOwi58NRS120tWajy/YfhP+Dg+YQw3LJRq9wQ8sNDYmJC5V1FTUhNnP2pDwLcyjHd+bxOTZ'
    b'RglCz+jE2r8k/C86hPF+Ff4C81V2ZBl5yTIAAAAASUVORK5CYII=')

battery_0_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAL9JREFUOI3d0qFOA0EU'
    b'heFvt5uAQK2sJnVoEA1Jn2H9JtVNcE01Cc+AwPMECJ6AIvD1UL+SBOhmK3aHIMDNEMJ/M5k7'
    b'I87Jmbn8N7JhH+Mwgf4z2nCYoUu0roNJgVKm9WQEauc2XiOkuUL59aKS+dB91lEEE7hFgwdM'
    b'ikii33GHLZY4IV2iwDuqPLLoj/yaUco/usCUfppTJjrFmX76HkOi3M3QrczxFsHoGGvU9E/3'
    b'gsbCAdi5jGASuI+o9cfYA5ZlOxuxVETKAAAAAElFTkSuQmCC')

battery_100_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAZtJREFUOI2l1D2MjFEU'
    b'BuDnY0yG2ESIbTRqEQoTzW78FH6iUNgoFAoFEQW2Eo1ModhGpVGIdmVJhGhYW9gEQSKh2ohN'
    b'NpZkFRKKSdhJ9ii+mTCf72fCe3Obe8577jnvPecmqjGMvRU+H/FygFilOI8o2R3srgpSwyZc'
    b'QD3HfgV7KmJcxXdM5Nge4DkkOIa7dkn6XDZomzGEJal8eXhj3KglC95nfOb81HYPJ3pHYxId'
    b'8de6iW2KJfuB7UIrhxv2m8dj7ECyqkSSWeWyTeCzO6YwgpU+6xp1HMBbHCqraCsmSyqKbvCT'
    b'woiw0sf+IswLNYGxWkG2ixILFRVBS3iGF2TeeLi7u6dF0q0V9glHhabQwLWMz23fXMdDxc3S'
    b'hyLpeqst1PHab8lmnbNemC5kZaQb5KInGJIOZuADNgu3SjjhoMU/Ejtc1nU9PMWodLi/4ohw'
    b'GqdKWR3LmMZOPKohhNWahcJ+kjbFMo4746ym8cr05mzBK7wj7YmNuCj/C4IWZnADU7iMRuVF'
    b'Ke5LO3IgrMOlQZ3/Bw3ZGfkH/ALUxtK7L1L1qQAAAABJRU5ErkJggg==')

battery_100_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAMJJREFUOI3d07FKgmEU'
    b'BuDn//1xqCkFFweFArda3ANBuotuwRvwGhq9Bme3aKipwa0CEZQWwcHJwSAV+xsEEVq/D6T3'
    b'At6Hcw6H/5YEZXRQjNA/wCtkuEXXlWVQYqZorXYMJRI7ExdBoZZPz8q4xkcatPxv2njDXTyo'
    b'r25qqyDHeRYNqkhVpPiB2Ks7JN5EC6ywf6GIE92bu8ROgq940MY3nnCDxwy5XEEzMDRWxRDv'
    b'7G/0ouTBmUZQqGZppBe086TyC06eI23jNNSFAAAAAElFTkSuQmCC')

battery_20_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAXBJREFUOI2l1LFLVWEY'
    b'BvDfzUuKoYORU0s22GAq6C0HSQhCcCjw4uA/oTlJiwY5uEhDS3sYIi66WboYFKIEtdcQuCgO'
    b'KYJ6heNwziW1c79zwOfjwOE8z/s+5/3O852CbLRiIEPzB5s5egUxhihwVfAoq0kRtzGOmyn8'
    b'FJ5k9JjBX8ymcCv4CgUMY0m7w0uSO06te6remnj70vAdfXiH3ivcPXzCaPVBWUFF9N+qKCmp'
    b'vWXH6AhMOp8YdaJwIyDctqUnwM9iB80BzTP8wGDIaEM4bdPYx4sa/ATu4wy3QkZfZAfhNT7U'
    b'4HbxW7zNQkYlkecijeLQzF3hF/Am40UuoVYYquthotvyLwgbqM/o24o28Tkrhya6iCZ0J/e/'
    b'UMZJRs3bRFvEUV6j/qRgH0PYy1n3GV1YLSISqfPAQar0sbviUJxiJCn8mMOkemB/En/kFryU'
    b'/gsiTtY63mMRr9CQZxws41tOrUZM5hVfBw3iya+Fc6lEZ0b2D3viAAAAAElFTkSuQmCC')

battery_20_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAL1JREFUOI3d1DFKA1EU'
    b'heFv4mCTVAq2MphO1CVYiQtwITG9e8gqYh87tY+19tokVao0U4wRxmKi1QTCgwsh5/G6y/k5'
    b'B+5l35ThGAMcBvg/YQo5rvGgb9k6OjNX+U6AFDj9A8GdzEq98V0kQGCMF1wi6ySabKsbvOM2'
    b'EjTEGX7QzQNBi/WvIbq6f0UmOkFPs0KhiUb41IQpo6t7xRWec9RqB86VraNfHlElQArNHn3Q'
    b'9HeEezEnaIK3AN8d0C/+zyvqoFxR4QAAAABJRU5ErkJggg==')

battery_40_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAXtJREFUOI2l1L1rFFEU'
    b'BfDf6KJrEGWTsK0YUgXRREKwEGMjgkUKFwQLwb8g2gWbRTDFNpLCxsLWD8QmdkmQhAgRGyFW'
    b'NjYLAUEshCia4L4UM1skzrwZyBkGZuaeew/ncN8kytHEdAmni48VZkUxixC5dzFVNqSGIdzD'
    b'sZx6G1dKZszjJzo5tbfYgAQ38caE3j7KadvWNPBNGl8ePuESnmDyQO0slnG7/6ElsSv8dz3D'
    b'mOLI/uBcxOnzTOg8kiMR4rp4bB1s4VSEcw2buB5zdAYvI44CerhTINLEiHRZWkVC3Yy8VSLU'
    b'jrjpYwetouhOCK4KZgSTgjoeH+C8wqMKQkjXOw/DWM2ef6Nh/6F9j7tSV0Vo4qR0s8WWoY8N'
    b'ieMYz96/SjP/W9K3kHFr+FVFaB2Xs4YfuIHvFfpgBRewVEMQHHXRv1xqS1e65jtqbhk17YsX'
    b'FUT6B/YzaX6DuC//FwQP8Q5P8RoPUK/oaBEfKnINYK4q+TCoyzbnMNgD4KZ6+duPB9YAAAAA'
    b'SUVORK5CYII=')

battery_40_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAMNJREFUOI3d0zFLglEY'
    b'xfHfmy8tuglNQojNubg7RVuLH0Taow/QoJ+iD2Cbuji52x40ijg0qBQGb8Nbzg/CHexc7nbO'
    b'Pff/wMN/U4Y6+jhP8P4L5pCjiwdXPkLRpaWNXcDZxOVfEfRk9orwuQvSPGOCa2RnwdCxusEC'
    b'tymL7tHCN6p5wqLV7y0g9egOSkl0gZpyhZISDfGmhNmmHt0UbYxzFAoVnWD03QCPAWdTuUev'
    b'lFgzVU++NEJFe2t8Br81CvpOUD9ihTaDkt9ZZAAAAABJRU5ErkJggg==')

battery_60_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAYlJREFUOI2l1D9IVWEY'
    b'BvDftUtKNFUKDg625CAV5A2nhCDJgoYkqMEtCRqqTVrEocGQJhdHCcSIFt3SXAoSUYKaGqJB'
    b'ECIIrJa4N/oazrn5p3O+c8Dn4yzned5/D+/3VRSjAwMFmk2slcgVxT2EyNfA+aIkVRzHfRzO'
    b'4MdxoSDHI3zHZAa3iLdQwXW8cMrPPZJ2dSsuavVKYl8W3qEf0+jbx3VjCbeaP4ZVNIT/TkNN'
    b'Tb5lv9AruJnTxFxa6DQq1RwRbFh3LsJPYstT9YjmEt5jKDbRY8xHJgr4g5GcIh04KVmW4ZZI'
    b'N28UL8KEYDGH+4rPaUNihWqCa4I+QRee7OOf2TaN2YJm/iHPut3nNtbtWPbaXUcFy4KPOXn3'
    b'WFeu0JKzaUDAJ7QLZlI2r9DcrsYux6xr4otBnZLL/Q1XBKO4UyJ2GWfwsoogOKTHj0zplAXJ'
    b'UtRxw4CreoyR6n87gY2MyOaF/UDyMhzDA9lPEExgBTN4jodoKzENLGC1pNYRjJUVHwRtkskP'
    b'hL9V3qHk1y7eAwAAAABJRU5ErkJggg==')

battery_60_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAL5JREFUOI3d1DFKA2EQ'
    b'BeBvdbHRKoKtLNoJyRFSBQ+Q2itktc8dcgoPoJ2mN7X2XmBhiRZbJfBbrFptICwMiG+YauC9'
    b'eQ9m+G/IcIoSRwH8j3iBHGPMXfroRVWrrX12TAqc/wjBVGYj9a5yxwr3eMYQ2UEvF/tjgldc'
    b'Rwrd4QJbHOeBQtV3J4iO7heRjs5woj2hUEcLvGvNNNHRLTHCU44kOXSl6UVVmeGmY1Jo7+iN'
    b'Nr8BbsW8oAesAnj/AL4Ankg7VJ9XvGoAAAAASUVORK5CYII=')

battery_80_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAaFJREFUOI2l1LtrFUEY'
    b'BfDf6iVcYkTiI7ViYRTRQrExGhtRFCziA/wDgmChpgo2eguLNGJhk8JWkCiIgoUvxAc+CgXT'
    b'CREkIAQlcK+CiBHHYvdqcrOzu+IZBga+M+fjO3tmE+Xow2AJZxqvKmgV4hRCwZ7DjjKRGlbh'
    b'NLpy6uewu0TjAloYy6ndxnNIMIQbNvi6gNKj6bW1mJHal4c3Rgx4b9K7jNPSNOMz1uEejrfJ'
    b'hyXmhEXrCjaJW/YdmwWNjnuXMt2rWaMtSJYUWPJEsW1j+Oi6CezErxzOXrzFvrJGRWk7j1nH'
    b'bJN+gqSjPoL1+IlltYjItMQH5UFoCJ7hZU6jT9kOEJuoW7BHcEiwXVDHxQ7ONU2XcUc8LH8Q'
    b'm2g1HmXnb+i10ManThq2wk1sjGj0oce8SWOpa68HWC59mAFTWCMYj/Dnp66d0P1FYWjjMQay'
    b'6WdxQDCMExXu3sdW3K0hCJbq9yWXesSUNBQ/cNSgg/qNEuG3DGGXvw92ktS/lTgj/xcEDTzE'
    b'OCZwFvUK08AtvKjI1Y3RquT/Qd3iN/LP+A1p9JJLxgJfGAAAAABJRU5ErkJggg==')

battery_80_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAALdJREFUOI3d1DFKA2EQ'
    b'xfHfxsXGVAppRbQLJBcQrMQ+HkTtc4fkEjmAdll7U5s+F1gQNbBVhM9iVzu7b0Dyhmn/j/dg'
    b'hn1TgRPc4TCA/4QXKHGFqQsfWdBbn2pvOMPpjxHcKuykbDPvuAtUGKHoZUnxt67xiptIowec'
    b'4wtHZaBR3W2C6Op+FZlogL72hEITzbDRhmmiq3vGGMsSSXJgqMmCfjfBpfZgK6xp+zvGvZgX'
    b'9IhVAPcf6Bt0VUM1MRvoPQAAAABJRU5ErkJggg==')

battery_unknown_charging_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAYRJREFUOI2l1DFoFFEQ'
    b'xvHfxSOeGgUV02oipFBJFew0ghamEeJhmVbEQtMFxQRBERsrG23sRLHTwkK0sVAkQUNqq4Bg'
    b'kUIFQRK5sbhdWZZ7uwv5hq3me/N/O7yZlnqNYrrGs45PDWpV6hqi4tvCyboibRzEdQwPyC/h'
    b'dE2Nu/iJ+wNyr/AhB03jliGrenoF0/fstqcqIJ9xDw8xVcqN4XAOgq6WLeGX8FiYLJiPSbfs'
    b'D05UXOIp3mASrSKoGCvCBK5UgG5jP/ZVgHLv+RQohCN4VgEK9DCXAI1iXL/93RRoPTN/qwEt'
    b'VbQu1ya6Q4nkLuGMcEGYEjp4UPI8x50GoP9KtS6P38Iwlgt/8t5VI8KicC5Rt1HrivEWe7MD'
    b'ga84JDwpPZ7Lwp4CqPFjyGMRM9mBDUwINxPeH9mIHFd63m2EsMNRGwMbcNYX/e2wiUtmzBo3'
    b'r5Xwc1GY1bbTX6+xRn+QDmDe4BVEf17e4RFe4AY6CW9ZL/GxodduLDQ1b0cd2QrZjv4BYCXU'
    b'7Qqoik4AAAAASUVORK5CYII=')

battery_unknown_dk = PyEmbeddedImage(
    b'iVBORw0KGgoAAAANSUhEUgAAABoAAAAQCAYAAAAI0W+oAAAACXBIWXMAAAMYAAADGAG0VarP'
    b'AAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAAPhJREFUOI3d1L0uRGEQ'
    b'xvHfHksjGoTSVyt7B6LZQn+iVWrptnEBewsuQLMdJT0NiWhEr9BS7nJGcc4RxH7Z3UQ8T6ab'
    b'zD95Zt6X/6YKFnCAmQnMP8MlVLGNI4lbmWyMkDWslCBI0RZehGOhNibQCc5RkycnVdERX3wt'
    b'7AnTI4KiqJ1uoNJPQlNY/QVoCevoyFPrCSr9JlwIu8LUkMA20mTA5gR1tPAgNITFYWg5qJIv'
    b'a0BtoIlHoSXUu/SV0X3MTiVe+0TXzzfCvjD7CfTDMYwOKv1cPJFN3867ipBJzLkfIr5e2ipq'
    b'uQDdKfKbx6HJfEGnuJrA3D+gd4QDpFIjXsUDAAAAAElFTkSuQmCC')

