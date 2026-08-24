"""Removing one uploaded KRA CSV from an active session.

KRA uploads append, and nothing recorded which rows came from which file, so a user who
picked the wrong CSV had to reload the page and re-fetch SAP to get rid of it. Rows now
carry `source_filename` and a DELETE takes a single file back out.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.reconciliation_session import (
    ReconciliationSession,
    SessionInvoice,
    SessionReconciliationResult,
)
from app.schemas.invoice import InvoiceSource

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_kra_removal_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SEC_B_ROW = (
    b"P051393568M,Autoports Freight Terminals Limited,IN1080,02/03/2026,"
    b"|0190439340000000455,16,1118894.84\n"
)
SEC_B_OTHER_ROW = (
    b"P051137818X,GRAIN INDUSTRIES LIMITED,IN1081,11/03/2026,"
    b"|0190439340000000456,16,3977701.88\n"
)
SEC_E_ROW = (
    b"P051352116L,Aspendos Dairy Limited,IN1082,12/03/2026,"
    b"|0190439340000000457,0,1263600.00\n"
)


@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    from app.models.settings import KRAVATMapping
    db.add(KRAVATMapping(section_prefix="SEC_B", canonical_rate="16"))
    db.add(KRAVATMapping(section_prefix="SEC_E", canonical_rate="0"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def fixture_auth_headers(client):
    client.post("/api/v1/auth/register", json={
        "username": "removal_tester",
        "password": "SecureP@ss123",
        "email": "removal_tester@example.com",
    })
    from conftest import seed_test_sap_connection
    seed_test_sap_connection(client)
    res = client.post("/api/v1/auth/login", json={
        "username": "removal_tester", "password": "SecureP@ss123",
    })
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _session_with_files(client, auth_headers, *files):
    """Start a session and upload the given (filename, content) pairs in one request."""
    res = client.get("/api/v1/sales?from=2026-03-01&to=2026-03-30", headers=auth_headers)
    session_id = res.json()["session_id"]
    upload = client.post(
        f"/api/v1/sales/upload?session_id={session_id}",
        headers=auth_headers,
        files=[("files", (name, content, "text/csv")) for name, content in files],
    )
    assert upload.status_code == 200, upload.text
    return session_id, upload.json()


def _kra_rows(db, session_id):
    return db.query(SessionInvoice).filter(
        SessionInvoice.session_id == session_id,
        SessionInvoice.source == InvoiceSource.KRA,
    ).all()


def test_upload_records_which_file_each_row_came_from(client, auth_headers, db_session):
    session_id, _ = _session_with_files(
        client, auth_headers,
        ("SEC_B.csv", SEC_B_ROW),
        ("SEC_E.csv", SEC_E_ROW),
    )
    by_file = {r.invoice_number: r.source_filename for r in _kra_rows(db_session, session_id)}
    assert by_file == {"IN1080": "SEC_B.csv", "IN1082": "SEC_E.csv"}


def test_remove_deletes_only_that_files_rows(client, auth_headers, db_session):
    session_id, _ = _session_with_files(
        client, auth_headers,
        ("SEC_B.csv", SEC_B_ROW + SEC_B_OTHER_ROW),
        ("SEC_E.csv", SEC_E_ROW),
    )
    assert len(_kra_rows(db_session, session_id)) == 3

    res = client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=SEC_B.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["removed"] == 2
    assert body["total_kra_records"] == 1
    assert body["remaining_files"] == ["SEC_E.csv"]

    survivors = _kra_rows(db_session, session_id)
    assert [r.invoice_number for r in survivors] == ["IN1082"]


def test_remove_leaves_sap_rows_untouched(client, auth_headers, db_session):
    """The whole point: the session survives, so no SAP re-fetch is needed."""
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))
    sap_before = db_session.query(SessionInvoice).filter(
        SessionInvoice.session_id == session_id,
        SessionInvoice.source == InvoiceSource.SAP,
    ).count()
    assert sap_before > 0

    client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=SEC_B.csv",
        headers=auth_headers,
    )

    sap_after = db_session.query(SessionInvoice).filter(
        SessionInvoice.session_id == session_id,
        SessionInvoice.source == InvoiceSource.SAP,
    ).count()
    assert sap_after == sap_before
    assert db_session.get(ReconciliationSession, session_id) is not None


def test_remove_invalidates_a_cached_comparison(client, auth_headers, db_session):
    """A stored comparison describes rows that no longer exist, so it must not be served."""
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))

    compare = client.post(
        "/api/v1/reconciliation/compare",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert compare.status_code == 200, compare.text

    db_session.expire_all()
    session = db_session.get(ReconciliationSession, session_id)
    assert session.is_compared is True
    assert db_session.query(SessionReconciliationResult).filter(
        SessionReconciliationResult.session_id == session_id
    ).count() > 0

    client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=SEC_B.csv",
        headers=auth_headers,
    )

    db_session.expire_all()
    session = db_session.get(ReconciliationSession, session_id)
    assert session.is_compared is False
    assert session.comparison_results is None
    assert db_session.query(SessionReconciliationResult).filter(
        SessionReconciliationResult.session_id == session_id
    ).count() == 0


def test_removing_then_re_uploading_restores_the_rows(client, auth_headers, db_session):
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))
    client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=SEC_B.csv",
        headers=auth_headers,
    )
    assert _kra_rows(db_session, session_id) == []

    again = client.post(
        f"/api/v1/sales/upload?session_id={session_id}",
        headers=auth_headers,
        files=[("files", ("SEC_B.csv", SEC_B_ROW, "text/csv"))],
    )
    assert again.status_code == 200
    # The dedup guard keys on row content, and the earlier rows are gone, so this is
    # genuinely new rather than skipped as a duplicate.
    assert again.json()["added"] == 1
    assert again.json()["duplicates_skipped"] == 0
    assert len(_kra_rows(db_session, session_id)) == 1


def test_remove_unknown_filename_is_a_no_op(client, auth_headers, db_session):
    """Zero removed is not an error — a file that failed to parse contributed no rows."""
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))

    res = client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=SEC_NOPE.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["removed"] == 0
    assert res.json()["remaining_files"] == ["SEC_B.csv"]
    # An untouched session keeps its comparison; only a real deletion invalidates it.
    assert len(_kra_rows(db_session, session_id)) == 1


def test_remove_requires_authentication(client):
    res = client.delete("/api/v1/sales/upload?session_id=dummy&filename=SEC_B.csv")
    assert res.status_code == 401


def test_remove_rejects_a_blank_filename(client, auth_headers):
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))
    res = client.delete(
        f"/api/v1/sales/upload?session_id={session_id}&filename=%20%20",
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "filename is required" in res.json()["detail"].lower()


def test_remove_rejects_a_purchases_call_on_a_sales_session(client, auth_headers):
    """Guards the same session-type mismatch the upload path already refuses."""
    session_id, _ = _session_with_files(client, auth_headers, ("SEC_B.csv", SEC_B_ROW))
    res = client.delete(
        f"/api/v1/purchases/upload?session_id={session_id}&filename=SEC_B.csv",
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "not for Purchases" in res.json()["detail"]
