"""
Weather App — v3 (Large Drift)
Developer adds weather alert subscription (email + Slack + Sentry monitoring).
New env vars: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SLACK_WEBHOOK_URL, SENTRY_DSN (all critical)
              ALERT_THRESHOLD_CELSIUS, WEATHER_UNITS, FORECAST_DAYS (warnings)
UI: 🔔 Alert button in card — clicking shows inline email form.
    Subscribing fails with "Email service not configured" because SMTP vars missing from deployment.
Pipeline: BLOCKS (critical drift).
"""
import os, logging
from flask import Flask, jsonify, request, render_template_string
import requests

app = Flask(__name__)

API_KEY                 = os.getenv("OPENWEATHER_API_KEY")
PORT                    = int(os.getenv("PORT", "5000"))
REDIS_URL               = os.getenv("REDIS_URL", "redis://localhost:6379")
LOG_LEVEL               = os.getenv("LOG_LEVEL", "INFO")
DATABASE_URL            = os.getenv("DATABASE_URL")
DB_USER                 = os.getenv("DB_USER")
DB_PASSWORD             = os.getenv("DB_PASSWORD")
JWT_SECRET              = os.getenv("JWT_SECRET")
RATE_LIMIT_PER_HOUR     = os.getenv("RATE_LIMIT_PER_HOUR", "100")
SMTP_HOST               = os.getenv("SMTP_HOST")                          # ❌ critical
SMTP_PORT               = os.getenv("SMTP_PORT", "587")                   # ⚠️ warning
SMTP_USER               = os.getenv("SMTP_USER")                          # ❌ critical
SMTP_PASSWORD           = os.getenv("SMTP_PASSWORD")                      # ❌ critical
SLACK_WEBHOOK_URL       = os.getenv("SLACK_WEBHOOK_URL")                  # ❌ critical
ALERT_THRESHOLD_CELSIUS = os.getenv("ALERT_THRESHOLD_CELSIUS", "35")      # ⚠️ warning
SENTRY_DSN              = os.getenv("SENTRY_DSN")                         # ❌ critical
WEATHER_UNITS           = os.getenv("WEATHER_UNITS", "metric")            # ⚠️ warning
FORECAST_DAYS           = os.getenv("FORECAST_DAYS", "7")                 # ⚠️ warning

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)
BASE_URL = "https://api.openweathermap.org/data/2.5"

