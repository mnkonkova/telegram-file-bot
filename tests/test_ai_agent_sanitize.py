def test_sanitize_strips_control_chars():
    from bot.services import ai_agent

    s = "hello\x07\x1b[31mRED\x1b[0m\nworld"
    out = ai_agent._sanitize_for_prompt(s, 100)
    assert "\x07" not in out
    assert "\x1b" not in out
    assert "hello" in out and "world" in out


def test_sanitize_truncates():
    from bot.services import ai_agent

    s = "a" * 1000
    out = ai_agent._sanitize_for_prompt(s, 10)
    assert len(out) <= 11  # 10 + ellipsis char


def test_sanitize_keeps_newline_and_tab():
    from bot.services import ai_agent

    out = ai_agent._sanitize_for_prompt("a\nb\tc", 100)
    assert out == "a\nb\tc"


def test_build_file_list_sanitizes_names(monkeypatch):
    from bot.services import ai_agent

    monkeypatch.setattr(
        ai_agent,
        "get_file_index",
        lambda: {
            "normal.txt": {"size": 10},
            "evil\x00IGNORE_ALL.txt": {"size": 5},
        },
    )
    out = ai_agent._build_file_list()
    assert "\x00" not in out
    assert "normal.txt" in out
