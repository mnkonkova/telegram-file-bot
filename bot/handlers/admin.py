from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.auth import add_user, get_allowed_users, remove_user, require_admin


@require_admin
async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /adduser @username")
        return
    username = context.args[0].lstrip("@")
    try:
        added = add_user(username)
    except ValueError as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    if added:
        await update.message.reply_text(f"Пользователь @{username} добавлен.")
    else:
        await update.message.reply_text(f"@{username} уже в списке.")


@require_admin
async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /removeuser @username")
        return
    username = context.args[0].lstrip("@")
    try:
        removed = remove_user(username)
    except ValueError as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return
    if removed:
        await update.message.reply_text(f"Пользователь @{username} удалён.")
    else:
        await update.message.reply_text(f"@{username} не найден в списке.")


@require_admin
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_allowed_users()
    if not users:
        await update.message.reply_text("Список пользователей пуст.\nАдмины имеют доступ всегда.")
        return
    lines = [f"@{u}" for u in users]
    await update.message.reply_text(
        "Допущенные пользователи:\n" + "\n".join(lines) + "\n\nАдмины имеют доступ всегда."
    )
