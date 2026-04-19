import pytest


def test_add_user_rejects_invalid(tmp_paths):
    from bot.middleware import auth

    with pytest.raises(ValueError):
        auth.add_user("has space")
    with pytest.raises(ValueError):
        auth.add_user("emoji😀")
    with pytest.raises(ValueError):
        auth.add_user("")


def test_add_and_remove_user(tmp_paths):
    from bot.middleware import auth

    assert auth.add_user("alice") is True
    assert auth.add_user("alice") is False  # duplicate
    assert "alice" in auth.get_allowed_users()
    assert auth.remove_user("alice") is True
    assert auth.remove_user("alice") is False


def test_is_allowed(tmp_paths):
    from bot.middleware import auth

    auth.add_user("bob")
    assert auth.is_allowed("bob") is True
    assert auth.is_allowed("BOB") is True
    assert auth.is_allowed("eve") is False
    assert auth.is_allowed(None) is False


def test_admins_always_allowed(tmp_paths):
    from bot.middleware import auth
    from bot.config import ADMIN_USERNAMES

    admin = next(iter(ADMIN_USERNAMES))
    assert auth.is_allowed(admin) is True
