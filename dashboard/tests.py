import pytest
from rest_framework.test import APIClient
from accounts.models import User


@pytest.mark.django_db
def test_dashboard_overview_returns_baseline():
    User.objects.create_user(username="op", email="op@example.com", password="pwd12345", role="OPERATOR")
    client = APIClient()
    login = client.post("/api/v1/auth/login/", {"username": "op", "password": "pwd12345"}, format="json")
    token = login.json()["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.get("/api/v1/dashboard/overview/")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "current_water_flow" in body
    assert "system_health" in body
    assert body["active_alerts"] == 0