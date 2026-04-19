import os


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Environment variable {name} is required")
    return val


def __getattr__(name: str):
    # Lazy lookup: secrets are only fetched when actually used. This lets
    # healthcheck and tests import this module without all secrets set.
    if name == "TELEGRAM_BOT_TOKEN":
        return _require("TELEGRAM_BOT_TOKEN")
    if name == "DEEPSEEK_API_KEY":
        return _require("DEEPSEEK_API_KEY")
    raise AttributeError(name)


DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
DATA_PATH = os.environ.get("DATA_PATH", "/app/data")
MAX_AGENT_ITERATIONS = int(os.environ.get("MAX_AGENT_ITERATIONS", "10"))

ADMIN_USERNAMES = {"waymax", "mashakon"}
