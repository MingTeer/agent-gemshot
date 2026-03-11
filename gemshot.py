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
    pass


def capture_window(hwnd):
    pass


def save_image(img):
    pass


def main():
    pass
