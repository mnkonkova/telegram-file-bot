import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import TELEGRAM_BOT_TOKEN
from bot.middleware.auth import is_admin, is_allowed, require_auth
from bot.handlers.admin import cmd_adduser, cmd_removeuser, cmd_users
from bot.handlers.agent import cmd_ask, handle_text
from bot.handlers.files import cmd_cat, cmd_delete, cmd_files, handle_document
from bot.mcp_client import start_mcp, stop_mcp
from bot.services.error_reporter import error_handler, remember_chat_id
from bot.services.heartbeat import start_heartbeat, stop_heartbeat

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _main_keyboard(admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("📂 Файлы", callback_data="files"),
            InlineKeyboardButton("🤖 Задать вопрос AI", callback_data="ask"),
        ],
    ]
    if admin:
        buttons.append([
            InlineKeyboardButton("👥 Пользователи", callback_data="users"),
            InlineKeyboardButton("➕ Добавить юзера", callback_data="adduser"),
        ])
    return InlineKeyboardMarkup(buttons)


async def track_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if user and chat:
        remember_chat_id(user.username, chat.id)


@require_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin = is_admin(user.username)
    text = f"Привет, {user.first_name}!\n\nЯ бот для управления файлами и AI-ассистент.\nВыбери действие:"
    await update.message.reply_text(text, reply_markup=_main_keyboard(admin))


MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # Telegram bot upload limit


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not user or not is_allowed(user.username):
        await query.message.reply_text("Доступ запрещён.")
        return
    admin = is_admin(user.username)
    data = query.data

    if data == "files":
        from bot.services.file_manager import list_files, _format_size
        try:
            entries = list_files()
        except Exception as e:
            await query.message.reply_text(f"Ошибка: {e}")
            return
        if not entries:
            text = "📂 Хранилище пусто."
            kb = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        else:
            text = "📂 Нажми на файл, чтобы скачать:"
            kb = []
            for e in entries:
                if e["is_dir"]:
                    label = f"📁 {e['name']}/"
                else:
                    label = f"📄 {e['name']} ({_format_size(e['size'])})"
                kb.append([
                InlineKeyboardButton(label, callback_data=f"dl:{e['name']}"),
                InlineKeyboardButton("🗑", callback_data=f"rm:{e['name']}"),
            ])
            kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("dl:"):
        import os
        from bot.services.file_manager import _safe_path, _validate_filename
        filename = data[3:]
        try:
            _validate_filename(filename)
            path = _safe_path(filename)
        except ValueError:
            await query.message.reply_text("Недопустимый путь.")
            return
        if not os.path.isfile(path):
            await query.message.reply_text(f"Файл не найден: {filename}")
            return
        if os.path.getsize(path) > MAX_DOWNLOAD_BYTES:
            await query.message.reply_text(
                f"Файл слишком большой для отправки (>{MAX_DOWNLOAD_BYTES // 1024 // 1024} MB)."
            )
            return
        with open(path, "rb") as fh:
            await query.message.reply_document(document=fh, filename=filename)
        kb = [
            [InlineKeyboardButton("📂 К файлам", callback_data="files")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back")],
        ]
        await query.message.reply_text("Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("rm:"):
        filename = data[3:]
        kb = [
            [
                InlineKeyboardButton("Да, удалить", callback_data=f"rm_yes:{filename}"),
                InlineKeyboardButton("Отмена", callback_data="files"),
            ],
        ]
        await query.message.edit_text(
            f"Удалить файл {filename}?",
            reply_markup=InlineKeyboardMarkup(kb),
        )

    elif data.startswith("rm_yes:"):
        from bot.services.file_manager import delete_file
        filename = data[7:]
        try:
            delete_file(filename)
            await query.message.edit_text(f"Файл удалён: {filename}")
        except Exception as e:
            await query.message.edit_text(f"Ошибка: {e}")
        # Return to file list after a moment
        kb = [
            [InlineKeyboardButton("📂 К файлам", callback_data="files")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back")],
        ]
        await query.message.reply_text("Выбери действие:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "ask":
        await query.message.edit_text(
            "🤖 Напиши свой вопрос в чат — я проанализирую файлы и отвечу.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            ),
        )

    elif data == "users" and admin:
        from bot.middleware.auth import get_allowed_users
        users = get_allowed_users()
        if users:
            text = "👥 Допущенные пользователи:\n" + "\n".join(f"• @{u}" for u in users)
        else:
            text = "👥 Список пользователей пуст."
        text += "\n\nАдмины имеют доступ всегда."
        kb = [
            [
                InlineKeyboardButton("➕ Добавить", callback_data="adduser"),
                InlineKeyboardButton("➖ Удалить", callback_data="removeuser"),
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")],
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adduser" and admin:
        context.user_data["awaiting"] = "adduser"
        await query.message.edit_text(
            "Введи @username пользователя для добавления:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Отмена", callback_data="back")]]
            ),
        )

    elif data == "removeuser" and admin:
        context.user_data["awaiting"] = "removeuser"
        await query.message.edit_text(
            "Введи @username пользователя для удаления:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Отмена", callback_data="back")]]
            ),
        )

    elif data == "back":
        context.user_data.pop("awaiting", None)
        text = "Выбери действие:"
        await query.message.edit_text(text, reply_markup=_main_keyboard(admin))


