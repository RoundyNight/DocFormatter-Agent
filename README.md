


---

# AI Document Agent (智能文档排版助手)


基于 AI 智能体驱动的 **Office 文档自动排版与格式优化** 全栈 Web 应用。
只需上传 Word 文档，用自然语言描述排版要求，AI 便会自动调整字体、字号、缩进、行距等格式，并支持一键下载修改后的文件。

---

## 核心特性

- **自然语言排版**：像和人说话一样下达指令，例如“按学术论文格式排版”或“把所有标题改成黑体三号”。
- **智能格式理解**：自动分析文档现有默认字体、字号等，避免重复设置。
- **多文档模板**：内置论文、报告、公文排版规范（轻量 RAG 检索），AI 按需调用。（预置规范不完全准确，请以官方具体要求为准）
- **所见即所得**：右侧实时预览文档修改效果（支持分页、字体、缩进等）。
- **安全本地运行**：完全离线，无需联网（除调用 AI API 外），文档和API不会上传到第三方。

---

## 快速开始（Windows）

> **要求**：Windows 10 或更高，无需安装 Python 或任何依赖。

1. **解压** `DocPolish-beta.zip` 到任意目录（建议路径不含空格，如 `C:\DocPolish`）。
2. 双击 `start.bat`，等待几秒。
   - 将自动启动后端服务并打开浏览器（`http://127.0.0.1:8000`）。
3. 在左侧面板输入你的 **DeepSeek API Key**，点击“测试连接”。
4. 上传一个 `.docx` 文件。
5. 在对话框输入排版要求，例如 `按学术论文格式排版`，点击发送。
6. 查看 AI 返回的修改建议，点击 **执行这些修改**。
7. 右侧预览区将更新，也可点击 **下载文档** 保存修改后的文件。

> 关闭浏览器窗口并关闭命令行窗口即可停止服务。

---

## 开发者指南

### 环境准备
- Python 3.10+
- 安装依赖：`pip install -r requirements.txt`
- 下载 [OfficeCLI](https://github.com/ccaijimmy/office-cli) 并将其路径配置在 `backend/main.py` 中

### 启动开发服务器
```bash
cd backend
uvicorn main:app --reload --port 8000
```
前端文件可在 `frontend/` 中编辑，开发时需单独启动前端服务（如 `python -m http.server 5500` 在 frontend 目录）。

### 项目结构
```
AI-Document-Agent/
├── backend/               # FastAPI 后端
│   ├── main.py            # 主路由、AI 对话、执行
│   ├── dehydrator.py      # 文档结构压缩（脱水器）
│   ├── mcp_server.py      # 文档编辑工具集（基于 python-docx）
│   ├── retriever.py       # 模板关键词检索
│   ├── templates.txt      # 排版规范模板库
│   └── prompts/           # 系统提示词
├── frontend/              # 前端聊天界面 + 文档预览
│   ├── index.html
│   ├── chat.js
│   └── jszip.min.js, docx-preview.min.js
├── workspace/             # 用户上传的文档存储
└── start.bat              # 一键启动脚本
```

---

## 支持的排版操作（工具清单）

| 工具名称 | 功能 | 示例参数 |
|----------|------|----------|
| `set_font` | 设置字体、字号 | `font_east_asia="仿宋"` `font_size="12pt"` |
| `set_bold` | 加粗/取消加粗 | `bold=true` |
| `set_alignment` | 对齐方式 | `alignment="center"` |
| `set_indent` | 缩进（首行、左右） | `first_line_indent="2ch"` |
| `set_spacing` | 行距、段间距 | `line_spacing=1.5` `space_before="6pt"` |
| `set_color` | 文字颜色 | `color="#FF0000"` |

---

## ⚠️ 注意事项

- API Key 仅保存在浏览器本地，不会上传到任何服务器。
- 文档处理全程在本地进行，无需担心隐私泄露。
- 如遇到 officecli 未被识别，请安装 [Visual C++ 运行时](https://aka.ms/vs/17/release/vc_redist.x64.exe)。
- 目前支持 `.docx` 格式，不支持旧版 `.doc`。

---

## 📄 许可

MIT License

---
