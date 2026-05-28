const BACKEND_URL = "http://127.0.0.1:8000/api/parse-doc";

document.addEventListener("DOMContentLoaded", () => {
    fetchDehydratedData();
});

// 从后端获取脱水后的 JSON 数据，并分别渲染左侧的纯 JSON 和右侧的视觉还原
async function fetchDehydratedData() {
    const statusEl = document.getElementById("status");
    try {
        const response = await fetch(BACKEND_URL);
        const result = await response.json();

        if (result.status === "success") {
            statusEl.innerText = `✅ 成功加载测试文档: ${result.file_name}`;
            statusEl.style.color = "green";
            
            const dehydratedData = result.data || [];
            
            // 1. 渲染左侧：把纯净的 JSON 直接打印出来
            document.getElementById("jsonViewer").innerText = JSON.stringify(dehydratedData, null, 2);
            
            // 2. 渲染右侧：根据过滤 JSON 还原排版视觉
            renderVisuals(dehydratedData);
        } else {
            throw new Error("后端返回状态异常");
        }
    } catch (error) {
        statusEl.innerText = "❌ 后端连接失败，请检查 main.py 是否启动！";
        statusEl.style.color = "red";
        document.getElementById("jsonViewer").innerText = "Error: " + error.message;
        document.getElementById("visualViewer").innerText = "无数据可渲染";
    }
}

// 文档还原引擎（检验格式是否丢失）
function renderVisuals(nodes) {
    const container = document.getElementById("visualViewer");
    container.innerHTML = ""; // 清空

    if (nodes.length === 0) {
        container.innerHTML = "<p>文档为空或全部被过滤。</p>";
        return;
    }

    nodes.forEach(node => {
        if (node.type === "table") {
            container.appendChild(renderTable(node));
        } else {
            container.appendChild(renderParagraph(node));
        }
    });
}

// 根据脱水后的 JSON 节点渲染段落，保留智能样式属性，并显示路径信息
function renderParagraph(node) {
    const div = document.createElement("div");
    div.className = "doc-paragraph";

    // 顶部显示它的身份证号 (Path)
    const pathSpan = document.createElement("span");
    pathSpan.className = "path-badge";
    pathSpan.innerText = `📍 ${node.path} [${node.style || "Normal"}]`;
    div.appendChild(pathSpan);

    const p = document.createElement("p");
    p.style.margin = "0";

    // 将过滤器保留的样式还原为 CSS（用于肉眼校验）
    if (node.bold) p.style.fontWeight = "bold";            // 原 is_bold -> bold
    if (node.italic) p.style.fontStyle = "italic";
    if (node.color) p.style.color = node.color;
    if (node.alignment) p.style.textAlign = node.alignment;
    if (node.size) p.style.fontSize = node.size;
    if (node.font_cn || node.font_en) p.style.fontFamily = `"${node.font_cn || ''}", "${node.font_en || ''}", sans-serif`;

    // 处理行内差异 (Runs)
    if (node.runs && node.runs.length > 0) {
        node.runs.forEach(run => {
            const span = document.createElement("span");
            span.innerText = run.text;
            if (run.bold) span.style.fontWeight = "bold";
            if (run.italic) span.style.fontStyle = "italic";
            if (run.color) span.style.color = run.color;
            if (run.size) span.style.fontSize = run.size;
            if (run["font-eastasia"]) span.style.fontFamily = run["font-eastasia"];
            p.appendChild(span);
        });
    } else {
        // 普通段落
        p.innerText = node.text || (node.text === "" ? "[空行]" : node.text);
        if(node.text === "") p.style.color = "#cbd5e1";
    }

    div.appendChild(p);
    return div;
}

// 根据脱水后的 JSON 节点渲染表格，递归处理行、单元格和段落，并显示路径信息
function renderTable(tableNode) {
    const wrapper = document.createElement("div");
    
    const pathSpan = document.createElement("span");
    pathSpan.className = "path-badge";
    pathSpan.innerText = `📍 ${tableNode.path} [Table]`;
    wrapper.appendChild(pathSpan);

    const table = document.createElement("table");
    table.className = "doc-table";

    (tableNode.rows || []).forEach(rowData => {
        const tr = document.createElement("tr");
        (rowData.cells || []).forEach(cellData => {
            const td = document.createElement("td");
            // 单元格里可能有多个段落
            (cellData.paragraphs || []).forEach(pNode => {
                td.appendChild(renderParagraph(pNode));
            });
            tr.appendChild(td);
        });
        table.appendChild(tr);
    });

    wrapper.appendChild(table);
    return wrapper;
}

