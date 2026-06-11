let currentDehydratedData = null;
let currentThreadId = null;

const apiKeyInput = document.getElementById("apiKey");
const modelSelect = document.getElementById("model");
const testConnBtn = document.getElementById("testConnBtn");
const uploadInput = document.getElementById("uploadInput");
const uploadBtn = document.getElementById("uploadBtn");
const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const statusBar = document.getElementById("statusBar");

// 本地存储恢复
const savedApiKey = localStorage.getItem("deepseek_api_key");
const savedModel = localStorage.getItem("deepseek_model");
if (savedApiKey) apiKeyInput.value = savedApiKey;
if (savedModel) modelSelect.value = savedModel;

apiKeyInput.addEventListener("input", () => {
    localStorage.setItem("deepseek_api_key", apiKeyInput.value.trim());
});
modelSelect.addEventListener("change", () => {
    localStorage.setItem("deepseek_model", modelSelect.value);
});

// 测试连接
testConnBtn.addEventListener("click", async () => {
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) { alert("请输入 API Key"); return; }
    testConnBtn.disabled = true;
    testConnBtn.textContent = "测试中...";
    try {
        const resp = await fetch("https://api.deepseek.com/v1/models", {
            headers: { Authorization: `Bearer ${apiKey}` }
        });
        if (resp.ok) {
            alert("连接成功!");
        } else {
            const err = await resp.json();
            alert("连接失败: " + (err.error?.message || resp.statusText));
        }
    } catch (e) {
        alert("网络错误: " + e.message);
    } finally {
        testConnBtn.disabled = false;
        testConnBtn.textContent = "测试连接";
    }
});

// 上传
uploadBtn.addEventListener("click", () => uploadInput.click());

uploadInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
        const uploadResp = await fetch("http://127.0.0.1:8000/api/upload-doc", {
            method: "POST", body: formData
        });
        if (!uploadResp.ok) throw new Error("上传失败");
        const parseResp = await fetch("http://127.0.0.1:8000/api/parse-doc");
        const parseData = await parseResp.json();
        if (parseData.status !== "success") throw new Error("解析文档失败");
        currentDehydratedData = parseData.data;
        appendMessage("system", `已上传并解析文档: ${file.name}`);
        loadPreview();
        if (userInput) {
            userInput.placeholder = "输入排版需求，如\"帮我优化文档格式\"";
            userInput.removeAttribute("readonly");
        }
    } catch (err) {
        alert("上传或解析出错: " + err.message);
    }
});

// ---------- 状态栏管理 ----------
function setStatus(label, variant = "active") {
    statusBar.textContent = label;
    statusBar.className = "status-bar " + variant;
    statusBar.style.display = "block";
}
function clearStatus() {
    statusBar.textContent = "";
    statusBar.className = "status-bar idle";
    statusBar.style.display = "none";
}

// ---------- SSE 解析 ----------
async function fetchSSE(url, body, onEvent) {
    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        const errText = await resp.text();
        onEvent("error", { message: errText });
        return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // last incomplete line
        let currentEvent = "";
        let currentData = "";
        for (const line of lines) {
            if (line.startsWith("event: ")) {
                currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
                currentData = line.slice(6).trim();
            } else if (line === "" && currentEvent && currentData) {
                try {
                    onEvent(currentEvent, JSON.parse(currentData));
                } catch (e) {
                    onEvent("error", { message: "SSE parse error" });
                }
                currentEvent = "";
                currentData = "";
            }
        }
    }
}

// ---------- Agent 交互 ----------
sendBtn.addEventListener("click", startAgent);
userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") startAgent();
});

async function startAgent() {
    const apiKey = apiKeyInput.value.trim();
    const model = modelSelect.value;
    const message = userInput.value.trim();
    if (!apiKey) { alert("请输入 API Key"); return; }
    if (!currentDehydratedData) { alert("请先上传文档"); return; }
    if (!message) return;

    appendMessage("user", message);
    userInput.value = "";
    setStatus("分析文档中...", "active");

    await fetchSSE("http://127.0.0.1:8000/api/agent/start", {
        api_key: apiKey,
        model: model,
        dehydrated_data: currentDehydratedData,
        message: message,
    }, (event, data) => {
        if (event === "state") {
            setStatus(data.label, "active");
        } else if (event === "interrupt") {
            currentThreadId = data.thread_id;
            setStatus(data.label, "review");
            showPlanForReview(data.plan);
        } else if (event === "result") {
            currentThreadId = null;
            setStatus(data.label, "success");
            showExecutionResult(data.execution_results);
            loadPreview();
        } else if (event === "error") {
            setStatus("出错了", "error");
            appendMessage("ai", "错误: " + data.message);
        }
    });
}

function showPlanForReview(plan) {
    const toolCalls = plan.tool_calls || [];
    if (!toolCalls.length) {
        appendMessage("ai", "AI 未返回任何排版规划。");
        return;
    }
    let html = `<b>AI 排版规划 (${toolCalls.length} 条操作):</b><br>`;
    toolCalls.forEach((call, idx) => {
        html += `<div style="margin:6px 0; padding:5px; background:#f0f0f0; border-radius:4px;">
            <b>${idx + 1}:</b> ${call.tool}<br>
            <b>参数:</b> ${JSON.stringify(call.arguments)}
        </div>`;
    });
    const msgId = appendMessage("ai", html);
    addReviewButtons(msgId);
}

