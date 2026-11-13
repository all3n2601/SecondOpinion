from pathlib import Path

import pytest

from second_opinion.ai.config import AIConfig, ai_status, load_config

KEY = "sk-test-SECRET-1234"
BASE = {"SO_AI_API_KEY": KEY, "SO_AI_MODEL": "some-model"}


def write_env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text)
    return path


def test_not_configured_returns_none():
    assert load_config(env={}) is None
    assert load_config(env={"SO_AI_API_KEY": KEY}) is None  # model missing
    assert load_config(env={"SO_AI_MODEL": "m"}) is None  # key missing


def test_reads_environment_with_defaults():
    cfg = load_config(env=dict(BASE))
    assert cfg == AIConfig(base_url="http://localhost:20128/v1", api_key=KEY, model="some-model", timeout=60.0)


def test_base_url_and_timeout_from_environment():
    cfg = load_config(env={**BASE, "SO_AI_BASE_URL": "https://gateway.example/v1/", "SO_AI_TIMEOUT": "12.5"})
    assert cfg.base_url == "https://gateway.example/v1"
    assert cfg.timeout == 12.5


@pytest.mark.parametrize("bad", ["abc", "0", "-3", ""])
def test_bad_timeout_falls_back_to_default(bad):
    assert load_config(env={**BASE, "SO_AI_TIMEOUT": bad}).timeout == 60.0


@pytest.mark.parametrize("flag", ["off", "OFF", "0", "false", "False", " off "])
def test_disabled_flag(flag):
    assert load_config(env={**BASE, "SO_AI": flag}) is None


@pytest.mark.parametrize("flag", ["on", "1", "true", ""])
def test_other_flag_values_keep_it_enabled(flag):
    assert load_config(env={**BASE, "SO_AI": flag}) is not None


def test_dotenv_fallback(tmp_path):
    path = write_env(tmp_path, f"SO_AI_API_KEY={KEY}\nSO_AI_MODEL=from-file\n")
    cfg = load_config(env={}, dotenv_path=path)
    assert cfg is not None and cfg.api_key == KEY and cfg.model == "from-file"


def test_dotenv_never_overrides_real_environment(tmp_path):
    path = write_env(tmp_path, "SO_AI_API_KEY=file-key\nSO_AI_MODEL=file-model\nSO_AI_BASE_URL=http://file/v1\n")
    cfg = load_config(env={"SO_AI_API_KEY": KEY, "SO_AI_MODEL": "env-model"}, dotenv_path=path)
    assert cfg.api_key == KEY
    assert cfg.model == "env-model"
    assert cfg.base_url == "http://file/v1"  # only the unset setting comes from the file


def test_dotenv_syntax(tmp_path):
    path = write_env(
        tmp_path,
        "# a comment\n\n"
        f'export SO_AI_API_KEY="{KEY}"\n'
        "SO_AI_MODEL = 'quoted model'  \n"
        "SO_AI_BASE_URL=http://host:1/v1  # trailing comment\n"
        "OTHER=ignored\n"
        "not a setting line\n",
    )
    cfg = load_config(env={}, dotenv_path=path)
    assert (cfg.api_key, cfg.model, cfg.base_url) == (KEY, "quoted model", "http://host:1/v1")


def test_dotenv_can_disable(tmp_path):
    path = write_env(tmp_path, f"SO_AI_API_KEY={KEY}\nSO_AI_MODEL=m\nSO_AI=off\n")
    assert load_config(env={}, dotenv_path=path) is None


def test_missing_dotenv_file_is_fine(tmp_path):
    assert load_config(env={}, dotenv_path=tmp_path / "nope.env") is None


def test_explicit_env_does_not_read_the_repo_dotenv(monkeypatch, tmp_path):
    # a hermetic call (env given, no dotenv_path) must never pick up a developer's real .env
    from second_opinion.ai import config

    write_env(tmp_path, f"SO_AI_API_KEY={KEY}\nSO_AI_MODEL=m\n")
    monkeypatch.setattr(config, "_DEFAULT_DOTENV", tmp_path / ".env")
    assert load_config(env={}) is None


def test_default_uses_process_environment_and_repo_dotenv(monkeypatch, tmp_path):
    from second_opinion.ai import config

    write_env(tmp_path, "SO_AI_MODEL=file-model\n")
    monkeypatch.setattr(config, "_DEFAULT_DOTENV", tmp_path / ".env")
    for name in ("SO_AI", "SO_AI_BASE_URL", "SO_AI_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SO_AI_API_KEY", KEY)
    monkeypatch.delenv("SO_AI_MODEL", raising=False)
    cfg = load_config()
    assert cfg is not None and cfg.model == "file-model" and cfg.api_key == KEY


def test_key_is_masked_in_repr_and_str():
    cfg = load_config(env=dict(BASE))
    assert KEY not in repr(cfg) and KEY not in str(cfg) and KEY not in f"{cfg!r} {cfg}"
    assert "some-model" in repr(cfg)
    assert "***" in repr(cfg)


def test_config_is_frozen():
    cfg = load_config(env=dict(BASE))
    with pytest.raises(Exception):
        cfg.model = "other"  # type: ignore[misc]


def test_status_when_enabled_has_host_only():
    status = ai_status(env={**BASE, "SO_AI_BASE_URL": "https://user:pw@gw.example:8443/secret/path/v1?token=abc"})
    assert status["enabled"] is True
    assert status["model"] == "some-model"
    assert status["host"] == "gw.example:8443"
    assert status["reason"] is None
    text = repr(status)
    for leak in (KEY, "secret", "path", "token", "user", "pw"):
        assert leak not in text


def test_status_default_host():
    assert ai_status(env=dict(BASE))["host"] == "localhost:20128"


def test_status_reasons():
    assert ai_status(env={}) == {"enabled": False, "model": None, "host": None, "reason": "No AI key set"}
    off = ai_status(env={**BASE, "SO_AI": "off"})
    assert off["enabled"] is False and off["reason"] == "AI turned off"
    assert KEY not in repr(off)
    assert ai_status(env={"SO_AI_API_KEY": KEY})["reason"] == "No AI model set"
