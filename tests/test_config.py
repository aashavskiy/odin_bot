import os

import pytest

from app.config import load_config


def set_required_env(monkeypatch, **overrides):
    env = {
        "BOT_TOKEN": "token",
        "OPENAI_API_KEY": "key",
        "ADMIN_ID": "123",
    }
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_load_config_requires_minimum_env(monkeypatch):
    set_required_env(monkeypatch, BOT_TOKEN=None)
    with pytest.raises(RuntimeError):
        load_config()


def test_load_config_firestore_requires_project(monkeypatch):
    set_required_env(monkeypatch, GCP_PROJECT_ID=None, FIRESTORE_DISABLED="0")
    with pytest.raises(RuntimeError):
        load_config()


def test_load_config_defaults(monkeypatch):
    set_required_env(
        monkeypatch,
        GCP_PROJECT_ID="proj",
        FIRESTORE_DISABLED="0",
    )
    config = load_config()
    assert config.webhook_path == "/webhook"
    assert config.history_max_messages == 16
    assert config.summary_trigger == 20
    assert config.history_ttl_days == 7


def test_load_config_disables_firestore(monkeypatch):
    set_required_env(
        monkeypatch,
        FIRESTORE_DISABLED="1",
        GCP_PROJECT_ID=None,
    )
    config = load_config()
    assert config.firestore_enabled is False
