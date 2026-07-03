from fastapi import Response

import server


def test_auth_cookies_use_secure_samesite_when_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)

    response = Response()
    server.set_auth_cookies(response, "access", "refresh")

    cookie_headers = [header.lower() for header in response.headers.getlist("set-cookie")]
    assert any("access_token" in header for header in cookie_headers)
    assert any("secure" in header for header in cookie_headers)
    assert any("samesite=none" in header for header in cookie_headers)


def test_auth_cookies_fallback_to_secure_cross_site_for_https_frontend(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://brandkrt.com")

    response = Response()
    server.set_auth_cookies(response, "access", "refresh")

    cookie_headers = [header.lower() for header in response.headers.getlist("set-cookie")]
    assert any("secure" in header for header in cookie_headers)
    assert any("samesite=none" in header for header in cookie_headers)


def test_auth_cookies_keep_lax_samesite_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("COOKIE_SAMESITE", "lax")

    response = Response()
    server.set_auth_cookies(response, "access", "refresh")

    cookie_headers = [header.lower() for header in response.headers.getlist("set-cookie")]
    assert any("samesite=lax" in header for header in cookie_headers)
