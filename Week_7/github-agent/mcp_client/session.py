"""
MCP Client Session — HTTP/SSE transport

Connects to a running MCP server via SSE URL.
The server must be started separately with `python mcp_server/http_app.py`.
"""
from __future__ import annotations

from mcp import ClientSession
from mcp.client.sse import sse_client

from config import MCP_PORT

DEFAULT_URL = f"http://localhost:{MCP_PORT}/sse"


class MCPSession:
    def __init__(self, url: str = DEFAULT_URL) -> None:
        self.url      = url
        self._cm      = None
        self._session: ClientSession | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict]:
        result = await self._session.list_tools()
        return [{"name": t.name, "description": t.description} for t in result.tools]

    async def call_tool(self, name: str, **kwargs) -> str:
        result = await self._session.call_tool(name, kwargs)
        return "\n".join(c.text for c in result.content if hasattr(c, "text"))

    async def tools_for_ollama(self) -> list[dict]:
        """Return tool schemas in Ollama/OpenAI tool format."""
        result = await self._session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema,
                },
            }
            for t in result.tools
        ]

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "MCPSession":
        self._cm = sse_client(self.url)
        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        if self._session:
            await self._session.__aexit__(*args)
        if self._cm:
            await self._cm.__aexit__(*args)
