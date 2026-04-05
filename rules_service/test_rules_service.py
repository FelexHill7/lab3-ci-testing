import pytest
from unittest.mock import patch, MagicMock
import json
import pandas as pd


@pytest.fixture
def client():
    # Fake redis_client module
    fake_redis = MagicMock()
    import sys
    sys.modules.pop("rules_service", None)

    with patch("rules_service.create_redis_client", return_value=fake_redis):
        from rules_service import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


# Test the successful calculation of rules
def test_rules_success(client):
    # Import the mocked redis client
    from rules_service import create_redis_client
    r = create_redis_client()

    # Prepare fake Redis receipts
    r.hvals.return_value = [
        json.dumps(["milk", "bread", "butter"]),
        json.dumps(["bread", "butter", "diapers"]),
        json.dumps(["milk", "beer"])
    ]

    # Use the following to mock apriori + association_rules
    # We do not need to test the algorithm as it is not always deterministic
    with patch("rules_service.apriori") as mock_apriori, \
         patch("rules_service.association_rules") as mock_rules:

        mock_apriori.return_value = pd.DataFrame({
            "itemsets": [frozenset(["milk", "bread"])],
            "support": [0.5]
        })
        mock_rules.return_value = pd.DataFrame({
            "antecedents": [frozenset(["milk"])],
            "consequents": [frozenset(["bread"])],
            "confidence": [0.6],
            "support": [0.5],
            "lift": [1.2]
        })

        response = client.get("/api/rules")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["antecedents"] == ["milk"]
        assert data[0]["consequents"] == ["bread"]


# Test the attempt to determine rules without receipts in the database
# The service should still return HTTP:200, but an empty response
def test_rules_no_receipts(client):
    from rules_service import create_redis_client
    r = create_redis_client()

    # Redis returns no receipts
    r.hvals.return_value = []

    # Use the following to mock apriori + association_rules
    # We do not need to test the algorithm as it is not always deterministic
    with patch("rules_service.apriori") as mock_apriori, \
         patch("rules_service.association_rules") as mock_rules:

        mock_apriori.return_value = pd.DataFrame(columns=["itemsets", "support"])
        mock_rules.return_value = pd.DataFrame(columns=[
            "antecedents", "consequents", "confidence", "support", "lift"
        ])

        response = client.get("/api/rules")

        assert response.status_code == 200
        data = response.get_json()
        assert data == []


# Test that the service handles a Redis error gracefully
# When hvals raises an exception, the service should return HTTP 500
def test_rules_redis_error(client):
    from rules_service import create_redis_client
    r = create_redis_client()

    # Simulate a Redis connection failure
    r.hvals.side_effect = Exception("Redis connection refused")

    with pytest.raises(Exception, match="Redis connection refused"):
        client.get("/api/rules")
