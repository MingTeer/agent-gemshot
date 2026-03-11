# gemini-capture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend `agent-gemshot capture <hwnd> --prompt "..."` to send the captured screenshot to Gemini for analysis and return the reply as JSON — image is never saved to disk.

**Architecture:** Add `analyze_with_gemini(img, prompt)` that converts a PIL Image to PNG bytes in-memory via `io.BytesIO` and calls the `google-genai` SDK. Modify `cmd_capture(hwnd, prompt)` to call it instead of `save_image()`. Load API config from `.env` via `python-dotenv` at `main()` entry.

**Tech Stack:** Python 3.8+, google-genai SDK, python-dotenv, existing pywin32/Pillow stack, pytest + unittest.mock

---

### Task 1: Add dependencies and create .env files

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `.env.example`
- Modify: `.gitignore`

**Step 1: Add new deps to `pyproject.toml`**

In the `dependencies` list, add two entries:

```toml
[project]
dependencies = [
    "pywin32",
    "Pillow",
    "questionary",
    "psutil",
    "google-genai",
    "python-dotenv",
]
```

**Step 2: Add new deps to `requirements.txt`**

```
pywin32
Pillow
questionary
psutil
google-genai
python-dotenv
```

**Step 3: Create `.env.example`**

```
GEMINI_API_KEY=sk-your-key-here
GEMINI_MODEL=gemini-2.0-flash
GOOGLE_GEMINI_BASE_URL=https://vip.claude-codex.cn
```

`GOOGLE_GEMINI_BASE_URL` is optional. If absent, the SDK uses the official Google endpoint.

**Step 4: Add `.env` to `.gitignore`**

Append to `.gitignore`:

```
.env
```

