import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def reload_oauth_module(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("REACT_APP_GOOGLE_CLIENT_ID", raising=False)
    import oauth

    return importlib.reload(oauth)


def test_google_client_id_falls_back_to_react_env_name(reload_oauth_module, monkeypatch):
    monkeypatch.setenv("REACT_APP_GOOGLE_CLIENT_ID", "react-client.apps.googleusercontent.com")
    importlib.reload(reload_oauth_module)

    assert reload_oauth_module.is_configured() is True
    assert reload_oauth_module.get_client_id() == "react-client.apps.googleusercontent.com"


def test_google_client_id_falls_back_to_oauth_env_name(reload_oauth_module, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "oauth-client.apps.googleusercontent.com")
    importlib.reload(reload_oauth_module)

    assert reload_oauth_module.is_configured() is True
    assert reload_oauth_module.get_client_id() == "oauth-client.apps.googleusercontent.com"


def test_google_certificate_request_is_cached(reload_oauth_module):
    class Response:
        headers = {"cache-control": "public, max-age=3600"}

    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    cached = reload_oauth_module._CachedGoogleRequest(request)
    first = cached("https://www.googleapis.com/oauth2/v1/certs")
    second = cached("https://www.googleapis.com/oauth2/v1/certs")

    assert first is second
    assert len(calls) == 1
