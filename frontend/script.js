// 1. 指定后端的门牌号（API 地址）
const BACKEND_URL = "";
const BACKEND_URL = "http://127.0.0.1:8000/api/raw-doc";
// 2. 当网页加载完毕启动“抓取任务”
document.addEventListener("DOMContentLoaded", () => {
    console.log("准备抓取数据...");
    fetchDocumentStructure();
});

// 3. 核心函数：连接后端并把数据画在网页上
async function fetchDocumentStructure() {
    try {
        // 第一步：抓数据
        const response = await fetch(BACKEND_URL);
        const result = await response.json();
        
        console.log("成功抓到最新版后端数据:", result);

        if (result.status === "success") {
            // 1. 精准填坑文件名
            document.getElementById("fileName").innerText = result.file_name;
            
            const docTreeContainer = document.getElementById("docTree");
            docTreeContainer.innerHTML = ""; // 清空加载提示

            // 2. 因为后端直接 get 了 /body，现在的数据结构直接就是 body 节点本身
            const paragraphs = result.data?.data?.results?.[0]?.children || [];

            if (paragraphs.length === 0) {
                docTreeContainer.innerHTML = "<p style='color: #666;'>📄 文档中没有任何段落文字。</p>";
                return;
            }

            paragraphs.forEach(node => {
                // 过滤掉节属性（section），只显示段落
                if (node.type === "section") return;

                const pElement = document.createElement("p");
                
                // 1. 修正：直接从 node.text 拿文字
                const text = node.text || ""; 
                
                // 2. 修正：直接从 node.style 拿样式
                const type = node.style || node.type || "Normal";

                // 给特殊的标题套上漂亮的外壳类名
                pElement.className = `doc-node ${type.replace(/\s+/g, '-')}`;
                
                // 如果是彻底的空行，我们网页上留空或者变淡，如果是字就正常显示
                if (text.trim() === "") {
                    pElement.innerHTML = `<span style="color: #ccc;">[空行]</span>`;
                } else {
                    pElement.innerText = `[${type}] ${text}`;
                }
                
                // 3. 绑定它的唯一稳定路径（格式如：/body/p[@paraId=2DF9B415]）
                pElement.setAttribute("data-path", node.path);

                docTreeContainer.appendChild(pElement);
            });

        } else {
            showError("后端返回了失败状态。");
        }

    } catch (error) {
        console.error("抓取数据时崩溃了:", error);
        showError("无法连接到后端服务器，请确保 Uvicorn 服务已启动。");
    }
}

// 辅助函数：在网页上显示明显的错误提示
function showError(message) {
    const docTreeContainer = document.getElementById("docTree");
    docTreeContainer.innerHTML = `<p style="color: #ef4444; font-weight: bold;">❌ 错误: ${message}</p>`;
}