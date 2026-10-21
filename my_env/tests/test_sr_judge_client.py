"""The OpenRouter client against a fake transport (no network): request shape, the
API key kept out of every output, retries, and temperature sent only where the model
supports it."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from environment.incident.judge import (
    API_KEY_ENV,
    JudgeClientError,
    OpenRouterClient,
)

SECRET = "sk-or-v1-test-secret-0123456789"


class FakeResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeTransport:
    """Answers POSTs from ``replies`` in order and ``GET /models`` from ``models``
    (a model listing; ``None``: HTTP 404, as if the listing were unavailable)."""

    def __init__(self, replies, models=None):
        self.replies = list(replies)
        self.models = models
        self.requests = []
        self.listings = 0

    def __call__(self, request, timeout=None):
        if request.get_method() == "GET":
            assert request.full_url.endswith("/models")
            self.listings += 1
            if self.models is None:
                raise urllib.error.HTTPError(
                    request.full_url, 404, "missing", {}, io.BytesIO(b"{}")
                )
            return FakeResponse(200, json.dumps({"data": self.models}))
        self.requests.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": dict(request.header_items()),
                "body": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        if status != 200:
            raise urllib.error.HTTPError(
                request.full_url, status, "error", {}, io.BytesIO(body.encode("utf-8"))
            )
        return FakeResponse(status, body)


def ok_body(content="{}", **extra) -> str:
    return json.dumps(
        {
            "id": "gen-1",
            "model": "openai/gpt-6.1-sol-20261001",
            "provider": "OpenAI",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0001},
            **extra,
        }
    )


PAYLOAD = {
    "model": "openai/gpt-6.1-sol",
    "messages": [{"role": "user", "content": "hi"}],
    "temperature": 0,
    "response_format": {"type": "json_schema", "json_schema": {"name": "x"}},
}


def client(transport, sleeps=None, **kwargs):
    return OpenRouterClient(
        SECRET,
        urlopen=transport,
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
        app_title="gb2019-sr-judge",
        **kwargs,
    )


def test_request_shape_and_response():
    transport = FakeTransport([(200, ok_body('{"a": 1}'))])
    response = client(transport, timeout_s=12).complete(PAYLOAD)
    sent = transport.requests[0]
    assert sent["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert sent["method"] == "POST" and sent["timeout"] == 12
    assert sent["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert sent["headers"]["X-title"] == "gb2019-sr-judge"
    assert sent["body"] == PAYLOAD
    assert response.content == '{"a": 1}'
    assert response.usage["cost"] == 0.0001
    assert response.model == "openai/gpt-6.1-sol-20261001"
    assert response.provider == "OpenAI" and response.finish_reason == "stop"
    assert response.temperature_sent is True
    assert SECRET not in json.dumps(response.to_dict())


def test_key_never_in_repr_or_errors():
    c = client(FakeTransport([(401, json.dumps({"error": f"bad key {SECRET}"}))]))
    assert SECRET not in repr(c) and "[redacted]" in repr(c)
    with pytest.raises(JudgeClientError) as info:
        c.complete(PAYLOAD)
    assert "HTTP 401" in str(info.value)
    assert SECRET not in str(info.value) and "[redacted]" in str(info.value)


def test_key_from_environment_only(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(JudgeClientError, match=API_KEY_ENV):
        OpenRouterClient()
    monkeypatch.setenv(API_KEY_ENV, SECRET)
    transport = FakeTransport([(200, ok_body())])
    OpenRouterClient(urlopen=transport).complete(PAYLOAD)
    assert transport.requests[0]["headers"]["Authorization"] == f"Bearer {SECRET}"


def test_retries_rate_limits_and_server_errors():
    sleeps: list[float] = []
    transport = FakeTransport([(429, "slow down"), (503, "busy"), (200, ok_body())])
    response = client(transport, sleeps).complete(PAYLOAD)
    assert response.content == "{}"
    assert sleeps == [1.0, 2.0] and len(transport.requests) == 3
    exhausted = FakeTransport([(429, "no")] * 3)
    with pytest.raises(JudgeClientError, match="HTTP 429"):
        client(exhausted, [], max_retries=2).complete(PAYLOAD)
    assert len(exhausted.requests) == 3


def test_network_errors_are_retried_then_reported():
    error = urllib.error.URLError(f"connection refused for {SECRET}")
    transport = FakeTransport([error, error])
    with pytest.raises(JudgeClientError) as info:
        client(transport, [], max_retries=1).complete(PAYLOAD)
    assert "cannot reach the judge API" in str(info.value)
    assert SECRET not in str(info.value)


def test_temperature_follows_the_model_listing():
    """openai/gpt-6.1-sol lists no temperature parameter on OpenRouter: it is not
    sent, so a require_parameters request still finds an endpoint."""
    listing = [
        {
            "id": "openai/gpt-6.1-sol",
            "supported_parameters": ["max_tokens", "response_format", "reasoning"],
        },
        {"id": "google/gemini-4-pro", "supported_parameters": ["temperature"]},
    ]
    transport = FakeTransport([(200, ok_body()), (200, ok_body())], models=listing)
    c = client(transport)
    response = c.complete(PAYLOAD)
    assert "temperature" not in transport.requests[0]["body"]
    assert response.temperature_sent is False
    gemini = c.complete({**PAYLOAD, "model": "google/gemini-4-pro"})
    assert transport.requests[1]["body"]["temperature"] == 0
    assert gemini.temperature_sent is True
    assert transport.listings == 1  # read once and remembered
    assert c.supported_parameters("unknown/model") is None


def test_temperature_is_dropped_when_rejected():
    transport = FakeTransport(
        [
            (
                400,
                json.dumps(
                    {"error": {"message": "Unsupported parameter: temperature"}}
                ),
            ),
            (200, ok_body()),
        ]
    )
    response = client(transport).complete(PAYLOAD)
    assert "temperature" in transport.requests[0]["body"]
    assert "temperature" not in transport.requests[1]["body"]
    assert response.temperature_sent is False
    no_endpoint = FakeTransport(
        [
            (
                404,
                json.dumps(
                    {
                        "error": {
                            "message": "No endpoints found that can handle the "
                            "requested parameters."
                        }
                    }
                ),
            ),
            (200, ok_body()),
        ]
    )
    assert client(no_endpoint).complete(PAYLOAD).temperature_sent is False


def test_error_objects_and_content_parts():
    with pytest.raises(JudgeClientError, match="judge API error"):
        client(
            FakeTransport([(200, json.dumps({"error": {"code": 400, "message": "x"}}))])
        ).complete(PAYLOAD)
    with pytest.raises(JudgeClientError, match="no choices"):
        client(FakeTransport([(200, json.dumps({"choices": []}))])).complete(PAYLOAD)
    with pytest.raises(JudgeClientError, match="non-JSON"):
        client(FakeTransport([(200, "<html>")])).complete(PAYLOAD)
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": '{"a"'},
                            {"type": "text", "text": ": 1}"},
                        ]
                    }
                }
            ]
        }
    )
    assert client(FakeTransport([(200, body)])).complete(PAYLOAD).content == '{"a": 1}'
