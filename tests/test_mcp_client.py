import asyncio

import pytest


async def test_supervisor_reconnects_on_crash(monkeypatch):
    from bot import mcp_client as mcp

    monkeypatch.setattr(mcp, "RECONNECT_BACKOFF_START", 0.01)
    monkeypatch.setattr(mcp, "RECONNECT_BACKOFF_MAX", 0.05)
    monkeypatch.setattr(mcp, "READY_TIMEOUT", 2.0)

    attempts = {"count": 0}

    async def fake_run_once():
        attempts["count"] += 1
        mcp._session = object()  # pretend we connected
        mcp._ready.set()
        if attempts["count"] < 3:
            mcp._session = None
            raise RuntimeError("simulated crash")
        # On 3rd attempt, hold until shutdown
        await mcp._shutdown.wait()
        mcp._session = None

    monkeypatch.setattr(mcp, "_run_once", fake_run_once)

    await mcp.start_mcp()
    # Wait for the supervisor to go through two crashes + successful reconnect
    for _ in range(200):
        if attempts["count"] >= 3:
            break
        await asyncio.sleep(0.01)

    assert attempts["count"] >= 3
    assert mcp._session is not None

    await mcp.stop_mcp()
    assert mcp._session is None


async def test_supervisor_exits_on_shutdown(monkeypatch):
    from bot import mcp_client as mcp

    async def fake_run_once():
        mcp._session = object()
        mcp._ready.set()
        await mcp._shutdown.wait()
        mcp._session = None

    monkeypatch.setattr(mcp, "_run_once", fake_run_once)
    monkeypatch.setattr(mcp, "READY_TIMEOUT", 2.0)

    await mcp.start_mcp()
    assert mcp._session is not None
    await mcp.stop_mcp()
    assert mcp._task is None


async def test_call_tool_retries_on_failure(monkeypatch):
    from bot import mcp_client as mcp

    monkeypatch.setattr(mcp, "TOOL_CALL_RETRIES", 2)
    monkeypatch.setattr(mcp, "TOOL_CALL_RETRY_DELAY", 0.001)

    calls = {"n": 0}

    class FakeBlock:
        def __init__(self, text):
            self.text = text

    class FakeResult:
        content = [FakeBlock("ok")]

    class FakeSession:
        async def call_tool(self, name, args):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("transient")
            return FakeResult()

    monkeypatch.setattr(mcp, "get_session", lambda: FakeSession())

    result = await mcp.call_tool("read_file", {})
    assert result == "ok"
    assert calls["n"] == 2


async def test_call_tool_raises_after_max_retries(monkeypatch):
    from bot import mcp_client as mcp

    monkeypatch.setattr(mcp, "TOOL_CALL_RETRIES", 1)
    monkeypatch.setattr(mcp, "TOOL_CALL_RETRY_DELAY", 0.001)

    class FakeSession:
        async def call_tool(self, name, args):
            raise RuntimeError("always fails")

    monkeypatch.setattr(mcp, "get_session", lambda: FakeSession())

    with pytest.raises(RuntimeError, match="always fails"):
        await mcp.call_tool("read_file", {})


def test_get_session_raises_when_not_ready(monkeypatch):
    from bot import mcp_client as mcp

    monkeypatch.setattr(mcp, "_session", None)
    with pytest.raises(RuntimeError, match="not available"):
        mcp.get_session()


async def test_call_tool_rejects_non_allowed(monkeypatch):
    from bot import mcp_client as mcp

    with pytest.raises(PermissionError, match="не разрешён"):
        await mcp.call_tool("write_file", {"path": "a", "contents": "x"})


async def test_get_tools_filters_non_allowed(monkeypatch):
    from bot import mcp_client as mcp

    class FakeTool:
        def __init__(self, name):
            self.name = name
            self.description = f"desc-{name}"
            self.inputSchema = {"type": "object"}

    class FakeResult:
        tools = [FakeTool("read_file"), FakeTool("write_file"), FakeTool("search_files")]

    class FakeSession:
        async def list_tools(self):
            return FakeResult()

    monkeypatch.setattr(mcp, "get_session", lambda: FakeSession())

    tools = await mcp.get_tools_as_openai_format()
    names = [t["function"]["name"] for t in tools]
    assert "read_file" in names
    assert "search_files" in names
    assert "write_file" not in names
