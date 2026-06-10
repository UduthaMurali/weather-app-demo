import os
from flask import Flask, request, render_template_string
import requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', '.env'))

app = Flask(__name__)
API_KEY  = os.getenv('OPENWEATHER_API_KEY', '7a8c5e266aab89f1ba50a75c4c1b56af')
PORT     = int(os.getenv('PORT', '5000'))
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
{% endif %}
</body></html>"""

@app.route('/')
def index():
    city = request.args.get('city', '').strip()
    if not city:
        return render_template_string(HTML, city=None, weather=None, icon=None, error=None)
    resp = requests.get(f'{BASE_URL}/weather', params={'q': city, 'appid': API_KEY, 'units': 'metric'}, timeout=5)
    data = resp.json()
    if resp.status_code != 200:
        return render_template_string(HTML, city=city, weather=None, icon=None, error=data.get('message', 'City not found'))
    return render_template_string(HTML, city=city, weather=data, icon=data['weather'][0]['icon'], error=None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)