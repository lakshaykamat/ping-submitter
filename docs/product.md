# Ping Submission Automation MVP

## Product Summary

Ping Submission Automation MVP is a small operator-facing tool for submitting one or more URLs to external ping submission services, watching the submission process, handling CAPTCHA interruptions manually, and downloading a clear result report.

The product is built for low-volume, transparent submission workflows where the operator needs visibility into what happened for every URL and every selected site.

## Product Goals

- Let a user submit URLs to supported external ping services from one place.
- Show job progress clearly while submissions are running.
- Keep every attempt traceable through status, activity logs, and reports.
- Handle dynamic third-party page behavior safely.
- Pause for manual CAPTCHA handling instead of bypassing CAPTCHA systems.
- Provide a visible live smoke-test flow so an operator can watch real browser activity.

## Non-Goals

- It does not guarantee indexing, crawling, ranking, or search-engine acceptance.
- It does not bypass CAPTCHA or anti-bot protections.
- It is not designed for high-volume automated submissions.
- It is not a distributed production queue system.
- It does not verify downstream search-engine processing after a ping site accepts a request.

## Users

- Operator: creates jobs, watches status, handles CAPTCHA if needed, and downloads reports.
- Reviewer: checks logs and reports to understand whether each submission succeeded or failed.

## Core Features

- URL submission job creation.
- Multiple URL and site combinations per job.
- Real external ping-site browser automation.
- Visible browser mode for live verification.
- Job detail page with status, attempts, activity, and reports.
- Manual CAPTCHA workflow with screenshot and operator action.
- Retry handling for temporary navigation or network failures.
- Structured activity timeline.
- JSON and Markdown result reports.
- Cleanup support for old generated artifacts.
- Live smoke-test flow for immediate real-site submission.

## Supported Site Strategy

The MVP focuses on real ping submission tools and keeps questionable or unsuitable targets disabled.

Enabled sites are treated as external systems that may change without notice. The product therefore records clear success, failure, retry, and CAPTCHA states instead of assuming every external site remains stable.

Guestbook-style pages and unrelated targets are disabled by default because they are not legitimate ping submission tools.

## Success Criteria

A submission is considered successful when:

- The job finishes as completed.
- Every selected URL/site attempt finishes as successful.
- The final report shows all attempts succeeded.
- The external site response contains a known success confirmation.
- No configured site-side error message is detected.

This proves the external ping site accepted the submission flow. It does not prove that any search engine later processed or indexed the submitted URL.

## Outcome

The completed MVP provides an end-to-end flow:

- Create a submission job.
- Run it against a real external ping service.
- Watch the local job page update.
- Watch the external browser submit the request.
- Pause and handle CAPTCHA manually if needed.
- Receive a final success or failure result.
- Download a report that explains what happened.

## High-Level Architecture

```text
+------------------+        +------------------+        +----------------------+
|                  |        |                  |        |                      |
|     Operator     +------->+   Web Dashboard  +------->+   Submission Job     |
|                  |        |                  |        |                      |
+------------------+        +---------+--------+        +----------+-----------+
                                      |                            |
                                      |                            v
                                      |                 +----------+-----------+
                                      |                 |                      |
                                      |                 |  Automation Runner   |
                                      |                 |                      |
                                      |                 +----------+-----------+
                                      |                            |
                                      |                            v
                                      |                 +----------+-----------+
                                      |                 |                      |
                                      +<----------------+ External Ping Sites  |
                                      |                 |                      |
                                      |                 +----------+-----------+
                                      |                            |
                                      v                            v
                           +----------+-----------+     +----------+-----------+
                           |                      |     |                      |
                           | Logs and Activity    |     | Reports and Results  |
                           |                      |     |                      |
                           +----------------------+     +----------------------+
```

## Product Flow

```text
+-------------+
| Start Job   |
+------+------+
       |
       v
+------+------+
| Validate    |
| URLs/Sites  |
+------+------+
       |
       v
+------+------+
| Create Job  |
| + Attempts  |
+------+------+
       |
       v
+------+------+
| Open Site   |
| in Browser  |
+------+------+
       |
       v
+------+------+
| CAPTCHA?    |
+---+-----+---+
    |     |
  Yes     No
    |     |
    v     v
+---+--+  +----------------+
| Pause |  | Fill Form      |
| Job   |  | and Submit     |
+---+--+  +--------+-------+
    |              |
    v              v
+---+------+  +----+--------+
| Operator |  | Check Site  |
| Solves   |  | Response    |
+---+------+  +----+--------+
    |              |
    v              v
+---+--------------+---+
| Success, Failure,    |
| Retry, or Timeout    |
+-----------+----------+
            |
            v
+-----------+----------+
| Update Job, Logs,    |
| Activity, Report     |
+-----------+----------+
            |
            v
+-----------+----------+
| Final Result         |
+----------------------+
```

## CAPTCHA Handling

