import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.database import get_db
from app.main import app

import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
if os.path.exists("./test.db"):
    os.remove("./test.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_auth_flow():
    # 1. Register a user
    register_payload = {
        "username": "testuser",
        "password": "StrongPassword123!",
        "email": "test@example.com",
        "role": "checker",
    }
    response = client.post("/api/v1/auth/register", json=register_payload)
    print("Register response status:", response.status_code)
    print("Register response JSON:", response.json())
    assert response.status_code == 201
    assert response.json()["username"] == "testuser"
    assert response.json()["email"] == "test@example.com"
    assert response.json()["is_active"] is True

    # 2. Login with form data (OAuth2PasswordRequestForm)
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "StrongPassword123!"},
    )
    print("Login response status:", response.status_code)
    print("Login response JSON:", response.json())
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    access_token = response.json()["access_token"]
    refresh_token = response.json()["refresh_token"]

    # 3. Access /me
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    print("Me response status:", response.status_code)
    print("Me response JSON:", response.json())
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

    # 4. Refresh the token
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    print("Refresh response status:", response.status_code)
    print("Refresh response JSON:", response.json())
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    new_access_token = response.json()["access_token"]
    new_refresh_token = response.json()["refresh_token"]
    assert new_access_token != access_token
    assert new_refresh_token != refresh_token

    # 5. Old refresh token no longer works (rotation)
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    print("Old refresh response status:", response.status_code)
    assert response.status_code == 401

    # 6. Logout
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh_token},
    )
    print("Logout response status:", response.status_code)
    assert response.status_code == 200

    # 7. Logged-out refresh token no longer works
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh_token},
    )
    print("Used refresh response status:", response.status_code)
    assert response.status_code == 401

    # 8. Duplicate register returns 400
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "password": "AnotherPassword123!",
        },
    )
    print("Duplicate register status:", response.status_code)
    assert response.status_code == 400

    print("\n=== ALL AUTH TESTS PASSED ===")


if __name__ == "__main__":
    try:
        test_auth_flow()
    except Exception as e:
        print("TEST FAILED:", e)
        raise
    finally:
        import os

        if os.path.exists("./test.db"):
            os.remove("./test.db")
