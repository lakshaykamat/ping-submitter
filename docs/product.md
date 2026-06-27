# Ping Submission Automation

## Summary

Ping Submission Automation is a low-volume automation tool for submitting URLs to external ping submission services. It uses an agentic browser-use runner for every target service.

The product is built for visibility. Every attempt should end with clear evidence: success, failure, skipped, or CAPTCHA failure.

## High-Level Design

```text
+------------------+
| User             |
| chooses URLs and |
| target services  |
+--------+---------+
         |
         v
+------------------+        +----------------------+
| Web Dashboard    |------->| Job Record           |
| shows progress,  |        | URLs, services,      |
| reports, results |        | status, evidence     |
+--------+---------+        +----------+-----------+
         |                             |
         v                             v
+--------------------------------------------------+
| Automation Coordinator                           |
| Starts each browser-use attempt and records      |
| success, failure, skip, CAPTCHA, and reasons.    |
+----------------------+---------------------------+
                       |
        +--------------+--------------+
        |                             |
        v                             v
+------------------+        +----------------------+
| Browser Session  |        | Automated Decisions  |
| opens the target |        | detect CAPTCHA,      |
| service and      |        | continue, skip, or   |
| tries to submit  |        | fail safely          |
+--------+---------+        +----------+-----------+
         |                             |
         +--------------+--------------+
                        |
                        v
              +------------------+
              | External Service |
              | accepts, rejects,|
              | blocks, or shows |
              | CAPTCHA          |
              +--------+---------+
                       |
                       v
              +------------------+
              | Evidence Output  |
              | screenshots and  |
              | JSON/MD report   |
              +------------------+
```

The user starts from the dashboard, submits one or more URLs, and watches each target service move through a clear state. The browser-use agent takes browser actions, fails when CAPTCHA appears, and records evidence for every outcome.

The system is intentionally conservative. If the agent reaches a step it should not complete, such as login, payment, account creation, or email verification, it does not ask for a human checkpoint. It skips or fails the attempt with a clear reason.

## Low-Level Design

```text
+---------------------+
| Job Created         |
| URLs x services     |
+----------+----------+
           |
           v
+---------------------+
| Pick Next Attempt   |
| queued or retryable |
+----------+----------+
           |
           v
+---------------------+
| Load Service Rules  |
| browser-use target  |
| and CAPTCHA policy  |
+----------+----------+
           |
           v
           |
           v
+----------------+
| Agentic Path   |
| observe page,  |
| choose action, |
| use browser,   |
| repeat until   |
| done or final  |
+-------+--------+
        |
        v
              +------------------+
              | Check Page State |
              | success, error,  |
              | CAPTCHA, blocked,|
              | unsupported step |
              +---+----------+---+
                  |          |
       +----------+          +-------------+
       |                                   |
       v                                   v
+-------------+                    +----------------+
| Final Result|                    | CAPTCHA Seen   |
| success,    |                    | fail attempt   |
| retry, skip,|                    | with reason    |
| or failure  |                    |                |
+------+------+                    +-------+--------+
       |                                   |
       +----------------+--------+
                        |
                        v
              +------------------+
              | Save Evidence   |
              | status, reason, |
              | screenshots,    |
              | report files    |
              +--------+---------+
                       |
                       v
              +------------------+
              | More Attempts?  |
              +---+----------+---+
                  |          |
                 yes         no
                  |          |
                  v          v
        +---------+--+   +----------+
        | Next Attempt|  | Job Done |
        +-------------+  +----------+
```

The agentic path works as a loop: inspect the current page, decide the next safe browser action, take that action, then check whether the task is complete. If CAPTCHA appears, the attempt fails with a clear reason because CAPTCHA solving is not implemented. If the page requires login, payment, account creation, email verification, or another unsupported step, the agent skips or fails the attempt with a clear reason.

## Core Behavior

- Jobs contain one attempt per URL/site pair.
- Each target service uses the browser-use agentic runner.
- Agentic runs receive only the selected site, submitted URL, allowed context, approved profile path, and approved site memory.
- Browser profiles are optional per site and can be reset from the dashboard.
- Successful agent strategies can be stored as site memory and reused after sensitive values are redacted.

## Crawler Reliability

The crawler may use browser-session hardening that improves stability and reduces unnecessary load on target services:

- Configurable action delays and retry backoff.
- Stable viewport, navigation timeout, and action timeout settings.
- Persisted browser profiles when a site is explicitly configured for profile reuse.
- Consent, login, CAPTCHA, rate-limit, and restricted-checkpoint detection.
- Clear reporting when a target service blocks, rejects, or cannot complete an attempt.

These controls are for reliability, observability, and respectful low-volume operation. They are not a stealth layer and must not spoof browser fingerprints, rotate identities to avoid limits, bypass anti-bot checks, solve CAPTCHA, or hide automation from services that restrict it.

## Checkpoints

CAPTCHA solving is not implemented:

- If a CAPTCHA appears, the attempt is marked failed.
- The failure reason says CAPTCHA solving is not implemented and is reserved for future work.
- The system does not call a CAPTCHA provider or ask for manual CAPTCHA entry.
- There is no human CAPTCHA checkpoint in the agent flow.

Sensitive or unsupported actions are not handed to a human checkpoint. Payment, signup, account changes, deletion, subscription, email/OTP verification, and uncertain irreversible actions cause the agent to skip or fail the attempt with evidence.

## Reporting

Each finished run writes screenshots where useful and JSON/Markdown reports under `reports/`. Reports include runner mode, CAPTCHA policy, attempt status, retry count, checkpoint count, latest agent confidence, final evidence, and artifact paths.

## Boundaries

- No high-volume automation.
- No CAPTCHA solver or CAPTCHA provider integration.
- No email or OTP automation.
- No stealth or evasion layer, including Phantomwright-style fingerprint masking, user-agent spoofing, browser-property spoofing, or bot-detection bypass.
- No unrestricted browsing.
- Prefer a clear skip or failure over an unverified success.