WEATHER_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
    "Drizzle": "🌦️", "Thunderstorm": "⛈️", "Snow": "❄️",
    "Mist": "🌫️", "Fog": "🌫️", "Haze": "🌫️",
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WeatherApp</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', sans-serif; min-height: 100vh;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      display: flex; flex-direction: column; align-items: center;
      justify-content: flex-start; padding: 40px 20px; color: #fff;
    }
    h1 { font-size: 2rem; font-weight: 300; letter-spacing: 4px;
         text-transform: uppercase; margin-bottom: 32px; opacity: 0.9; }
    .search-box { display: flex; gap: 10px; margin-bottom: 40px; width: 100%; max-width: 480px; }
    .search-box input {
      flex: 1; padding: 14px 20px; border-radius: 30px; border: none;
      background: rgba(255,255,255,0.12); color: #fff; font-size: 1rem;
      outline: none; backdrop-filter: blur(10px);
    }
    .search-box input::placeholder { color: rgba(255,255,255,0.5); }
    .search-box input:focus { background: rgba(255,255,255,0.2); }
    .search-box button {
      padding: 14px 24px; border-radius: 30px; border: none;
      background: #e94560; color: #fff; font-size: 1rem; cursor: pointer;
    }
    .card {
      background: rgba(255,255,255,0.08); backdrop-filter: blur(20px);
      border: 1px solid rgba(255,255,255,0.12); border-radius: 24px;
      padding: 40px; width: 100%; max-width: 480px; text-align: center;
      animation: fadeIn 0.4s ease;
    }
    @keyframes fadeIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
    .card-header { display: flex; justify-content: flex-end; margin-bottom: 8px; }
    .cache-badge {
      font-size: 0.7rem; letter-spacing: 1px; padding: 4px 12px;
      border-radius: 20px; font-weight: 600;
      background: rgba(255,165,0,0.2); border: 1px solid rgba(255,165,0,0.4); color: #ffa500;
    }
    .city-name { font-size: 1.8rem; font-weight: 600; margin-bottom: 4px; }
    .country   { font-size: 1rem; opacity: 0.6; margin-bottom: 24px; }
    .weather-icon { font-size: 5rem; margin: 16px 0; }
    .temp      { font-size: 4.5rem; font-weight: 200; line-height: 1; }
    .temp sup  { font-size: 1.8rem; vertical-align: super; }
    .description { font-size: 1.1rem; text-transform: capitalize; opacity: 0.75; margin: 12px 0 28px; }
    .details {
      display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
      border-top: 1px solid rgba(255,255,255,0.1); padding-top: 24px; margin-bottom: 24px;
    }
    .detail-item .label { font-size: 0.72rem; opacity: 0.55; text-transform: uppercase; letter-spacing: 1px; }
    .detail-item .value { font-size: 1.1rem; font-weight: 600; margin-top: 4px; }
    .action-row { display: flex; gap: 10px; margin-top: 8px; }
    .btn {
      flex: 1; padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);
      background: rgba(255,255,255,0.08); color: #fff; font-size: 0.9rem;
      cursor: pointer; transition: background 0.2s;
    }
    .btn:hover { background: rgba(255,255,255,0.15); }
    .alert-form {
      display: none; margin-top: 16px; text-align: left;
      border-top: 1px solid rgba(255,255,255,0.1); padding-top: 16px;
    }
    .alert-form label { font-size: 0.75rem; opacity: 0.6; display: block; margin-bottom: 4px; margin-top: 12px; }
    .alert-form input {
      width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15);
      background: rgba(255,255,255,0.08); color: #fff; font-size: 0.9rem; outline: none;
    }
    .subscribe-btn {
      width: 100%; margin-top: 14px; padding: 12px; border-radius: 12px; border: none;
      background: #e94560; color: #fff; font-size: 0.95rem; cursor: pointer;
    }
    .toast {
      margin-top: 14px; padding: 12px 16px; border-radius: 10px;
      font-size: 0.85rem; display: none;
    }
    .toast.error   { background: rgba(233,69,96,0.2); border: 1px solid rgba(233,69,96,0.4); color: #ff8fa3; }
    .toast.success { background: rgba(0,200,120,0.2); border: 1px solid rgba(0,200,120,0.4); color: #00c878; }
    .error-box {
      background: rgba(233,69,96,0.2); border: 1px solid rgba(233,69,96,0.4);
      border-radius: 16px; padding: 24px 32px; color: #ff8fa3;
      font-size: 1rem; width: 100%; max-width: 480px; text-align: center;
    }
  </style>
</head>
<body>
  <h1>&#127783; WeatherApp</h1>
  <form class="search-box" action="/" method="get">
    <input type="text" name="city" placeholder="Search city..." value="{{ city or '' }}" autofocus>
    <button type="submit">Search</button>
  </form>
  {% if error %}
    <div class="error-box">{{ error }}</div>
  {% elif weather %}
    <div class="card">
      <div class="card-header">
        <span class="cache-badge">🔄 LIVE — cache not configured</span>
      </div>
      <div class="city-name">{{ weather.name }}</div>
      <div class="country">{{ weather.sys.country }}</div>
      <div class="weather-icon">{{ icon }}</div>
      <div class="temp">{{ temp }}<sup>&deg;C</sup></div>
      <div class="description">{{ weather.weather[0].description }}</div>
      <div class="details">
        <div class="detail-item">
          <div class="label">Feels like</div>
          <div class="value">{{ feels_like }}&deg;C</div>
        </div>
        <div class="detail-item">
          <div class="label">Humidity</div>
          <div class="value">{{ weather.main.humidity }}%</div>
        </div>
        <div class="detail-item">
          <div class="label">Wind</div>
          <div class="value">{{ wind }} m/s</div>
        </div>
      </div>
      <div class="action-row">
        <button class="btn" onclick="saveFavorite('{{ weather.name }}')">★ Favorite</button>
        <button class="btn" onclick="toggleAlert()">🔔 Alert me</button>
      </div>
      <div class="alert-form" id="alertForm">
        <label>Your email</label>
        <input type="email" id="alertEmail" placeholder="you@example.com">
        <label>Alert when temperature exceeds (°C)</label>
        <input type="number" id="alertThreshold" value="{{ threshold }}" min="-20" max="60">
        <button class="subscribe-btn" onclick="subscribeAlert('{{ weather.name }}')">Subscribe to Alerts</button>
      </div>
      <div class="toast" id="toast"></div>
    </div>
  {% endif %}
  <script>
    function showToast(msg, type) {
      const t = document.getElementById('toast');
      t.style.display = 'block';
      t.className = 'toast ' + type;
      t.textContent = (type === 'error' ? '❌ ' : '✅ ') + msg;
    }
    function saveFavorite(city) {
      fetch('/api/favorite', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({city})})
        .then(r => r.json())
        .then(d => d.error ? showToast(d.error, 'error') : showToast(city + ' saved!', 'success'));
    }
    function toggleAlert() {
      const f = document.getElementById('alertForm');
      f.style.display = f.style.display === 'block' ? 'none' : 'block';
    }
    function subscribeAlert(city) {
      const email = document.getElementById('alertEmail').value;
      const threshold = document.getElementById('alertThreshold').value;
      if (!email) { showToast('Please enter your email', 'error'); return; }
      fetch('/api/subscribe-alert', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({city, email, threshold})})
        .then(r => r.json())
        .then(d => d.error ? showToast(d.error, 'error') : showToast('Alert set for ' + city, 'success'));
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    city = request.args.get("city", "").strip()
    if not city:
        return render_template_string(HTML, city=None, weather=None, error=None,
                                      icon=None, temp=None, feels_like=None,
                                      wind=None, threshold=ALERT_THRESHOLD_CELSIUS)
    if not API_KEY:
        return render_template_string(HTML, city=city, weather=None,
                                      error="OPENWEATHER_API_KEY is not set.",
                                      icon=None, temp=None, feels_like=None,
                                      wind=None, threshold=ALERT_THRESHOLD_CELSIUS)
    resp = requests.get(f"{BASE_URL}/weather",
                        params={"q": city, "appid": API_KEY, "units": WEATHER_UNITS}, timeout=5)
    if resp.status_code == 404:
        return render_template_string(HTML, city=city, weather=None,
                                      error=f'City "{city}" not found.',
                                      icon=None, temp=None, feels_like=None,
                                      wind=None, threshold=ALERT_THRESHOLD_CELSIUS)
    data       = resp.json()
    icon       = WEATHER_ICONS.get(data["weather"][0]["main"], "🌡️")
    temp       = round(data["main"]["temp"])
    feels_like = round(data["main"]["feels_like"])
    wind       = round(data["wind"]["speed"], 1)
    return render_template_string(HTML, city=city, weather=data, icon=icon,
                                  temp=temp, feels_like=feels_like, wind=wind,
                                  threshold=ALERT_THRESHOLD_CELSIUS, error=None)

@app.route("/api/favorite", methods=["POST"])
def save_favorite():
    if not all([DATABASE_URL, DB_USER, DB_PASSWORD]):
        return jsonify({"error": "Favorites unavailable — DATABASE_URL not configured in deployment"}), 503
    return jsonify({"saved": request.json.get("city")})

@app.route("/api/subscribe-alert", methods=["POST"])
def subscribe_alert():
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        return jsonify({"error": "Alert service unavailable — SMTP_HOST, SMTP_USER, SMTP_PASSWORD not configured in deployment"}), 503
    return jsonify({"subscribed": True})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "v3",
                    "db": "configured" if DATABASE_URL else "missing",
                    "smtp": "configured" if SMTP_HOST else "missing"})

if __name__ == "__main__":
    print(f"\n  WeatherApp v3 running at http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=True)
