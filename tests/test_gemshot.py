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


def test_capture_window_returns_pil_image():
    """capture_window returns a PIL Image when PrintWindow succeeds."""
    mock_hwnd = 12345
    mock_rect = (0, 0, 800, 600)
    fake_image = PILImage.new("RGB", (800, 600))

    with patch("win32gui.GetWindowRect", return_value=mock_rect), \
         patch("gemshot._printwindow_capture", return_value=fake_image):
        result = gemshot.capture_window(mock_hwnd)

    assert isinstance(result, PILImage.Image)
    assert result.size == (800, 600)


def test_capture_window_falls_back_to_imagegrab_on_error():
    """capture_window falls back to ImageGrab.grab when PrintWindow fails."""
    mock_hwnd = 12345
    mock_rect = (10, 20, 500, 400)
    fake_image = PILImage.new("RGB", (490, 380))

    with patch("win32gui.GetWindowRect", return_value=mock_rect), \
         patch("gemshot._printwindow_capture", side_effect=RuntimeError("fail")), \
         patch("PIL.ImageGrab.grab", return_value=fake_image) as mock_grab:
        result = gemshot.capture_window(mock_hwnd)

    mock_grab.assert_called_once_with(bbox=(10, 20, 500, 400))
    assert isinstance(result, PILImage.Image)
