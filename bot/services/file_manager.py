import json
import os

from bot.config import DATA_PATH, STORAGE_PATH

INDEX_FILE = os.path.join(DATA_PATH, "file_index.json")
PREVIEW_CHARS = 500


def _safe_path(filename: str) -> str:
    joined = os.path.join(STORAGE_PATH, filename)
    real = os.path.realpath(joined)
    if not real.startswith(os.path.realpath(STORAGE_PATH)):
        raise ValueError("Недопустимый путь")
    return real


def list_files(subpath: str = "") -> list[dict]:
    target = _safe_path(subpath) if subpath else os.path.realpath(STORAGE_PATH)
    if not os.path.isdir(target):
        raise FileNotFoundError(f"Директория не найдена: {subpath}")

    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        is_dir = os.path.isdir(full)
        size = os.path.getsize(full) if not is_dir else None
        entries.append({"name": name, "is_dir": is_dir, "size": size})
    return entries


CHUNK_SIZE = 50_000  # ~50KB per chunk (text files)
TEXT_EXTENSIONS = {
    ".txt", ".csv", ".json", ".md", ".py", ".js", ".ts", ".html",
    ".css", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".log", ".sql", ".sh", ".env", ".rst", ".tex",
}


def _is_text_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in TEXT_EXTENSIONS


def save_file(data: bytes, filename: str) -> str | list[str]:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Недопустимое имя файла")

    if _is_text_file(filename) and len(data) > CHUNK_SIZE:
        parts = _save_chunked(data, filename)
        for p in parts:
            index_file(p)
        _vector_index(filename, data)
        return parts

    path = _safe_path(filename)
    with open(path, "wb") as f:
        f.write(data)
    index_file(filename)
    _vector_index(filename, data)
    return filename


def _vector_index(filename: str, data: bytes) -> None:
    if not _is_text_file(filename):
        return
    try:
        from bot.services.vector_store import index_file as vec_index
        text = data.decode("utf-8", errors="replace")
        vec_index(filename, text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Vector indexing failed for %s: %s", filename, e)


def _save_chunked(data: bytes, filename: str) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    name, ext = os.path.splitext(filename)
    parts = []
    for i in range(0, len(text), CHUNK_SIZE):
        chunk = text[i : i + CHUNK_SIZE]
        part_name = f"{name}_part{len(parts) + 1}{ext}"
        path = _safe_path(part_name)
        with open(path, "w") as f:
            f.write(chunk)
        parts.append(part_name)
    return parts


def delete_file(filename: str) -> None:
    path = _safe_path(filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл не найден: {filename}")
    if os.path.isdir(path):
        raise IsADirectoryError(f"Нельзя удалить директорию: {filename}")
    os.remove(path)
    unindex_file(filename)
    try:
        from bot.services.vector_store import remove_file as vec_remove
        vec_remove(filename)
    except Exception:
        pass


def read_file(filename: str, max_chars: int = 4000) -> str:
    path = _safe_path(filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Файл не найден: {filename}")
    with open(path, "r", errors="replace") as f:
        content = f.read(max_chars + 1)
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return content, truncated


def format_file_list(entries: list[dict]) -> str:
    if not entries:
        return "Папка пуста."
    lines = []
    for e in entries:
        if e["is_dir"]:
            lines.append(f"📁 {e['name']}/")
        else:
            size = _format_size(e["size"])
            lines.append(f"📄 {e['name']}  ({size})")
    return "\n".join(lines)


def _format_size(size: int | None) -> str:
    if size is None:
        return "?"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# --- File index ---

def _load_index() -> dict:
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE) as f:
        return json.load(f)


def _save_index(index: dict) -> None:
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _make_preview(filepath: str) -> str:
    try:
        with open(filepath, "r", errors="replace") as f:
            text = f.read(PREVIEW_CHARS + 1)
        if len(text) > PREVIEW_CHARS:
            text = text[:PREVIEW_CHARS] + "..."
        return text.strip()
    except Exception:
        return "(бинарный файл)"


def index_file(filename: str) -> None:
    path = _safe_path(filename)
    if not os.path.isfile(path):
        return
    index = _load_index()
    _, ext = os.path.splitext(filename.lower())
    if ext in TEXT_EXTENSIONS:
        preview = _make_preview(path)
    else:
        preview = f"(бинарный файл, {_format_size(os.path.getsize(path))})"
    index[filename] = {
        "size": os.path.getsize(path),
        "ext": ext,
        "preview": preview,
    }
    _save_index(index)


def unindex_file(filename: str) -> None:
    index = _load_index()
    index.pop(filename, None)
    _save_index(index)


def get_file_index() -> dict:
    return _load_index()


def rebuild_index() -> None:
    index = {}
    storage = os.path.realpath(STORAGE_PATH)
    for name in sorted(os.listdir(storage)):
        full = os.path.join(storage, name)
        if not os.path.isfile(full):
            continue
        _, ext = os.path.splitext(name.lower())
        if ext in TEXT_EXTENSIONS:
            preview = _make_preview(full)
        else:
            preview = f"(бинарный файл, {_format_size(os.path.getsize(full))})"
        index[name] = {
            "size": os.path.getsize(full),
            "ext": ext,
            "preview": preview,
        }
    _save_index(index)
