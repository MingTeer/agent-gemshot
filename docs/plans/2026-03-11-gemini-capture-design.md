# gemini-capture 设计文档

**日期：** 2026-03-11

---

## 概述

为 `agent-gemshot capture` 子命令添加 Gemini 视觉分析能力。用户指定窗口句柄和提示词，工具截图后将图片以内存字节流方式发送给 Gemini SDK，返回分析结果 JSON，图片不写入磁盘。

---

## CLI 接口

```bash
agent-gemshot capture <hwnd> --prompt "这个界面有什么问题？"
```

`--prompt` 为必填参数。

**成功输出（stdout）：**

```json
{
  "hwnd": 12345,
  "title": "My Window",
  "width": 800,
  "height": 600,
  "prompt": "这个界面有什么问题？",
  "gemini_reply": "界面左上角有一个错误提示..."
}
```

**失败输出（stderr，exit 1）：**

```json
{"error": "<原因>"}
```

---

## 配置（.env）

项目根目录 `.env` 文件，已在 `.gitignore` 中排除：

```
GEMINI_API_KEY=sk-xxx
GEMINI_MODEL=gemini-2.0-flash
GOOGLE_GEMINI_BASE_URL=https://vip.claude-codex.cn
```

`GOOGLE_GEMINI_BASE_URL` 可选；不填时 SDK 使用官方端点。

---

## 核心组件

### 新增：`analyze_with_gemini(img, prompt) -> str`

1. 从 `os.environ` 读取 `GEMINI_API_KEY`、`GEMINI_MODEL`、`GOOGLE_GEMINI_BASE_URL`
2. PIL Image → `io.BytesIO` → PNG bytes（全程内存，不落盘）
3. 构造 `google-genai` SDK client，`GOOGLE_GEMINI_BASE_URL` 非空时传入 `http_options={"base_url": ...}`
4. 调用 `client.models.generate_content(model, contents=[Part.from_bytes(...), prompt])`
5. 返回 `response.text`

### 修改：`cmd_capture(hwnd, prompt)`

```
validate hwnd ∈ list_windows()
  ↓
capture_window(hwnd) → PIL Image
  ↓
analyze_with_gemini(img, prompt) → reply_text
  ↓
print JSON { hwnd, title, width, height, prompt, gemini_reply }
```

### 修改：`main()`

- `capture` 子命令新增 `--prompt` 参数（required）
- 入口处调用 `load_dotenv()` 加载 `.env`

---

## 数据流

```
CLI: capture <hwnd> --prompt "..."
  ↓
load_dotenv()
  ↓
validate hwnd
  ↓
capture_window(hwnd) → PIL Image
  ↓
BytesIO → PNG bytes（内存）
  ↓
google-genai SDK → Gemini API
  ↓
response.text
  ↓
stdout: JSON { hwnd, title, width, height, prompt, gemini_reply }
```

---

## 错误处理

| 情况 | 输出 |
|---|---|
| `GEMINI_API_KEY` 未设置 | `{"error": "GEMINI_API_KEY not set"}` → exit 1 |
| `--prompt` 未传 | argparse 自动报错 |
| Gemini API 失败 | `{"error": "gemini: <原始错误>"}` → exit 1 |
| hwnd 不存在 | `{"error": "hwnd xxx not found"}` → exit 1 |
| 截图失败 | `{"error": "<原始错误>"}` → exit 1 |

---

## 新增依赖

| 包 | 用途 |
|---|---|
| `google-genai` | Gemini SDK |
| `python-dotenv` | 加载 `.env` |

---

## 不在范围内（YAGNI）

- 流式输出（streaming）
- 多轮对话
- 重试逻辑
- prompt 默认值
- 图片格式选择
