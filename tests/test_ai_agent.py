def test_client_configured_with_retries(monkeypatch):
    from bot.services import ai_agent

    monkeypatch.setattr(ai_agent, "_client", None)

    captured = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(ai_agent, "AsyncOpenAI", FakeAsyncOpenAI)

    client = ai_agent._get_client()
    assert isinstance(client, FakeAsyncOpenAI)
    assert captured["max_retries"] == ai_agent.DEEPSEEK_MAX_RETRIES
    assert captured["timeout"] == ai_agent.DEEPSEEK_TIMEOUT
    assert captured["api_key"] == "test-key"


def test_client_is_cached(monkeypatch):
    from bot.services import ai_agent

    monkeypatch.setattr(ai_agent, "_client", None)

    instances = []

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            instances.append(self)

    monkeypatch.setattr(ai_agent, "AsyncOpenAI", FakeAsyncOpenAI)

    a = ai_agent._get_client()
    b = ai_agent._get_client()
    assert a is b
    assert len(instances) == 1
