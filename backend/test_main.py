import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app, get_db
from database import Base
import models
from security import get_password_hash

# Setup in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Seed test data
    hashed_pass = get_password_hash("testpass")
    student = models.User(user_id="s1", name="student", password_hash=hashed_pass, role=models.RoleEnum.student)
    admin = models.User(user_id="a1", name="admin", password_hash=hashed_pass, role=models.RoleEnum.admin)
    book = models.Book(isbn="123", title="Test Book", category="CS", format=models.FormatEnum.physical, status=models.StatusEnum.available)
    db.add_all([student, admin, book])
    db.commit()
    db.close()
    yield
    # Cleanup
    Base.metadata.drop_all(bind=engine)

def test_login_success():
    response = client.post("/token", json={"member_id": "student", "password": "testpass"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["role"] == "student"

def test_login_fail():
    response = client.post("/token", json={"member_id": "student", "password": "wrongpassword"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Credentials!"

def test_issue_book():
    # 1. Login to get token
    login_res = client.post("/token", json={"member_id": "student", "password": "testpass"})
    token = login_res.json()["access_token"]
    
    # 2. Issue book
    response = client.post(
        "/api/transactions/issue/123",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "issued successfully" in response.json()["message"]

def test_admin_rbac():
    # 1. Login as student
    login_res = client.post("/token", json={"member_id": "student", "password": "testpass"})
    token = login_res.json()["access_token"]
    
    # 2. Try to hit admin endpoint
    response = client.get(
        "/api/admin/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access denied"
