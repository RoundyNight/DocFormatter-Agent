# main.py
import json
import os
import subprocess
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dehydrator import dehydrate_document

app = FastAPI(title="AI Document Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 原有测试文档路径（保留，用于开发调试）
TEST_DOC_PATH = os.path.abspath("../test-docs/test.docx")
# 工作区文档路径（用户上传文件覆盖后成为当前操作文档）
WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "workspace")
WORKSPACE_DOC = os.path.join(WORKSPACE_DIR, "current.docx")
os.makedirs(WORKSPACE_DIR, exist_ok=True)


def get_current_doc_path():
    """返回当前活动文档的绝对路径：优先工作区文件，否则测试文档。"""
    if os.path.exists(WORKSPACE_DOC):
        return WORKSPACE_DOC
    return TEST_DOC_PATH


def parse_doc_with_officecli(doc_path):
    """调用 OfficeCLI 获取文档原始 JSON 并完过滤处理（复用逻辑）。"""
    try:
        cmd = ["officecli", "get", doc_path, "/body", "--depth", "6", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_json = json.loads(result.stdout)
        return raw_json
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"OfficeCLI 失败: {e.stderr}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="OfficeCLI 返回的数据无法解析为 JSON")


# 原始json数据（开发者调试用，现在也能展示用户上传的文档）
@app.get("/api/raw-doc")
def get_raw_document():
    doc_path = get_current_doc_path()
    if not os.path.exists(doc_path):
        raise HTTPException(status_code=404, detail=f"找不到文档: {doc_path}")
    try:
        raw_json = parse_doc_with_officecli(doc_path)
        return {
            "status": "success",
            "file_name": os.path.basename(doc_path),
            "data": raw_json,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 过滤后json数据（过滤检验台用，同样自动指向当前文档）
@app.get("/api/parse-doc")
def parse_document():
    doc_path = get_current_doc_path()
    if not os.path.exists(doc_path):
        raise HTTPException(status_code=404, detail=f"找不到文档: {doc_path}")
    try:
        raw_json = parse_doc_with_officecli(doc_path)
        dehydrated_data = dehydrate_document(raw_json)
        return {
            "status": "success",
            "file_name": os.path.basename(doc_path),
            "data": dehydrated_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="解析失败")


# 新增：用户上传文档接口（覆盖工作区文件）
@app.post("/api/upload-doc")
async def upload_doc(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="只支持 .docx 文件")
    try:
        # 覆盖保存
        with open(WORKSPACE_DOC, "wb") as f:
            content = await file.read()
            f.write(content)
        return {
            "status": "success",
            "file_name": file.filename,
            "message": "文档已上传并设为当前工作文档"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")


@app.get("/")
def read_root():
    return {"status": "success", "message": "Doc-Agent 后端引擎与过滤层已启动"}