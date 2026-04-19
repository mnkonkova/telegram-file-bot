from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.auth import require_auth
from bot.services.file_manager import (
    delete_file,
    format_file_list,
    list_files,
    read_file,
    save_file,
)
from bot.services.rate_limit import upload_limiter


@require_auth
async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subpath = " ".join(context.args) if context.args else ""
    try:
        entries = list_files(subpath)
    except (FileNotFoundError, ValueError) as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    text = format_file_list(entries)
    header = f"📂 /{subpath}" if subpath else "📂 /storage"
    await update.message.reply_text(f"{header}\n\n{text}")


@require_auth
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /delete <имя_файла>")
        return
    filename = " ".join(context.args)
    try:
        delete_file(filename)
    except (FileNotFoundError, ValueError, IsADirectoryError) as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    await update.message.reply_text(f"Файл удалён: {filename}")


@require_auth
async def cmd_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /cat <имя_файла>")
        return
    filename = " ".join(context.args)
    try:
        content, truncated = read_file(filename)
    except (FileNotFoundError, ValueError) as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    msg = f"📄 {filename}\n\n{content}"
    if truncated:
        msg += "\n\n⚠️ Файл обрезан (слишком большой)"
    # Plain text: avoids Markdown injection via filename or content.
    await update.message.reply_text(msg)


@require_auth
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return
    username = update.effective_user.username if update.effective_user else None
    if not upload_limiter.allow(username):
        await update.message.reply_text(
            "Слишком часто. Попробуй через минуту."
        )
        return
    if not doc.file_name or not doc.file_name.lower().endswith(".txt"):
        await update.message.reply_text("Принимаю только .txt файлы.")
        return
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("Файл слишком большой (макс. 20 MB).")
        return
    file = await doc.get_file()
    data = await file.download_as_bytearray()
    try:
        result = save_file(bytes(data), doc.file_name)
    except ValueError as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    if isinstance(result, list):
        parts_list = "\n".join(f"  • {p}" for p in result)
        await update.message.reply_text(
            f"Файл большой — разбит на {len(result)} частей:\n{parts_list}"
        )
    else:
        await update.message.reply_text(f"Файл сохранён: {result}")
