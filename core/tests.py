import pytest
from core.utils import success_response, error_response


@pytest.mark.django_db
def test_success_response_shape():
    resp = success_response({"x": 1})
    assert resp.status_code == 200
    assert resp.data == {"success": True, "message": "Data retrieved successfully", "data": {"x": 1}}


def test_error_response_shape():
    resp = error_response("bad", {"field": ["oops"]})
    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert resp.data["errors"] == {"field": ["oops"]}