"""
Weather App — v1 (Small Drift)
================================
Developer adds Redis response caching and structured logging.
Config files are NOT updated.

New env vars added to code:
  REDIS_URL   → no default  → CRITICAL drift  (app breaks without it)
  LOG_LEVEL   → default "INFO" → WARNING drift (silent failure)

Drift check result: ⚠️ LOW  (score 4)
  - 1 critical item  (+3 pts)
  - 1 warning item   (+1 pt)
"""
import os
import logging
import json
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
API_KEY   = os.getenv("OPENWEATHER_API_KEY")           # ✅ in config
PORT      = int(os.getenv("PORT", "5000"))             # ✅ in config

REDIS_URL = os.getenv("REDIS_URL")                     # ❌ DRIFT: critical — no default
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")             # ❌ DRIFT: warning  — has default

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5"


def _redis_client():
    if not REDIS_URL:
        return None
    try:
        import redis
        return redis.from_url(REDIS_URL)
    except Exception:
        return None


def cache_get(key):
    r = _redis_client()
    if not r:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key, value, ttl=300):
    r = _redis_client()
    if not r:
        return
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


@app.route("/weather")
def get_weather():
    city = request.args.get("city", "Hamburg")
    cached = cache_get(f"weather:{city}")
    if cached:
        log.info("Cache HIT for %s", city)
        return jsonify({"source": "cache", "data": cached}), 200

    log.info("Cache MISS for %s — calling API", city)
    resp = requests.get(
        f"{BASE_URL}/weather",
        params={"q": city, "appid": API_KEY, "units": "metric"},
    )
    data = resp.json()
    cache_set(f"weather:{city}", data)
    return jsonify(data), resp.status_code


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": "v1",
        "cache": "connected" if REDIS_URL else "disabled",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
