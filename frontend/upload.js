const UPLOAD_URL = "http://127.0.0.1:8000/api/upload-doc";

document.getElementById("uploadBtn").addEventListener("click", async () => {
    const fileInput = document.getElementById("fileInput");
    const statusDiv = document.getElementById("status");
    const file = fileInput.files[0];

    if (!file) {
        statusDiv.innerText = "请先选择一个 .docx 文件";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(UPLOAD_URL, {
            method: "POST",
            body: formData,
        });
        const result = await response.json();

        if (result.status === "success") {
            statusDiv.innerText = "上传成功，即将跳转到文档大纲...";
            // 1.5 秒后跳转检验台，此时 /api/parse-doc 会读取刚刚上传的工作区文件
            setTimeout(() => {
                window.location.href = "dev_dashboard.html";
            }, 1500);
        } else {
            statusDiv.innerText = "上传失败：" + (result.detail || "未知错误");
        }
    } catch (error) {
        statusDiv.innerText = "网络错误，请确认后端服务已启动";
    }
});