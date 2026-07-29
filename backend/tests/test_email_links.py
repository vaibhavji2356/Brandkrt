import importlib


def test_production_email_links_never_point_to_render_backend(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_URL", "https://brandkrt.onrender.com")

    import server

    importlib.reload(server)
    assert server.EmailService().frontend_url == "https://brandkrt.com"


def test_non_backend_frontend_url_is_preserved(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_URL", "https://www.brandkrt.com/")

    import server

    importlib.reload(server)
    assert server.EmailService().frontend_url == "https://www.brandkrt.com"
