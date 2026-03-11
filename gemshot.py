"""agent-gemshot: Screenshot any Windows process window via CLI."""

import argparse
import ctypes
import io
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types
import psutil
import questionary
import win32gui
import win32process
import win32ui
from PIL import Image, ImageGrab


def _is_qt_window(hwnd):
    """Return True when the window class belongs to a Qt top-level window."""
    return win32gui.GetClassName(hwnd).startswith("Qt")


def _printwindow_capture(hwnd, width, height):
    """Capture a window using user32.PrintWindow."""
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bmp)

    try:
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
        if not result:
            raise RuntimeError("PrintWindow returned 0")

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        return Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bits,
            "raw",
            "BGRX",
            0,
            1,
        )
    finally:
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


def list_windows():
    """Return [(hwnd, title, proc_name)] for visible titled Qt windows."""
    results = []

    def _callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        if win32gui.IsIconic(hwnd):
            return
        if not _is_qt_window(hwnd):
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


def _build_choice_map(windows):
    """Return display-label-to-hwnd mapping for interactive selection."""
    base_counts = {}

    for _, title, proc in windows:
        base_label = f"[{proc}] {title}"
        base_counts[base_label] = base_counts.get(base_label, 0) + 1

    choice_map = {}
    for hwnd, title, proc in windows:
        base_label = f"[{proc}] {title}"
        label = base_label
        if base_counts[base_label] > 1:
            label = f"{base_label} (hwnd: {hwnd})"
        choice_map[label] = hwnd

    return choice_map


def capture_window(hwnd):
    """Capture a Qt window by hwnd."""
    if win32gui.IsIconic(hwnd):
        raise RuntimeError(f"hwnd {hwnd} is minimized")
    if not _is_qt_window(hwnd):
        raise RuntimeError(f"hwnd {hwnd} is not a Qt window")

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    try:
        return _printwindow_capture(hwnd, width, height)
    except Exception:
        try:
            return ImageGrab.grab(window=hwnd)
        except Exception:
            return ImageGrab.grab(
                bbox=(left, top, right, bottom),
                all_screens=True,
            )


def save_image(img):
    """Save PIL Image to cwd with timestamp filename. Returns the file path."""
    filename = datetime.now().strftime("gemshot_%Y%m%d_%H%M%S.png")
    path = os.path.join(os.getcwd(), filename)
    img.save(path)
    return path


def analyze_with_gemini(img, prompt):
    """Send PIL Image + prompt to Gemini and return the reply text.

    Reads GEMINI_API_KEY, GEMINI_MODEL, GOOGLE_GEMINI_BASE_URL from environment.
    Raises ValueError if GEMINI_API_KEY is not set.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    base_url = os.environ.get("GOOGLE_GEMINI_BASE_URL", "")

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["http_options"] = {"base_url": base_url}

    client = genai.Client(**client_kwargs)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
            prompt,
        ],
    )
    return response.text


def cmd_list():
    """Print all visible windows as a JSON array to stdout."""
    windows = list_windows()
    print(json.dumps([
        {"hwnd": hwnd, "title": title, "proc": proc}
        for hwnd, title, proc in windows
    ]))


def cmd_capture(hwnd: int, prompt: str):
    """Capture window by hwnd, analyze with Gemini; print JSON result to stdout."""
    windows = list_windows()
    title = next((t for h, t, _ in windows if h == hwnd), None)
    if title is None:
        print(json.dumps({"error": f"hwnd {hwnd} not found"}), file=sys.stderr)
        sys.exit(1)

    try:
        img = capture_window(hwnd)
        reply = analyze_with_gemini(img, prompt)
        print(json.dumps({
            "hwnd": hwnd,
            "title": title,
            "width": img.width,
            "height": img.height,
            "prompt": prompt,
            "gemini_reply": reply,
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


def main():
    """CLI entry point. No args → interactive. Subcommands: list, capture <hwnd>."""
    parser = argparse.ArgumentParser(
        prog="agent-gemshot",
        description="Screenshot visible Qt/PyQt/PySide windows.",
    )
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("list", help="Print visible windows as JSON array.")

    capture_parser = subparsers.add_parser("capture", help="Screenshot a window by hwnd.")
    capture_parser.add_argument("hwnd", type=int, help="Window handle (from 'list').")

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list()
        return
    if args.cmd == "capture":
        cmd_capture(args.hwnd)
        return

    # No subcommand: original interactive mode
    windows = list_windows()
    if not windows:
        print("未找到可用窗口。")
        sys.exit(0)

    choice_map = _build_choice_map(windows)

    try:
        choice = questionary.autocomplete(
            "选择要截图的窗口（输入关键词过滤，回车确认，Ctrl+C 退出）:",
            choices=list(choice_map),
            match_middle=True,
            validate=lambda value: value in choice_map,
        ).ask()
    except KeyboardInterrupt:
        sys.exit(0)

    if choice is None:
        sys.exit(0)

    hwnd = choice_map.get(choice)
    if hwnd is None:
        sys.exit(0)

    try:
        img = capture_window(hwnd)
        path = save_image(img)
        print(f"截图已保存: {path}")
    except PermissionError:
        print("错误: 当前目录无写入权限，请切换目录后重试。")
        sys.exit(1)
    except Exception as e:
        print(f"截图失败: {e}")
        sys.exit(1)