function addReviewButtons(msgId) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "review-actions";

    const approveBtn = document.createElement("button");
    approveBtn.className = "approve-btn";
    approveBtn.textContent = "批准执行";
    approveBtn.addEventListener("click", () => approvePlan(msgId));

    const reviseBtn = document.createElement("button");
    reviseBtn.className = "revise-btn";
    reviseBtn.textContent = "提出修改";
    reviseBtn.addEventListener("click", () => showReviseInput(msgId));

    actionsDiv.appendChild(approveBtn);
    actionsDiv.appendChild(reviseBtn);
    msgDiv.appendChild(actionsDiv);
}

async function approvePlan(msgId) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;
    // 移除审核按钮
    const actions = msgDiv.querySelector(".review-actions");
    if (actions) actions.remove();
    const reviseArea = msgDiv.querySelector(".revise-input-area");
    if (reviseArea) reviseArea.remove();

    setStatus("执行排版中...", "active");

    await fetchSSE("http://127.0.0.1:8000/api/agent/continue", {
        thread_id: currentThreadId,
        decision: "approve",
        feedback: "",
    }, (event, data) => {
        if (event === "state") {
            setStatus(data.label, "active");
        } else if (event === "result") {
            currentThreadId = null;
            setStatus(data.label, "success");
            showExecutionResult(data.execution_results);
            loadPreview();
        } else if (event === "interrupt") {
            // 执行后又产生中断（不太可能，但安全处理）
            currentThreadId = data.thread_id;
            setStatus(data.label, "review");
            showPlanForReview(data.plan);
        } else if (event === "error") {
            setStatus("出错了", "error");
            appendMessage("ai", "错误: " + data.message);
        }
    });
}

function showReviseInput(msgId) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;
    // 隐藏审核按钮
    const actions = msgDiv.querySelector(".review-actions");
    if (actions) actions.style.display = "none";

    const areaDiv = document.createElement("div");
    areaDiv.className = "revise-input-area";

    const textarea = document.createElement("textarea");
    textarea.className = "revise-input";
    textarea.placeholder = "请输入修改意见...";
    textarea.rows = 3;

    const submitBtn = document.createElement("button");
    submitBtn.className = "revise-submit-btn";
    submitBtn.textContent = "提交修改意见";
    submitBtn.addEventListener("click", () => revisePlan(msgId, textarea.value));

    areaDiv.appendChild(textarea);
    areaDiv.appendChild(submitBtn);
    msgDiv.appendChild(areaDiv);
}

async function revisePlan(msgId, feedback) {
    if (!feedback.trim()) { alert("请输入修改意见"); return; }
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;
    const reviseArea = msgDiv.querySelector(".revise-input-area");
    if (reviseArea) reviseArea.remove();
    const actions = msgDiv.querySelector(".review-actions");
    if (actions) actions.remove();

    appendMessage("user", "修改意见: " + feedback);
    setStatus("重新规划中...", "active");

    await fetchSSE("http://127.0.0.1:8000/api/agent/continue", {
        thread_id: currentThreadId,
        decision: "revise",
        feedback: feedback,
    }, (event, data) => {
        if (event === "state") {
            setStatus(data.label, "active");
        } else if (event === "interrupt") {
            currentThreadId = data.thread_id;
            setStatus(data.label, "review");
            showPlanForReview(data.plan);
        } else if (event === "result") {
            currentThreadId = null;
            setStatus(data.label, "success");
            showExecutionResult(data.execution_results);
            loadPreview();
        } else if (event === "error") {
            setStatus("出错了", "error");
            appendMessage("ai", "错误: " + data.message);
        }
    });
}

function showExecutionResult(results) {
    if (!results || !results.length) {
        appendMessage("ai", "排版执行完成（无具体操作结果）");
        return;
    }
    const success = results.filter(r => r.status === "success").length;
    const total = results.length;
    let html = `<b>执行结果: ${success}/${total} 成功</b><br>`;
    results.forEach((r, idx) => {
        const icon = r.status === "success" ? "✓" : "✗";
        html += `<div style="margin:4px 0; padding:4px; background:#f8f8f8; border-radius:4px;">
            ${icon} <b>${r.tool}</b>: ${r.status}${r.reason ? " - " + r.reason : ""}
        </div>`;
    });
    appendMessage("ai", html);
}

// ---------- 消息辅助 ----------
function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const id = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 5);
    div.id = id;
    div.innerHTML = text.replace(/\n/g, "<br>");
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ---------- 下载 ----------
document.getElementById("downloadBtn").addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = "http://127.0.0.1:8000/api/download-doc";
    link.download = "";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

// ---------- 预览 ----------
async function loadPreview() {
    const previewDiv = document.getElementById("docPreview");
    previewDiv.innerHTML = "加载预览中...";
    try {
        const resp = await fetch("http://127.0.0.1:8000/api/download-doc");
        const blob = await resp.blob();
        if (typeof docx !== "undefined" && docx.renderAsync) {
            await docx.renderAsync(blob, previewDiv);
        } else {
            previewDiv.innerHTML = `<p>预览功能需要 docx-preview 库支持</p>`;
        }
    } catch (error) {
        previewDiv.innerHTML = `<p style="color:red">预览失败: ${error.message}</p>`;
    }
}
