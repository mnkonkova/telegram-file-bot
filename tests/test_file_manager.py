import pytest


def test_save_file_writes_bytes(tmp_paths):
    storage, _ = tmp_paths
    from bot.services import file_manager as fm

    result = fm.save_file(b"hello", "a.txt")
    assert result == "a.txt"
    assert (storage / "a.txt").read_bytes() == b"hello"


def test_save_file_rejects_duplicate(tmp_paths):
    from bot.services import file_manager as fm

    fm.save_file(b"hello", "a.txt")
    with pytest.raises(ValueError, match="уже существует"):
        fm.save_file(b"world", "a.txt")


def test_save_file_rejects_path_traversal(tmp_paths):
    from bot.services import file_manager as fm

    with pytest.raises(ValueError, match="Недопустимое имя"):
        fm.save_file(b"x", "../evil.txt")
    with pytest.raises(ValueError, match="Недопустимое имя"):
        fm.save_file(b"x", "sub/a.txt")
    with pytest.raises(ValueError, match="Недопустимое имя"):
        fm.save_file(b"x", "\\evil.txt")
    with pytest.raises(ValueError, match="Недопустимое имя"):
        fm.save_file(b"x", "a\x00b.txt")
    with pytest.raises(ValueError, match="Недопустимое имя"):
        fm.save_file(b"x", ".")


def test_safe_path_prefix_bug_blocked(tmp_paths):
    from bot.services import file_manager as fm

    storage, _ = tmp_paths
    sibling = storage.parent / (storage.name + "-evil")
    sibling.mkdir()
    # commonpath check must reject "storage-evil" even though its realpath
    # starts with the storage realpath as a string prefix.
    with pytest.raises(ValueError):
        fm._safe_path("../" + sibling.name + "/leak.txt")


def test_save_file_chunk_limit(tmp_paths, monkeypatch):
    from bot.services import file_manager as fm

    monkeypatch.setattr(fm, "CHUNK_SIZE", 10)
    monkeypatch.setattr(fm, "MAX_CHUNKS_PER_FILE", 3)
    with pytest.raises(ValueError, match="слишком большой"):
        fm.save_file(b"a" * 100, "huge.txt")


def test_save_file_chunked_duplicate_rejected(tmp_paths, monkeypatch):
    from bot.services import file_manager as fm

    monkeypatch.setattr(fm, "CHUNK_SIZE", 10)
    big = b"a" * 35  # >10 bytes -> 4 parts
    fm.save_file(big, "big.txt")
    with pytest.raises(ValueError, match="уже существует"):
        fm.save_file(big, "big.txt")


def test_delete_file(tmp_paths):
    from bot.services import file_manager as fm

    fm.save_file(b"x", "a.txt")
    fm.delete_file("a.txt")
    with pytest.raises(FileNotFoundError):
        fm.delete_file("a.txt")
