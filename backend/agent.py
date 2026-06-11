# backend/agent.py -- LangGraph Agent 流程定义 (JSON mode + 顺序 execute_tools)
"""
工作流: analyze_document -> plan_formatting(JSON tool_calls) -> human_review(interrupt) -> 条件边
  批准 -> execute_tools(顺序执行) -> END
  修订 -> plan_formatting(重新规划)
"""
import json
import os
import subprocess
import uuid
from typing import TypedDict, Literal, Annotated

from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI

from dehydrator import calculate_dynamic_baseline
from retriever import match_template
from doc_tools import all_tools

# ---------- 系统提示词 ----------
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")
SYSTEM_PROMPT_PATH = os.path.join(PROMPT_DIR, "system_prompt.txt")

def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

SYSTEM_PROMPT = load_system_prompt()

_TOOLS_BY_NAME = {t.name: t for t in all_tools}

_GLOBAL_INTENT_KEYWORDS = ("优化", "排版", "格式", "全文", "整体", "统一", "美化", "规范", "调整")

def _is_global_intent(user_message: str) -> bool:
    return any(kw in user_message for kw in _GLOBAL_INTENT_KEYWORDS)

def _build_doc_structure_hint(dehydrated_data: list, user_message: str) -> str:
    """为规划阶段注入段落规模与非空预览，避免全局指令只改 index 0。"""
    indexed = [item for item in dehydrated_data if isinstance(item, dict) and "index" in item]
    if not indexed:
        return ""
    count = len(indexed)
    max_idx = max(item["index"] for item in indexed)
    is_global = _is_global_intent(user_message)
    lines = [f"【文档结构】共 {count} 个正文段落，index 范围 0–{max_idx}。"]
    if is_global:
        lines.append(
            "当前为全局/模糊排版指令：你必须分析每一个 index 的角色并生成完整规划，"
            "禁止只修改 index 0 或极少数段落；相同格式的 index 必须合并到同一 para_index 数组。"
        )
    previews = []
    for item in indexed:
        text = (item.get("text") or "").strip()
        if text:
            previews.append(f"  index {item['index']}: {text[:50]}")
    if previews:
        lines.append("非空段落预览：")
        lines.extend(previews[:80])
        if len(previews) > 80:
            lines.append(f"  ... 另有 {len(previews) - 80} 个非空段落未列出")
    return "\n".join(lines) + "\n\n"

def _last_ai_with_tool_calls(messages: list) -> AIMessage | None:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.tool_calls:
            return m
    return None

def _indexed_paragraph_count(dehydrated_data: list) -> int:
    return sum(1 for item in dehydrated_data if isinstance(item, dict) and "index" in item)

def _tool_call_args(tc: dict) -> dict:
    """兼容 AIMessage.tool_calls 与 JSON 中的 arguments 字段。"""
    if not isinstance(tc, dict):
        return {}
    return tc.get("args") or tc.get("arguments") or {}

def _json_to_ai_message(data: dict) -> AIMessage:
    """将 system_prompt 约定的 JSON 转为带 tool_calls 的 AIMessage。"""
    raw_calls = data.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        raise ValueError("tool_calls 必须是数组")

    tool_calls = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        name = call.get("tool") or call.get("name")
        if not name:
            continue
        tool_calls.append({
            "name": name,
            "args": call.get("arguments") or call.get("args") or {},
            "id": call.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            "type": "tool_call",
        })
    if not tool_calls:
        raise ValueError("tool_calls 为空")
    return AIMessage(content="", tool_calls=tool_calls)

def _covered_indices(tool_calls: list) -> set[int]:
    covered = set()
    for tc in tool_calls:
        args = _tool_call_args(tc)
        raw_indices = args.get("para_index")
        if isinstance(raw_indices, int):
            covered.add(raw_indices)
        elif isinstance(raw_indices, list):
            for idx in raw_indices:
                try:
                    covered.add(int(idx))
                except (TypeError, ValueError):
                    continue
    return covered

