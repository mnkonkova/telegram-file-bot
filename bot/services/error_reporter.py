import html
import json
import logging
import os
import traceback

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import DATA_PATH

CHAT_IDS_FILE = os.path.join(DATA_PATH, "chat_ids.json")
TRACE_ADMIN_USERNAME = "mashakon"
MAX_TRACE_CHARS = 3500

logger = logging.getLogger(__name__)


def _load_chat_ids() -> dict[str, int]:
    if not os.path.exists(CHAT_IDS_FILE):
        return {}
    try:
        with open(CHAT_IDS_FILE) as f:
            return {k.lower(): int(v) for k, v in json.load(f).items()}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _save_chat_ids(data: dict[str, int]) -> None:
    os.makedirs(os.path.dirname(CHAT_IDS_FILE), exist_ok=True)
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(data, f)


def remember_chat_id(username: str | None, chat_id: int | None) -> None:
    if not username or chat_id is None:
        return
    username = username.lower()
    # Only persist chat_ids we actually need (the trace admin).
    # Avoid storing PII of arbitrary users.
    if username != TRACE_ADMIN_USERNAME.lower():
        return
    data = _load_chat_ids()
    if data.get(username) == chat_id:
        return
    data[username] = chat_id
    _save_chat_ids(data)


def get_chat_id(username: str) -> int | None:
    return _load_chat_ids().get(username.lower())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)

    chat_id = get_chat_id(TRACE_ADMIN_USERNAME)
    if chat_id is None:
        logger.warning(
            "Cannot send trace: @%s has not messaged the bot yet", TRACE_ADMIN_USERNAME
        )
        return

    tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    if len(tb) > MAX_TRACE_CHARS:
        tb = tb[-MAX_TRACE_CHARS:]

    header_parts = ["<b>⚠️ Ошибка в боте</b>"]
    if isinstance(update, Update) and update.effective_user:
        u = update.effective_user
        header_parts.append(f"user: @{u.username or u.id}")
    if isinstance(update, Update) and update.effective_message:
        text = update.effective_message.text or update.effective_message.caption or ""
        if text:
            header_parts.append(f"msg: {html.escape(text[:200])}")
    header = "\n".join(header_parts)

    message = f"{header}\n\n<pre>{html.escape(tb)}</pre>"
    try:
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to deliver error trace to admin")
