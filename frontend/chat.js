let currentDehydratedData = null;

// 只保留存在的元素
const apiKeyInput = document.getElementById("apiKey");
const modelSelect = document.getElementById("model");
const testConnBtn = document.getElementById("testConnBtn");
const uploadInput = document.getElementById("uploadInput");
const uploadBtn = document.getElementById("uploadBtn");
const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

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
            alert("连接成功！");
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
uploadBtn.addEventListener("click", () => {
    uploadInput.click();
});

uploadInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
        const uploadResp = await fetch("http://127.0.0.1:8000/api/upload-doc", {
            method: "POST",
            body: formData
        });
        if (!uploadResp.ok) throw new Error("上传失败");
        const parseResp = await fetch("http://127.0.0.1:8000/api/parse-doc");
        const parseData = await parseResp.json();
        if (parseData.status !== "success") throw new Error("解析文档失败");
        currentDehydratedData = parseData.data;
        appendMessage("system", `已上传并解析文档: ${file.name}`);
        loadPreview();
        // 上传成功后启用输入框，开始轮播提示
        if (userInput) {
            userInput.placeholder = "试试发送“帮我优化文档格式”";
            userInput.removeAttribute('readonly');
        }
    } catch (err) {
        alert("上传或解析出错: " + err.message);
    }
});

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
    const apiKey = apiKeyInput.value.trim();
    const model = modelSelect.value;
    const message = userInput.value.trim();
    if (!apiKey) { alert("请输入 API Key"); return; }
    if (!currentDehydratedData) { alert("请先上传文档"); return; }
    if (!message) return;

    appendMessage("user", message);
    userInput.value = "";
    const thinkingId = appendMessage("ai", "思考中...");

    try {
        const resp = await fetch("http://127.0.0.1:8000/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                api_key: apiKey,
                model: model,
                dehydrated_data: currentDehydratedData,
                message: message
            })
        });
        const data = await resp.json();
        removeMessage(thinkingId);

        if (data.status === "success") {
            if (data.response && data.response.tool_calls) {
                const html = formatToolCalls(data.response.tool_calls);
                const msgId = appendMessage("ai", html);
                addExecuteButton(msgId, data.response.tool_calls);
            } else if (data.raw_response) {
                appendMessage("ai", "AI 返回了非 JSON 内容:\n" + data.raw_response);
            } else {
                appendMessage("ai", "操作列表为空或格式错误");
            }
        } 
        else {
            appendMessage("ai", "错误: " + (data.detail || JSON.stringify(data)));
        }
    } catch (err) {
        removeMessage(thinkingId);
        appendMessage("ai", "请求失败: " + err.message);
    }
}

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

function formatToolCalls(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) {
        return `<p>AI 未返回任何操作。</p>`;
    }
    let html = `<b>AI 工具调用 (${toolCalls.length} 条)：</b><br>`;
    toolCalls.forEach((call, idx) => {
        html += `<div style="margin:6px 0; padding:5px; background:#f0f0f0; border-radius:4px;">
            <b>${idx+1}:</b> ${call.tool}<br>
            <b>参数:</b> ${JSON.stringify(call.arguments)}
        </div>`;
    });
    return html;
}

function addExecuteButton(msgId, operations) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    const oldBtn = msgDiv.querySelector(".execute-btn");
    if (oldBtn) oldBtn.remove();

    const btn = document.createElement("button");
    btn.className = "execute-btn";
    btn.textContent = "执行这些修改";
    btn.style.marginTop = "8px";
    btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "执行中...";
        try {
            const execResp = await fetch("http://127.0.0.1:8000/api/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tool_calls: operations })
            });
            const result = await execResp.json();
            if (result.status === "success") {
                alert("修改已成功应用到文档！");
                loadPreview();
            } else {
                alert(`部分操作失败：成功 ${result.success}，失败 ${result.failed}。查看控制台获取详情。`);
                loadPreview();
                console.error(result);
            }
        } catch (e) {
            alert("执行失败: " + e.message);
        }
        btn.disabled = false;
        btn.textContent = "执行这些修改";
    });
    msgDiv.appendChild(btn);
}

// 下载按钮
document.getElementById("downloadBtn").addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = "http://127.0.0.1:8000/api/download-doc";
    link.download = "";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

// 预览
async function loadPreview() {
    const previewDiv = document.getElementById("docPreview");
    previewDiv.innerHTML = "加载预览中...";
    try {
        const resp = await fetch("http://127.0.0.1:8000/api/download-doc");
        const blob = await resp.blob();
        if (typeof docx !== 'undefined' && docx.renderAsync) {
            await docx.renderAsync(blob, previewDiv);
        } else {
            previewDiv.innerHTML = `<p>预览功能需要 docx-preview 库支持</p>`;
        }
    } catch (error) {
        previewDiv.innerHTML = `<p style="color:red">预览失败: ${error.message}</p>`;
        console.error(error);
    }
}
