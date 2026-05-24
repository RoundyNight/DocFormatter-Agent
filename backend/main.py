import json
import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Document Agent Backend")

# 解决跨域问题（因为前端和后端运行在不同的端口，不加这个前端无法访问后端）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有人访问
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义我们的测试文档路径
TEST_DOC_PATH = os.path.abspath("../test-docs/test.docx")


@app.get("/")
def read_root():
    return {"status": "success", "message": "Doc-Agent 后端引擎已成功通电！"}


@app.get("/api/parse-doc")
def parse_document():
    """核心接口：调用 officecli 提取 Word 文档的完整段落和标题结构"""
    # 1. 检查测试文档是否存在
    if not os.path.exists(TEST_DOC_PATH):
        raise HTTPException(
            status_code=404,
            detail=f"找不到测试文档，请检查路径: {TEST_DOC_PATH}",
        )

    try:
        # 2. 用 Python 调用系统里的 officecli 命令
        # 我们使用 `officecli get <文件> / --depth 2 --json` 拿到全量的语义节点
        # cmd = ["officecli", "get", TEST_DOC_PATH, "/", "--depth", "6", "--json"]
        # cmd = ["officecli", "view", TEST_DOC_PATH, "outline", "--json"]
        # 核心修正：路径从 "/" 换成 "/body"！深度给 2（代表 body 本身和它下面的那16个段落）
        cmd = ["officecli", "get", TEST_DOC_PATH, "/body", "--depth", "2", "--json"]

        # 执行命令并捕获它的输出
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # 3. 将 officecli 返回的纯文本 JSON 字符串，转化为 Python 的字典/列表
        raw_json = json.loads(result.stdout)

        # 4. 数据直接吐给前端
        return {
            "status": "success",
            "file_name": os.path.basename(TEST_DOC_PATH),
            "data": raw_json,  # 这里面包含了文档里所有的标题、正文和对应的路径标签
        }

    except subprocess.CalledProcessError as e:
        # 如果 officecli 执行失败（比如系统没装好），抓出错误原因
        raise HTTPException(
            status_code=500, detail=f"OfficeCLI 执行失败，错误信息: {e.stderr}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, detail="OfficeCLI 返回的数据无法被正确解析为 JSON"
        )