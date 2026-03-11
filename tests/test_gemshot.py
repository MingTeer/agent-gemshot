import contextlib
import json
import os
import re
from io import StringIO
from unittest.mock import patch

import pytest
import psutil
from PIL import Image as PILImage
import gemshot


def test_list_windows_returns_visible_qt_windows_with_titles():
    """list_windows returns (hwnd, title, proc_name) for visible Qt windows."""
    mock_hwnd = 12345
    mock_pid = 999

    def fake_enum(callback, extra):
        callback(mock_hwnd, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"), \
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


def test_list_windows_skips_non_qt_windows():
    """list_windows excludes visible non-Qt windows."""
    def fake_enum(callback, extra):
        callback(99, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Chrome_WidgetWin_1"), \
         patch("win32gui.GetWindowText", return_value="Browser"):
        result = gemshot.list_windows()

    assert result == []


def test_list_windows_skips_empty_title_windows():
    """list_windows excludes windows with empty titles."""
    def fake_enum(callback, extra):
        callback(99, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"), \
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
         patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"), \
         patch("win32gui.GetWindowText", return_value="Some Window"), \
         patch("win32process.GetWindowThreadProcessId", return_value=(0, mock_pid)), \
         patch("psutil.Process") as mock_proc:
        mock_proc.return_value.name.side_effect = psutil.NoSuchProcess(pid=mock_pid)
        result = gemshot.list_windows()

    assert result == [(mock_hwnd, "Some Window", "unknown")]


def test_list_windows_skips_minimized_windows():
    """list_windows excludes minimized windows even if IsWindowVisible is True."""
    def fake_enum(callback, extra):
        callback(99, extra)

    with patch("win32gui.EnumWindows", side_effect=fake_enum), \
         patch("win32gui.IsWindowVisible", return_value=True), \
         patch("win32gui.IsIconic", return_value=True), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"), \
         patch("win32gui.GetWindowText", return_value="Minimized"):
        result = gemshot.list_windows()

    assert result == []


def test_build_choice_map_disambiguates_duplicate_labels():
    """duplicate window labels keep both hwnd values accessible."""
    windows = [
        (101, "Shared Title", "same.exe"),
        (202, "Shared Title", "same.exe"),
    ]

    result = gemshot._build_choice_map(windows)

    assert result == {
        "[same.exe] Shared Title (hwnd: 101)": 101,
        "[same.exe] Shared Title (hwnd: 202)": 202,
    }


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


def test_capture_window_raises_on_minimized_window():
    """capture_window rejects minimized windows instead of returning a black image."""
    mock_hwnd = 12345

    with patch("win32gui.IsIconic", return_value=True), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"):
        with pytest.raises(RuntimeError, match="minimized"):
            gemshot.capture_window(mock_hwnd)


def test_capture_window_raises_on_non_qt_window():
    """capture_window rejects non-Qt windows."""
    mock_hwnd = 12345

    with patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Chrome_WidgetWin_1"):
        with pytest.raises(RuntimeError, match="Qt"):
            gemshot.capture_window(mock_hwnd)


def test_capture_window_uses_printwindow_for_qt_windows():
    """Qt/PySide windows prefer native PrintWindow capture."""
    mock_hwnd = 12345
    fake_image = PILImage.new("RGB", (380, 160))

    with patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetClassName", return_value="Qt6102QWindowIcon"), \
         patch("win32gui.GetWindowRect", return_value=(10, 20, 390, 180)), \
         patch("gemshot._printwindow_capture", return_value=fake_image) as mock_print, \
         patch("PIL.ImageGrab.grab") as mock_grab:
        result = gemshot.capture_window(mock_hwnd)

    mock_print.assert_called_once_with(mock_hwnd, 380, 160)
    mock_grab.assert_not_called()
    assert isinstance(result, PILImage.Image)


def test_capture_window_qt_falls_back_to_window_then_bbox():
    """Qt/PySide windows fall back from PrintWindow to window capture to bbox capture."""
    mock_hwnd = 12345
    mock_rect = (10, 20, 500, 400)
    fake_image = PILImage.new("RGB", (490, 380))

    with patch("win32gui.IsIconic", return_value=False), \
         patch("win32gui.GetWindowRect", return_value=mock_rect), \
         patch("win32gui.GetClassName", return_value="Qt5152QWindowIcon"), \
         patch("gemshot._printwindow_capture", side_effect=RuntimeError("printwindow failed")), \
         patch(
             "PIL.ImageGrab.grab",
             side_effect=[RuntimeError("window capture failed"), fake_image],
         ) as mock_grab:
        result = gemshot.capture_window(mock_hwnd)

    assert mock_grab.call_args_list == [
        ((), {"window": mock_hwnd}),
        ((), {"bbox": (10, 20, 500, 400), "all_screens": True}),
    ]
    assert isinstance(result, PILImage.Image)

def test_main_exits_with_message_when_no_windows():
    """main prints a message and exits cleanly when no windows are available."""
    stdout = StringIO()

    with patch("gemshot.list_windows", return_value=[]), \
         patch("sys.argv", ["agent-gemshot"]), \
         contextlib.redirect_stdout(stdout), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.main()

    assert exc_info.value.code == 0
    assert stdout.getvalue().strip() == "未找到可用窗口。"


def test_main_uses_autocomplete_choice_mapping():
    """main uses autocomplete labels and maps the chosen label back to hwnd."""
    stdout = StringIO()
    image = PILImage.new("RGB", (1, 1))
    windows = [
        (101, "Alpha Window", "alpha.exe"),
        (202, "Beta Window", "beta.exe"),
    ]

    with patch("gemshot.list_windows", return_value=windows), \
         patch("questionary.select", side_effect=AssertionError("select should not be used")), \
         patch("questionary.autocomplete") as mock_autocomplete, \
         patch("gemshot.capture_window", return_value=image) as mock_capture, \
         patch("gemshot.save_image", return_value=r"C:\tmp\gemshot_20260311_120000.png"), \
         patch("sys.argv", ["agent-gemshot"]), \
         contextlib.redirect_stdout(stdout):
        mock_autocomplete.return_value.ask.return_value = "[beta.exe] Beta Window"
        gemshot.main()

    assert mock_autocomplete.call_args.kwargs["choices"] == [
        "[alpha.exe] Alpha Window",
        "[beta.exe] Beta Window",
    ]
    mock_capture.assert_called_once_with(202)
    assert "截图已保存: C:\\tmp\\gemshot_20260311_120000.png" in stdout.getvalue()


def test_main_exits_when_autocomplete_returns_unknown_label():
    """main exits cleanly when autocomplete returns a label outside known choices."""
    windows = [(101, "Alpha Window", "alpha.exe")]

    with patch("gemshot.list_windows", return_value=windows), \
         patch("questionary.select", side_effect=AssertionError("select should not be used")), \
         patch("questionary.autocomplete") as mock_autocomplete, \
         patch("sys.argv", ["agent-gemshot"]), \
         pytest.raises(SystemExit) as exc_info:
        mock_autocomplete.return_value.ask.return_value = "not-a-real-choice"
        gemshot.main()

    assert exc_info.value.code == 0


def test_cmd_list_outputs_json_array(capsys):
    """cmd_list prints a JSON array of {hwnd, title, proc} to stdout."""
    windows = [
        (101, "Qt Login", "python.exe"),
        (202, "Qt Settings", "python.exe"),
    ]
    with patch("gemshot.list_windows", return_value=windows):
        gemshot.cmd_list()

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data == [
        {"hwnd": 101, "title": "Qt Login", "proc": "python.exe"},
        {"hwnd": 202, "title": "Qt Settings", "proc": "python.exe"},
    ]


def test_cmd_list_outputs_empty_array_when_no_windows(capsys):
    """cmd_list prints [] when no visible windows exist."""
    with patch("gemshot.list_windows", return_value=[]):
        gemshot.cmd_list()

    out = capsys.readouterr().out
    assert json.loads(out) == []


def test_cmd_capture_outputs_json_on_success(capsys, tmp_path, monkeypatch):
    """cmd_capture prints JSON {path, hwnd, title, width, height} on success."""
    monkeypatch.chdir(tmp_path)
    windows = [(12345, "Qt Login", "python.exe")]
    fake_img = PILImage.new("RGB", (380, 160))

    with patch("gemshot.list_windows", return_value=windows), \
         patch("gemshot.capture_window", return_value=fake_img):
        gemshot.cmd_capture(12345)

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["hwnd"] == 12345
    assert data["title"] == "Qt Login"
    assert data["width"] == 380
    assert data["height"] == 160
    assert data["path"].endswith(".png")


def test_cmd_capture_prints_error_and_exits_when_hwnd_not_found(capsys):
    """cmd_capture writes JSON error to stderr and exits 1 when hwnd is unknown."""
    windows = [(99999, "Other", "other.exe")]

    with patch("gemshot.list_windows", return_value=windows), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.cmd_capture(12345)

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    data = json.loads(err)
    assert "not found" in data["error"]


def test_cmd_capture_prints_error_and_exits_on_capture_failure(capsys, tmp_path, monkeypatch):
    """cmd_capture writes JSON error to stderr and exits 1 when capture raises."""
    monkeypatch.chdir(tmp_path)
    windows = [(12345, "Qt Login", "python.exe")]

    with patch("gemshot.list_windows", return_value=windows), \
         patch("gemshot.capture_window", side_effect=Exception("win32 error")), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.cmd_capture(12345)

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    data = json.loads(err)
    assert "win32 error" in data["error"]


def test_main_routes_list_subcommand():
    """main() with ['list'] calls cmd_list()."""
    with patch("gemshot.cmd_list") as mock_list, \
         patch("sys.argv", ["agent-gemshot", "list"]):
        gemshot.main()

    mock_list.assert_called_once()


def test_main_routes_capture_subcommand():
    """main() with ['capture', '12345'] calls cmd_capture(12345)."""
    with patch("gemshot.cmd_capture") as mock_capture, \
         patch("sys.argv", ["agent-gemshot", "capture", "12345"]):
        gemshot.main()

    mock_capture.assert_called_once_with(12345)


def test_main_capture_rejects_non_integer_hwnd():
    """main() with ['capture', 'abc'] exits with code 2 (argparse error)."""
    with patch("sys.argv", ["agent-gemshot", "capture", "abc"]), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.main()

    assert exc_info.value.code == 2


def test_main_falls_through_to_interactive_when_no_subcommand():
    """main() with no args calls the interactive flow, not cmd_list/cmd_capture."""
    with patch("gemshot.cmd_list") as mock_list, \
         patch("gemshot.cmd_capture") as mock_capture, \
         patch("gemshot.list_windows", return_value=[]), \
         patch("sys.argv", ["agent-gemshot"]), \
         pytest.raises(SystemExit):  # exits 0 on empty window list
        gemshot.main()

    mock_list.assert_not_called()
    mock_capture.assert_not_called()
