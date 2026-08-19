"""/auth/me must name the user's company.

The UI had no way to tell a signed-in user which company's books they were looking at,
because the endpoint returned only company_id.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.models.company import Company
from app.models.user import User
from app.services.user_service import list_users

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_me_company.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


def _seed(db, username, role, company_name=None):
    company = None
    if company_name:
        company = Company(name=company_name)
        db.add(company)
        db.commit()
        db.refresh(company)
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("SecureP@ss123"),
        is_active=True,
        role=role,
        company_id=company.id if company else None,
    )
    db.add(user)
    db.commit()
    return user


def _me(client, username):
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "SecureP@ss123"}
    ).json()["access_token"]
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    return res.json()


def test_me_returns_the_company_name(client, db_session):
    _seed(db_session, "umi", "checker", company_name="KRISH COMMODITIES LTD")

    body = _me(client, "umi")
    assert body["company_name"] == "KRISH COMMODITIES LTD"
    assert body["company_id"] is not None


def test_company_admin_also_gets_the_name(client, db_session):
    _seed(db_session, "twalha", "company_admin", company_name="Techbiz Infotech")
    assert _me(client, "twalha")["company_name"] == "Techbiz Infotech"


def test_saas_admin_has_no_company_name(client, db_session):
    """Admins belong to no company; the header hides the label rather than inventing one."""
    _seed(db_session, "root", "admin")

    body = _me(client, "root")
    assert body["company_id"] is None
    assert body["company_name"] is None


def test_user_listing_carries_company_names(client, db_session):
    _seed(db_session, "umi", "checker", company_name="KRISH COMMODITIES LTD")
    _seed(db_session, "root", "admin")

    names = {u.username: u.company_name for u in list_users(db_session)}
    assert names == {"umi": "KRISH COMMODITIES LTD", "root": None}