(`.env.example` is intentionally NOT ignored — it's safe to commit as a template.)

**Step 5: Install new packages**

```bash
pip install google-genai python-dotenv
```

Expected: packages install without error.

**Step 6: Create `.env` with real credentials**

Copy `.env.example` to `.env` and fill in the real values. This file is gitignored and never committed.

**Step 7: Commit**

```bash
git add pyproject.toml requirements.txt .env.example .gitignore
git commit -m "chore: add google-genai and python-dotenv dependencies"
```

---

### Task 2: Implement `analyze_with_gemini(img, prompt)` (TDD)

**Files:**
- Modify: `gemshot.py`
- Modify: `tests/test_gemshot.py`

**Step 1: Add imports to `gemshot.py`**

At the top of `gemshot.py`, add these two imports alongside the existing ones:

```python
import io

from dotenv import load_dotenv
```

Do NOT add `google.genai` imports at the top level — import inside the function to keep load time fast and avoid import errors when Gemini isn't needed (e.g., `list` subcommand).

**Step 2: Write the failing tests**

Add to the end of `tests/test_gemshot.py`:

```python
# ---------------------------------------------------------------------------
# analyze_with_gemini
# ---------------------------------------------------------------------------

def test_analyze_with_gemini_calls_sdk_and_returns_text(monkeypatch):
    """analyze_with_gemini sends PNG bytes + prompt to Gemini and returns reply text."""
    from unittest.mock import MagicMock, patch as _patch
    from PIL import Image as PILImage

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.delenv("GOOGLE_GEMINI_BASE_URL", raising=False)

    fake_response = MagicMock()
    fake_response.text = "界面看起来正常。"

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    img = PILImage.new("RGB", (100, 100), color=(0, 128, 255))

    with _patch("gemshot.genai.Client", return_value=fake_client) as mock_client_cls:
        result = gemshot.analyze_with_gemini(img, "分析这个界面")

    assert result == "界面看起来正常。"
    mock_client_cls.assert_called_once_with(api_key="test-key")
    fake_client.models.generate_content.assert_called_once()
    call_kwargs = fake_client.models.generate_content.call_args
    assert call_kwargs.kwargs["model"] == "gemini-test-model"


def test_analyze_with_gemini_passes_base_url_when_set(monkeypatch):
    """analyze_with_gemini sets http_options when GOOGLE_GEMINI_BASE_URL is present."""
    from unittest.mock import MagicMock, patch as _patch
    from PIL import Image as PILImage

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", "https://proxy.example.com")

    fake_response = MagicMock()
    fake_response.text = "ok"
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    img = PILImage.new("RGB", (10, 10))

    with _patch("gemshot.genai.Client", return_value=fake_client) as mock_client_cls:
        gemshot.analyze_with_gemini(img, "test prompt")

    mock_client_cls.assert_called_once_with(
        api_key="test-key",
        http_options={"base_url": "https://proxy.example.com"},
    )


def test_analyze_with_gemini_raises_when_api_key_missing(monkeypatch):
    """analyze_with_gemini raises ValueError when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (10, 10))
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        gemshot.analyze_with_gemini(img, "test")
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/test_gemshot.py::test_analyze_with_gemini_calls_sdk_and_returns_text tests/test_gemshot.py::test_analyze_with_gemini_passes_base_url_when_set tests/test_gemshot.py::test_analyze_with_gemini_raises_when_api_key_missing -v
```

Expected: 3 FAILED — `AttributeError: module 'gemshot' has no attribute 'analyze_with_gemini'`

**Step 4: Implement `analyze_with_gemini()` in `gemshot.py`**

Add this import near the top (alongside `from google import genai` — add at module level):

```python
from google import genai
from google.genai import types
```

Then add the function after `save_image()`:

```python
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
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_gemshot.py::test_analyze_with_gemini_calls_sdk_and_returns_text tests/test_gemshot.py::test_analyze_with_gemini_passes_base_url_when_set tests/test_gemshot.py::test_analyze_with_gemini_raises_when_api_key_missing -v
```

Expected: 3 PASSED.

**Step 6: Run the full test suite to check nothing is broken**

```bash
pytest tests/ -v
```

Expected: all previously passing tests still PASS.

**Step 7: Commit**

```bash
git add gemshot.py tests/test_gemshot.py
git commit -m "feat: implement analyze_with_gemini() with google-genai SDK"
```

---

### Task 3: Modify `cmd_capture` to accept `prompt` and call Gemini

**Files:**
- Modify: `gemshot.py`
- Modify: `tests/test_gemshot.py`

**Step 1: Update existing `cmd_capture` tests to match new signature**

In `tests/test_gemshot.py`, replace the three existing `test_cmd_capture_*` tests with these updated versions:

```python
def test_cmd_capture_outputs_json_on_success(capsys):
    """cmd_capture prints JSON with gemini_reply on success; no path field."""
    windows = [(12345, "Qt Login", "python.exe")]
    fake_img = PILImage.new("RGB", (380, 160))

    with patch("gemshot.list_windows", return_value=windows), \
         patch("gemshot.capture_window", return_value=fake_img), \
         patch("gemshot.analyze_with_gemini", return_value="界面正常"):
        gemshot.cmd_capture(12345, "分析界面")

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["hwnd"] == 12345
    assert data["title"] == "Qt Login"
    assert data["width"] == 380
    assert data["height"] == 160
    assert data["prompt"] == "分析界面"
    assert data["gemini_reply"] == "界面正常"
    assert "path" not in data


def test_cmd_capture_prints_error_and_exits_when_hwnd_not_found(capsys):
    """cmd_capture writes JSON error to stderr and exits 1 when hwnd is unknown."""
    windows = [(99999, "Other", "other.exe")]

    with patch("gemshot.list_windows", return_value=windows), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.cmd_capture(12345, "test prompt")

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    data = json.loads(err)
    assert "not found" in data["error"]


def test_cmd_capture_prints_error_and_exits_on_capture_failure(capsys):
    """cmd_capture writes JSON error to stderr and exits 1 when capture raises."""
    windows = [(12345, "Qt Login", "python.exe")]

    with patch("gemshot.list_windows", return_value=windows), \
         patch("gemshot.capture_window", side_effect=Exception("win32 error")), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.cmd_capture(12345, "test prompt")

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    data = json.loads(err)
    assert "win32 error" in data["error"]


def test_cmd_capture_prints_error_when_api_key_missing(capsys, monkeypatch):
    """cmd_capture exits 1 with JSON error when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    windows = [(12345, "Qt Login", "python.exe")]
    fake_img = PILImage.new("RGB", (100, 100))

    with patch("gemshot.list_windows", return_value=windows), \
         patch("gemshot.capture_window", return_value=fake_img), \
         patch("gemshot.analyze_with_gemini", side_effect=ValueError("GEMINI_API_KEY not set")), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.cmd_capture(12345, "test prompt")

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    data = json.loads(err)
    assert "GEMINI_API_KEY" in data["error"]
```

**Step 2: Run updated tests to verify they fail**

```bash
pytest tests/test_gemshot.py::test_cmd_capture_outputs_json_on_success tests/test_gemshot.py::test_cmd_capture_prints_error_and_exits_when_hwnd_not_found tests/test_gemshot.py::test_cmd_capture_prints_error_and_exits_on_capture_failure tests/test_gemshot.py::test_cmd_capture_prints_error_when_api_key_missing -v
```

Expected: failures because `cmd_capture` still only takes one argument and still calls `save_image`.

**Step 3: Rewrite `cmd_capture` in `gemshot.py`**

Replace the existing `cmd_capture` function:

```python
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
```

**Step 4: Run updated tests to verify they pass**

```bash
pytest tests/test_gemshot.py::test_cmd_capture_outputs_json_on_success tests/test_gemshot.py::test_cmd_capture_prints_error_and_exits_when_hwnd_not_found tests/test_gemshot.py::test_cmd_capture_prints_error_and_exits_on_capture_failure tests/test_gemshot.py::test_cmd_capture_prints_error_when_api_key_missing -v
```

Expected: 4 PASSED.

**Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: `test_main_routes_capture_subcommand` will now FAIL because it still calls `cmd_capture(12345)` with no prompt. That's expected — we'll fix it in Task 4.

**Step 6: Commit**

```bash
git add gemshot.py tests/test_gemshot.py
git commit -m "feat: cmd_capture sends screenshot to Gemini, returns gemini_reply JSON"
```

---

### Task 4: Update `main()` — load dotenv, add `--prompt` to capture subcommand

**Files:**
- Modify: `gemshot.py`
- Modify: `tests/test_gemshot.py`

**Step 1: Update `test_main_routes_capture_subcommand` in `tests/test_gemshot.py`**

Replace the existing test:

```python
def test_main_routes_capture_subcommand():
    """main() with ['capture', '12345', '--prompt', '...'] calls cmd_capture(12345, prompt)."""
    with patch("gemshot.cmd_capture") as mock_capture, \
         patch("sys.argv", ["agent-gemshot", "capture", "12345", "--prompt", "分析界面"]):
        gemshot.main()

    mock_capture.assert_called_once_with(12345, "分析界面")
```

Also add a test for missing `--prompt`:

```python
def test_main_capture_requires_prompt():
    """main() with ['capture', '12345'] (no --prompt) exits with code 2."""
    with patch("sys.argv", ["agent-gemshot", "capture", "12345"]), \
         pytest.raises(SystemExit) as exc_info:
        gemshot.main()

    assert exc_info.value.code == 2
```

**Step 2: Run new/updated tests to verify they fail**

```bash
pytest tests/test_gemshot.py::test_main_routes_capture_subcommand tests/test_gemshot.py::test_main_capture_requires_prompt -v
```

Expected: `test_main_routes_capture_subcommand` FAILS (wrong call args), `test_main_capture_requires_prompt` FAILS (no `--prompt`, but argparse doesn't enforce it yet).

**Step 3: Update `main()` in `gemshot.py`**

Replace the full `main()` function:

```python
def main():
    """CLI entry point. No args → interactive. Subcommands: list, capture <hwnd> --prompt."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="agent-gemshot",
        description="Screenshot visible Qt/PyQt/PySide windows.",
    )
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("list", help="Print visible windows as JSON array.")

    capture_parser = subparsers.add_parser("capture", help="Screenshot a window by hwnd.")
    capture_parser.add_argument("hwnd", type=int, help="Window handle (from 'list').")
    capture_parser.add_argument(
        "--prompt",
        required=True,
        help="Analysis prompt sent to Gemini along with the screenshot.",
    )

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list()
        return
    if args.cmd == "capture":
        cmd_capture(args.hwnd, args.prompt)
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
```

Note: `load_dotenv()` is called at the top of `main()`. The `from dotenv import load_dotenv` import should be moved to the top-level imports in `gemshot.py` (it's already added in Task 2).

**Step 4: Run new/updated tests to verify they pass**

```bash
pytest tests/test_gemshot.py::test_main_routes_capture_subcommand tests/test_gemshot.py::test_main_capture_requires_prompt -v
```

Expected: 2 PASSED.

**Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: ALL tests PASS.

**Step 6: Manual smoke test**

First, list available windows:

```bash
agent-gemshot list
```

Expected: JSON array of Qt windows.

Pick an `hwnd` from the output and run:

```bash
agent-gemshot capture <hwnd> --prompt "这个界面显示的是什么内容？"
```

Expected output (JSON):
```json
{
  "hwnd": 12345,
  "title": "...",
  "width": 800,
  "height": 600,
  "prompt": "这个界面显示的是什么内容？",
  "gemini_reply": "..."
}
```

Verify no PNG file is created in the current directory.

**Step 7: Commit**

```bash
git add gemshot.py tests/test_gemshot.py
git commit -m "feat: load .env in main(), add --prompt to capture subcommand"
```

---

## Done

`agent-gemshot capture <hwnd> --prompt "..."` now:
1. Captures the target Qt window as a PIL Image (no disk I/O)
2. Converts to PNG bytes in memory via `io.BytesIO`
3. Sends to Gemini via `google-genai` SDK using credentials from `.env`
4. Returns JSON `{ hwnd, title, width, height, prompt, gemini_reply }` to stdout
5. Never writes an image file
