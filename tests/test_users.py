import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.company import Company
from app.models.user import User

import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_users.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("./test_users.db"):
            try:
                os.remove("./test_users.db")
            except OSError:
                pass


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


def test_user_management_and_password_reset(client, db_session):
    # Create 2 companies
    c1 = Company(name="Company Alpha", kra_pin="P000000001A")
    c2 = Company(name="Company Beta", kra_pin="P000000002B")
    db_session.add_all([c1, c2])
    db_session.commit()
    db_session.refresh(c1)
    db_session.refresh(c2)

    # Create Platform Admin
    platform_admin = User(
        username="platform_admin",
        password_hash=hash_password("AdminP@ss123!"),
        role="admin",
        company_id=None,
    )

    # Create Company 1 Admin
    c1_admin = User(
        username="c1_admin",
        password_hash=hash_password("AdminP@ss123!"),
        role="admin",
        company_id=c1.id,
    )

    # Create Company 1 Worker
    c1_worker = User(
        username="c1_worker",
        password_hash=hash_password("WorkerP@ss123!"),
        role="checker",
        company_id=c1.id,
    )

    # Create Company 2 Worker
    c2_worker = User(
        username="c2_worker",
        password_hash=hash_password("WorkerP@ss123!"),
        role="checker",
        company_id=c2.id,
    )

    db_session.add_all([platform_admin, c1_admin, c1_worker, c2_worker])
    db_session.commit()

    # Token for C1 Admin
    c1_admin_token = create_access_token({"sub": "c1_admin"})
    headers_c1 = {"Authorization": f"Bearer {c1_admin_token}"}

    # 1. Reset password with weak password (Should fail 422)
    res_weak = client.post(
        f"/api/v1/users/{c1_worker.id}/reset-password",
        json={"new_password": "weakpassword"},
        headers=headers_c1,
    )
    assert res_weak.status_code == 422

    # 1b. Company 1 Admin resets password for C1 worker (Should Succeed with compliant password)
    res = client.post(
        f"/api/v1/users/{c1_worker.id}/reset-password",
        json={"new_password": "NewP@ssw0rd1!"},
        headers=headers_c1,
    )
    assert res.status_code == 200, res.text

    # Verify C1 Worker can login with new password
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "c1_worker", "password": "NewP@ssw0rd1!"},
    )
    assert login_res.status_code == 200

    # 2. Company 1 Admin tries to reset password for C2 worker (Should fail 403 Forbidden)
    res_fail = client.post(
        f"/api/v1/users/{c2_worker.id}/reset-password",
        json={"new_password": "HackedP@ssw0rd1!"},
        headers=headers_c1,
    )
    assert res_fail.status_code == 403

    # 3. Company 1 Admin creates a user with weak password (Should fail 422)
    create_weak_res = client.post(
        "/api/v1/users",
        json={
            "username": "c1_weak_member",
            "password": "password123",
            "role": "checker",
        },
        headers=headers_c1,
    )
    assert create_weak_res.status_code == 422

    # 3b. Company 1 Admin creates a user for Company 1 with valid password (Should Succeed)
    create_res = client.post(
        "/api/v1/users",
        json={
            "username": "c1_new_member",
            "password": "SecureP@ss123!",
            "role": "checker",
        },
        headers=headers_c1,
    )
    assert create_res.status_code == 201

    # 3c. Creating user with removed 'viewer' role should fail validation
    invalid_role_res = client.post(
        "/api/v1/users",
        json={
            "username": "c1_invalid_role",
            "password": "SecureP@ss123!",
            "role": "viewer",
        },
        headers=headers_c1,
    )
    assert invalid_role_res.status_code == 422

    # 3d. Creating user without providing a password should auto-generate a compliant password
    create_auto_res = client.post(
        "/api/v1/users",
        json={
            "username": "c1_auto_pass_member",
            "role": "checker",
        },
        headers=headers_c1,
    )
    assert create_auto_res.status_code == 201
    auto_data = create_auto_res.json()
    assert "generated_password" in auto_data
    assert len(auto_data["generated_password"]) >= 8

    # 4. Company 1 Admin updates username of C1 worker (Should Succeed)
    update_res = client.patch(
        f"/api/v1/users/{c1_worker.id}",
        json={"username": "c1_worker_updated"},
        headers=headers_c1,
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["username"] == "c1_worker_updated"

    # 5. Attempting to set duplicate username (Should return 400 Bad Request)
    dup_res = client.patch(
        f"/api/v1/users/{c1_worker.id}",
        json={"username": "c1_admin"},
        headers=headers_c1,
    )
    assert dup_res.status_code == 400
    assert "already in use" in dup_res.json()["detail"]

