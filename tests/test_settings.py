import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.user import User
from app.core.security import hash_password

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_settings_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed a default company and a company-scoped test user.
        from app.models.company import Company
        company = Company(name="Default Company")
        db.add(company)
        db.commit()
        db.refresh(company)
        user = User(
            username="admin_tester",
            email="admin@example.com",
            password_hash=hash_password("securepass123"),
            is_active=True,
            role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
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


def test_get_and_update_settings(client: TestClient, db_session):
    # Login to get JWT
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_tester", "password": "securepass123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET settings
    response = client.get("/api/v1/settings?company_id=1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "system_settings" in data
    assert data["system_settings"]["sales_cu_source"] == "U_CUINV"
    assert data["system_settings"]["purchase_cu_source"] == "U_CUINV"

    # 2. Update System Settings
    sys_settings = data["system_settings"]
    sys_update_payload = {
        "amount_tolerance": "15.50",
        "base_amount_policy": "treat_as_zero",
        "unmapped_vat_policy": "needs_review",
        "ignore_missing_cu": True,
        "include_credit_notes": True,
        "include_debit_notes": True,
        "skip_cancelled": True,
        "sales_cu_source": "U_CUSTOM_SALES_CU",
        "purchase_cu_source": "NumAtCard",
        "version": sys_settings["version"],
        "reason": "Test tolerance update to 15.50 and custom sales CU source",
    }
    update_res = client.put("/api/v1/settings/system-settings?company_id=1", json=sys_update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_sys = update_res.json()
    assert updated_sys["amount_tolerance"] == "15.50"
    assert updated_sys["base_amount_policy"] == "treat_as_zero"
    assert updated_sys["sales_cu_source"] == "U_CUSTOM_SALES_CU"
    assert updated_sys["purchase_cu_source"] == "NumAtCard"
    assert updated_sys["version"] == sys_settings["version"] + 1

    # 3. Update SAP Connection
    sap_payload = {
        "name": "Test Enterprise SAP Connection",
        "base_url": "https://sap.test.company.com:50000/b1s/v1",
        "company_db": "TEST_DB_KE",
        "username": "manager",
        "password": "SecretPassword123!",
        "verify_ssl": False,
        "version": 1,
    }
    sap_res = client.put("/api/v1/settings/sap-connection?company_id=1", json=sap_payload, headers=headers)
    assert sap_res.status_code == 200
    updated_sap = sap_res.json()
    assert updated_sap["company_db"] == "TEST_DB_KE"
    assert updated_sap["password_set"] is True

    # 4. Save VAT Mappings
    curr_settings = client.get("/api/v1/settings?company_id=1", headers=headers).json()
    existing_mappings = curr_settings.get("vat_mappings", [])
    
    updated_mappings_list = list(existing_mappings)
    updated_mappings_list.append({
        "module": "sales",
        "sap_code": "CUSTOM1",
        "description": "Custom Reduced Rate",
        "canonical_rate": "8",
        "is_builtin": False,
    })

    conn_id = updated_sap["id"]
    vat_payload = {
        "connection_id": conn_id,
        "reason": "Add custom VAT mapping",
        "mappings": updated_mappings_list,
    }
    vat_res = client.put("/api/v1/settings/vat-mappings?company_id=1", json=vat_payload, headers=headers)
    assert vat_res.status_code == 200
    vat_data = vat_res.json()
    assert len(vat_data) == len(existing_mappings) + 1

    # 5. Check Audit Logs
    audit_res = client.get("/api/v1/settings/audit-logs?company_id=1", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 3


def test_multi_company_management(client: TestClient, db_session):
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_tester", "password": "securepass123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List all companies (should include initial primary company ID 1)
    res = client.get("/api/v1/company/all", headers=headers)
    assert res.status_code == 200
    companies = res.json()
    assert len(companies) >= 1
    assert companies[0]["id"] == 1

    # 2. Create a new company
    new_company_payload = {
        "name": "Safari Logistics Ltd",
        "kra_pin": "P059998887Z",
        "currency": "KES",
        "timezone": "Africa/Nairobi",
        "fiscal_year_start_month": 1,
    }
    create_res = client.post("/api/v1/company", json=new_company_payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "Safari Logistics Ltd"
    assert created["kra_pin"] == "P059998887Z"
    new_id = created["id"]

    # 3. List all again
    res2 = client.get("/api/v1/company/all", headers=headers)
    assert res2.status_code == 200
    all_companies = res2.json()
    assert len(all_companies) == len(companies) + 1

    # 4. Update the created company
    update_res = client.put(f"/api/v1/company/{new_id}", json={"name": "Safari Logistics KE Ltd"}, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Safari Logistics KE Ltd"

    # 5. Prevent deleting primary company (ID 1)
    del_primary = client.delete("/api/v1/company/1", headers=headers)
    assert del_primary.status_code == 400

    # 6. Delete created company
    del_res = client.delete(f"/api/v1/company/{new_id}", headers=headers)
    assert del_res.status_code == 204


def test_partial_system_settings_update(client: TestClient, db_session):
    login_res = client.post("/api/v1/auth/login", json={"username": "admin_tester", "password": "securepass123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET initial settings (confirm kra_parsing_profiles is present via fallback)
    response = client.get("/api/v1/settings?company_id=1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    sys_settings = data["system_settings"]
    assert sys_settings["kra_parsing_profiles"] is not None
    assert "SEC_B" in sys_settings["kra_parsing_profiles"]["profiles"]
    
    initial_version = sys_settings["version"]
    initial_tolerance = sys_settings["amount_tolerance"]

    # 2. Update ONLY amount_tolerance and version (SystemSettingsCard update)
    sys_update_payload = {
        "amount_tolerance": "42.00",
        "version": initial_version,
    }
    update_res = client.put("/api/v1/settings/system-settings?company_id=1", json=sys_update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_sys = update_res.json()
    assert updated_sys["amount_tolerance"] == "42.00"
    assert updated_sys["version"] == initial_version + 1
    # kra_parsing_profiles should NOT be None
    assert updated_sys["kra_parsing_profiles"] is not None
    assert "SEC_B" in updated_sys["kra_parsing_profiles"]["profiles"]

    # 3. Update ONLY kra_parsing_profiles and version (KRAParsingProfilesCard update)
    custom_profiles = {
        "schema_version": 1,
        "profiles": {
            "SEC_B": {
                "pin_column": 10,
                "partner_name_column": 11,
                "invoice_number_column": 12,
                "invoice_date_column": 13,
                "cu_number_column": 14,
                "base_amount_column": 15,
            }
        }
    }
    profiles_update_payload = {
        "kra_parsing_profiles": custom_profiles,
        "version": updated_sys["version"],
    }
    update_res2 = client.put("/api/v1/settings/system-settings?company_id=1", json=profiles_update_payload, headers=headers)
    assert update_res2.status_code == 200
    updated_sys2 = update_res2.json()
    assert updated_sys2["kra_parsing_profiles"]["profiles"]["SEC_B"]["pin_column"] == 10
    # amount_tolerance should NOT be reset to default (10.00), it should remain 42.00
    assert updated_sys2["amount_tolerance"] == "42.00"
    assert updated_sys2["version"] == updated_sys["version"] + 1


def test_settings_rbac_forbidden_for_standard_user(client: TestClient, db_session):
    # Seed standard (non-admin) user
    standard_user = User(
        username="standard_user",
        email="standard@example.com",
        password_hash=hash_password("userpass123"),
        is_active=True,
        role="user",
    )
    db_session.add(standard_user)
    db_session.commit()

    # Login as standard user
    login_res = client.post("/api/v1/auth/login", json={"username": "standard_user", "password": "userpass123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET settings should succeed for reading
    get_res = client.get("/api/v1/settings?company_id=1", headers=headers)
    assert get_res.status_code == 200

    # PUT system-settings should return 403 Forbidden
    sys_update_res = client.put(
        "/api/v1/settings/system-settings?company_id=1",
        json={"amount_tolerance": "20.00", "version": 1},
        headers=headers,
    )
    assert sys_update_res.status_code == 403
    assert "privileges required" in sys_update_res.json()["detail"]

    # PUT sap-connection should return 403 Forbidden
    sap_res = client.put(
        "/api/v1/settings/sap-connection?company_id=1",
        json={"base_url": "https://sap.test.com:50000/b1s/v1", "version": 1},
        headers=headers,
    )
    assert sap_res.status_code == 403



