# agent-gemshot

Windows CLI tool to screenshot any process window interactively.

## Install

```bash
pip install -e .
```

## Usage

```bash
agent-gemshot
```

Type keywords to filter visible windows, then confirm the desired entry to capture it. If multiple windows share the same label, the prompt appends `hwnd` so each choice stays distinct. The screenshot is saved as `gemshot_YYYYMMDD_HHMMSS.png` in the current directory.

> **Note:** Run from cmd.exe or PowerShell (not Git Bash) for the interactive menu to work correctly.

### AI / Programmatic Usage

**List all capturable windows (JSON):**

```bash
agent-gemshot list
```

Output:

```json
[
  {"hwnd": 12345, "title": "Notepad", "proc": "notepad.exe"},
  {"hwnd": 67890, "title": "Chrome - Google", "proc": "chrome.exe"}
]
```

**Capture a specific window by hwnd:**

```bash
agent-gemshot capture 12345
```

Success output (stdout):

```json
{"path": "C:\\...\\gemshot_20260311_153045.png", "hwnd": 12345, "title": "Notepad", "width": 800, "height": 600}
```

Error output (stderr, exit code 1):

```json
{"error": "hwnd 12345 not found"}
```

## Requirements

- Windows 10+
- Python 3.8+

## Dependencies

- [pywin32](https://pypi.org/project/pywin32/) — Windows API bindings
- [Pillow](https://pypi.org/project/Pillow/) — Image saving
- [questionary](https://pypi.org/project/questionary/) — Interactive CLI menu
- [psutil](https://pypi.org/project/psutil/) — Process name lookup
