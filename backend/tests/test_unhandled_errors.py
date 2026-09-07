from unittest.mock import AsyncMock

from tests.conftest import make_mock_conn, make_test_client


def test_unhandled_database_error_returns_safe_json():
    conn = make_mock_conn()
    conn.fetchrow = AsyncMock(side_effect=RuntimeError("private database details"))
    with make_test_client(conn=conn) as (client, _):
        response = client.get("/v1/keys/me", headers={"X-API-Key": "bbi_test_key"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error.",
            "status": 500,
        }
    }
    assert "private database details" not in response.text
