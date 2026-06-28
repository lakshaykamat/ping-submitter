# Ping Submission Automation

## Summary

Ping Submission Automation is a low-volume Flask application for creating URL submission jobs, running those jobs through a sequential worker, and preserving evidence for each attempt. The web app persists jobs in SQLite; a separate worker process polls runnable jobs and delegates browser automation to reusable packages.

The product is built for visibility. Every attempt should end with clear evidence: success, failure, skipped, or CAPTCHA failure.

## High-Level Design

```text
+-------------+       +----------------+
| Person      |       | Web Screen     |
| adds URLs   +------>| creates a job  |
+-------------+       +-------+--------+
                              |
                              v
                      +----------------+
                      | Saved Job List |
                      | work + history |
                      +-------+--------+
                              ^
                              |
                      +-------+--------+
                      | Job Runner     |
                      | picks one job  |
                      | at a time      |
                      +-------+--------+
                              |
                              v
                      +----------------+
                      | Browser        |
                      | visits target  |
                      | websites       |
                      +-------+--------+
                              |
                              v
                      +----------------+
                      | Results        |
                      | status, reason,|
                      | screenshots,   |
                      | reports        |
                      +----------------+
```

The dashboard and JSON API create jobs and expose status, events, and reports. They do not run automation inside web requests. Execution is owned by a plain Python sequential worker that picks the oldest runnable job from SQLite and processes its attempts one at a time.

Application-specific state lives under `app/`: routes, SQLAlchemy models, site loading, profile management, event recording, and report generation. Reusable automation logic lives under `packages/` and intentionally does not import Flask, SQLAlchemy, workers, or app services.

`config/sites.yaml` defines known targets. `app.services.sites.normalize_site_config()` normalizes all enabled sites to the agentic runner, preserves each site's `captcha_policy`, enables browser profile reuse by default, and allows per-site pre-attempt delays.

The system is intentionally conservative. If the agent reaches a step it should not complete, such as login, payment, account creation, or email verification, it does not ask for a human checkpoint. It skips or fails the attempt with a clear reason.

## Low-Level Design

```text
+----------------+
| User enters    |
| URLs and sites |
+-------+--------+
        |
        v
+----------------+
| System checks  |
| the request    |
+-------+--------+
        |
        v
+----------------+
| Job is saved   |
| for later work |
+-------+--------+
        |
        v
+----------------+
| Page shows the |
| job as queued  |
+-------+--------+
        |
        v
+----------------+
| Runner picks   |
| the next job   |
+-------+--------+
        |
        v
+----------------+
| Browser opens  |
| each selected  |
| website        |
+-------+--------+
        |
        v
+----------------+
| Browser tries  |
| to submit the  |
| URL safely     |
+-------+--------+
        |
        v
+----------------+
| Site accepts,  |
| is blocked     |
| needs CAPTCHA  |
+-------+--------+
        |
        v
+----------------+
| Save status,   |
| reason, and    |
| screenshots    |
+-------+--------+
        |
        v
+----------------+
| More websites  |
| or URLs left?  |
+---+--------+---+
    | yes    | no
    v        v
+------+  +----------------+
| Next |  | Final report   |
| try  |  | is created     |
+------+  +----------------+
```

Job creation is handled by `app.services.jobs.create_submission_job()`. It validates URL syntax, resolves selected site IDs from `config/sites.yaml`, stores a `SubmissionJob`, expands each URL/site pair into a `SubmissionAttempt`, and records creation events.

Worker execution starts in `worker.tasks.SequentialWorker`. `run_once()` selects the oldest job whose status is `queued` or `running`, then calls `worker.execution.AutomationRunner.run_job()`. `run_job()` marks the job running, executes queued/running attempts in database order, then finishes the job and writes a report. The current implementation does not schedule retries even though `max_attempts`, `retry_count`, and retry status constants exist.

Each attempt uses the agentic path in `AutomationRunner.run_agentic_attempt()`:

1. Mark the attempt running and record `agent_started`.
2. Apply the configured pre-attempt delay and record `polite_delay` when nonzero.
3. Create or reuse a browser profile when `browser_profile_enabled` is true.
4. Load up to three approved site-memory strategies for the same site.
5. Build a browser-use task with redacted attempt context, target URL variants, action constraints, CAPTCHA handling instructions, and unsupported-step guardrails.
6. Run local browser-use with `ChatOpenAI`, `use_vision=True`, one action per step, and `AGENTIC_MAX_STEPS`.
7. Copy browser-use history screenshots into `ARTIFACT_DIR/<job_id>/<attempt_id>/` and record `artifact_saved` events for copied files.
8. Parse the agent's compact JSON into `AgentResult` and map it to a terminal attempt status.

