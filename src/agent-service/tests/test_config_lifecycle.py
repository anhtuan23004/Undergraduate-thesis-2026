"""Tests for startup configuration and MongoDB lifecycle helpers."""

from __future__ import annotations

import pytest
from config import Settings, get_cors_origins, validate_startup_config
from mongodb_client import close_mongodb_client, get_mongodb_client
from persistence.mongodb_config import normalize_mongodb_url


def test_validate_startup_config_requires_core_env_in_non_debug() -> None:
    config = Settings(
        DEBUG=False,
        GEMINI_API_KEY="",
        MONGODB_URL="",
        OCR_SERVICE_URL="",
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_startup_config(config)

    message = str(exc_info.value)
    assert "GEMINI_API_KEY" in message
    assert "MONGODB_URL" in message
    assert "OCR_SERVICE_URL" in message


def test_validate_startup_config_allows_missing_core_env_in_debug() -> None:
    config = Settings(
        DEBUG=True,
        GEMINI_API_KEY="",
        MONGODB_URL="",
        OCR_SERVICE_URL="",
    )

    validate_startup_config(config)


def test_get_cors_origins_restricts_empty_production_default() -> None:
    config = Settings(DEBUG=False, ALLOWED_ORIGINS="")

    assert get_cors_origins(config) == []


def test_get_cors_origins_allows_debug_wildcard_default() -> None:
    config = Settings(DEBUG=True, ALLOWED_ORIGINS="")

    assert get_cors_origins(config) == ["*"]


def test_validate_startup_config_rejects_wildcard_cors_in_production() -> None:
    config = Settings(
        DEBUG=False,
        GEMINI_API_KEY="key",
        MONGODB_URL="mongodb://localhost:27017/claims",
        OCR_SERVICE_URL="http://ocr.local",
        ALLOWED_ORIGINS="*",
    )

    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        validate_startup_config(config)


def test_normalize_mongodb_url_adds_direct_connection_once() -> None:
    assert (
        normalize_mongodb_url("mongodb://localhost:27017/claims")
        == "mongodb://localhost:27017/claims?directConnection=true"
    )
    assert (
        normalize_mongodb_url("mongodb://localhost:27017/claims?authSource=admin")
        == "mongodb://localhost:27017/claims?authSource=admin&directConnection=true"
    )
    assert (
        normalize_mongodb_url("mongodb://localhost:27017/claims?directConnection=true")
        == "mongodb://localhost:27017/claims?directConnection=true"
    )


def test_get_mongodb_client_uses_explicit_timeouts(monkeypatch) -> None:
    captured = {}

    class FakeMongoClient:
        def __init__(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("mongodb_client.MongoClient", FakeMongoClient)
    monkeypatch.setattr("mongodb_client.settings.MONGODB_URL", "mongodb://localhost:27017/claims")
    monkeypatch.setattr("mongodb_client.settings.MONGODB_CONNECT_TIMEOUT_MS", 111)
    monkeypatch.setattr("mongodb_client.settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS", 222)
    monkeypatch.setattr("mongodb_client.settings.MONGODB_SOCKET_TIMEOUT_MS", 333)
    monkeypatch.setattr("mongodb_client._client", None)
    monkeypatch.setattr("mongodb_client._db", None)

    client = get_mongodb_client()

    assert client is not None
    assert captured == {
        "url": "mongodb://localhost:27017/claims?directConnection=true",
        "kwargs": {
            "connectTimeoutMS": 111,
            "serverSelectionTimeoutMS": 222,
            "socketTimeoutMS": 333,
        },
    }
    assert close_mongodb_client() is None
    assert captured["closed"] is True
