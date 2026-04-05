import json
import requests

RECEIPT_URL = "http://127.0.0.1:5000"
RULES_URL = "http://127.0.0.1:5001"

with open("data/receipts.json") as f:
    data = json.load(f)

print("Loaded receipts, now sending to receipt service …")
for receipt in data:
    payload = {
        "receipt_id": receipt["receipt_id"],
        "products": receipt["products"]
    }

    requests.post(f"{RECEIPT_URL}/api/receipt", json=payload)

print("Receipts sent, now fetching rules …")

response = requests.get(f"{RULES_URL}/api/rules")

print("Rules received:")
rules = response.json()
for rule in rules:
    print(f"Rule: {rule['antecedents']} -> {rule['consequents']} (confidence: {rule['confidence']:.2f})")

print("End of workload.")