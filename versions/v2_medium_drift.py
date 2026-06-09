"""
Weather App — v2 (Medium Drift)
=================================
Developer adds user accounts, PostgreSQL storage, and JWT authentication.
Config files are STILL not updated.

New env vars added to code (on top of v1):
  DATABASE_URL        → no default → CRITICAL
  DB_USER             → no default → CRITICAL
  DB_PASSWORD         → no default → CRITICAL
  JWT_SECRET          → no default → CRITICAL
  RATE_LIMIT_PER_HOUR → default "100" → WARNING

Cumulative drift:
  6 critical items   (REDIS_URL + 4 new)
  2 warning items    (LOG_LEVEL + RATE_LIMIT_PER_HOUR)

Drift check result: 🟠 HIGH  (score 20)
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

REDIS_URL = os.getenv("REDIS_URL")                     # ❌ critical
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")             # ❌ warning

# NEW in v2 — database & auth
DATABASE_URL        = os.getenv("DATABASE_URL")        # ❌ DRIFT: critical
DB_USER             = os.getenv("DB_USER")             # ❌ DRIFT: critical
DB_PASSWORD         = os.getenv("DB_PASSWORD")         # ❌ DRIFT: critical
JWT_SECRET          = os.getenv("JWT_SECRET")          # ❌ DRIFT: critical
RATE_LIMIT_PER_HOUR = os.getenv("RATE_LIMIT_PER_HOUR", "100")  # ❌ DRIFT: warning

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_db_conn():
    if not all([DATABASE_URL, DB_USER, DB_PASSWORD]):
        raise RuntimeError("Database not configured — DATABASE_URL / DB_USER / DB_PASSWORD missing!")
    import psycopg2
    return psycopg2.connect(DATABASE_URL, user=DB_USER, password=DB_PASSWORD)


def verify_jwt(token: str):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET not set!")
    import jwt
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def _require_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "Authorization header missing"}), 401)
    try:
        payload = verify_jwt(auth[7:])
        return payload, None
    except Exception as e:
        return None, (jsonify({"error": "Invalid token", "detail": str(e)}), 401)


@app.route("/weather")
def get_weather():
    city = request.args.get("city", "Hamburg")
    resp = requests.get(
        f"{BASE_URL}/weather",
        params={"q": city, "appid": API_KEY, "units": "metric"},
    )
    return jsonify(resp.json()), resp.status_code


@app.route("/users/favorites", methods=["GET"])
def get_favorites():
    user, err = _require_auth()
    if err:
        return err
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT city FROM favorites WHERE user_id = %s", (user["sub"],))
    cities = [row[0] for row in cur.fetchall()]
    conn.close()
    return jsonify({"favorites": cities})


@app.route("/users/favorites", methods=["POST"])
def add_favorite():
    user, err = _require_auth()
    if err:
        return err
    city = request.json.get("city")
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO favorites (user_id, city) VALUES (%s, %s)", (user["sub"], city))
    conn.commit()
    conn.close()
    return jsonify({"added": city}), 201


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "v2"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