async def handle_text_or_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    from bot.middleware.auth import is_allowed
    if not is_allowed(user.username):
        await update.message.reply_text("Доступ запрещён.")
        return

    awaiting = context.user_data.get("awaiting")

    if awaiting == "adduser" and is_admin(user.username):
        from bot.middleware.auth import add_user
        username = update.message.text.strip().lstrip("@")
        try:
            added = add_user(username)
            text = f"Пользователь @{username} добавлен." if added else f"@{username} уже в списке."
        except ValueError as e:
            text = f"Ошибка: {e}"
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(text, reply_markup=_main_keyboard(is_admin(user.username)))
        return

    if awaiting == "removeuser" and is_admin(user.username):
        from bot.middleware.auth import remove_user
        username = update.message.text.strip().lstrip("@")
        try:
            removed = remove_user(username)
            text = f"Пользователь @{username} удалён." if removed else f"@{username} не найден в списке."
        except ValueError as e:
            text = f"Ошибка: {e}"
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(text, reply_markup=_main_keyboard(is_admin(user.username)))
        return

    # Default: AI agent
    await handle_text(update, context)


async def post_init(app):
    logger.info("Setting bot commands...")
    await app.bot.set_my_commands([
        BotCommand("start", "Начало работы"),
        BotCommand("files", "Список файлов"),
        BotCommand("cat", "Показать файл"),
        BotCommand("delete", "Удалить файл"),
        BotCommand("ask", "Задать вопрос AI"),
        BotCommand("adduser", "Добавить пользователя (админ)"),
        BotCommand("removeuser", "Удалить пользователя (админ)"),
        BotCommand("users", "Список пользователей (админ)"),
    ])
    from bot.services.file_manager import rebuild_index
    logger.info("Rebuilding file index...")
    rebuild_index()
    logger.info("Starting MCP filesystem server...")
    await start_mcp()
    logger.info("MCP ready.")
    await start_heartbeat()


async def post_shutdown(app):
    logger.info("Stopping MCP...")
    await stop_mcp()
    await stop_heartbeat()


def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Track chat_ids for error reporting (group=-1 runs before other handlers)
    app.add_handler(MessageHandler(filters.ALL, track_chat_id), group=-1)

    # Error handler (sends tracebacks to admin)
    app.add_error_handler(error_handler)

    # Start
    app.add_handler(CommandHandler("start", cmd_start))

    # File commands
    app.add_handler(CommandHandler("files", cmd_files))
    app.add_handler(CommandHandler("ls", cmd_files))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(CommandHandler("cat", cmd_cat))

    # Admin commands
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("users", cmd_users))

    # AI agent
    app.add_handler(CommandHandler("ask", cmd_ask))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Document upload
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Plain text -> agent or awaiting input (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_or_action))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
