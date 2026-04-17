import json
import os
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import ADMIN_USERNAMES, DATA_PATH

USERS_FILE = os.path.join(DATA_PATH, "allowed_users.json")


def _load_users() -> set[str]:
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE) as f:
        return set(json.load(f))


def _save_users(users: set[str]) -> None:
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(sorted(users), f)


def is_admin(username: str | None) -> bool:
    if not username:
        return False
    return username.lower() in {u.lower() for u in ADMIN_USERNAMES}


def is_allowed(username: str | None) -> bool:
    if not username:
        return False
    if is_admin(username):
        return True
    return username.lower() in {u.lower() for u in _load_users()}


def add_user(username: str) -> bool:
    username = username.lstrip("@").lower()
    users = _load_users()
    if username in {u.lower() for u in users}:
        return False
    users.add(username)
    _save_users(users)
    return True


def remove_user(username: str) -> bool:
    username = username.lstrip("@").lower()
    users = _load_users()
    lower_users = {u.lower() for u in users}
    if username not in lower_users:
        return False
    users = {u for u in users if u.lower() != username}
    _save_users(users)
    return True


def get_allowed_users() -> list[str]:
    return sorted(_load_users())


def require_auth(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not is_allowed(user.username):
            await update.message.reply_text("Доступ запрещён.")
            return
        return await func(update, context)
    return wrapper


def require_admin(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not is_admin(user.username):
            await update.message.reply_text("Эта команда доступна только админам.")
            return
        return await func(update, context)
    return wrapper
