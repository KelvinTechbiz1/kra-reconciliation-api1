import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_templates_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
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
        "username": "templates_tester",
        "password": "SecureP@ss123",
        "email": "templates_tester@example.com",
    }
    client.post("/api/v1/auth/register", json=register_payload)

    login_payload = {
        "username": "templates_tester",
        "password": "SecureP@ss123",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_download_sales_template_success(client, auth_headers):
    response = client.get("/api/v1/templates/sales", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=kra_sales_template.csv" in response.headers["Content-Disposition"]
    assert "public, max-age=86400" in response.headers["Cache-Control"]
    
    # Verify Content starts with UTF-8 BOM bytes (\xef\xbb\xbf)
    content = response.content
    assert content.startswith(b"\xef\xbb\xbf")
    
    # Decode using utf-8-sig
    decoded = content.decode("utf-8-sig")
    lines = decoded.splitlines()
    assert len(lines) == 2
    assert "Customer PIN" in lines[0]
    assert "ABC Customer Limited" in lines[1]

def test_download_purchases_template_success(client, auth_headers):
    response = client.get("/api/v1/templates/purchases", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=kra_purchases_template.csv" in response.headers["Content-Disposition"]
    assert "public, max-age=86400" in response.headers["Cache-Control"]
    
    content = response.content
    assert content.startswith(b"\xef\xbb\xbf")
    
    decoded = content.decode("utf-8-sig")
    lines = decoded.splitlines()
    assert len(lines) == 2
    assert "Supplier PIN" in lines[0]
    assert "XYZ Supplier Limited" in lines[1]

def test_download_template_invalid_type(client, auth_headers):
    response = client.get("/api/v1/templates/invalid_type", headers=auth_headers)
    assert response.status_code == 422 # FastAPI validation error for invalid Enum value

def test_download_template_unauthenticated(client):
    response = client.get("/api/v1/templates/sales")
    assert response.status_code == 401
