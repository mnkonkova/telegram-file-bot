from unittest.mock import AsyncMock, MagicMock


def test_remember_chat_id_admin_only(tmp_paths):
    from bot.services import error_reporter as er

    # Non-admin: not persisted (PII minimization)
    er.remember_chat_id("alice", 12345)
    assert er.get_chat_id("alice") is None

    # Trace admin: persisted
    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, 99)
    assert er.get_chat_id(er.TRACE_ADMIN_USERNAME) == 99
    assert er.get_chat_id(er.TRACE_ADMIN_USERNAME.upper()) == 99


def test_remember_chat_id_ignores_none(tmp_paths):
    from bot.services import error_reporter as er

    er.remember_chat_id(None, 1)
    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, None)
    assert er.get_chat_id(er.TRACE_ADMIN_USERNAME) is None


def test_remember_chat_id_updates_existing(tmp_paths):
    from bot.services import error_reporter as er

    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, 100)
    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, 200)
    assert er.get_chat_id(er.TRACE_ADMIN_USERNAME) == 200


async def test_error_handler_sends_trace_to_admin(tmp_paths):
    from bot.services import error_reporter as er

    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, 999)

    try:
        raise RuntimeError("boom")
    except RuntimeError as e:
        err = e

    context = MagicMock()
    context.error = err
    context.bot.send_message = AsyncMock()

    await er.error_handler(object(), context)

    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 999
    assert "RuntimeError" in kwargs["text"]
    assert "boom" in kwargs["text"]
    assert kwargs["parse_mode"] == "HTML"


async def test_error_handler_skips_when_admin_unknown(tmp_paths):
    from bot.services import error_reporter as er

    context = MagicMock()
    context.error = RuntimeError("boom")
    context.bot.send_message = AsyncMock()

    await er.error_handler(object(), context)

    context.bot.send_message.assert_not_called()


async def test_error_handler_truncates_long_trace(tmp_paths):
    from bot.services import error_reporter as er

    er.remember_chat_id(er.TRACE_ADMIN_USERNAME, 1)

    try:
        raise RuntimeError("X" * 10_000)
    except RuntimeError as e:
        err = e

    context = MagicMock()
    context.error = err
    context.bot.send_message = AsyncMock()

    await er.error_handler(object(), context)
    text = context.bot.send_message.await_args.kwargs["text"]
    # message includes header + <pre>...</pre>, length bounded
    assert len(text) < er.MAX_TRACE_CHARS + 500
