import os
import sys

# Required env vars must be set BEFORE importing bot.config (module-level os.environ[...])
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import pytest


@pytest.fixture
def tmp_paths(tmp_path, monkeypatch):
    """Redirect STORAGE_PATH and DATA_PATH to a tmp dir, and reset any modules
    that cached these paths at import time."""
    storage = tmp_path / "storage"
    data = tmp_path / "data"
    storage.mkdir()
    data.mkdir()

    import bot.config as config
    monkeypatch.setattr(config, "STORAGE_PATH", str(storage))
    monkeypatch.setattr(config, "DATA_PATH", str(data))

    # Patch already-imported modules that bound these constants at import time.
    for mod_name in (
        "bot.services.file_manager",
        "bot.services.error_reporter",
        "bot.services.heartbeat",
        "bot.middleware.auth",
    ):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "STORAGE_PATH"):
                monkeypatch.setattr(mod, "STORAGE_PATH", str(storage))
            if hasattr(mod, "DATA_PATH"):
                monkeypatch.setattr(mod, "DATA_PATH", str(data))
            if hasattr(mod, "INDEX_FILE"):
                monkeypatch.setattr(mod, "INDEX_FILE", str(data / "file_index.json"))
            if hasattr(mod, "CHAT_IDS_FILE"):
                monkeypatch.setattr(mod, "CHAT_IDS_FILE", str(data / "chat_ids.json"))
            if hasattr(mod, "HEARTBEAT_FILE"):
                monkeypatch.setattr(mod, "HEARTBEAT_FILE", str(data / "heartbeat"))
            if hasattr(mod, "USERS_FILE"):
                monkeypatch.setattr(mod, "USERS_FILE", str(data / "allowed_users.json"))

    # Prevent vector_store side-effects (network calls) during file_manager tests
    import bot.services.file_manager as fm_mod
    monkeypatch.setattr(fm_mod, "_vector_index", lambda *a, **kw: None)

    return storage, data
