import json
import logging
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from second_opinion.ai import client as client_module
from second_opinion.ai.client import AIError, OpenAICompatClient, ScriptedClient, make_client
from second_opinion.ai.config import AIConfig

KEY = "sk-test-SECRET-1234"


def chat(content, **extra):
    return {"choices": [{"message": {"role": "assistant", "content": content, **extra}}]}


class Reply:
    def __init__(self, status=200, body=None, raw=None, delay=0.0, drop=False):
        self.status, self.body, self.raw, self.delay, self.drop = status, body, raw, delay, drop


class Gateway:
    def __init__(self):
        self.replies: list[Reply] = []
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                outer.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(raw)}
                )
                reply = outer.replies.pop(0) if outer.replies else Reply(500)
                if reply.delay:
                    threading.Event().wait(reply.delay)
                if reply.drop:
                    self.close_connection = True
                    return
                payload = reply.raw if reply.raw is not None else json.dumps(reply.body or {}).encode()
                try:
                    self.send_response(reply.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/v1"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(client_module, "_BACKOFF_SECONDS", 0.0)
    gw = Gateway()
    yield gw
    gw.close()


def make(gateway, timeout=5.0):
    return OpenAICompatClient(AIConfig(base_url=gateway.base_url, api_key=KEY, model="test-model", timeout=timeout))


def assert_no_key(exc: BaseException):
    text = "".join(traceback.format_exception(exc)) + str(exc) + repr(exc)
    assert KEY not in text


def test_request_shape(gateway):
    gateway.replies = [Reply(body=chat('{"ok": true}'))]
    assert make(gateway).complete_json("SYS", "USER") == {"ok": True}
    (req,) = gateway.requests
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["Authorization"] == f"Bearer {KEY}"
    assert req["headers"]["Content-Type"] == "application/json"
    assert req["body"] == {
        "model": "test-model",
        "messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}],
        "temperature": 0,
        "stream": False,
        "response_format": {"type": "json_object"},
    }


def test_fenced_json(gateway):
    gateway.replies = [Reply(body=chat('```json\n{"a": 1}\n```'))]
    assert make(gateway).complete_json("s", "u") == {"a": 1}


def test_prose_wrapped_json(gateway):
    content = 'Sure! Here is the plan: {"a": {"b": "x } y"}, "c": [1, 2]} Hope that helps {not json}'
    gateway.replies = [Reply(body=chat(content))]
    assert make(gateway).complete_json("s", "u") == {"a": {"b": "x } y"}, "c": [1, 2]}


def test_reasoning_content_is_ignored(gateway):
    gateway.replies = [Reply(body=chat('{"a": 1}', reasoning_content='thinking {"a": 2} ...'))]
    assert make(gateway).complete_json("s", "u") == {"a": 1}


def test_think_block_with_braces_is_skipped(gateway):
    gateway.replies = [Reply(body=chat('<think>maybe {"a": 2}</think>{"a": 1}'))]
    assert make(gateway).complete_json("s", "u") == {"a": 1}


@pytest.mark.parametrize("content", ["no json here", "", "[1, 2, 3]", '{"a": ', None])
def test_invalid_json_is_an_ai_error(gateway, content):
    gateway.replies = [Reply(body=chat(content))]
    with pytest.raises(AIError) as err:
        make(gateway).complete_json("s", "u")
    assert str(err.value) == "The AI answer was not valid JSON"


def sse(*contents):
    chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
    chunks += [{"choices": [{"index": 0, "delta": {"content": c}}]} for c in contents]
    chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
    return ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()


def test_a_streamed_answer_is_joined(gateway):
    gateway.replies = [Reply(raw=sse('{"ok": ', "true}"))]
    assert make(gateway).complete_json("s", "u") == {"ok": True}


def test_a_stream_with_no_content_is_an_ai_error(gateway):
    gateway.replies = [Reply(raw=sse())]
    with pytest.raises(AIError):
        make(gateway).complete_json("s", "u")


def test_unexpected_payload_is_an_ai_error(gateway):
    gateway.replies = [Reply(body={"nope": 1})]
    with pytest.raises(AIError):
        make(gateway).complete_json("s", "u")
    gateway.replies = [Reply(raw=b"<html>gateway</html>")]
    with pytest.raises(AIError):
        make(gateway).complete_json("s", "u")


@pytest.mark.parametrize("status", [401, 403, 404])
def test_client_errors_are_not_retried_and_do_not_leak(gateway, status):
    gateway.replies = [Reply(status=status, body={"error": {"message": f"bad key {KEY}"}})]
    with pytest.raises(AIError) as err:
        make(gateway).complete_json("s", "u")
    assert f"HTTP {status}" in str(err.value)
    assert_no_key(err.value)
    assert len(gateway.requests) == 1


def test_server_error_retries_once_then_fails(gateway):
    gateway.replies = [Reply(status=502, body={"error": KEY}), Reply(status=502, body={"error": KEY})]
    with pytest.raises(AIError) as err:
        make(gateway).complete_json("s", "u")
    assert str(err.value) == "The AI service did not answer (HTTP 502)"
    assert_no_key(err.value)
    assert len(gateway.requests) == 2


def test_server_error_then_success(gateway):
    gateway.replies = [Reply(status=500), Reply(status=429), Reply(body=chat('{"a": 1}'))]
    client = make(gateway)
    with pytest.raises(AIError):  # one retry only: 500, 429 -> fail
        client.complete_json("s", "u")
    gateway.requests.clear()
    gateway.replies = [Reply(status=503), Reply(body=chat('{"a": 1}'))]
    assert client.complete_json("s", "u") == {"a": 1}
    assert len(gateway.requests) == 2


def test_connection_reset_is_retried(gateway):
    gateway.replies = [Reply(drop=True), Reply(body=chat('{"a": 1}'))]
    assert make(gateway).complete_json("s", "u") == {"a": 1}
    assert len(gateway.requests) == 2


def test_response_format_rejected_retries_without_it(gateway):
    gateway.replies = [
        Reply(status=400, body={"error": {"message": "Unsupported parameter: 'response_format'"}}),
        Reply(body=chat('{"a": 1}')),
    ]
    assert make(gateway).complete_json("s", "u") == {"a": 1}
    first, second = gateway.requests
    assert "response_format" in first["body"]
    assert "response_format" not in second["body"]
    assert second["body"]["temperature"] == 0 and second["body"]["messages"] == first["body"]["messages"]


def test_response_format_422_also_retries(gateway):
    gateway.replies = [Reply(status=422, body={"detail": "response_format not allowed"}), Reply(body=chat("{}"))]
    assert make(gateway).complete_json("s", "u") == {}


def test_other_400_is_not_retried(gateway):
    gateway.replies = [Reply(status=400, body={"error": {"message": f"model not found {KEY}"}})]
    with pytest.raises(AIError) as err:
        make(gateway).complete_json("s", "u")
    assert "HTTP 400" in str(err.value)
    assert_no_key(err.value)
    assert len(gateway.requests) == 1


def test_response_format_rejected_twice_fails(gateway):
    gateway.replies = [Reply(status=400, body={"error": "response_format"})] * 2
    with pytest.raises(AIError):
        make(gateway).complete_json("s", "u")
    assert len(gateway.requests) == 2


def test_timeout(gateway):
    gateway.replies = [Reply(body=chat("{}"), delay=1.5)]
    with pytest.raises(AIError) as err:
        make(gateway, timeout=0.3).complete_json("s", "u")
    assert str(err.value) == "The AI service timed out"
    assert_no_key(err.value)


def test_unreachable_service():
    cfg = AIConfig(base_url="http://127.0.0.1:1/v1", api_key=KEY, model="m", timeout=2.0)
    with pytest.raises(AIError) as err:
        OpenAICompatClient(cfg).complete_json("s", "u")
    assert_no_key(err.value)


def test_non_http_scheme_is_refused():
    cfg = AIConfig(base_url="file:///etc/passwd", api_key=KEY, model="m")
    with pytest.raises(AIError) as err:
        OpenAICompatClient(cfg).complete_json("s", "u")
    assert_no_key(err.value)


def test_key_that_cannot_be_sent_does_not_leak(gateway):
    odd = "sk-ключ-SECRET"
    cfg = AIConfig(base_url=gateway.base_url, api_key=odd, model="m")
    with pytest.raises(AIError) as err:
        OpenAICompatClient(cfg).complete_json("s", "u")
    assert odd not in "".join(traceback.format_exception(err.value))


def test_nothing_is_logged(gateway, caplog):
    caplog.set_level(logging.DEBUG)
    gateway.replies = [Reply(status=500, body={"error": KEY}), Reply(status=500, body={"error": KEY})]
    with pytest.raises(AIError):
        make(gateway).complete_json("s", "u")
    assert KEY not in caplog.text


def test_client_repr_does_not_leak():
    cfg = AIConfig(base_url="http://x/v1", api_key=KEY, model="m")
    assert KEY not in repr(OpenAICompatClient(cfg))


def test_scripted_client_returns_raises_and_records():
    boom = AIError("The AI service timed out")
    scripted = ScriptedClient([{"a": 1}, boom, {"b": 2}])
    assert scripted.complete_json("s1", "u1") == {"a": 1}
    with pytest.raises(AIError):
        scripted.complete_json("s2", "u2")
    assert scripted.complete_json("s3", "u3") == {"b": 2}
    assert scripted.calls == [("s1", "u1"), ("s2", "u2"), ("s3", "u3")]


def test_make_client(monkeypatch):
    monkeypatch.setattr(client_module, "load_config", lambda: None)
    assert make_client() is None
    monkeypatch.setattr(client_module, "load_config", lambda: AIConfig("http://x/v1", KEY, "m"))
    assert isinstance(make_client(), OpenAICompatClient)
