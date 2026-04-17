import asyncio
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bot.config import STORAGE_PATH

logger = logging.getLogger(__name__)

_session: ClientSession | None = None
_task: asyncio.Task | None = None
_ready = None
_shutdown = None


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", STORAGE_PATH],
    )


async def _run_mcp():
    global _session
    params = _server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            _session = session
            tools = await session.list_tools()
            logger.info("MCP connected. Tools: %s", [t.name for t in tools.tools])
            _ready.set()
            await _shutdown.wait()
    _session = None


async def start_mcp() -> None:
    global _task, _ready, _shutdown
    _ready = asyncio.Event()
    _shutdown = asyncio.Event()
    _task = asyncio.create_task(_run_mcp())
    await _ready.wait()


async def stop_mcp() -> None:
    global _task
    if _shutdown:
        _shutdown.set()
    if _task:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (asyncio.TimeoutError, Exception):
            _task.cancel()
        _task = None


def get_session() -> ClientSession:
    if _session is None:
        raise RuntimeError("MCP session not started")
    return _session


async def get_tools_as_openai_format() -> list[dict]:
    session = get_session()
    result = await session.list_tools()
    tools = []
    for t in result.tools:
        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        })
    return tools


MAX_TOOL_RESULT_CHARS = 30_000


async def call_tool(name: str, arguments: dict) -> str:
    session = get_session()
    result = await session.call_tool(name, arguments)
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    text = "\n".join(parts)
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + "\n\n... [обрезано, файл слишком большой]"
    return text
