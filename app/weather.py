"""
Weather App — v1 (Small Drift)
Developer adds Redis response caching.
New env vars: REDIS_URL (warning - has default), LOG_LEVEL (warning - has default)
Pipeline: warns but does NOT block.
UI: shows cache status badge — always "LIVE" because Redis isn't in deployment config.
"""
import os, logging, json
from flask import Flask, jsonify, request, render_template_string
import requests

app = Flask(__name__)

API_KEY   = os.getenv("OPENWEATHER_API_KEY")
PORT      = int(os.getenv("PORT", "5000"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")   # ⚠️ warning — not in config
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")                     # ⚠️ warning — not in config

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5"

WEATHER_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
    "Drizzle": "🌦️", "Thunderstorm": "⛈️", "Snow": "❄️",
    "Mist": "🌫️", "Fog": "🌫️", "Haze": "🌫️",
}

def redis_client():
    try:
        import redis
        r = redis.from_url(REDIS_URL, socket_connect_timeout=1)
        r.ping()
        return r
    except Exception:
        return None

def cache_get(key):
    r = redis_client()
    if not r: return None, False
    try:
        val = r.get(key)
        return (json.loads(val), True) if val else (None, False)
    except Exception:
        return None, False

def cache_set(key, value):
    r = redis_client()
    if not r: return
    try: r.setex(key, 300, json.dumps(value))
    except Exception: pass

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
    }
    .cache-live    { background: rgba(255,165,0,0.2); border: 1px solid rgba(255,165,0,0.4); color: #ffa500; }
    .cache-hit     { background: rgba(0,200,120,0.2); border: 1px solid rgba(0,200,120,0.4); color: #00c878; }
    .city-name { font-size: 1.8rem; font-weight: 600; margin-bottom: 4px; }
    .country   { font-size: 1rem; opacity: 0.6; margin-bottom: 24px; }
    .weather-icon { font-size: 5rem; margin: 16px 0; }
    .temp      { font-size: 4.5rem; font-weight: 200; line-height: 1; }
    .temp sup  { font-size: 1.8rem; vertical-align: super; }
    .description { font-size: 1.1rem; text-transform: capitalize; opacity: 0.75; margin: 12px 0 28px; }
    .details {
      display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
      border-top: 1px solid rgba(255,255,255,0.1); padding-top: 24px;
    }
    .detail-item .label { font-size: 0.72rem; opacity: 0.55; text-transform: uppercase; letter-spacing: 1px; }
    .detail-item .value { font-size: 1.1rem; font-weight: 600; margin-top: 4px; }
    .error {
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
    <div class="error">{{ error }}</div>
  {% elif weather %}
    <div class="card">
      <div class="card-header">
        {% if from_cache %}
          <span class="cache-badge cache-hit">⚡ CACHED</span>
        {% else %}
          <span class="cache-badge cache-live">🔄 LIVE — cache not configured</span>
        {% endif %}
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
    </div>
  {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    city = request.args.get("city", "").strip()
    if not city:
        return render_template_string(HTML, city=None, weather=None, error=None,
                                      icon=None, temp=None, feels_like=None,
                                      wind=None, from_cache=False)
    if not API_KEY:
        return render_template_string(HTML, city=city, weather=None,
                                      error="OPENWEATHER_API_KEY is not set.",
                                      icon=None, temp=None, feels_like=None,
                                      wind=None, from_cache=False)
    cached, hit = cache_get(f"weather:{city.lower()}")
    if hit:
        data = cached
        from_cache = True
    else:
        resp = requests.get(f"{BASE_URL}/weather",
                            params={"q": city, "appid": API_KEY, "units": "metric"}, timeout=5)
        if resp.status_code == 404:
            return render_template_string(HTML, city=city, weather=None,
                                          error=f'City "{city}" not found.',
                                          icon=None, temp=None, feels_like=None,
                                          wind=None, from_cache=False)
        data = resp.json()
        cache_set(f"weather:{city.lower()}", data)
        from_cache = False
        log.info("Fetched live data for %s", city)

    icon       = WEATHER_ICONS.get(data["weather"][0]["main"], "🌡️")
    temp       = round(data["main"]["temp"])
    feels_like = round(data["main"]["feels_like"])
    wind       = round(data["wind"]["speed"], 1)
    return render_template_string(HTML, city=city, weather=data, icon=icon,
                                  temp=temp, feels_like=feels_like,
                                  wind=wind, from_cache=from_cache, error=None)

@app.route("/health")
def health():
    r = redis_client()
    return jsonify({"status": "ok", "version": "v1", "cache": "connected" if r else "disconnected"})

if __name__ == "__main__":
    print(f"\n  WeatherApp v1 running at http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=True)
