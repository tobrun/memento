"""Tests for inbox.config — env loading, CLI overrides, defaults."""

import os

import pytest

from inbox.config import Config, load_config


class TestDefaults:
    """load_config() with no env vars and no overrides uses built-in defaults."""

    def test_model_default(self, clean_env):
        cfg = load_config()
        assert cfg.model == "gemini-2.0-flash-lite"

    def test_google_api_key_default(self, clean_env):
        cfg = load_config()
        assert cfg.google_api_key is None

    def test_openai_api_base_default(self, clean_env):
        cfg = load_config()
        assert cfg.openai_api_base is None

    def test_openai_api_key_default(self, clean_env):
        cfg = load_config()
        assert cfg.openai_api_key == "not-needed"

    def test_max_file_size_default(self, clean_env):
        cfg = load_config()
        assert cfg.max_file_size == 5_242_880


class TestEnvVars:
    """Environment variables override defaults."""

    def test_model_from_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("MODEL", "gpt-4o")
        assert load_config().model == "gpt-4o"

    def test_google_api_key_from_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "secret-key")
        assert load_config().google_api_key == "secret-key"

    def test_openai_api_base_from_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("OPENAI_API_BASE", "http://localhost:11434/v1")
        assert load_config().openai_api_base == "http://localhost:11434/v1"

    def test_openai_api_key_from_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert load_config().openai_api_key == "sk-test"

    def test_max_file_size_from_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("MAX_FILE_SIZE", "1048576")
        cfg = load_config()
        assert cfg.max_file_size == 1_048_576
        assert isinstance(cfg.max_file_size, int)


class TestCLIOverrides:
    """Keyword overrides take precedence over env vars."""

    def test_override_beats_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("MODEL", "gpt-4o")
        cfg = load_config(model="claude-sonnet-4-20250514")
        assert cfg.model == "claude-sonnet-4-20250514"

    def test_override_beats_default(self, clean_env):
        cfg = load_config(max_file_size=1024)
        assert cfg.max_file_size == 1024

    def test_none_override_falls_through_to_env(self, clean_env, monkeypatch):
        monkeypatch.setenv("MODEL", "gpt-4o")
        cfg = load_config(model=None)
        assert cfg.model == "gpt-4o"

    def test_none_override_falls_through_to_default(self, clean_env):
        cfg = load_config(model=None)
        assert cfg.model == "gemini-2.0-flash-lite"

    def test_multiple_overrides(self, clean_env):
        cfg = load_config(model="llama3", max_file_size=999, openai_api_key="key123")
        assert cfg.model == "llama3"
        assert cfg.max_file_size == 999
        assert cfg.openai_api_key == "key123"


class TestConfigImmutability:
    """Config is a frozen dataclass — fields cannot be reassigned."""

    def test_frozen(self, clean_env):
        cfg = load_config()
        with pytest.raises(AttributeError):
            cfg.model = "other"


# ── fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def clean_env(monkeypatch):
    """Remove all config-related env vars so defaults are deterministic."""
    for var in ("MODEL", "GOOGLE_API_KEY", "OPENAI_API_BASE",
                "OPENAI_API_KEY", "MAX_FILE_SIZE"):
        monkeypatch.delenv(var, raising=False)
