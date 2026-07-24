import pytest
from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test user registration."""
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"
    assert data["data"]["email"] == "test@example.com"
    assert "hashed_password" not in data["data"]


def test_register_duplicate_username(client: TestClient, db_session):
    """Test registering with duplicate username."""
    # First registration
    client.post(
        "/auth/register",
        json={
            "username": "duplicateuser",
            "email": "test1@example.com",
            "password": "password123"
        }
    )
    
    # Second registration with same username
    response = client.post(
        "/auth/register",
        json={
            "username": "duplicateuser",
            "email": "test2@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


def test_login_success(client: TestClient):
    """Test successful login."""
    # Register a user first
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123"
        }
    )
    
    # Login
    response = client.post(
        "/auth/login",
        data={
            "username": "loginuser",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    """Test login with wrong password."""
    # Register a user first
    client.post(
        "/auth/register",
        json={
            "username": "wrongpassuser",
            "email": "wrong@example.com",
            "password": "password123"
        }
    )
    
    # Login with wrong password
    response = client.post(
        "/auth/login",
        data={
            "username": "wrongpassuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_get_current_user(client: TestClient):
    """Test getting current user with valid token."""
    # Register and login
    client.post(
        "/auth/register",
        json={
            "username": "meuser",
            "email": "me@example.com",
            "password": "password123"
        }
    )
    
    login_response = client.post(
        "/auth/login",
        data={
            "username": "meuser",
            "password": "password123"
        }
    )
    
    token = login_response.json()["data"]["access_token"]
    
    # Get current user
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "meuser"


def test_get_current_user_invalid_token(client: TestClient):
    """Test getting current user with invalid token."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
