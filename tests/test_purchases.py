from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.reconciliation_session import ReconciliationSession, SessionInvoice
from app.schemas.invoice import InvoiceSource, ReconciliationType


# Setup test database for purchases
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_purchases_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    from app.models.settings import KRAVATMapping
    db.add(KRAVATMapping(section_prefix="SEC_F", canonical_rate="16"))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client", scope="function")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers", scope="function")
def fixture_auth_headers(client):
    register_payload = {
        "username": "purchases_tester",
        "password": "SecureP@ss123",
        "email": "purchases_tester@example.com",
    }
    client.post("/api/v1/auth/register", json=register_payload)
    from conftest import seed_test_sap_connection
    seed_test_sap_connection(client)

    login_payload = {
        "username": "purchases_tester",
        "password": "SecureP@ss123",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Router Tests ---

def test_get_purchases_success(client: TestClient, auth_headers, mock_sap_client):
    mock_login, mock_get_pages = mock_sap_client
    def mock_get_pages_side_effect(from_date, to_date, endpoint_name, **kwargs):
        if endpoint_name == "PurchaseInvoices":
            return (p for p in [
                [
                    {
                        "DocNum": 5001,
                        "CardName": "Supplier A",
                        "DocDate": "2026-03-10",
                        "FederalTaxID": "SUPP-PIN-1",
                        "U_CUINV": "CU-PURCH-1",
                        "DocumentLines": [
                            {"VatGroup": "A16", "LineTotal": 2000.00}
                        ]
                    }
                ]
            ])
        return (p for p in [[]])
        
    mock_get_pages.side_effect = mock_get_pages_side_effect

    response = client.get(
        "/api/v1/purchases?from=2026-03-01&to=2026-03-30",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "SAP"
    assert data["count"] == 1
    assert len(data["invoices"]) == 1
    assert data["invoices"][0]["partner_name"] == "Supplier A"
    assert data["invoices"][0]["invoice_number"] == "5001"
    assert data["invoices"][0]["cu_number"] == "CU-PURCH-1"
    assert data["invoices"][0]["base_amount"] == 2000.00

    # Verify mock was called for both PurchaseInvoices and PurchaseCreditNotes
    assert mock_get_pages.call_count == 2
    
    first_call_args = mock_get_pages.call_args_list[0]
    assert first_call_args[0][0] == "2026-03-01"
    assert first_call_args[0][1] == "2026-03-30"
    assert first_call_args[1]["endpoint_name"] == "PurchaseInvoices"
    assert first_call_args[1]["reconciliation_session_id"] == data["session_id"]
    
    second_call_args = mock_get_pages.call_args_list[1]
    assert second_call_args[1]["endpoint_name"] == "PurchaseCreditNotes"


def test_upload_purchases_success(client: TestClient, auth_headers, db_session):
    # Create active purchases session
    session = ReconciliationSession(
        user_id=1,
        company_id=1,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 30),
        session_type=ReconciliationType.PURCHASES,
        is_compared=False
    )
    db_session.add(session)
    db_session.commit()

    csv_content = (
        "Local,Supplier PIN,Supplier Name,Invoice Date,CU Number,Extra1,Extra2,Line Total\n"
        "Local,SUPP-PIN-1,Supplier A,10/03/2026,CU-PURCH-1,A,B,2000.00\n"
    )
    
    response = client.post(
        f"/api/v1/purchases/upload?session_id={session.id}",
        headers=auth_headers,
        files=[("files", ("SEC_F_purchases.csv", csv_content, "text/csv"))]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["files"][0]["parsed"] == 1
    assert len(data["invoices"]) == 1
    assert data["invoices"][0]["partner_name"] == "Supplier A"

    # Verify DB records
    saved = db_session.query(SessionInvoice).filter(
        SessionInvoice.session_id == session.id,
        SessionInvoice.source == InvoiceSource.KRA
    ).all()
    assert len(saved) == 1
    assert saved[0].partner_name == "Supplier A"
    assert saved[0].invoice_number == ""
    assert saved[0].base_amount == Decimal("2000.00")


def test_upload_purchases_cross_session_validation_error(client: TestClient, auth_headers, db_session):
    # Create active SALES session
    session = ReconciliationSession(
        user_id=1,
        company_id=1,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 30),
        session_type=ReconciliationType.SALES,
        is_compared=False
    )
    db_session.add(session)
    db_session.commit()

    csv_content = (
        "Supplier PIN,Supplier Name,Invoice Number,Invoice Date,CU Number,VAT Group,Line Total\n"
        "SUPP-PIN-1,Supplier A,5001,10/03/2026,CU-PURCH-1,A16,2000.00\n"
    )
    
    # Try uploading to purchases/upload using a sales session
    response = client.post(
        f"/api/v1/purchases/upload?session_id={session.id}",
        headers=auth_headers,
        files=[("files", ("SEC_F_purchases.csv", csv_content, "text/csv"))]
    )
    assert response.status_code == 400
    assert "Active session type is not for Purchases reconciliation" in response.json()["detail"]

    # Try uploading to sales/upload using a purchases session
    purchases_session = ReconciliationSession(
        user_id=1,
        company_id=1,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 30),
        session_type=ReconciliationType.PURCHASES,
        is_compared=False
    )
    db_session.add(purchases_session)
    db_session.commit()

    response2 = client.post(
        f"/api/v1/sales/upload?session_id={purchases_session.id}",
        headers=auth_headers,
        files=[("files", ("sales.csv", csv_content, "text/csv"))]
    )
    assert response2.status_code == 400
    assert "Active session type is not for Sales reconciliation" in response2.json()["detail"]
