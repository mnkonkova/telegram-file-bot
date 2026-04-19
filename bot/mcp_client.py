import asyncio
import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bot.config import STORAGE_PATH

logger = logging.getLogger(__name__)

RECONNECT_BACKOFF_START = 1.0
RECONNECT_BACKOFF_MAX = 60.0
READY_TIMEOUT = 30.0

# Allowlist: the agent may only invoke read-only tools. Anything else
# (write_file, edit_file, move_file, create_directory, ...) is rejected
# even if the MCP server exposes it.
ALLOWED_TOOLS = frozenset({
    "read_file",
    "read_text_file",
    "read_multiple_files",
    "list_directory",
    "list_allowed_directories",
    "search_files",
    "get_file_info",
    "directory_tree",
})

_session: ClientSession | None = None
_task: asyncio.Task | None = None
_ready: asyncio.Event | None = None
_shutdown: asyncio.Event | None = None


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", STORAGE_PATH],
    )


async def _run_once() -> None:
    global _session
    params = _server_params()
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            _session = session
            tools = await session.list_tools()
            logger.info("MCP connected. Tools: %s", [t.name for t in tools.tools])
            if _ready is not None:
                _ready.set()
            assert _shutdown is not None
            await _shutdown.wait()
    _session = None


async def _supervisor() -> None:
    backoff = RECONNECT_BACKOFF_START
    assert _shutdown is not None
    while not _shutdown.is_set():
        try:
            await _run_once()
            # Normal shutdown path — exit supervisor.
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            global _session
            _session = None
            if _shutdown.is_set():
                return
            logger.exception("MCP crashed: %s. Reconnecting in %.1fs", e, backoff)
            try:
                await asyncio.wait_for(_shutdown.wait(), timeout=backoff)
                return  # shutdown during backoff
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)


async def start_mcp() -> None:
    global _task, _ready, _shutdown
    _ready = asyncio.Event()
    _shutdown = asyncio.Event()
    _task = asyncio.create_task(_supervisor())
    try:
        await asyncio.wait_for(_ready.wait(), timeout=READY_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("MCP did not become ready within %.0fs", READY_TIMEOUT)
        raise


async def stop_mcp() -> None:
    global _task
    if _shutdown is not None:
        _shutdown.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except (asyncio.TimeoutError, Exception):
            _task.cancel()
        _task = None


def get_session() -> ClientSession:
    if _session is None:
        raise RuntimeError("MCP session not available (reconnecting)")
    return _session


async def get_tools_as_openai_format() -> list[dict]:
    session = get_session()
    result = await session.list_tools()
    tools = []
    for t in result.tools:
        if t.name not in ALLOWED_TOOLS:
            logger.debug("Skipping non-allowed MCP tool: %s", t.name)
            continue
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
TOOL_CALL_RETRIES = 2
TOOL_CALL_RETRY_DELAY = 0.5


async def call_tool(name: str, arguments: dict) -> str:
    if name not in ALLOWED_TOOLS:
        raise PermissionError(f"Инструмент '{name}' не разрешён")
    last_error: Exception | None = None
    for attempt in range(TOOL_CALL_RETRIES + 1):
        try:
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
        except Exception as e:
            last_error = e
            if attempt < TOOL_CALL_RETRIES:
                logger.warning("MCP call_tool %s failed (attempt %d): %s", name, attempt + 1, e)
                await asyncio.sleep(TOOL_CALL_RETRY_DELAY)
            else:
                raise
    raise last_error  # unreachable
