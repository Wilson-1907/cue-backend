import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from accounts.models import User


@pytest.mark.django_db
def test_login_returns_tokens_and_user():
    User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="pwd12345",
        role=User.Role.OPERATOR,
    )
    client = APIClient()
    resp = client.post("/api/v1/auth/login/", {"username": "alice", "password": "pwd12345"}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "access" in body["data"]
    assert body["data"]["user"]["username"] == "alice"


@pytest.mark.django_db
def test_login_denies_viewer_role():
    User.objects.create_user(
        username="viewer1",
        email="viewer1@example.com",
        password="pwd12345",
        role=User.Role.VIEWER,
    )
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/login/",
        {"username": "viewer1", "password": "pwd12345"},
        format="json",
    )
    assert resp.status_code == 403
    assert resp.json()["success"] is False


@pytest.mark.django_db
def test_me_requires_auth():
    client = APIClient()
    resp = client.get("/api/v1/auth/me/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_change_password():
    user = User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="oldpwd123",
        role=User.Role.ADMIN,
    )
    client = APIClient()
    login = client.post("/api/v1/auth/login/", {"username": "bob", "password": "oldpwd123"}, format="json")
    assert login.status_code == 200
    token = login.json()["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.post(
        "/api/v1/auth/password/change/",
        {"old_password": "oldpwd123", "new_password": "newpwd12345"},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("newpwd12345")