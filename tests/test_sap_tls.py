"""Pinned-certificate TLS for SAP Service Layer connections.

Runs a real local HTTPS server with a self-signed certificate issued to an internal hostname,
reached by IP, which is the shape of a typical on-premise Service Layer install.
"""
import json
import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.sap_client import SAPClient
from app.core.sap_tls import build_verify, fetch_server_certificate, normalize_certificate_pem
from app.core.security import hash_password
from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.settings import CompanySAPConnection, SettingAuditLog
from app.models.user import User

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sap_tls_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _self_signed(common_name: str) -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return cert_pem, key_pem


class _ServiceLayerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps({"SessionId": "abc", "SessionTimeout": 30}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def sap_server(tmp_path_factory):
    cert_pem, key_pem = _self_signed("sap-internal.local")
    d = tmp_path_factory.mktemp("sap_tls")
    (d / "cert.pem").write_text(cert_pem)
    (d / "key.pem").write_text(key_pem)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(d / "cert.pem", d / "key.pem")
    server = HTTPServer(("127.0.0.1", 0), _ServiceLayerHandler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}/b1s/v1", normalize_certificate_pem(cert_pem)
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        from app.models.company import Company

        db.add(Company(name="Default Company"))
        db.add(
            User(
                username="admin_tester",
                email="admin@example.com",
                password_hash=hash_password("securepass123"),
                is_active=True,
                role="admin",
            )
        )
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="headers")
def fixture_headers(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin_tester", "password": "securepass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _test_sap(client, headers, base_url, **extra):
    payload = {"base_url": base_url, "company_db": "DB", "username": "manager", "password": "pw", **extra}
    res = client.post("/api/v1/settings/test-sap?company_id=1", json=payload, headers=headers)
    assert res.status_code == 200
    return res.json()


# --------------------------------------------------------------------------- #
# Core TLS behaviour
# --------------------------------------------------------------------------- #
def test_self_signed_server_rejected_without_pin(sap_server):
    base_url, _ = sap_server
    with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
        httpx.post(f"{base_url}/Login", verify=build_verify(True, None))


def test_pinned_certificate_is_trusted_when_reached_by_ip(sap_server):
    base_url, cert = sap_server
    res = httpx.post(f"{base_url}/Login", json={}, verify=build_verify(True, cert))
    assert res.json()["SessionId"] == "abc"


def test_different_pinned_certificate_is_rejected(sap_server):
    base_url, _ = sap_server
    other_cert, _ = _self_signed("sap-internal.local")
    with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
        httpx.post(f"{base_url}/Login", verify=build_verify(True, normalize_certificate_pem(other_cert)))


def test_fetch_server_certificate_returns_presented_cert(sap_server):
    base_url, cert = sap_server
    assert fetch_server_certificate(base_url) == cert


def test_sap_client_uses_pinned_certificate(sap_server):
    base_url, cert = sap_server
    client = SAPClient(base_url=base_url, verify_ssl=True, ca_certificate=cert).clone()
    assert client.client.post(f"{base_url}/Login", json={}).status_code == 200


@pytest.mark.parametrize("bad", ["not a cert", "-----BEGIN CERTIFICATE-----\nZZZ\n-----END CERTIFICATE-----"])
def test_normalize_rejects_invalid_pem(bad):
    with pytest.raises(ValueError):
        normalize_certificate_pem(bad)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_test_sap_reports_untrusted_certificate(client, headers, sap_server):
    base_url, _ = sap_server
    data = _test_sap(client, headers, base_url)
    assert data["connected"] is False
    assert data["certificate_untrusted"] is True
    assert "not trusted" in data["error_message"]


def test_test_sap_succeeds_with_pinned_certificate(client, headers, sap_server):
    base_url, cert = sap_server
    data = _test_sap(client, headers, base_url, ca_certificate=cert)
    assert data["connected"] is True


def test_fetch_endpoint_returns_certificate_details(client, headers, sap_server):
    base_url, cert = sap_server
    res = client.post("/api/v1/settings/sap-certificate/fetch", json={"base_url": base_url}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["pem"] == cert
    assert body["info"]["subject"] == "CN=sap-internal.local"
    assert body["info"]["is_self_signed"] is True
    assert body["info"]["is_expired"] is False


def test_fetch_endpoint_rejects_http_url(client, headers):
    res = client.post(
        "/api/v1/settings/sap-certificate/fetch", json={"base_url": "http://sap.example/b1s/v1"}, headers=headers
    )
    assert res.status_code == 400


def test_save_pin_then_test_uses_saved_certificate_and_clear(client, headers, db_session, sap_server):
    base_url, cert = sap_server
    save = {"base_url": base_url, "company_db": "DB", "username": "manager", "password": "pw", "version": 1}

    res = client.put("/api/v1/settings/sap-connection?company_id=1", json={**save, "ca_certificate": cert}, headers=headers)
    assert res.status_code == 200
    conn = res.json()
    assert conn["ca_certificate"] == cert
    assert conn["ca_certificate_info"]["subject"] == "CN=sap-internal.local"

    # Omitting ca_certificate in the test request falls back to the saved one.
    assert _test_sap(client, headers, base_url)["connected"] is True

    res = client.put(
        "/api/v1/settings/sap-connection?company_id=1",
        json={**save, "version": conn["version"], "ca_certificate": ""},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["ca_certificate"] is None
    assert db_session.query(CompanySAPConnection).one().ca_certificate is None
    audit = db_session.query(SettingAuditLog).filter(SettingAuditLog.action == "update_sap_connection").all()
    assert any("ca_certificate" in (log.changes_json or {}) for log in audit)


def test_save_rejects_invalid_certificate(client, headers):
    res = client.put(
        "/api/v1/settings/sap-connection?company_id=1",
        json={
            "base_url": "https://sap.example/b1s/v1",
            "company_db": "DB",
            "username": "manager",
            "password": "pw",
            "ca_certificate": "garbage",
            "version": 1,
        },
        headers=headers,
    )
    assert res.status_code == 400
