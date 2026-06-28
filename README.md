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

Run the worker in a separate terminal:

```bash
flask --app app:create_app worker
```

For a single pass, use:

```bash
python -m worker --once
```

## Run a Job

Create a job from the dashboard. The app redirects to the job detail page and leaves the job queued for the worker. The worker runs one job at a time, and the browser-use agent records progress in the database-backed activity panel.

API flow:

```bash
curl -X POST http://127.0.0.1:5000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/post-1"],"sites":["pingomatic"],"max_attempts":3}'

curl -X POST http://127.0.0.1:5000/api/jobs/<job_id>/run
```

The run endpoint confirms that the job exists and is queued for worker execution. It does not execute automation inside the web request.

Reports:

```text
GET /api/jobs/<job_id>/report.json
GET /api/jobs/<job_id>/report.md
```

Generated report files and screenshots are written under `reports/`.

## Browser Automation

Reusable browser automation lives under `packages/browser_automation/`. It has no Flask, SQLAlchemy, job, attempt, report, or worker dependencies. The worker uses that package to run browser-use with a local Chromium profile, real browser-style request headers, and low-volume pacing.

Reusable CAPTCHA helpers live under `packages/captcha_solver/`. App-specific CAPTCHA challenge rows and screenshot paths are handled by `app.services.captcha`.

The worker owns job execution: it loads site config, profiles, and memory from app services, calls the reusable browser automation package, then records events, attempt status, and reports.

To avoid detection and mimic natural human behavior, browser automation introduces:

- Random mouse movements and scrolling patterns.
- Variable typing speeds and pauses between actions.
- Realistic viewport sizes and window resizing.
- Stealth techniques (e.g., modifying navigator properties, WebGL fingerprints, and canvas rendering) where appropriate.
- Re‑use of persistent browser profiles (when `browser_profile_enabled: true` in `config/sites.yaml`) to maintain session cookies and trusted fingerprints.

Configuration defaults can be tuned via environment variables:

```text
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_NAVIGATION_TIMEOUT_MS=30000
PLAYWRIGHT_ACTION_TIMEOUT_MS=10000
PLAYWRIGHT_SLOW_MO_MS=0
AGENTIC_MIN_ACTION_DELAY_SECONDS=0.6
AGENTIC_MAX_ACTION_DELAY_SECONDS=2.0
AGENTIC_PRE_ATTEMPT_DELAY_SECONDS=1.0
AGENTIC_MAX_STEPS=80
CAPTCHA_POLICY_DEFAULT=solve
OHMYCAPTCHA_BASE_URL=http://127.0.0.1:8000
OHMYCAPTCHA_CLIENT_KEY=
OHMYCAPTCHA_REQUEST_TIMEOUT_SECONDS=30
OHMYCAPTCHA_POLL_INTERVAL_SECONDS=2
OHMYCAPTCHA_MAX_WAIT_SECONDS=120
```

CAPTCHA solving is enabled by default through `CAPTCHA_POLICY_DEFAULT=solve`.
When a supported reCAPTCHA, hCaptcha, or Cloudflare Turnstile widget appears,
the browser session creates an OhMyCaptcha task and injects the returned token
before the agent continues the visible submission flow. Individual entries in
`config/sites.yaml` may set `captcha_policy: none` to opt out,
`browser_profile_enabled: true` to reuse an approved profile, and
`pre_attempt_delay_seconds` to wait longer before opening that service.
Image CAPTCHA and classification tasks are exposed by the shared
`packages.captcha_solver` client for callers that already have the image data
and question prompt. OhMyCaptcha task names are package constants in
`packages.captcha_solver.types`, not environment settings. Hard
anti-abuse checkpoints such as access denied, rate limits, and Cloudflare
challenge pages are reported as `restricted_checkpoint` with evidence instead
of being bypassed.

## Cleanup

```bash
flask --app app:create_app cleanup --days 7
```
