"""Chat client for OpenRouter's OpenAI-compatible API (standard library only).

The API key comes from the ``OPENROUTER_API_KEY`` environment variable (or the
constructor, for tests). It is sent only in the ``Authorization`` header and never
appears in ``repr``, logs, exceptions or outputs: every error text is redacted.

Any object with a ``complete(payload) -> ChatResponse`` method can stand in for the
client (the tests use a mocked client and never call the network).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "API_KEY_ENV",
    "ChatClient",
    "ChatResponse",
    "JudgeClientError",
    "OpenRouterClient",
]

API_KEY_ENV = "OPENROUTER_API_KEY"
_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}


class JudgeClientError(RuntimeError):
    """The judge model could not be called (text redacted; no key inside)."""


@dataclass
class ChatResponse:
    """One chat completion: the message text and what the provider reported."""

    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    provider: str | None = None
    finish_reason: str | None = None
    response_id: str | None = None
    latency_s: float | None = None
    temperature_sent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "usage": dict(self.usage),
            "model": self.model,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
            "response_id": self.response_id,
            "latency_s": self.latency_s,
            "temperature_sent": self.temperature_sent,
        }


class ChatClient(Protocol):
    def complete(self, payload: Mapping[str, Any]) -> ChatResponse: ...


def _redact(text: str, secret: str | None) -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
    return text


class OpenRouterClient:
    """POST ``{base_url}/chat/completions`` with retries on rate limits, server errors
    and timeouts.

    Temperature is sent only where the model supports it: before the first request
    for a model the client reads the model's ``supported_parameters`` from the public
    ``{base_url}/models`` listing (no cost), and drops ``temperature`` when it is not
    listed (reasoning models such as ``openai/gpt-6.1-sol`` do not take one). If the
    listing is unavailable and the provider rejects the parameter, the request is
    repeated once without it. ``ChatResponse.temperature_sent`` records which
    happened."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_s: float = 300.0,
        max_retries: int = 3,
        app_title: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get(API_KEY_ENV, "")
        if not key or not key.strip():
            raise JudgeClientError(
                f"{API_KEY_ENV} is not set: the judge needs an OpenRouter API key in "
                "the environment"
            )
        self.__key = key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.app_title = app_title
        self._sleep = sleep
        self._urlopen = urlopen or urllib.request.urlopen
        self._listing: dict[str, frozenset[str]] | None = None

    def __repr__(self) -> str:
        return (
            f"OpenRouterClient(base_url={self.base_url!r}, api_key='[redacted]', "
            f"timeout_s={self.timeout_s}, max_retries={self.max_retries})"
        )

    def supported_parameters(self, model: str) -> frozenset[str] | None:
        """The request parameters OpenRouter lists for ``model`` (``None`` when the
        listing cannot be read or does not hold the model); the listing is read once
        per client."""
        if self._listing is None:
            listing: dict[str, frozenset[str]] = {}
            try:
                status, text = self._send("GET", "/models", None)
                data = json.loads(text) if status == 200 else {}
                for entry in data.get("data") or []:
                    params = entry.get("supported_parameters")
                    if isinstance(entry.get("id"), str) and isinstance(params, list):
                        listing[entry["id"]] = frozenset(str(p) for p in params)
            except (OSError, ValueError, AttributeError):
                listing = {}
            self._listing = listing
        return self._listing.get(model)

    def _post(self, payload: Mapping[str, Any]) -> tuple[int, str]:
        return self._send("POST", "/chat/completions", payload)

    def _send(
        self, method: str, path: str, payload: Mapping[str, Any] | None
    ) -> tuple[int, str]:
        headers = {
            "Authorization": f"Bearer {self.__key}",
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.app_title:
            headers["X-Title"] = self.app_title
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with self._urlopen(request, timeout=self.timeout_s) as response:
                return int(response.status), response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            try:
                text = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - the body is optional
                text = ""
            return int(exc.code), text

    def complete(self, payload: Mapping[str, Any]) -> ChatResponse:
        payload = dict(payload)
        if "temperature" in payload:
            params = self.supported_parameters(str(payload.get("model")))
            if params is not None and "temperature" not in params:
                payload.pop("temperature")
        temperature_sent = "temperature" in payload
        attempt = 0
        dropped_temperature = False
        while True:
            started = time.monotonic()
            try:
                status, text = self._post(payload)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < self.max_retries:
                    self._sleep(min(2.0**attempt, 30.0))
                    attempt += 1
                    continue
                raise JudgeClientError(
                    _redact(f"cannot reach the judge API: {exc}", self.__key)
                ) from None
            latency = round(time.monotonic() - started, 3)
            if (
                status in (400, 404)
                and "temperature" in payload
                and not dropped_temperature
                and ("temperature" in text.lower() or "parameters" in text.lower())
            ):
                payload.pop("temperature")
                temperature_sent = False
                dropped_temperature = True
                continue
            if status in _RETRY_STATUS and attempt < self.max_retries:
                self._sleep(min(2.0**attempt, 30.0))
                attempt += 1
                continue
            if status != 200:
                raise JudgeClientError(
                    _redact(
                        f"judge API returned HTTP {status}: {text[:500]}", self.__key
                    )
                )
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                raise JudgeClientError(
                    _redact(f"judge API returned non-JSON: {text[:200]}", self.__key)
                ) from None
            if not isinstance(data, Mapping):
                raise JudgeClientError("judge API returned a non-object response")
            if data.get("error"):
                error = json.dumps(data["error"], ensure_ascii=False)[:500]
                code = (
                    data["error"].get("code")
                    if isinstance(data["error"], Mapping)
                    else None
                )
                if code in _RETRY_STATUS and attempt < self.max_retries:
                    self._sleep(min(2.0**attempt, 30.0))
                    attempt += 1
                    continue
                raise JudgeClientError(_redact(f"judge API error: {error}", self.__key))
            choices = data.get("choices") or []
            if not choices or not isinstance(choices[0], Mapping):
                raise JudgeClientError("judge API returned no choices")
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):  # content parts
                content = "".join(
                    str(part.get("text") or "")
                    for part in content
                    if isinstance(part, Mapping)
                )
            return ChatResponse(
                content=str(content or ""),
                usage=dict(data.get("usage") or {}),
                model=data.get("model"),
                provider=data.get("provider"),
                finish_reason=choices[0].get("finish_reason"),
                response_id=data.get("id"),
                latency_s=latency,
                temperature_sent=temperature_sent,
            )