CAPTCHA is handled as an operator checkpoint.

When a CAPTCHA is detected, the product:

- Stops the affected attempt.
- Marks the job as waiting for CAPTCHA.
- Captures a screenshot for the operator.
- Shows a CAPTCHA action page in the dashboard.
- Waits for manual input.
- Continues only after the operator responds.
- Marks the attempt as timed out if no answer is provided in time.

The product intentionally does not automate CAPTCHA solving.

## Failure Handling

Failures are classified so the operator can understand what happened:

- Temporary failures may be retried.
- Site validation errors fail the attempt.
- Missing forms fail the attempt.
- CAPTCHA timeout fails the attempt.
- Unsupported or disabled sites are rejected before running.
- External page changes are surfaced as clear failure reasons.

## Reporting

Each job produces a report with:

- Job status.
- Submitted URLs.
- Selected sites.
- Total attempts.
- Success, failure, skipped, and CAPTCHA counts.
- Per-attempt status.
- Failure reason when available.
- Retry count.
- Start and finish timing.
- Duration.

Reports are intended to answer one question quickly: what happened to every URL/site pair?

## Live Verification

The product includes a live smoke-test flow for real external submission.

The flow:

- Uses a dummy or user-provided URL.
- Starts a visible browser session.
- Creates and runs a job.
- Opens the local job page.
- Shows the external ping site interaction.
- Prints progress events.
- Exits successfully only when the final report confirms full success.

This is useful for proving that the current external-site flow still works.

## Current MVP State

The core product flow is implemented and verified:

- Jobs can be created.
- Real external ping submission can run.
- Ping-O-Matic live submission succeeds with a dummy URL.
- Job activity is visible.
- Reports are generated.
- CAPTCHA states are detected and routed to manual handling.
- Automated tests pass.

## Product Principles

- Be transparent about every attempt.
- Prefer clear failure over silent uncertainty.
- Keep third-party interaction low-volume and visible.
- Do not bypass external protections.
- Make reports useful enough to debug a failed submission without rerunning immediately.

## Next Evolution: Agentic Browser Runner

The current MVP uses deterministic Playwright automation: configured site adapters, selector heuristics, text extraction, and explicit success/error patterns. That approach works for stable ping submission forms, but it is not enough for broader website automation because every site can present different form layouts, multi-step flows, dynamic widgets, CAPTCHA, or login gates.

The next version should add a browser agent that can inspect the active page, reason about the visible goal, and choose browser actions based on the website state. The recommended implementation is to integrate `browser-use` as an AI browser automation layer while keeping the existing Playwright runner for known stable sites.

### Why a Browser Agent Is Needed

- Forms differ across sites, including labels, hidden fields, multi-step pages, and non-standard submit controls.
- Some sites require account login, consent dialogs, or multi-step confirmation before a submission is accepted.
- CAPTCHA can appear before, during, or after form submission, and needs an explicit handling policy per site.
- Success can be represented by page text, redirects, toast messages, or account dashboard state.
- Pure selector extraction cannot reliably decide which action to take when the page changes.

### Target Agent Behavior

The browser agent should receive a clear task such as: submit this URL to this site, stop when the site confirms acceptance, and follow the configured CAPTCHA policy if a challenge appears.

For each attempt, the agent should:

- Open the target site in a controlled browser session.
- Observe the current page state through DOM, accessibility tree, screenshots, and visible text.
- Decide the next action using the goal, site metadata, and attempt context.
- Fill only allowed data fields from the job payload or secure credential store.
- Click, type, wait, navigate, and retry with natural pacing and bounded delays so the flow does not hammer a site or behave like an instant script.
- Detect checkpoints such as CAPTCHA, login, consent, or suspicious blocking.
- Use an existing CAPTCHA-solving provider only when the selected site is explicitly configured for provider-based CAPTCHA handling and the operator has confirmed the use is authorized.
- Return a structured result with status, confidence, evidence, screenshots, and next required operator action.

### Boundaries

The product should not silently bypass CAPTCHA or anti-abuse systems. CAPTCHA handling is policy-driven: by default the agent records the checkpoint and pauses, skips, or fails with evidence. If a site is explicitly marked as authorized for provider-based CAPTCHA handling, the system may call an existing CAPTCHA-solving service through a narrow provider adapter. The product does not implement its own solver.

The product should not give the agent unrestricted browsing access. Each job should restrict domains, secrets, file access, and tools to the minimum required for the selected site.

Email verification is out of scope. If a site requires email or OTP verification, the agent records the checkpoint and skips or fails the attempt based on job policy.

### Two-Phase Delivery

The recommended delivery plan is documented in `docs/browser_agent_two_phase_plan.md`.

Phase 1 adds the agentic browser runner behind a controlled feature flag and uses it for unknown or changing form flows while preserving existing deterministic adapters.

Phase 2 adds site memory, profile/proxy configuration, stronger operator review, replay artifacts, and production hardening.
