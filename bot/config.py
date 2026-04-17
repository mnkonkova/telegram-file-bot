import os


TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
DATA_PATH = os.environ.get("DATA_PATH", "/app/data")
MAX_AGENT_ITERATIONS = int(os.environ.get("MAX_AGENT_ITERATIONS", "10"))

ADMIN_USERNAMES = {"waymax", "mashakon"}
