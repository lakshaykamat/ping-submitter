# Ping Submission Automation MVP

Flask MVP for creating ping submission jobs, running Playwright automation, handling CAPTCHA through a manual operator page, writing structured activity logs, and downloading JSON or Markdown reports.

The app is intentionally small: Flask, SQLite, SQLAlchemy, Playwright, and pytest. Jobs run through a plain Python worker entrypoint, without Redis or a queue broker.

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

Create a job from the dashboard, then click **Run now** on the job detail page. The page action starts a local background thread and writes progress to the terminal, the job activity panel, and `logs/<job_id>.jsonl`.

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

Generated files are written to `logs/` and `reports/`.

## Test

```bash
pytest -v
```

For a visible live smoke test against a real external ping site:

```bash
./scripts/live_flow_test.sh
```

This creates a job with a random dummy `example.com` URL, starts Flask with
`PLAYWRIGHT_HEADLESS=false`, opens the local job page in your browser, and shows the external
ping site in a visible Playwright browser. If port 5000 already has a server, the command starts
its own visible-browser server on the next open port. It exits successfully only when the report
says the job is `completed` and every attempt is `success`.

To submit a specific URL:

```bash
./scripts/live_flow_test.sh https://example.com/my-test-page
```

## Cleanup

```bash
flask --app app:create_app cleanup --days 7
```
