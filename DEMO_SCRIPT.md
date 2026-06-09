# Config Drift Detector — Live Demo Script

## Overview

A weather app is developed in 3 feature updates.
After each update, a GitHub Action runs the Config Drift Detector.
The deployment config (`config/`) is **never updated** — drift grows with each push.

```
config/.env              ← declares: OPENWEATHER_API_KEY, PORT  (only these 2, forever)
config/docker-compose.yml
config/k8s/deployment.yaml
```

---

## Setup (one-time before the demo)

```bash
# 1. Create a new GitHub repo, e.g. "weather-app-demo"
# 2. Push this entire folder to it
cd "C:\Users\mural\Desktop\ASE Demo"
git init
git add .
git commit -m "Initial weather app — baseline clean"
git remote add origin https://github.com/YOUR_USERNAME/weather-app-demo.git
git push -u origin main

# 3. Copy the baseline app into the active app/ folder
cp versions/v0_clean.py app/weather.py
git add app/weather.py
git commit -m "chore: set active app to v0 baseline"
git push origin main
```

---

## Demo Step 0 — Baseline (no drift)

**What to say:**  
> "The app starts clean. It uses two env vars — the API key and a port.  
>  Both are declared in our Kubernetes config. The drift check passes."

```bash
# (already pushed in setup)
# GitHub Action runs → shows ✅ NONE, score 0
```

**Expected GitHub Action output:**
```
✅ Config Drift Report
Drift Level: NONE | Drift Score: 0
All environment variables are declared in deployment config. No drift detected.
```

---

## Demo Step 1 — Small Drift (Redis caching)

**What to say:**  
> "The developer adds Redis caching to speed up API responses.  
>  They add REDIS_URL and LOG_LEVEL to the code — but forget to update the config.  
>  The drift detector catches it immediately."

```bash
cp versions/v1_small_drift.py app/weather.py
git add app/weather.py
git commit -m "feat: add Redis caching and structured logging"
git push origin feature/add-caching
# Open a Pull Request on GitHub
```

**Expected GitHub Action output:**
```
⚠️ Config Drift Report
Drift Level: LOW | Drift Score: 4

🔴 Critical — 1 variable(s) with NO default:
  REDIS_URL   → app/weather.py  (os.getenv)

⚠️ Warning — 1 variable(s) with default not in config:
  LOG_LEVEL   → app/weather.py  (os.getenv)
```

**PR status:** ❌ BLOCKED (critical drift)

---

## Demo Step 2 — Medium Drift (User accounts + JWT)

**What to say:**  
> "Now the developer adds user accounts, a PostgreSQL database, and JWT authentication.  
>  Four more critical variables land in the code. Config still not updated.  
>  Drift score jumps from 4 to 20."

```bash
cp versions/v2_medium_drift.py app/weather.py
git add app/weather.py
git commit -m "feat: add user accounts, PostgreSQL storage, JWT auth"
git push origin feature/user-accounts
# Open a Pull Request on GitHub
```

**Expected GitHub Action output:**
```
🟠 Config Drift Report
Drift Level: HIGH | Drift Score: 20

🔴 Critical — 5 variable(s) with NO default:
  REDIS_URL       → app/weather.py
  DATABASE_URL    → app/weather.py
  DB_USER         → app/weather.py
  DB_PASSWORD     → app/weather.py
  JWT_SECRET      → app/weather.py

⚠️ Warning — 2 variable(s):
  LOG_LEVEL           → app/weather.py
  RATE_LIMIT_PER_HOUR → app/weather.py
```

**PR status:** ❌ BLOCKED (critical drift)

---

## Demo Step 3 — Large Drift (Alerts + Slack + Sentry)

**What to say:**  
> "The developer adds weather alerts, email notifications, Slack integration, and Sentry  
>  monitoring. Nine more env vars are added to the code.  
>  Total: 11 critical, 6 warnings. Score: 39. The pipeline blocks hard."

```bash
cp versions/v3_large_drift.py app/weather.py
git add app/weather.py
git commit -m "feat: add alert system, Slack, Sentry monitoring, extended forecast"
git push origin feature/alert-system
# Open a Pull Request on GitHub
```

**Expected GitHub Action output:**
```
🔴 Config Drift Report
Drift Level: HIGH | Drift Score: 39

🔴 Critical — 11 variable(s) with NO default:
  REDIS_URL, DATABASE_URL, DB_USER, DB_PASSWORD, JWT_SECRET,
  SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SLACK_WEBHOOK_URL, SENTRY_DSN

⚠️ Warning — 6 variable(s):
  LOG_LEVEL, RATE_LIMIT_PER_HOUR, SMTP_PORT,
  ALERT_THRESHOLD_CELSIUS, WEATHER_UNITS, FORECAST_DAYS

╔═══════════════════════════════════════╗
║  ❌  CRITICAL CONFIG DRIFT DETECTED   ║
╚═══════════════════════════════════════╝
```

**PR status:** ❌ BLOCKED

---

## Demo Step 4 — Fix the drift (optional)

**What to say:**  
> "The fix is simple — update the config files to declare the missing variables.  
>  Once we push the fix, the drift check passes and the PR is unblocked."

Add the missing vars to `config/.env`, `config/docker-compose.yml`,
and `config/k8s/deployment.yaml`, then:

```bash
git add config/
git commit -m "fix: declare all env vars in deployment config"
git push origin feature/alert-system
```

**Expected GitHub Action output:**
```
✅ Config Drift Report
Drift Level: NONE | Drift Score: 0
All environment variables are declared. Safe to merge! ✅
```

---

## Drift Progression Summary

| Version | Feature Added | New Critical | New Warnings | Total Score | Result |
|---------|--------------|:---:|:---:|:---:|--------|
| v0 | Baseline | 0 | 0 | 0 | ✅ PASS |
| v1 | Redis caching | 1 | 1 | 4 | ❌ BLOCKED |
| v2 | DB + JWT auth | +4 | +1 | 20 | ❌ BLOCKED |
| v3 | Alerts + Sentry | +5 | +4 | 39 | ❌ BLOCKED |

---

## Key Points to Mention

1. **Static analysis** — tool reads the code without running it; works at PR time before deployment.
2. **Cross-artifact** — compares source code against K8s YAML, Docker Compose, and .env simultaneously.
3. **Severity scoring** — variables without a default are critical (3 pts); with a default are warnings (1 pt).
4. **PR comment** — automatic table posted directly on the GitHub PR — no separate dashboard needed.
5. **Exit code 1** — integrates with branch protection rules to hard-block merging until fixed.
