"""
Weather App — v0 (Baseline / Clean)
====================================
No drift. All env vars used in code are declared in config/.env
and config/k8s/deployment.yaml.

Drift check result: ✅ NONE  (score 0)
"""
import os
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# ── Configuration (both declared in config/) ──────────────────────────────────
API_KEY = os.getenv("OPENWEATHER_API_KEY")
PORT    = int(os.getenv("PORT", "5000"))

BASE_URL = "https://api.openweathermap.org/data/2.5"


@app.route("/weather")
def get_weather():
    city = request.args.get("city", "Hamburg")
    resp = requests.get(
        f"{BASE_URL}/weather",
        params={"q": city, "appid": API_KEY, "units": "metric"},
    )
    return jsonify(resp.json()), resp.status_code


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "v0"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
