"""Loading a SAP date range as successive windows, appending into one session.

A single GET used to block until the whole range had been fetched from SAP, so the
preview table sat empty — sometimes for a minute — and then filled all at once. The
endpoint now takes an optional `session_id`, which lets the UI ask for a long range as a
series of short windows and show each one as it lands.

The mock SAP client returns the same five documents for any date range; the service layer
filters them to the requested window, which is what makes windowing observable here.
Document dates: 02/03, 11/03, and three on 12/03.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.domain.reconciliation_status import ReconciliationStatus
from app.main import app
from app.models.reconciliation_session import (
    ReconciliationSession,
    SessionInvoice,
    SessionReconciliationResult,
)
from app.schemas.invoice import InvoiceSource

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sap_window_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

FULL_RANGE = ("2026-03-01", "2026-03-31")
TOTAL_DOCS = 5


@pytest.fixture(name="db_session")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
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
        "username": "window_tester",
        "password": "SecureP@ss123",
        "email": "window_tester@example.com",
    })
    from conftest import seed_test_sap_connection
    seed_test_sap_connection(client)
    res = client.post("/api/v1/auth/login", json={
        "username": "window_tester", "password": "SecureP@ss123",
    })
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _load(client, auth_headers, frm, to, session_id=None, module="sales"):
    url = f"/api/v1/{module}?from={frm}&to={to}"
    if session_id:
        url += f"&session_id={session_id}"
    return client.get(url, headers=auth_headers)


def _sap_rows(db, session_id):
    return db.query(SessionInvoice).filter(
        SessionInvoice.session_id == session_id,
        SessionInvoice.source == InvoiceSource.SAP,
    ).all()


def test_a_single_call_still_creates_its_own_session(client, auth_headers, db_session):
    """The unwindowed path is unchanged — this is the first call of every load."""
    res = _load(client, auth_headers, *FULL_RANGE)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["count"] == TOTAL_DOCS
    assert body["total_sap_records"] == TOTAL_DOCS
    assert len(_sap_rows(db_session, body["session_id"])) == TOTAL_DOCS


def test_windows_append_into_one_session(client, auth_headers, db_session):
    first = _load(client, auth_headers, "2026-03-01", "2026-03-05").json()
    assert first["count"] == 1
    assert first["total_sap_records"] == 1

    second = _load(
        client, auth_headers, "2026-03-06", "2026-03-31", session_id=first["session_id"]
    ).json()

    # Same session, and the whole range is now loaded.
    assert second["session_id"] == first["session_id"]
    assert second["count"] == TOTAL_DOCS - 1
    assert second["total_sap_records"] == TOTAL_DOCS
    assert len(_sap_rows(db_session, first["session_id"])) == TOTAL_DOCS


def test_an_empty_window_is_not_an_error(client, auth_headers):
    """Quiet weeks are ordinary; the window must not abort the rest of the load."""
    first = _load(client, auth_headers, "2026-03-01", "2026-03-05").json()
    empty = _load(
        client, auth_headers, "2026-03-06", "2026-03-10", session_id=first["session_id"]
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["count"] == 0
    assert empty.json()["total_sap_records"] == 1


def test_row_numbers_continue_across_windows(client, auth_headers, db_session):
    """session_invoices carries UniqueConstraint(session_id, source, row_number)."""
    first = _load(client, auth_headers, "2026-03-01", "2026-03-05").json()
    _load(client, auth_headers, "2026-03-06", "2026-03-31", session_id=first["session_id"])

    numbers = sorted(r.row_number for r in _sap_rows(db_session, first["session_id"]))
    assert numbers == list(range(1, TOTAL_DOCS + 1))


def test_the_session_range_widens_to_cover_every_window(client, auth_headers, db_session):
    first = _load(client, auth_headers, "2026-03-10", "2026-03-20").json()
    body = _load(
        client, auth_headers, "2026-03-01", "2026-03-09", session_id=first["session_id"]
    ).json()

    assert body["from_date"] == "2026-03-01"
    assert body["to_date"] == "2026-03-20"

    session = db_session.query(ReconciliationSession).filter_by(id=first["session_id"]).one()
    assert session.from_date.isoformat() == "2026-03-01"
    assert session.to_date.isoformat() == "2026-03-20"


def test_an_overlapping_window_does_not_double_count(client, auth_headers, db_session):
    """A duplicated SAP row would silently double an amount, not raise."""
    first = _load(client, auth_headers, *FULL_RANGE).json()
    again = _load(client, auth_headers, *FULL_RANGE, session_id=first["session_id"]).json()

    assert again["count"] == 0
    assert again["total_sap_records"] == TOTAL_DOCS
    assert len(_sap_rows(db_session, first["session_id"])) == TOTAL_DOCS


def test_appending_invalidates_a_cached_comparison(client, auth_headers, db_session):
    first = _load(client, auth_headers, "2026-03-01", "2026-03-05").json()
    session_id = first["session_id"]

    session = db_session.query(ReconciliationSession).filter_by(id=session_id).one()
    session.is_compared = True
    session.comparison_results = {"matches": 1}
    db_session.add(SessionReconciliationResult(
        session_id=session_id, row_number=1, cu_number="X",
        status=ReconciliationStatus.MATCH,
    ))
    db_session.commit()

    _load(client, auth_headers, "2026-03-06", "2026-03-31", session_id=session_id)

    db_session.expire_all()
    session = db_session.query(ReconciliationSession).filter_by(id=session_id).one()
    assert session.is_compared is False
    assert session.comparison_results is None
    assert db_session.query(SessionReconciliationResult).filter_by(session_id=session_id).count() == 0


def test_a_window_cannot_append_across_reconciliation_types(client, auth_headers):
    """A sales window must not land in a purchases session."""
    sales = _load(client, auth_headers, "2026-03-01", "2026-03-05").json()
    res = _load(
        client, auth_headers, "2026-03-06", "2026-03-31",
        session_id=sales["session_id"], module="purchases",
    )
    assert res.status_code == 400
    assert "not for purchases" in res.json()["detail"].lower()


def test_an_unknown_session_is_rejected(client, auth_headers):
    res = _load(client, auth_headers, *FULL_RANGE, session_id="does-not-exist")
    assert res.status_code == 404


def test_windowed_load_requires_authentication(client):
    res = client.get(f"/api/v1/sales?from={FULL_RANGE[0]}&to={FULL_RANGE[1]}&session_id=x")
    assert res.status_code in (401, 403)
