"""
MCP Server — tool registration and request handling.

All tool definitions live in schemas.py; all execution logic lives in handlers.py.
Run via http_app.py, not directly.
"""
from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server import handlers
from mcp_server.schemas import TOOLS

app = Server("github-agent-tools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(**t) for t in TOOLS]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        fn     = getattr(handlers, name)
        result = fn(**arguments)
        return [TextContent(type="text", text=result)]
    except AttributeError:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"ERROR: {exc}")]
