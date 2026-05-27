# mcp_client.py
import asyncio
import subprocess
import json
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

class McpDocClient:
    def __init__(self, server_script="mcp_server.py"):
        self.server_script = server_script
        self.process = None
        self.client = None

    async def start(self):
        """启动 MCP 子进程并建立连接"""
        self.process = subprocess.Popen(
            ["python", self.server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # 创建 MCP 客户端，连接子进程的 stdin/stdout
        self.client = Client(StdioServerParameters(
            command="python",
            args=[self.server_script],
        ))
        # Client 的构造函数需要传入连接参数，上面的 StdioServerParameters 可以这样用：
        # 但新版 mcp 0.x 的 API 可能有变化，我们使用更稳定的写法。
        # 下面的版本采用 asyncio.create_subprocess_exec + connect
        pass  # 稍后完善

    async def call_tool(self, tool_name: str, arguments: dict):
        """调用指定工具"""
        # 这里的实现依赖 mcp 库的版本，我们稍后统一处理。
        pass

    async def close(self):
        if self.process:
            self.process.terminate()