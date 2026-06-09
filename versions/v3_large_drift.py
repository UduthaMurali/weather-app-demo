"""
Weather App — v3 (Large Drift)
================================
Developer adds weather alert emails, Slack notifications, Sentry error tracking,
and extended forecast. Config files are STILL not updated.

New env vars added to code (on top of v2):
  SMTP_HOST              → no default → CRITICAL
  SMTP_PORT              → default "587" → WARNING
  SMTP_USER              → no default → CRITICAL
  SMTP_PASSWORD          → no default → CRITICAL
  SLACK_WEBHOOK_URL      → no default → CRITICAL
  ALERT_THRESHOLD_CELSIUS→ default "35" → WARNING
  SENTRY_DSN             → no default → CRITICAL
  WEATHER_UNITS          → default "metric" → WARNING
  FORECAST_DAYS          → default "7" → WARNING

Cumulative drift:
  11 critical items
  6  warning items

Drift check result: 🔴 HIGH  (score 39)
  PR IS BLOCKED — exit code 1
"""
import os
import logging
import json
import smtplib
from email.mime.text import MIMEText
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
API_KEY   = os.getenv("OPENWEATHER_API_KEY")           # ✅ in config
PORT      = int(os.getenv("PORT", "5000"))             # ✅ in config

REDIS_URL           = os.getenv("REDIS_URL")                    # ❌ critical (v1)
LOG_LEVEL           = os.getenv("LOG_LEVEL", "INFO")            # ❌ warning  (v1)
DATABASE_URL        = os.getenv("DATABASE_URL")                 # ❌ critical (v2)
DB_USER             = os.getenv("DB_USER")                      # ❌ critical (v2)
DB_PASSWORD         = os.getenv("DB_PASSWORD")                  # ❌ critical (v2)
JWT_SECRET          = os.getenv("JWT_SECRET")                   # ❌ critical (v2)
RATE_LIMIT_PER_HOUR = os.getenv("RATE_LIMIT_PER_HOUR", "100")  # ❌ warning  (v2)

# NEW in v3 — alerts, notifications, monitoring
SMTP_HOST               = os.getenv("SMTP_HOST")                         # ❌ DRIFT: critical
SMTP_PORT               = os.getenv("SMTP_PORT", "587")                  # ❌ DRIFT: warning
SMTP_USER               = os.getenv("SMTP_USER")                         # ❌ DRIFT: critical
SMTP_PASSWORD           = os.getenv("SMTP_PASSWORD")                     # ❌ DRIFT: critical
SLACK_WEBHOOK_URL       = os.getenv("SLACK_WEBHOOK_URL")                 # ❌ DRIFT: critical
ALERT_THRESHOLD_CELSIUS = float(os.getenv("ALERT_THRESHOLD_CELSIUS", "35"))  # ❌ DRIFT: warning
SENTRY_DSN              = os.getenv("SENTRY_DSN")                        # ❌ DRIFT: critical
WEATHER_UNITS           = os.getenv("WEATHER_UNITS", "metric")           # ❌ DRIFT: warning
FORECAST_DAYS           = int(os.getenv("FORECAST_DAYS", "7"))           # ❌ DRIFT: warning

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)

# Initialise Sentry error tracking
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)
        log.info("Sentry initialised")
    except ImportError:
        log.warning("sentry-sdk not installed — error tracking disabled")

BASE_URL = "https://api.openweathermap.org/data/2.5"


# ── Notifications ─────────────────────────────────────────────────────────────

def send_email_alert(subject: str, body: str, recipient: str):
    """Send alert email via SMTP."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        log.warning("SMTP not configured — alert email NOT sent to %s", recipient)
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = recipient
        with smtplib.SMTP(SMTP_HOST, int(SMTP_PORT)) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        log.info("Alert email sent to %s", recipient)
    except Exception as e:
        log.error("Failed to send email: %s", e)


def send_slack_alert(message: str):
    """Post alert to Slack channel via webhook."""
    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL not set — Slack alert skipped")
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=5)
        log.info("Slack alert posted")
    except Exception as e:
        log.error("Slack alert failed: %s", e)


def check_extreme_weather(city: str, temp: float):
    """Fire alerts if temperature exceeds threshold."""
    if temp > ALERT_THRESHOLD_CELSIUS:
        msg = (f"⚠️  Extreme heat alert for {city}: "
               f"{temp:.1f}°C exceeds threshold of {ALERT_THRESHOLD_CELSIUS}°C")
        log.warning(msg)
        send_slack_alert(msg)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/weather")
def get_weather():
    city = request.args.get("city", "Hamburg")
    resp = requests.get(
        f"{BASE_URL}/weather",
        params={"q": city, "appid": API_KEY, "units": WEATHER_UNITS},
    )
    data = resp.json()
    temp = data.get("main", {}).get("temp", 0)
    check_extreme_weather(city, temp)
    return jsonify(data), resp.status_code


@app.route("/forecast")
def get_forecast():
    city = request.args.get("city", "Hamburg")
    resp = requests.get(
        f"{BASE_URL}/forecast",
        params={
            "q": city,
            "appid": API_KEY,
            "units": WEATHER_UNITS,
            "cnt": FORECAST_DAYS * 8,   # 8 slots per day (3-hour intervals)
        },
    )
    return jsonify(resp.json()), resp.status_code


@app.route("/alerts/test", methods=["POST"])
def test_alert():
    """Test endpoint to fire a manual alert (demo use)."""
    city = request.json.get("city", "Hamburg")
    temp = float(request.json.get("temp", 40))
    check_extreme_weather(city, temp)
    return jsonify({"fired": temp > ALERT_THRESHOLD_CELSIUS})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "v3"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
