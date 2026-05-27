import json
import os
import subprocess
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dehydrator import dehydrate_document, calculate_dynamic_baseline  # 合并导入
from executor import execute_operations
from mcp_server import TOOL_MAP # MCP工具清单
import httpx

app = FastAPI(title="AI Document Agent Backend")

def _parse_raw_doc(doc_path: str):
    """仅用于内部分析，返回原始 JSON 或 None"""
    try:
        cmd = ["officecli", "get", doc_path, "/body", "--depth", "6", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception:
        return None

# 加载系统提示词
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
SYSTEM_PROMPT_PATH = os.path.join(PROMPT_DIR, "system_prompt.txt")
def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = load_system_prompt()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路径配置
TEST_DOC_PATH = os.path.abspath("../test-docs/test.docx")
WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "workspace")
WORKSPACE_DOC = os.path.join(WORKSPACE_DIR, "current.docx")
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def get_current_doc_path():
    """返回当前活动文档的绝对路径：优先工作区文件，否则测试文档。"""
    if os.path.exists(WORKSPACE_DOC):
        return WORKSPACE_DOC
    return TEST_DOC_PATH

def parse_doc_with_officecli(doc_path):
    """调用 OfficeCLI 获取文档原始 JSON"""
    try:
        cmd = ["officecli", "get", doc_path, "/body", "--depth", "6", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw_json = json.loads(result.stdout)
        return raw_json
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"OfficeCLI 失败: {e.stderr}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="OfficeCLI 返回的数据无法解析为 JSON")

# ---------------- 已有路由 ----------------
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
        import traceback
        tb = traceback.format_exc()
        # 直接把 traceback 放回响应里，方便浏览器查看
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}\n\n{tb}")

@app.post("/api/upload-doc")
async def upload_doc(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="只支持 .docx 文件")
    try:
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

# ---------------- 请求模型 ----------------
class ChatRequest(BaseModel):
    api_key: str
    model: str
    dehydrated_data: list
    message: str

class ToolCall(BaseModel):
    tool: str
    arguments: dict

class ExecuteRequest(BaseModel):
    tool_calls: list[ToolCall]

# ---------------- AI 对话路由 ----------------
@app.post("/api/chat")
async def chat_with_ai(req: ChatRequest):
    # 动态获取文档基线
    baseline_text = ""
    try:
        doc_path = get_current_doc_path()
        if os.path.exists(doc_path):
            raw_json = _parse_raw_doc(doc_path)
            if raw_json:
                results = raw_json.get("data", {}).get("results", [])
                raw_nodes = results[0].get("children", []) if results else []
                if raw_nodes:
                    baseline = calculate_dynamic_baseline(raw_nodes)
                    label_map = {
                        "effective.font.eastAsia": "中文字体",
                        "effective.font.ascii": "西文字体",
                        "effective.size": "字号",
                        "effective.bold": "加粗",
                        "effective.italic": "斜体",
                        "effective.color": "颜色",
                    }
                    parts = []
                    for key, label in label_map.items():
                        val = baseline.get(key)
                        if val is not None:
                            if isinstance(val, bool):
                                val = "是" if val else "否"
                            parts.append(f"{label}：{val}")
                    if parts:
                        baseline_text = f"文档默认格式（已省略的属性均为此值，无需重复设置）：{'；'.join(parts)}。\n"
    except Exception:
        pass

    user_message = (
        f"{baseline_text}"
        f"以下是用户的文档结构（仅保留有意义的格式差异）：\n"
        f"```json\n{json.dumps(req.dehydrated_data, ensure_ascii=False, indent=2)}\n```\n\n"
        f"以下是用户需求：{req.message}\n请生成操作指令。"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    base_url = "https://api.deepseek.com"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {req.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": req.model,
                    "messages": messages,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                },
                timeout=90.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            try:
                operations = json.loads(content)
                return {"status": "success", "response": operations}
            except json.JSONDecodeError:
                return {"status": "success", "raw_response": content}
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"请求大模型失败: {str(e)}")

# ---------------- 执行修改路由 ----------------
@app.post("/api/execute")
async def execute_ai_operations(req: ExecuteRequest):
    doc_path = get_current_doc_path()
    if not os.path.exists(doc_path):
        raise HTTPException(status_code=404, detail="当前工作区没有文档，请先上传")

    results = []
    for call in req.tool_calls:
        tool_name = call.tool
        args = call.arguments
        if tool_name not in TOOL_MAP:
            results.append({"tool": tool_name, "status": "failed", "reason": "未知工具"})
            continue
        try:
            func = TOOL_MAP[tool_name]
            # 如果工具是 async，需要 await；这里统一在同步路由中处理 async
            import asyncio
            if asyncio.iscoroutinefunction(func):
                res = await func(**args)
            else:
                res = func(**args)
            results.append({"tool": tool_name, "status": "success", "result": res})
        except Exception as e:
            results.append({"tool": tool_name, "status": "error", "reason": str(e)})

    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "status": "success" if success_count == len(req.tool_calls) else "partial_success",
        "details": results
    }

@app.get("/")
def read_root():
    return {"status": "success", "message": "Doc-Agent 后端引擎与过滤层已启动"}