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

Use arrow keys to select the target window, press Enter to capture. The screenshot is saved as `gemshot_YYYYMMDD_HHMMSS.png` in the current directory.

> **Note:** Run from cmd.exe or PowerShell (not Git Bash) for the interactive menu to work correctly.

## Requirements

- Windows 10+
- Python 3.8+

## Dependencies

- [pywin32](https://pypi.org/project/pywin32/) — Windows API bindings
- [Pillow](https://pypi.org/project/Pillow/) — Image saving
- [questionary](https://pypi.org/project/questionary/) — Interactive CLI menu
- [psutil](https://pypi.org/project/psutil/) — Process name lookup
