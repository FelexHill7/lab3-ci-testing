# Lab Test 3 – Report

## File Structure

```
.github/
  workflows/
    test.yml                  <- GitHub Actions workflow (created)
data/
  receipts.json               <- Sample receipt data (provided)
receipt_service/
  Dockerfile                  <- Docker config (provided)
  receipt_service.py          <- Receipt Flask service (provided)
  requirements.txt            <- Dependencies (provided)
  test_receipt_service.py     <- Receipt service tests (completed)
rules_service/
  Dockerfile                  <- Docker config (provided)
  rules_service.py            <- Rules Flask service (provided)
  requirements.txt            <- Dependencies (provided)
  test_rules_service.py       <- Rules service tests (completed)
shared/
  __init__.py                 <- Package init (provided)
  redis_client.py             <- Redis client helper (provided)
docker-compose.yml            <- Docker Compose config (provided)
workload.py                   <- Workload script (provided)
```

---

## Question 1 – Complete Tests for Both Services (40 points)

### Approach

Both services are Flask applications that depend on Redis. To test them in isolation (without a running Redis instance), we use `unittest.mock` to mock the `create_redis_client` function. Each test file uses a `@pytest.fixture` called `client` that:

1. Creates a `MagicMock` object to simulate the Redis client.
2. Patches `create_redis_client` in the service module to return the mock.
3. Creates a Flask test client via `app.test_client()` for making HTTP requests.

This follows the principle of unit testing: we isolate the component under test and mock its external dependencies.

### Receipt Service Tests (`receipt_service/test_receipt_service.py`)

```python
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
```

**Test descriptions:**

- **`test_receipt_success`**: Sends a POST request to `/api/receipt` with a valid receipt containing `receipt_id` and `products`. Asserts that:
  - The response status code is 200.
  - The response body contains `{"status": "ok"}`.
  - The mock Redis `hset` was called exactly once with the correct key (`receipt:1`) and the JSON-serialized products list.

- **`test_receipt_missing_fields`**: Sends a POST request with only `receipt_id` but no `products` field. The service attempts to access `data["products"]`, which raises a `KeyError`, caught by the `except` block, returning a 500 error. Asserts that the response status code is 500.

### Rules Service Tests (`rules_service/test_rules_service.py`)

```python
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

    # Mock apriori + association_rules (algorithm is non-deterministic)
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
def test_rules_no_receipts(client):
    from rules_service import create_redis_client
    r = create_redis_client()

    # Redis returns no receipts
    r.hvals.return_value = []

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
```

**Test descriptions:**

- **`test_rules_success`**: Configures the mock Redis `hvals` to return three JSON-encoded receipt lists. Mocks `apriori` and `association_rules` to return a DataFrame with one rule (milk -> bread). Sends a GET request to `/api/rules` and asserts:
  - HTTP status 200.
  - The JSON response contains exactly one rule.
  - The rule's antecedents and consequents are correct.

- **`test_rules_no_receipts`**: Sets `hvals` to return an empty list (no receipts). Mocks the algorithm functions to return empty DataFrames. Asserts that the service returns HTTP 200 with an empty JSON list `[]`.

**Note:** The `sys.modules.pop("rules_service", None)` in the fixture ensures the rules service module is re-imported cleanly with the mock applied, avoiding stale cached imports.

---

## Question 2 – GitHub Actions Workflow (30 points)

The workflow file is located at `.github/workflows/test.yml`:

```yaml
name: Run Tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest
          pip install -r receipt_service/requirements.txt
          pip install -r rules_service/requirements.txt

      - name: Run Receipt Service Tests
        env:
          PYTHONPATH: ${{ github.workspace }}
        run: |
          cd receipt_service
          python -m pytest test_receipt_service.py -v

      - name: Run Rules Service Tests
        env:
          PYTHONPATH: ${{ github.workspace }}
        run: |
          cd rules_service
          python -m pytest test_rules_service.py -v
```

**Workflow description:**

