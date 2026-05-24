# AI Document Agent (智能文档排版助手)

这是一个基于 AI 智能体驱动的 Office 文档自动排版与格式优化全栈 Web 应用。通过深度结合 `OfficeCLI` 引擎，实现对 Word 文档结构的精准解析与互联网级的高级排版体验。

## 阶段性成果

- **[已完成] 全栈文档解析基座**：后端成功基于 Python 连通 OfficeCLI，实现对 `.docx` 物理结构的逐层深度解析（DOM 级抓取）。
- **[已完成] 前端毛坯看台**：前端基于纯原生技术（HTML/JS）通过异步通信（Fetch API）无缝接引后端结构化 JSON 数据，成功展现文档骨骼树。

## 📂 项目结构

```text
~/doc-agent/
├── backend/             # Python FastAPI 后端
│   ├── main.py          # 后端核心路由与 OfficeCLI 控制器
│   └── requirements.txt # 依赖采购清单
├── frontend/            # 原生前端展示区
│   ├── index.html       # 网页骨架
│   ├── script.js        # 神经系统（Fetch 异步抓取）
│   └── style.css        # 视觉衣服（待装修）
└── test-docs/           # 本地测试文档仓