import pytest
from unittest.mock import patch, MagicMock
import json


@pytest.fixture
def client():
    # Create a fake redis_client module
    fake_redis = MagicMock()

    with patch("receipt_service.create_redis_client", return_value=fake_redis):
        from receipt_service import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


# Test that a receipt was submitted successfully to the database.
def test_receipt_success(client):
    from receipt_service import create_redis_client
    r = create_redis_client()

    response = client.post("/api/receipt", json={
        "receipt_id": "1",
        "products": ["milk", "bread", "butter"]
    })

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    r.hset.assert_called_once_with(
        "receipt:1", "products", json.dumps(["milk", "bread", "butter"])
    )


# Test writing a receipt when there are no products in the receipt.
# The service should return error 500
def test_receipt_missing_fields(client):
    response = client.post("/api/receipt", json={"receipt_id": "2"})
    assert response.status_code == 500