- **Triggers**: Runs on push/PR to `main` or `master` branches, and can be triggered manually via `workflow_dispatch`.
- **Environment**: Uses `ubuntu-latest` runner with Python 3.11.
- **Steps**:
  1. **Checkout** – clones the repository.
  2. **Set up Python** – installs Python 3.11 using the official action.
  3. **Install dependencies** – installs `pytest` and all requirements from both services.
  4. **Run Receipt Service Tests** – runs tests in the `receipt_service/` directory with `PYTHONPATH` set to the workspace root (so `shared/` can be imported).
  5. **Run Rules Service Tests** – same for the `rules_service/` directory.

No deployment steps are included as per the instructions.

---

## Question 3 – Local Test Results (15 points)

### Receipt Service Tests

```
========================================================== test session starts ===========================================================
platform win32 -- Python 3.11.9, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\Charm\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Charm\Downloads\LabTest3-Code\LabTest3-Code\receipt_service
collected 2 items

test_receipt_service.py::test_receipt_success PASSED                                                                                [ 50%]
test_receipt_service.py::test_receipt_missing_fields PASSED                                                                         [100%]

=========================================================== 2 passed in 1.98s ============================================================
```

### Rules Service Tests

```
========================================================== test session starts ===========================================================
platform win32 -- Python 3.11.9, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\Charm\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Charm\Downloads\LabTest3-Code\LabTest3-Code\rules_service
collected 2 items

test_rules_service.py::test_rules_success PASSED                                                                                    [ 50%]
test_rules_service.py::test_rules_no_receipts PASSED                                                                                [100%]

=========================================================== 2 passed in 24.10s ===========================================================
```

**All 4 tests passed locally.**

---

## Question 4 – GitHub Actions Workflow Output (15 points)

The workflow was executed locally using `act.exe -n` (dry-run mode) from the repository root:

```
*DRYRUN* [Run Tests/test] ⭐ Run Set up job
*DRYRUN* [Run Tests/test] 🚀  Start image=catthehacker/ubuntu:act-latest
*DRYRUN* [Run Tests/test]   🐳  docker pull image=catthehacker/ubuntu:act-latest platform= username= forcePull=true
*DRYRUN* [Run Tests/test]   🐳  docker create image=catthehacker/ubuntu:act-latest platform= entrypoint=["tail" "-f" "/dev/null"] cmd=[] network="host"
*DRYRUN* [Run Tests/test]   🐳  docker run image=catthehacker/ubuntu:act-latest platform= entrypoint=["tail" "-f" "/dev/null"] cmd=[] network="host"
*DRYRUN* [Run Tests/test]   ✅  Success - Set up job
*DRYRUN* [Run Tests/test]   ⬇  git clone 'https://github.com/actions/setup-python' # ref=v5
*DRYRUN* [Run Tests/test] ⭐ Run Main actions/checkout@v4
*DRYRUN* [Run Tests/test]   ✅  Success - Main actions/checkout@v4
*DRYRUN* [Run Tests/test] ⭐ Run Main Set up Python
*DRYRUN* [Run Tests/test]   ✅  Success - Main Set up Python
*DRYRUN* [Run Tests/test] ⭐ Run Main Install dependencies
*DRYRUN* [Run Tests/test]   ✅  Success - Main Install dependencies
*DRYRUN* [Run Tests/test] ⭐ Run Main Run Receipt Service Tests
*DRYRUN* [Run Tests/test]   ✅  Success - Main Run Receipt Service Tests
*DRYRUN* [Run Tests/test] ⭐ Run Main Run Rules Service Tests
*DRYRUN* [Run Tests/test]   ✅  Success - Main Run Rules Service Tests
*DRYRUN* [Run Tests/test] ⭐ Run Post Set up Python
*DRYRUN* [Run Tests/test]   ✅  Success - Post Set up Python
*DRYRUN* [Run Tests/test] ⭐ Run Complete job
*DRYRUN* [Run Tests/test] Cleaning up container for job test
*DRYRUN* [Run Tests/test]   ✅  Success - Complete job
*DRYRUN* [Run Tests/test] 🏁  Job succeeded
```

All workflow steps completed successfully. The `act` tool validated the workflow structure and steps using Docker with the `catthehacker/ubuntu:act-latest` image.
