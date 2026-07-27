from common import llm


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, calls):
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs["model"])
        if kwargs["model"] == "deepseek-ai/deepseek-v4-pro":
            raise RuntimeError("nvidia unavailable")
        return _Response("official fallback worked")


class _Chat:
    def __init__(self, calls):
        self.completions = _Completions(calls)


class _Client:
    def __init__(self, calls):
        self.chat = _Chat(calls)


def test_explain_falls_back_from_nvidia_to_official_deepseek(monkeypatch):
    calls = []
    monkeypatch.setattr(llm.config, "chat_providers", lambda: [
        {
            "name": "nvidia",
            "api_key": "nvapi-test",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "deepseek-ai/deepseek-v4-pro",
            "extra_body": {"chat_template_kwargs": {"thinking": False}},
        },
        {
            "name": "deepseek",
            "api_key": "sk-test",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-pro",
            "extra_body": None,
        },
    ])
    monkeypatch.setattr(llm, "_get_client", lambda _provider: _Client(calls))

    assert llm.explain("system", "user", "fallback") == "official fallback worked"
    assert calls == ["deepseek-ai/deepseek-v4-pro", "deepseek-v4-pro"]
