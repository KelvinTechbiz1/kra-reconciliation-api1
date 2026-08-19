"""Email transport selection.

Outbound SMTP is blocked by default on several hosts (DigitalOcean among them), which
shows up as a connect timeout to smtp.sendgrid.net:587. MAIL_MAILER=sendgrid_api routes
the same message and the same API key over HTTPS:443 instead.
"""
import pytest

from app.core.config import get_settings
from app.services import email_service


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _configure(monkeypatch, **env):
    defaults = {
        "MAIL_PASSWORD": "SG.test-key",
        "MAIL_FROM_ADDRESS": "noreply@example.com",
        "MAIL_FROM_NAME": "Techbiz Group",
    }
    for key, value in {**defaults, **env}.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


class _Response:
    def __init__(self, status_code=202, text=""):
        self.status_code = status_code
        self.text = text


def test_api_mailer_posts_to_sendgrid(monkeypatch):
    _configure(monkeypatch, MAIL_MAILER="sendgrid_api")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers)
        return _Response()

    monkeypatch.setattr("httpx.post", fake_post)

    assert email_service.send_email(
        "her@example.com", "Subject line", "<p>html</p>", "plain"
    ) is True

    assert captured["url"] == email_service.SENDGRID_API_URL
    assert captured["headers"]["Authorization"] == "Bearer SG.test-key"
    body = captured["json"]
    assert body["personalizations"] == [{"to": [{"email": "her@example.com"}]}]
    assert body["from"] == {"email": "noreply@example.com", "name": "Techbiz Group"}
    assert body["subject"] == "Subject line"
    # SendGrid renders the last matching part, so plain text must come first.
    assert [c["type"] for c in body["content"]] == ["text/plain", "text/html"]


def test_api_mailer_omits_plain_part_when_absent(monkeypatch):
    _configure(monkeypatch, MAIL_MAILER="sendgrid_api")
    captured = {}
    monkeypatch.setattr(
        "httpx.post",
        lambda url, json=None, headers=None, timeout=None: (
            captured.update(json=json) or _Response()
        ),
    )

    email_service.send_email("her@example.com", "s", "<p>html</p>")
    assert [c["type"] for c in captured["json"]["content"]] == ["text/html"]


def test_api_mailer_reports_rejection(monkeypatch):
    """A 4xx from SendGrid (bad key, unverified sender) must not read as success."""
    _configure(monkeypatch, MAIL_MAILER="sendgrid_api")
    monkeypatch.setattr(
        "httpx.post",
        lambda *a, **kw: _Response(401, '{"errors":[{"message":"unauthorized"}]}'),
    )
    assert email_service.send_email("her@example.com", "s", "<p>h</p>") is False


def test_api_mailer_survives_transport_error(monkeypatch):
    _configure(monkeypatch, MAIL_MAILER="sendgrid_api")

    def boom(*a, **kw):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("httpx.post", boom)
    assert email_service.send_email("her@example.com", "s", "<p>h</p>") is False


@pytest.mark.parametrize("value", ["sendgrid_api", "sendgrid-api", "api", "https", "  API  "])
def test_api_mailer_aliases(monkeypatch, value):
    _configure(monkeypatch, MAIL_MAILER=value)
    monkeypatch.setattr("httpx.post", lambda *a, **kw: _Response())
    monkeypatch.setattr(
        "smtplib.SMTP", lambda *a, **kw: pytest.fail("should not have used SMTP")
    )
    assert email_service.send_email("her@example.com", "s", "<p>h</p>") is True


def test_smtp_remains_the_default(monkeypatch):
    """Unset MAIL_MAILER must keep the existing behaviour, not silently switch."""
    _configure(monkeypatch, MAIL_MAILER="smtp")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: pytest.fail("should not have used the API"))

    sent = {}

    class _SMTP:
        def __init__(self, host, port, timeout=None):
            sent.update(host=host, port=port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = (user, password)

        def sendmail(self, from_addr, to, message):
            sent["to"] = to

    monkeypatch.setattr("smtplib.SMTP", _SMTP)

    assert email_service.send_email("her@example.com", "s", "<p>h</p>", "plain") is True
    assert sent["host"] == "smtp.sendgrid.net"
    assert sent["to"] == ["her@example.com"]


def test_smtp_timeout_is_reported_as_failure(monkeypatch):
    _configure(monkeypatch, MAIL_MAILER="smtp")

    def boom(*a, **kw):
        raise TimeoutError("timed out")

    monkeypatch.setattr("smtplib.SMTP", boom)
    assert email_service.send_email("her@example.com", "s", "<p>h</p>") is False


def test_missing_password_still_short_circuits(monkeypatch):
    """No credential means nothing is sent, on either transport."""
    _configure(monkeypatch, MAIL_PASSWORD="", MAIL_MAILER="sendgrid_api")
    monkeypatch.setattr("httpx.post", lambda *a, **kw: pytest.fail("should not have sent"))
    assert email_service.send_email("her@example.com", "s", "<p>h</p>") is True
