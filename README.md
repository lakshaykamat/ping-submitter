# Ping Submission Automation

Flask app for creating ping submission jobs, running autonomous browser-use automation, and downloading final JSON or Markdown reports with success, failure, and reason evidence.

The app is intentionally small: Flask, SQLite, SQLAlchemy, Playwright, and local browser-use. Jobs run through a plain Python worker entrypoint, without Redis or a queue broker.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
flask --app app:create_app run
```

Open `http://127.0.0.1:5000`.

## Run a Job

Create a job from the dashboard. The app redirects to the job detail page and starts a local background thread automatically. The **Run now** button remains available as a manual fallback for queued jobs. The browser-use agent takes all browser actions on its own and records progress in the database-backed activity panel.

API flow:

```bash
curl -X POST http://127.0.0.1:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/post-1"],"sites":["pingomatic"],"max_attempts":3}'

curl -X POST http://127.0.0.1:5000/api/jobs/<job_id>/run
```

Reports:

```text
GET /api/jobs/<job_id>/report.json
GET /api/jobs/<job_id>/report.md
```

Generated report files and screenshots are written under `reports/`.

## Browser Engine

Browser automation is isolated under `engine/browser_agent/`. The local runner always uses browser-use with a local Chromium profile, real browser-style request headers, and low-volume pacing. It does not use stealth scripts, fingerprint masking, random mouse movement, or fake human activity:

```text
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_NAVIGATION_TIMEOUT_MS=30000
PLAYWRIGHT_ACTION_TIMEOUT_MS=10000
PLAYWRIGHT_SLOW_MO_MS=0
AGENTIC_MIN_ACTION_DELAY_SECONDS=0.6
AGENTIC_MAX_ACTION_DELAY_SECONDS=2.0
AGENTIC_PRE_ATTEMPT_DELAY_SECONDS=1.0
AGENTIC_MAX_STEPS=80
```

Individual entries in `config/sites.yaml` may set `browser_profile_enabled: true` to reuse an approved profile and `pre_attempt_delay_seconds` to wait longer before opening that service.

## Cleanup

```bash
flask --app app:create_app cleanup --days 7
```
