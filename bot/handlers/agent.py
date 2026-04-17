import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.auth import require_auth
from bot.services.ai_agent import run_agent

logger = logging.getLogger(__name__)


@require_auth
async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /ask <ваш вопрос>")
        return
    question = " ".join(context.args)
    await _process_question(update, question)


@require_auth
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    question = update.message.text
    await _process_question(update, question)


async def _process_question(update: Update, question: str):
    status_msg = await update.message.reply_text("⏳ Запускаю агента...")
    last_text = status_msg.text

    async def on_status(text: str):
        nonlocal last_text
        if text == last_text:
            return
        last_text = text
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    try:
        answer = await run_agent(question, on_status=on_status)
    except asyncio.TimeoutError:
        await status_msg.edit_text("⏰ Агент не успел ответить за 2 минуты. Попробуй уточнить вопрос.")
        return
    except Exception as e:
        await status_msg.edit_text(f"Ошибка агента: {e}")
        return

    try:
        await status_msg.delete()
    except Exception:
        pass

    if len(answer) <= 4096:
        await update.message.reply_text(answer)
    else:
        for i in range(0, len(answer), 4096):
            await update.message.reply_text(answer[i : i + 4096])
