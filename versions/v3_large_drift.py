import os
from flask import Flask, request, render_template_string
import requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', '.env'))

app = Flask(__name__)
API_KEY              = os.getenv('OPENWEATHER_API_KEY', '7a8c5e266aab89f1ba50a75c4c1b56af')
PORT                 = int(os.getenv('PORT', '5000'))
REDIS_URL            = os.getenv('REDIS_URL')             # critical
LOG_LEVEL            = os.getenv('LOG_LEVEL', 'INFO')     # warning
DATABASE_URL         = os.getenv('DATABASE_URL')          # critical
DB_USER              = os.getenv('DB_USER')               # critical
DB_PASSWORD          = os.getenv('DB_PASSWORD')           # critical
JWT_SECRET           = os.getenv('JWT_SECRET')            # critical
RATE_LIMIT_PER_HOUR  = os.getenv('RATE_LIMIT_PER_HOUR', '100')  # warning
SMTP_HOST            = os.getenv('SMTP_HOST')             # critical
SMTP_PORT            = os.getenv('SMTP_PORT', '587')      # warning
SMTP_USER            = os.getenv('SMTP_USER')             # critical
SMTP_PASSWORD        = os.getenv('SMTP_PASSWORD')         # critical
SLACK_WEBHOOK_URL    = os.getenv('SLACK_WEBHOOK_URL')     # critical
SENTRY_DSN           = os.getenv('SENTRY_DSN')            # critical
WEATHER_UNITS        = os.getenv('WEATHER_UNITS', 'metric')  # warning
FORECAST_DAYS        = os.getenv('FORECAST_DAYS', '7')    # warning
BASE_URL = 'https://api.openweathermap.org/data/2.5'

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);min-height:100vh;color:white}
.header{text-align:center;padding:2rem;font-size:1.4rem;font-weight:700;letter-spacing:4px}
.search-bar{display:flex;justify-content:center;gap:.75rem;padding:0 1rem 2rem}
.search-bar input{width:420px;padding:.85rem 1.4rem;border-radius:50px;border:none;background:rgba(255,255,255,.12);color:white;font-size:1rem;outline:none}
.search-bar input::placeholder{color:rgba(255,255,255,.45)}
.search-bar button{padding:.85rem 1.8rem;border-radius:50px;border:none;background:#e94560;color:white;font-size:1rem;font-weight:600;cursor:pointer}
.card{max-width:520px;margin:0 auto 2rem;background:rgba(255,255,255,.08);border-radius:20px;padding:2.5rem 2rem;text-align:center}
.city{font-size:2rem;font-weight:700}.country{opacity:.6;margin-bottom:.5rem}
.icon img{width:80px;height:80px}.temp{font-size:4rem;font-weight:300}
.desc{font-size:1.1rem;opacity:.8;margin-bottom:1.5rem}
.details{display:flex;justify-content:space-around;border-top:1px solid rgba(255,255,255,.15);padding-top:1.2rem}
.detail .label{font-size:.7rem;opacity:.6;letter-spacing:1px;text-transform:uppercase}
.detail .value{font-size:1.1rem;font-weight:600;margin-top:.2rem}
.error{max-width:520px;margin:0 auto;background:rgba(220,38,38,.15);border:1px solid rgba(220,38,38,.4);border-radius:16px;padding:1.5rem;text-align:center;color:#f87171}
.cache-bar{max-width:520px;margin:0 auto .75rem;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:.5rem 1rem;font-size:.82rem;color:#86efac;text-align:center}
.actions{max-width:520px;margin:.75rem auto 0;display:flex;gap:.75rem;justify-content:center}
.btn-fav{padding:.6rem 1.4rem;border-radius:50px;border:1px solid rgba(251,191,36,.3);background:rgba(251,191,36,.15);color:#fbbf24;font-size:.9rem;cursor:pointer}
.btn-alert{padding:.6rem 1.4rem;border-radius:50px;border:1px solid rgba(99,102,241,.3);background:rgba(99,102,241,.15);color:#a5b4fc;font-size:.9rem;cursor:pointer}
.toast{display:none;position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);padding:.75rem 1.5rem;border-radius:50px;font-size:.9rem;font-weight:600;color:white;z-index:999}
"""

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>WeatherApp</title>
<style>""" + CSS + """</style></head><body>
<div class="header">&#9925; WEATHER APP</div>
<div class="search-bar">
  <form method="get" action="/" style="display:flex;gap:.75rem">
    <input name="city" placeholder="Search city..." value="{{ city or '' }}" autocomplete="off">
    <button type="submit">Search</button>
  </form>
</div>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
{% if weather %}
<div class="cache-bar">&#9889; Redis cache enabled &mdash; faster responses</div>
<div class="card">
  <div class="city">{{ weather.name }}</div>
  <div class="country">{{ weather.sys.country }}</div>
  <div class="icon"><img src="https://openweathermap.org/img/wn/{{ icon }}@2x.png"></div>
  <div class="temp">{{ weather.main.temp|round|int }}&deg;C</div>
  <div class="desc">{{ weather.weather[0].description|title }}</div>
  <div class="details">
    <div class="detail"><div class="label">Feels Like</div><div class="value">{{ weather.main.feels_like|round|int }}&deg;C</div></div>
    <div class="detail"><div class="label">Humidity</div><div class="value">{{ weather.main.humidity }}%</div></div>
    <div class="detail"><div class="label">Wind</div><div class="value">{{ weather.wind.speed }} m/s</div></div>
  </div>
</div>
<div class="actions">
  <button class="btn-fav" onclick="showToast('t1')">&#9733; Favorites</button>
  <button class="btn-alert" onclick="showToast('t2')">&#128276; Alert me</button>
</div>
{% if db_ok %}
<div class="toast" id="t1" style="background:#22c55e">&#10003; Added to favorites!</div>
{% else %}
<div class="toast" id="t1" style="background:#dc2626">&#10060; Error: DATABASE_URL not configured</div>
{% endif %}
{% if smtp_ok %}
<div class="toast" id="t2" style="background:#6366f1">&#10003; Weather alert set!</div>
{% else %}
<div class="toast" id="t2" style="background:#dc2626">&#10060; Error: SMTP_HOST not configured</div>
{% endif %}
<script>
function showToast(id){
  var t=document.getElementById(id);
  t.style.display='block';
  setTimeout(function(){t.style.display='none'},3000);
}
</script>
{% endif %}
</body></html>"""

@app.route('/')
def index():
    city = request.args.get('city', '').strip()
    db_ok   = bool(DATABASE_URL)
    smtp_ok = bool(SMTP_HOST)
    if not city:
        return render_template_string(HTML, city=None, weather=None, icon=None, error=None, db_ok=db_ok, smtp_ok=smtp_ok)
    resp = requests.get(f'{BASE_URL}/weather', params={'q': city, 'appid': API_KEY, 'units': 'metric'}, timeout=5)
    data = resp.json()
    if resp.status_code != 200:
        return render_template_string(HTML, city=city, weather=None, icon=None, error=data.get('message', 'City not found'), db_ok=db_ok, smtp_ok=smtp_ok)
    return render_template_string(HTML, city=city, weather=data, icon=data['weather'][0]['icon'], error=None, db_ok=db_ok, smtp_ok=smtp_ok)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)