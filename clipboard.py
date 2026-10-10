"""Windows clipboard helper that keeps secrets out of Win+V history and cloud sync.

Copies the text with three extra flags Windows (and many clipboard managers) respect:
  - CanIncludeInClipboardHistory = 0   -> not saved in Win+V history
  - CanUploadToCloudClipboard    = 0   -> not synced to other devices
  - ExcludeClipboardContentFromMonitorProcessing -> clipboard monitors skip it
On non-Windows systems or on failure, functions return False so the caller can
fall back to Tkinter's normal clipboard.
"""
import sys
import time

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.GetClipboardData.restype = wintypes.HANDLE
    _user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    _user32.RegisterClipboardFormatW.restype = wintypes.UINT

    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.restype = wintypes.BOOL
    _kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalFree.restype = wintypes.HGLOBAL

    _EXCLUDE_FORMATS = (
        "ExcludeClipboardContentFromMonitorProcessing",
        "CanIncludeInClipboardHistory",
        "CanUploadToCloudClipboard",
    )

    def _open(hwnd) -> bool:
        # The clipboard can be briefly locked by another app, so retry a few times.
        for _ in range(20):
            if _user32.OpenClipboard(hwnd):
                return True
            time.sleep(0.025)
        return False

    def _alloc(data: bytes):
        handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return None
        ptr = _kernel32.GlobalLock(handle)
        if not ptr:
            _kernel32.GlobalFree(handle)
            return None
        ctypes.memmove(ptr, data, len(data))
        _kernel32.GlobalUnlock(handle)
        return handle

    def _set(fmt: int, data: bytes) -> bool:
        handle = _alloc(data)
        if not handle:
            return False
        if not _user32.SetClipboardData(fmt, handle):
            _kernel32.GlobalFree(handle)   # only free on failure; on success Windows owns it
            return False
        return True


def copy_secret(text: str, hwnd: int) -> bool:
    """Copy text to the clipboard, excluded from history/cloud sync. True on success."""
    if not IS_WINDOWS:
        return False
    try:
        if not _open(hwnd):
            return False
        try:
            _user32.EmptyClipboard()
            ok = _set(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            for name in _EXCLUDE_FORMATS:
                fmt = _user32.RegisterClipboardFormatW(name)
                if fmt:
                    _set(fmt, b"\x00\x00\x00\x00")
            return ok
        finally:
            _user32.CloseClipboard()
    except Exception:
        return False


def clear_if_equal(text: str, hwnd: int) -> bool:
    """Empty the clipboard only if it still contains `text`. True if handled on Windows."""
    if not IS_WINDOWS:
        return False
    try:
        if not _open(hwnd):
            return False
        try:
            handle = _user32.GetClipboardData(CF_UNICODETEXT)
            current = None
            if handle:
                ptr = _kernel32.GlobalLock(handle)
                if ptr:
                    try:
                        current = ctypes.wstring_at(ptr)
                    finally:
                        _kernel32.GlobalUnlock(handle)
            if current == text:
                _user32.EmptyClipboard()
            return True
        finally:
            _user32.CloseClipboard()
    except Exception:
        return False