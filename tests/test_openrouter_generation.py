import json

from app import ai_generate


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_generate_collection_calls_openrouter_with_configured_model(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        content = {
            "name": "Noir Night",
            "description": "Shadowy crime picks.",
            "movies": [
                {"title": "Le Samourai", "year": 1967, "reason": "Cool procedural restraint with a lonely edge."}
            ],
        }
        return DummyResponse({"choices": [{"message": {"content": json_dumps(content)}}]})

    monkeypatch.setattr(ai_generate, "search_media", lambda *args, **kwargs: None)
    monkeypatch.setattr(ai_generate.httpx, "post", fake_post)

    result = ai_generate.generate_collection(
        "moody crime",
        movie_count=1,
        openrouter_key="test-openrouter-key",
        media_type="movie",
    )

    assert result["name"] == "Noir Night"
    assert result["movies"][0]["match_reason"] == "Cool procedural restraint with a lonely edge."
    assert calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-openrouter-key"
    assert calls[0]["headers"]["HTTP-Referer"] == "https://flickvault.fly.dev"
    assert calls[0]["headers"]["X-OpenRouter-Title"] == "Flickvault"
    assert calls[0]["json"]["model"] == "z-ai/glm-5.2"
    assert calls[0]["json"]["messages"][0]["role"] == "system"
    assert calls[0]["json"]["messages"][1]["role"] == "user"
    assert calls[0]["json"]["max_tokens"] == 2048


def test_generate_collection_requires_openrouter_key():
    try:
        list(ai_generate.generate_collection_iter("anything", openrouter_key=""))
    except ValueError as exc:
        assert str(exc) == "OPENROUTER_API_KEY is not set"
    else:
        raise AssertionError("Expected missing OpenRouter key to raise ValueError")


def json_dumps(value):
    return json.dumps(value)
