import os
import re
from unittest.mock import patch, MagicMock
import psutil
from PIL import Image as PILImage
import gemshot


def test_list_windows_returns_visible_windows_with_titles():
    """list_windows returns (hwnd, title, proc_name) for visible titled windows."""
    mock_hwnd = 12345
    mock_pid = 999

    def fake_enum(callback, extra):
        callback(mock_hwnd, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.GetWindowText", return_value="My Window"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(0, mock_pid)), \
         patch("psutil.Process") as mock_proc:
        mock_proc.return_value.name.return_value = "myapp.exe"
        result = gemshot.list_windows()

    assert result == [(mock_hwnd, "My Window", "myapp.exe")]


def test_list_windows_skips_invisible_windows():
    """list_windows excludes windows where IsWindowVisible is False."""
    def fake_enum(callback, extra):
        callback(99, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=False), \
         patch("win32gui.GetWindowText", return_value="Invisible"):
        result = gemshot.list_windows()

    assert result == []


def test_list_windows_skips_empty_title_windows():
    """list_windows excludes windows with empty titles."""
    def fake_enum(callback, extra):
        callback(99, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.GetWindowText", return_value=""):
        result = gemshot.list_windows()

    assert result == []


def test_list_windows_uses_unknown_for_inaccessible_processes():
    """list_windows uses 'unknown' as proc_name when psutil raises access errors."""
    mock_hwnd = 12345
    mock_pid = 999

    def fake_enum(callback, extra):
        callback(mock_hwnd, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.GetWindowText", return_value="Some Window"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(0, mock_pid)), \
         patch("psutil.Process") as mock_proc:
        mock_proc.return_value.name.side_effect = psutil.NoSuchProcess(pid=mock_pid)
        result = gemshot.list_windows()

    assert result == [(mock_hwnd, "Some Window", "unknown")]


def test_save_image_creates_png_in_cwd(tmp_path, monkeypatch):
    """save_image saves a PNG with timestamp name in current directory."""
    monkeypatch.chdir(tmp_path)
    img = PILImage.new("RGB", (100, 100), color=(255, 0, 0))
    path = gemshot.save_image(img)

    assert os.path.exists(path)
    assert path.startswith(str(tmp_path))
    assert path.endswith(".png")
    assert "gemshot_" in path


def test_save_image_filename_format(tmp_path, monkeypatch):
    """save_image filename matches gemshot_YYYYMMDD_HHMMSS.png pattern."""
    monkeypatch.chdir(tmp_path)
    img = PILImage.new("RGB", (10, 10))
    path = gemshot.save_image(img)
    filename = os.path.basename(path)
    assert re.match(r"gemshot_\d{8}_\d{6}\.png", filename)