def _global_plan_too_narrow(state: "AgentState", response: AIMessage) -> tuple[bool, str]:
    """全局排版请求不接受只覆盖标题/极少段落的计划。"""
    if not _is_global_intent(state.get("user_message", "")):
        return False, ""

    total = _indexed_paragraph_count(state.get("dehydrated_data", []))
    if total < 10:
        return False, ""

    covered = _covered_indices(response.tool_calls or [])
    min_required = max(8, int(total * 0.25))
    if len(covered) >= min_required:
        return False, ""

    sample = sorted(covered)[:30]
    return True, (
        f"上一版规划不完整：文档共有 {total} 个可操作段落，"
        f"但 tool_calls 只覆盖 {len(covered)} 个 index（示例：{sample}）。"
        "用户请求是全局排版/优化，不是只修改标题。"
        "请重新阅读全部 JSON，至少覆盖正文、一级标题、二级/步骤标题、说明/列表段落等主要角色；"
        "相同格式必须合并成大数组，生成完整 tool_calls。"
    )

# ---------- Agent State ----------
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # LangChain BaseMessage 列表(对话+tool_calls)
    user_message: str
    dehydrated_data: list
    api_key: str
    model: str
    doc_path: str
    baseline_text: str
    template_prompt: str
    human_decision: str
    human_feedback: str
    current_step: str
    error: str

