

---

# AI Document Agent (智能文档排版助手)


基于 LangGraph 智能体驱动的 **Office 文档自动排版与格式优化** 全栈 Web 应用。
上传 Word 文档，用自然语言描述排版要求，AI 生成排版规划并经你审核后自动执行，支持实时预览与下载。

>**基于 Apache 2.0 许可证使用了 OfficeCLI 实现文档解析**

---

## 核心特性

- **自然语言排版**：例如「按学术论文格式排版」或「把所有标题改成黑体三号」。
- **人机协同审核**：AI 生成排版规划后，你可批准执行或提出修改意见，Agent 会重新规划。
- **智能格式理解**：自动分析文档默认字体、字号等，避免重复设置。
- **排版模板库**：内置论文、报告、公文等规范，通过关键词匹配注入提示词（预置规范仅供参考，请以官方要求为准）。
- **所见即所得**：左侧实时预览文档修改效果。
- **本地处理**：除调用 DeepSeek API 外，文档在本地解析与修改，不上传第三方。

---

## 快速开始（Windows Release）

> **要求**：Windows 10 或更高。Release 包内已包含运行时，无需单独安装 Python。

1. 解压 Release 版 `.zip` 到任意目录（建议路径不含空格）。
2. 双击 `start.bat`，等待服务启动并打开浏览器（`http://127.0.0.1:8000`）。
3. 输入 **DeepSeek API Key**，点击「测试连接」。
4. 点击「+」上传 `.docx` 文件。
5. 输入排版要求，例如 `按学术论文格式排版`，点击发送。
6. 查看 AI 排版规划，点击 **批准执行** 或 **提出修改**。
7. 预览区更新后，可点击 **下载文档** 保存。

> 关闭浏览器与命令行窗口即可停止服务。

---

## 开发者指南

### 环境准备

- Python 3.10+（推荐 3.13）
- 安装 [OfficeCLI](https://github.com/ccaijimmy/office-cli)，确保 `officecli` 在 PATH 中可用
- 安装依赖：

```bash
cd backend
pip install -r requirements.txt
```

### 启动服务

**后端**（在 `backend` 目录）：

```bash
uvicorn main:app --reload --port 8000
```

**前端**（在 `frontend` 目录，另开终端）：

```bash
python -m http.server 5500
```

浏览器访问 `http://127.0.0.1:5500`。前端 API 默认指向 `http://127.0.0.1:8000`。

### 项目结构

```
doc-agent/
├── backend/
│   ├── main.py            # FastAPI 路由、Agent SSE 端点
│   ├── agent.py           # LangGraph Agent（分析→规划→审核→执行）
│   ├── doc_tools.py       # LangChain @tool 文档修改（python-docx）
│   ├── dehydrator.py      # 文档结构脱水（OfficeCLI JSON → 简化 JSON）
│   ├── retriever.py       # 排版模板关键词匹配
│   ├── templates.txt      # 排版规范模板库
│   ├── prompts/           # 系统提示词
│   └── workspace/         # 当前工作文档（current.docx）
├── frontend/
│   ├── index.html         # 主界面
│   ├── chat.js            # Agent 交互与 SSE
│   ├── style.css
│   └── docx-preview.min.js, jszip.min.js
├── test-docs/             # 测试用文档
└── docs.txt               # 项目导航（开发时优先阅读）
```

### Agent 工作流

```
分析文档 → AI 规划(tool_calls) → 用户审核(interrupt)
  ├─ 批准 → 执行修改 → 完成
  └─ 修订 → 重新规划 → 再次审核 → ...
```

主要 API：`POST /api/agent/start`、`POST /api/agent/continue`（SSE 流式）。

---

## 支持的排版操作

| 工具名称 | 功能 | 示例参数 |
|----------|------|----------|
| `set_font` | 字体、字号 | `para_index=[0,1]` `font_east_asia="仿宋"` `font_size="12pt"` |
| `set_bold` | 加粗/取消加粗 | `para_index=[0]` `bold=true` |
| `set_alignment` | 对齐方式 | `alignment="center"` |
| `set_indent` | 缩进 | `first_line_indent="2ch"` |
| `set_spacing` | 行距、段间距 | `line_spacing=1.5` `space_before="6pt"` |
| `set_color` | 文字颜色 | `color="#FF0000"` |

> `para_index` 为正文段落索引数组，与脱水 JSON 中的 `index` 字段对应。表格内段落暂不支持修改。

---

## 注意事项

- API Key 仅保存在浏览器 `localStorage`，不会上传到本后端以外的服务器。
- 文档解析与修改在本地完成；排版规划需调用 DeepSeek API。
- 若 `officecli` 无法识别，Windows 用户可安装 [Visual C++ 运行时](https://aka.ms/vs/17/release/vc_redist.x64.exe)。
- 仅支持 `.docx`，不支持旧版 `.doc`。

---

## 许可

Apache 2.0

---
