"""agent-gemshot: Screenshot any Windows process window via CLI."""

import os
import sys
from datetime import datetime

import psutil
import questionary
import win32con
import win32gui
import win32process
import win32ui
from PIL import Image, ImageGrab


def list_windows():
    """Return [(hwnd, title, proc_name)] for all visible titled windows."""
    results = []

    def _callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc_name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            proc_name = "unknown"
        results.append((hwnd, title, proc_name))

    win32gui.EnumWindows(_callback, None)
    return results


def _printwindow_capture(hwnd, width, height):
    """Capture window using Win32 PrintWindow. Raises RuntimeError on failure."""
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bmp)

    # PW_RENDERFULLCONTENT (2) captures GPU/DX accelerated content too
    result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    if not result:
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        raise RuntimeError("PrintWindow returned 0")

    bmp_info = bmp.GetInfo()
    bmp_bits = bmp.GetBitmapBits(True)
    img = Image.frombuffer(
        "RGB",
        (bmp_info["bmWidth"], bmp_info["bmHeight"]),
        bmp_bits,
        "raw",
        "BGRX",
        0,
        1,
    )

    win32gui.DeleteObject(bmp.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img


def capture_window(hwnd):
    """Capture window by hwnd. Returns PIL Image. Falls back to screen grab on failure."""
    win32gui.SetForegroundWindow(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    try:
        return _printwindow_capture(hwnd, width, height)
    except Exception:
        return ImageGrab.grab(bbox=(left, top, right, bottom))


def save_image(img):
    """Save PIL Image to cwd with timestamp filename. Returns the file path."""
    filename = datetime.now().strftime("gemshot_%Y%m%d_%H%M%S.png")
    path = os.path.join(os.getcwd(), filename)
    img.save(path)
    return path


def main():
    pass