# ---------- Node: analyze_document ----------
async def analyze_document(state: AgentState) -> dict:
    """读取文档结构,计算基准线,匹配排版模板"""
    doc_path = state.get("doc_path", "")
    baseline_text = ""

    try:
        if os.path.exists(doc_path):
            cmd = ["officecli", "get", doc_path, "/body", "--depth", "6", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            raw_json = json.loads(result.stdout)
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

    matched_content = match_template(state["user_message"])
    template_prompt = ""
    if matched_content:
        template_prompt = (
            "用户指定了如下排版规范（若用户未明确指定，则为系统默认的通用规范），请严格遵循所有细节，逐条转换为工具调用。\n"
            "请根据文档的语义（如\"摘要\"二字、标题层级编号）来识别段落角色并执行对应设置。\n"
            f"【排版规范】：\n{matched_content}\n\n"
        )
    else:
        template_prompt = "用户未指定特定排版规范，请根据通用美观原则排版。\n"

    return {
        "baseline_text": baseline_text,
        "template_prompt": template_prompt,
        "current_step": "analyze_done",
        "error": "",
    }

# ---------- Node: plan_formatting ----------
async def plan_formatting(state: AgentState) -> dict:
    """调用 DeepSeek API (JSON mode) 生成完整 tool_calls 规划。"""
    existing_messages = state.get("messages", [])
    is_revision = bool(existing_messages)

    if not is_revision:
        structure_hint = _build_doc_structure_hint(state["dehydrated_data"], state["user_message"])
        user_content = (
            f"{state.get('baseline_text', '')}"
            f"{state.get('template_prompt', '')}"
            f"{structure_hint}"
            f"以下是用户的文档结构（文本已截断，请重点关注 index 和样式）：\n"
            f"```json\n{json.dumps(state['dehydrated_data'], ensure_ascii=False, indent=2)}\n```\n\n"
            f"以下是用户需求：{state['user_message']}\n请生成操作指令。"
        )
        new_messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    else:
        feedback = state.get("human_feedback", "")
        new_messages = [
            HumanMessage(
                content=f"上一版排版规划不满意，修改意见如下：{feedback}\n请根据修改意见重新规划。"
            ),
        ]

    model = state["model"]
    # deepseek-reasoner 不支持 json_object，规划阶段回退 deepseek-chat
    plan_model = "deepseek-chat" if model == "deepseek-reasoner" else model

    llm = ChatOpenAI(
        model=plan_model,
        api_key=state["api_key"],
        base_url="https://api.deepseek.com",
        temperature=0.1,
        max_tokens=8192,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    dialogue = list(new_messages)
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            raw_response = await llm.ainvoke(existing_messages + dialogue)
            content = raw_response.content or ""
            finish_reason = (raw_response.response_metadata or {}).get("finish_reason")

            if finish_reason == "length":
                if attempt < max_retries:
                    dialogue.append(
                        HumanMessage(
                            content="输出因长度被截断。请减少重复说明，但必须输出完整 tool_calls JSON，"
                            "相同格式的大段 index 合并到同一 para_index 数组。"
                        )
                    )
                    continue
                return {
                    "error": "AI 输出过长被截断，请尝试更具体的指令或分段处理。",
                    "current_step": "error",
                }

            data = json.loads(content)
            ai_message = _json_to_ai_message(data)

            if not is_revision:
                too_narrow, narrow_feedback = _global_plan_too_narrow(state, ai_message)
                if too_narrow and attempt < max_retries:
                    dialogue.append(HumanMessage(content=narrow_feedback))
                    continue

            return {
                "messages": dialogue + [ai_message],
                "current_step": "plan_done",
                "error": "",
            }
        except json.JSONDecodeError:
            if attempt < max_retries:
                dialogue.append(
                    HumanMessage(
                        content="输出不是合法 JSON。请严格按 system prompt 只输出包含 tool_calls 的 JSON 对象。"
                    )
                )
                continue
            return {
                "error": "AI 返回了无法解析的 JSON，请重试。",
                "current_step": "error",
            }
        except ValueError as e:
            if attempt < max_retries:
                dialogue.append(HumanMessage(content=f"规划无效：{e}。请重新生成完整 tool_calls。"))
                continue
            return {"error": str(e), "current_step": "error"}
        except Exception as e:
            return {"error": f"LLM 调用失败: {str(e)}", "current_step": "error"}

# ---------- Node: human_review ----------
async def human_review(state: AgentState) -> dict:
    """等待用户审核排版规划,使用 interrupt() 暂停执行"""
    messages = state.get("messages", [])
    last_ai = _last_ai_with_tool_calls(messages)

    tool_calls_info = []
    if last_ai:
        for tc in last_ai.tool_calls:
            tool_calls_info.append({"tool": tc["name"], "arguments": tc["args"]})

    decision = interrupt({
        "plan": {"tool_calls": tool_calls_info},
        "current_step": state.get("current_step", ""),
    })
    return {
        "human_decision": decision.get("decision", "approve"),
        "human_feedback": decision.get("feedback", ""),
    }

# ---------- Node: execute_tools (顺序执行, 避免 ToolNode 并行写同一 docx) ----------
async def execute_tools(state: AgentState) -> dict:
    """按顺序执行 tool_calls 并写入 ToolMessage（替代并行 ToolNode）。"""
    last_ai = _last_ai_with_tool_calls(state.get("messages", []))
    if not last_ai:
        return {"current_step": "execute_done", "error": "未找到可执行的排版规划"}

    tool_messages: list[ToolMessage] = []
    for tc in last_ai.tool_calls:
        tool = _TOOLS_BY_NAME.get(tc["name"])
        if tool is None:
            tool_messages.append(
                ToolMessage(
                    content=f"未知工具: {tc['name']}",
                    name=tc["name"],
                    tool_call_id=tc["id"],
                    status="error",
                )
            )
            continue
        try:
            result = await tool.ainvoke(tc["args"])
            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    name=tc["name"],
                    tool_call_id=tc["id"],
                )
            )
        except Exception as e:
            tool_messages.append(
                ToolMessage(
                    content=str(e),
                    name=tc["name"],
                    tool_call_id=tc["id"],
                    status="error",
                )
            )
    return {"messages": tool_messages, "current_step": "execute_done", "error": ""}

# ---------- Conditional Edge ----------
def route_after_review(state: AgentState) -> Literal["execute_tools", "plan_formatting"]:
    if state.get("human_decision") == "approve":
        return "execute_tools"
    return "plan_formatting"

# ---------- Build Graph ----------
def build_agent_graph():
    builder = StateGraph(AgentState)

    builder.add_node("analyze_document", analyze_document)
    builder.add_node("plan_formatting", plan_formatting)
    builder.add_node("human_review", human_review)
    builder.add_node("execute_tools", execute_tools)

    builder.add_edge(START, "analyze_document")
    builder.add_edge("analyze_document", "plan_formatting")
    builder.add_edge("plan_formatting", "human_review")
    builder.add_conditional_edges("human_review", route_after_review)
    builder.add_edge("execute_tools", END)

    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    return graph, checkpointer

# 全局实例
agent_graph, agent_checkpointer = build_agent_graph()
