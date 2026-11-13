"""Talk to an OpenAI-compatible chat-completions endpoint with the standard library only.

Every failure becomes an `AIError` with a plain message. Messages never contain the API key or the
request body, and nothing here logs.
"""

import http.client
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Protocol
from urllib.parse import urlsplit

from second_opinion.ai.config import AIConfig, load_config

_BACKOFF_SECONDS = 0.5
_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


class AIError(Exception):
    """The AI layer could not do its job. The message is safe to show to a user."""


class ChatClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict: ...


class _FormatRejected(Exception):
    """The server refused the `response_format` parameter."""


class _Retryable(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0] if "```" in text else text
    return text.strip()


def _balanced_objects(text: str):
    """Yield each balanced `{...}` slice, scanning from every opening brace (string-aware)."""
    start = text.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for pos in range(start, len(text)):
            ch = text[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : pos + 1]
                    break
        start = text.find("{", start + 1)


def _parse_object(content: str) -> dict:
    """The JSON object in a model answer: fenced, bare, or wrapped in prose."""
    if "</think>" in content:
        content = content.rsplit("</think>", 1)[1]
    content = _strip_fences(content)
    for candidate in [content, *_balanced_objects(content)]:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AIError("The AI answer was not valid JSON")


def _join_stream(body: bytes) -> dict | None:
    """A chat answer from a server-sent-events body (`data: {...}` chunks), or None if it is not one.

    Some gateways stream even when `stream` is false; the chunks' `delta.content` pieces are the answer.
    """
    pieces: list[str] = []
    seen_chunk = False
    for line in body.decode("utf-8", "replace").splitlines():
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
            delta = chunk["choices"][0].get("delta") or {}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            continue
        seen_chunk = True
        content = delta.get("content")
        if isinstance(content, str):
            pieces.append(content)
    if not seen_chunk:
        return None
    return {"choices": [{"message": {"role": "assistant", "content": "".join(pieces)}}]}


def _message_text(payload: object) -> str | None:
    try:
        content = payload["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        raise AIError("The AI service sent an unexpected answer") from None
    if isinstance(content, list):  # some gateways return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content if isinstance(content, str) else None


class OpenAICompatClient:
    def __init__(self, config: AIConfig):
        self._config = config

    def __repr__(self) -> str:
        return f"OpenAICompatClient(model={self._config.model!r})"

    def complete_json(self, system: str, user: str) -> dict:
        payload = {
            "model": self._config.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        try:
            answer = self._post(payload)
        except _FormatRejected:
            del payload["response_format"]
            try:
                answer = self._post(payload)
            except _FormatRejected:
                raise AIError("The AI service did not accept the request (HTTP 400)") from None
        text = _message_text(answer)
        if not text:
            raise AIError("The AI answer was not valid JSON")
        return _parse_object(text)

    def _post(self, payload: dict) -> object:
        """One request, plus one retry on 429 / 5xx / a dropped connection."""
        try:
            return self._send(payload)
        except _Retryable:
            time.sleep(_BACKOFF_SECONDS)
        try:
            return self._send(payload)
        except _Retryable as err:
            raise AIError(err.message) from None

    def _send(self, payload: dict) -> object:
        url = self._config.base_url + "/chat/completions"
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise AIError("The AI service address is not a valid http(s) URL")
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        # A local gateway must never be sent through a system proxy.
        opener = (
            urllib.request.build_opener(urllib.request.ProxyHandler({}))
            if parts.hostname in _LOOPBACK
            else urllib.request.build_opener()
        )
        try:
            with opener.open(request, timeout=self._config.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as err:
            raise self._http_failure(err) from None
        except (TimeoutError, socket.timeout):
            raise AIError("The AI service timed out") from None
        except urllib.error.URLError as err:
            if isinstance(err.reason, (TimeoutError, socket.timeout)):
                raise AIError("The AI service timed out") from None
            if isinstance(err.reason, ConnectionResetError):
                raise _Retryable("The AI service dropped the connection") from None
            raise AIError("The AI service could not be reached") from None
        except (ConnectionResetError, http.client.RemoteDisconnected):
            raise _Retryable("The AI service dropped the connection") from None
        except UnicodeEncodeError:
            raise AIError("The AI key contains characters that cannot be sent") from None
        except (OSError, http.client.HTTPException):
            raise AIError("The AI service request failed") from None
        try:
            return json.loads(body)
        except ValueError:
            pass
        streamed = _join_stream(body)
        if streamed is None:
            raise AIError("The AI service sent an unexpected answer")
        return streamed

    @staticmethod
    def _http_failure(err: urllib.error.HTTPError) -> Exception:
        status = err.code
        if status in (400, 422):
            try:
                detail = err.read(65536).decode("utf-8", "replace").lower()
            except Exception:
                detail = ""
            if "response_format" in detail:
                return _FormatRejected()
        if status == 429 or status >= 500:
            return _Retryable(f"The AI service did not answer (HTTP {status})")
        if status in (401, 403):
            return AIError(f"The AI service refused the key (HTTP {status})")
        return AIError(f"The AI service did not accept the request (HTTP {status})")


class ScriptedClient:
    """A stand-in for tests: returns or raises the scripted responses in order and records the prompts."""

    def __init__(self, responses: list[dict | Exception]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        if not self._responses:
            raise RuntimeError("ScriptedClient has no more scripted responses")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client() -> ChatClient | None:
    """A client for the configured endpoint, or None when the AI layer is off."""
    config = load_config()
    return OpenAICompatClient(config) if config else None
