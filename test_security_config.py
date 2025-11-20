import importlib
import sys

import pytest


def _reload_module(module_name: str):
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_admin_api_key_required_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)

    if "app.auth" in sys.modules:
        del sys.modules["app.auth"]

    with pytest.raises(RuntimeError):
        _reload_module("app.auth")

    # Restore module with safe defaults for other tests
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ADMIN_API_KEY", "dev-key")
    _reload_module("app.auth")


def test_user_cookie_flags_defaults(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("USER_SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("USER_SESSION_COOKIE_SAMESITE", raising=False)

    if "app.user_auth" in sys.modules:
        del sys.modules["app.user_auth"]

    user_auth = _reload_module("app.user_auth")

    assert user_auth.USER_SESSION_COOKIE_SECURE is True
    assert user_auth.USER_SESSION_COOKIE_SAMESITE == "strict"

    # Restore module for downstream imports
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("USER_SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("USER_SESSION_COOKIE_SAMESITE", "lax")
    _reload_module("app.user_auth")
