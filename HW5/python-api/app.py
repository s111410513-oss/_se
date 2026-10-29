import os
import datetime
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "python-api",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })

@app.route("/")
def root():
    return jsonify({
        "message": "Python API for HW5 Docker Microservices",
        "endpoints": ["/health"]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
