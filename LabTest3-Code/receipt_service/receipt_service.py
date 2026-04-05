from flask import request, Flask
from shared.redis_client import create_redis_client
import json

app = Flask(__name__)

@app.route("/api/receipt", methods=["POST"])
def api_receipt():
    try:
        r = create_redis_client()
        data = request.get_json()

        products = data["products"]
        receipt_id = data["receipt_id"]

        r.hset(f"receipt:{receipt_id}", "products", json.dumps(products))
    except Exception as e:
        return {"status": "error"}, 500

    return {"status": "ok"}, 200

if __name__ == "__main__":
    print("Receipt service starting on port 5000 …")
    app.run(host="0.0.0.0", port=5000)