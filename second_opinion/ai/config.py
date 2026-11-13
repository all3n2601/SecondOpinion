"""AI settings: environment variables first, the repo-root `.env` file as a fallback.

Variables: SO_AI_API_KEY and SO_AI_MODEL (both required), SO_AI_BASE_URL (default: a local gateway),
SO_AI (off / 0 / false switches the layer off even when configured) and SO_AI_TIMEOUT (seconds).
The key is only ever held in an `AIConfig`, whose repr hides it; `ai_status()` is what the app shows.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "http://localhost:20128/v1"
DEFAULT_TIMEOUT = 60.0
_DEFAULT_DOTENV = Path(__file__).resolve().parents[2] / ".env"
_SETTINGS = ("SO_AI_API_KEY", "SO_AI_MODEL", "SO_AI_BASE_URL", "SO_AI", "SO_AI_TIMEOUT")
_OFF_VALUES = {"off", "0", "false"}


@dataclass(frozen=True, repr=False)
class AIConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = DEFAULT_TIMEOUT

    def __repr__(self) -> str:
        return (
            f"AIConfig(base_url={self.base_url!r}, api_key='***', model={self.model!r}, timeout={self.timeout!r})"
        )

    __str__ = __repr__


def _parse_dotenv(path: Path) -> dict[str, str]:
    """`KEY=value` lines, optional `export`, optional quotes, `#` comments. Unknown keys are dropped."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or key not in _SETTINGS:
            continue
        if value[:1] in ("'", '"'):
            end = value.find(value[0], 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            comment = value.find(" #")
            value = (value[:comment] if comment != -1 else value).strip()
        values[key] = value
    return values


def _settings(env: Mapping[str, str] | None, dotenv_path: Path | None) -> dict[str, str]:
    """Real environment wins; the .env file only fills what is unset.

    An explicit `env` is used as given (no repo `.env`) unless a `dotenv_path` is also given,
    so callers and tests that pass their own environment never see a developer's real key.
    """
    fallback: dict[str, str] = {}
    if dotenv_path is not None:
        fallback = _parse_dotenv(dotenv_path)
    elif env is None:
        fallback = _parse_dotenv(_DEFAULT_DOTENV)
    source = os.environ if env is None else env
    merged = dict(fallback)
    merged.update({k: str(source[k]) for k in _SETTINGS if k in source})
    return merged


def _timeout(raw: str | None) -> float:
    try:
        value = float(raw) if raw is not None else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def _problem(settings: Mapping[str, str]) -> str | None:
    if settings.get("SO_AI", "").strip().lower() in _OFF_VALUES:
        return "AI turned off"
    if not settings.get("SO_AI_API_KEY", "").strip():
        return "No AI key set"
    if not settings.get("SO_AI_MODEL", "").strip():
        return "No AI model set"
    return None


def load_config(env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> AIConfig | None:
    """The AI settings, or None when the layer is not configured or is switched off."""
    settings = _settings(env, dotenv_path)
    if _problem(settings) is not None:
        return None
    return AIConfig(
        base_url=(settings.get("SO_AI_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/"),
        api_key=settings["SO_AI_API_KEY"].strip(),
        model=settings["SO_AI_MODEL"].strip(),
        timeout=_timeout(settings.get("SO_AI_TIMEOUT")),
    )


def ai_status(env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> dict:
    """What the app may show: whether AI is on, the model, the host (never the key, path or query)."""
    config = load_config(env, dotenv_path)
    if config is None:
        return {"enabled": False, "model": None, "host": None, "reason": _problem(_settings(env, dotenv_path))}
    parts = urlsplit(config.base_url)
    host = parts.hostname or ""
    try:
        port = parts.port
    except ValueError:
        port = None
    if ":" in host:
        host = f"[{host}]"
    return {"enabled": True, "model": config.model, "host": f"{host}:{port}" if port else host, "reason": None}
