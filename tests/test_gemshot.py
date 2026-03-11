from unittest.mock import patch, MagicMock
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
