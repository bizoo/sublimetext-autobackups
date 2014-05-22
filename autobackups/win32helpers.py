import ctypes
from ctypes.wintypes import LPWSTR, DWORD


# Return the subst path for the drive or the drive when there's no subst
# subst D: -> C:\mypath
# get_mapping('D') -> 'C:\\mypath'
def get_mapping(drive):
    _QueryDosDeviceW = ctypes.windll.kernel32.QueryDosDeviceW
    _QueryDosDeviceW.argtypes = [LPWSTR, LPWSTR, DWORD]
    _QueryDosDeviceW.restype = DWORD

    if not drive:
        drive = None
    ucchMax = 0x1000
    out = ctypes.create_unicode_buffer(u'', ucchMax)
    if _QueryDosDeviceW(LPWSTR(drive), out, ucchMax):
        if out.value[:4] == '\\??\\':
            return out.value[4:]
    return drive
