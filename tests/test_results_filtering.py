"""Server-side filtering of reconciliation results.

The table loads by infinite scroll and used to filter in the browser, so a filter could
only search rows already fetched: on a large session, picking "Matches" showed nothing
until the user had scrolled far enough to pull one in — and the chip did not even appear
until then. Filtering and the chip counts now come from SQL.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.domain.reconciliation_constants import RESULT_FILTERS, result_filter_counts
from app.domain.reconciliation_status import ReconciliationStatus
from app.main import app
from app.models.reconciliation_session import (
    ReconciliationSession,
    SessionReconciliationResult,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_results_filter.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Deliberately front-loaded with matches so a client-side filter over the first page
# would find no CU/PIN mismatches at all — the exact failure being fixed.
LAYOUT = (
    [ReconciliationStatus.MATCH] * 120
    + [ReconciliationStatus.AMOUNT_MISMATCH] * 5
    + [ReconciliationStatus.CU_MISMATCH] * 3
    + [ReconciliationStatus.PIN_MISMATCH] * 2
    + [ReconciliationStatus.MISSING_IN_KRA] * 4
    + [ReconciliationStatus.DUPLICATE_SOURCE_KEY] * 1
)


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
    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def fixture_auth_headers(client):
    client.post("/api/v1/auth/register", json={
        "username": "filter_tester",
        "password": "SecureP@ss123",
        "email": "filter_tester@example.com",
    })
    from conftest import seed_test_sap_connection
    seed_test_sap_connection(client)
    token = client.post("/api/v1/auth/login", json={
        "username": "filter_tester", "password": "SecureP@ss123",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="session_id")
def fixture_session(client, auth_headers, db_session):
    from app.models.user import User

    user = db_session.query(User).filter(User.username == "filter_tester").first()
    session = ReconciliationSession(
        user_id=user.id,
        company_id=user.company_id,
        from_date=date(2026, 7, 1),
        to_date=date(2026, 7, 31),
        is_compared=True,
        comparison_results={"summary": {}},
    )
    db_session.add(session)
    db_session.commit()

    db_session.add_all([
        SessionReconciliationResult(
            session_id=session.id,
            row_number=i + 1,
            cu_number=f"CU{i:05d}",
            status=status,
            amount_match=status is ReconciliationStatus.MATCH,
            vat_match=True,
            date_match=True,
            partner_name_matches=True,
            pin_matches=status is not ReconciliationStatus.PIN_MISMATCH,
        )
        for i, status in enumerate(LAYOUT)
    ])
    db_session.commit()
    return session.id


def _get(client, auth_headers, session_id, **params):
    res = client.get(
        f"/api/v1/sessions/{session_id}/results",
        params=params,
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_counts_cover_the_whole_session_not_just_the_page(client, auth_headers, session_id):
    """The first page is all matches; the chips must still know about the rest."""
    body = _get(client, auth_headers, session_id, page=1, limit=50)

    assert len(body["items"]) == 50
    assert all(r["status"] == "Match" for r in body["items"])

    counts = body["status_counts"]
    assert counts["All"] == len(LAYOUT) == 135
    assert counts["Matches"] == 120
    assert counts["Issues"] == 15
    assert counts["CU"] == 3
    assert counts["PIN"] == 2
    assert counts["Amount"] == 5
    assert counts["Missing KRA"] == 4
    assert counts["Multiple"] == 1


def test_filtering_reaches_rows_far_beyond_the_first_page(client, auth_headers, session_id):
    """CU mismatches sit at rows 126-128. One filtered request returns all of them."""
    body = _get(client, auth_headers, session_id, page=1, limit=50, status_filter="CU")

    assert body["total"] == 3
    assert body["total_pages"] == 1
    assert [r["status"] for r in body["items"]] == ["CU Mismatch"] * 3


def test_issues_excludes_matches(client, auth_headers, session_id):
    body = _get(client, auth_headers, session_id, page=1, limit=500, status_filter="Issues")

    assert body["total"] == 15
    assert len(body["items"]) == 15
    assert all(r["status"] != "Match" for r in body["items"])


def test_multiple_groups_two_statuses(client, auth_headers, session_id):
    body = _get(client, auth_headers, session_id, page=1, limit=500, status_filter="Multiple")
    assert [r["status"] for r in body["items"]] == ["Duplicate Source Key"]


def test_total_and_pages_describe_the_filtered_set(client, auth_headers, session_id):
    """Pagination must count the filtered rows, or infinite scroll stops early."""
    body = _get(client, auth_headers, session_id, page=1, limit=50, status_filter="Matches")

    assert body["total"] == 120
    assert body["total_pages"] == 3
    assert len(body["items"]) == 50

    last = _get(client, auth_headers, session_id, page=3, limit=50, status_filter="Matches")
    assert len(last["items"]) == 20


def test_filter_is_echoed_back(client, auth_headers, session_id):
    body = _get(client, auth_headers, session_id, status_filter="PIN")
    assert body["status_filter"] == "PIN"


def test_default_is_unfiltered(client, auth_headers, session_id):
    body = _get(client, auth_headers, session_id, page=1, limit=500)
    assert body["status_filter"] == "All"
    assert body["total"] == len(LAYOUT)


def test_unknown_filter_is_rejected(client, auth_headers, session_id):
    res = client.get(
        f"/api/v1/sessions/{session_id}/results",
        params={"status_filter": "Bogus"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "Bogus" in res.json()["detail"]


def test_empty_group_returns_no_rows_but_still_reports_counts(client, auth_headers, session_id):
    """The UI needs the counts to keep rendering chips and offer a way back to All."""
    body = _get(client, auth_headers, session_id, status_filter="Missing SAP")

    assert body["total"] == 0
    assert body["items"] == []
    assert body["status_counts"]["All"] == len(LAYOUT)


def test_every_filter_name_is_accepted(client, auth_headers, session_id):
    for name in list(RESULT_FILTERS) + ["All"]:
        body = _get(client, auth_headers, session_id, status_filter=name)
        assert body["status_filter"] == name


def test_filter_counts_are_exhaustive():
    """Issues + Matches must account for every status, or a row becomes unreachable."""
    per_status = {status: 1 for status in ReconciliationStatus}
    counts = result_filter_counts(per_status)
    assert counts["Matches"] + counts["Issues"] == counts["All"] == len(ReconciliationStatus)
