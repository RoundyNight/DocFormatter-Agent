let currentDehydratedData = null;

const toggleSidebarBtn = document.getElementById("toggleSidebar");
const sidebar = document.getElementById("sidebar");
const apiKeyInput = document.getElementById("apiKey");
const modelSelect = document.getElementById("model");
const testConnBtn = document.getElementById("testConnBtn");
const uploadInput = document.getElementById("uploadInput");
const uploadBtn = document.getElementById("uploadBtn");
const fileNameSpan = document.getElementById("fileName");
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

toggleSidebarBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
});

// 测试连接按钮，验证 API Key 是否有效，并能成功访问 DeepSeek 的模型列表接口
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

// 上传按钮，触发文件选择对话框
uploadBtn.addEventListener("click", () => {
    uploadInput.click();
});

// 文件选择后，上传到后端，并获取解析结果，更新当前脱水数据和界面显示
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
        fileNameSpan.textContent = file.name;
        appendMessage("system", `已上传并解析文档: ${file.name}`);
    } catch (err) {
        alert("上传或解析出错: " + err.message);
    }
});

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
});

// 发送用户消息到后端，并处理 AI 的响应，支持工具调用和原始文本两种情况
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

// 辅助函数：添加消息、删除消息、格式化工具调用列表，以及给 AI 消息添加执行按钮
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

// 给每条 AI 消息添加一个执行按钮，点击后会把对应的操作发送到后端执行
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
            } else {
                alert(`部分操作失败：成功 ${result.success}，失败 ${result.failed}。查看控制台获取详情。`);
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