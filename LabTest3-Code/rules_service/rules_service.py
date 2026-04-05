from flask import request, Flask, jsonify
from mlxtend.frequent_patterns import apriori, association_rules

from shared.redis_client import create_redis_client
from mlxtend.preprocessing import TransactionEncoder
import pandas as pd
import json

app = Flask(__name__)

@app.route("/api/rules", methods=["GET"])
def api_rules():
    receipts = read_receipts()
    te = TransactionEncoder()
    te_array = te.fit(receipts).transform(receipts)

    df = pd.DataFrame(te_array, columns=te.columns_)
    frequent_itemsets = apriori(df, min_support=0.3, use_colnames=True)
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.5)

    # Convert frozensets to lists for JSON
    rules['antecedents'] = rules['antecedents'].apply(list)
    rules['consequents'] = rules['consequents'].apply(list)

    return jsonify(rules.to_dict(orient="records"))


def read_receipts():
    r = create_redis_client()
    raw_receipts = r.hvals("receipt")

    receipts = [json.loads(r) for r in raw_receipts]

    return receipts

if __name__ == "__main__":
    print("Rules service starting on port 5001 …")
    app.run(host="0.0.0.0", port=5001, debug=True)