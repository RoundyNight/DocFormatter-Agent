# main.py
import json
import os
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dehydrator import dehydrate_document  # 引入我们的滤芯

app = FastAPI(title="AI Document Agent Backend")

# 解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEST_DOC_PATH = os.path.abspath("../test-docs/test.docx")

#原始json数据
@app.get("/api/raw-doc")
def get_raw_document():
    """纯透明管道：调用 officecli 提取结构后原封不动透传（绝不缩水）"""
    if not os.path.exists(TEST_DOC_PATH):
        raise HTTPException(
            status_code=404, detail=f"找不到测试文档: {TEST_DOC_PATH}"
        )

    try:
        # 保持深度为 6，抓出最饱满的底层 XML 映射树
        cmd = ["officecli", "get", TEST_DOC_PATH, "/body", "--depth", "6", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_json = json.loads(result.stdout)

        # 核心：原汁原味扔出去，不套任何 dehydrator 滤芯
        return {
            "status": "success",
            "file_name": os.path.basename(TEST_DOC_PATH),
            "data": raw_json,  
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"OfficeCLI 失败: {e.stderr}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="数据无法被正确解析为 JSON")

#过滤后json数据
@app.get("/")
def read_root():
    return {"status": "success", "message": "Doc-Agent 后端引擎与过滤层已启动"}

@app.get("/api/parse-doc")
def parse_document():
    """核心接口：调用 officecli 提取结构，并输送给滤芯净化"""
    if not os.path.exists(TEST_DOC_PATH):
        raise HTTPException(
            status_code=404,
            detail=f"找不到测试文档，请检查路径: {TEST_DOC_PATH}",
        )

    try:
        # 注意：因为要查表，如果你文档里的表格嵌套很深，深度建议从 2 提升到 4 或 6
        # 以确保能完整抓出 /body/tbl/tr/tc/p 的数据
        cmd = ["officecli", "get", TEST_DOC_PATH, "/body", "--depth", "6", "--json"]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_json = json.loads(result.stdout)

        # 唯一改动点：在这里接入 dehydrator.py 进行全量清洗
        dehydrated_data = dehydrate_document(raw_json)

        return {
            "status": "success",
            "file_name": os.path.basename(TEST_DOC_PATH),
            "data": dehydrated_data,  # 纯净、高保真的数据
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, detail=f"OfficeCLI 执行失败，错误信息: {e.stderr}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, detail="OfficeCLI 返回的数据无法被正确解析为 JSON"
        )