Result mapping is centralized in `AutomationRunner.apply_agent_result()`:

- `success` records approved site memory when a strategy summary is present and marks the attempt `success`.
- `login_required`, `restricted_checkpoint`, and `skipped` are treated as skipped attempts with a recorded reason.
- CAPTCHA statuses are mapped to `failed` when a site is not configured for CAPTCHA solving or when the configured solver cannot resolve the challenge.
- Known failure statuses are persisted directly; unknown statuses become `agent_uncertain`.

Reports are generated by `app.services.reports`. The system writes JSON and Markdown files under `REPORT_DIR`, stores the same content in the `job_reports` table, restores missing report files from the database when possible, and exposes report data through the dashboard and API.

## Core Behavior

- Jobs contain one attempt per URL/site pair.
- The web app creates and displays jobs; the worker executes jobs.
- Each target service currently uses the browser-use agentic runner.
- Agentic runs receive only the selected site, submitted URL, allowed context, approved profile path, and approved site memory.
- Browser profiles are enabled by default per normalized site config and can be reset from the dashboard.
- Successful agent strategies can be stored as site memory and reused after sensitive values are redacted.
- A job is marked `completed` only when every attempt succeeds; otherwise it is marked `failed`.
- Retry metadata exists in the model and status constants, but the active worker path currently executes each attempt once.

## Crawler Reliability

The browser automation package applies browser-session controls that improve stability and reduce friction with target services. The active implementation uses local browser-use with Playwright/Chromium, fixed realistic browser defaults, persisted profiles where configured, request header overrides, a Playwright stealth init script, and configurable delays.

Key settings include:

- Configurable pre-attempt and between-action delays.
- Stable viewport, request headers, user agent, navigation timeout, and action timeout settings.
- Persisted browser profiles by default, unless a site disables profile reuse.
- Agent instructions for consent, login, CAPTCHA, rate-limit, and restricted-checkpoint outcomes.
- Runtime restricted-checkpoint detection for hard access blocks that should be reported instead of retried.
- Clear reporting when a target service blocks, rejects, or cannot complete an attempt.

These measures are applied for reliability, observability, and respectful low-volume operation. The system does not rotate identities to avoid limits or perform high-volume submissions. CAPTCHA solving is enabled by default through a local OhMyCaptcha service, and sites can opt out with `captcha_policy: none`.

## Checkpoints

CAPTCHA solving is policy-controlled:

- Sites default to `captcha_policy: solve` and use the configured OhMyCaptcha-compatible service.
- Sites with `captcha_policy: none` skip automatic solver use.
- The default local service URL is `http://127.0.0.1:8000` through `OHMYCAPTCHA_BASE_URL`.
- `OHMYCAPTCHA_CLIENT_KEY` is read from `.env` when the solver service requires a client key.
- Supported CAPTCHA widgets are submitted to OhMyCaptcha as reCAPTCHA v2, hCaptcha, or Cloudflare Turnstile tasks.
- Solver tokens are injected into the browser page so the agent can continue the visible submission flow.
- If solving fails or the CAPTCHA remains unresolved, the attempt is marked failed with evidence.
- There is no human CAPTCHA checkpoint in the agent flow.

Hard anti-abuse checkpoints are separate from CAPTCHA solving. Access denied pages, rate-limit pages, and Cloudflare challenge pages without a supported widget are reported as `restricted_checkpoint` with evidence. The system does not bypass those checkpoints.

Sensitive or unsupported actions are not handed to a human checkpoint. Payment, signup, account changes, deletion, subscription, email/OTP verification, and uncertain irreversible actions cause the agent to skip or fail the attempt with evidence.

## Reporting

Each finished run writes screenshots where available and JSON/Markdown reports under `reports/`. Reports include runner mode, CAPTCHA policy, attempt status, retry count, checkpoint count, latest agent confidence, final evidence, artifact paths, attempts, events, timestamps, and duration.

## Boundaries

- No high-volume automation.
- CAPTCHA solving is available only through the configured local OhMyCaptcha-compatible service and can be disabled per site with `captcha_policy: none`.
- No email or OTP automation.
- Uses realistic browser defaults, persisted profiles, request headers, stealth initialization, pacing, and optional OhMyCaptcha solving to reduce avoidable browser friction, but does not automate email/OTP or perform high-volume submissions.
- No unrestricted browsing.
- Prefer a clear skip or failure over an unverified success.
