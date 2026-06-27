# Agentic Browser Runner Two-Phase Plan

## Objective

Build a browser agent that can submit URLs across different websites by reasoning over each page state instead of depending only on static selectors. Use `browser-use` for AI-driven browser automation, keep the existing Playwright runner for known stable flows, and add policy-driven handling for CAPTCHA, login, and other restricted steps.

## Current Baseline

The MVP currently has:

- Flask dashboard and API for creating and running jobs.
- SQLite-backed jobs, attempts, events, CAPTCHA challenges, and reports.
- Deterministic Playwright automation through `automation/runner.py`.
- Static site metadata in `config/sites.yaml`.
- Site adapters in `automation/adapters.py`.
- Heuristic form detection in `automation/forms.py`.
- Manual CAPTCHA pause/resume flow.
- JSONL logs and JSON/Markdown reports.

The main limitation is that the runner expects forms to be discoverable through configured selectors or simple URL input heuristics. It cannot reliably reason through different websites, multi-step forms, login gates, changing DOM structures, or ambiguous success states.

## Target Architecture

```text
+------------------+       +------------------+       +----------------------+
|                  |       |                  |       |                      |
| Operator / API   +------>+ Submission Job   +------>+ Runner Orchestrator  |
|                  |       |                  |       |                      |
+------------------+       +------------------+       +----------+-----------+
                                                               |
                         +-------------------------------------+----------------------------------+
                         |                                                                        |
                         v                                                                        v
              +----------+-----------+                                                +-----------+----------+
              |                      |                                                |                      |
              | Deterministic Runner |                                                | Browser-Use Agent    |
              | Playwright Adapters  |                                                | AI Action Loop       |
              |                      |                                                |                      |
              +----------+-----------+                                                +-----------+----------+
                         |                                                                        |
                         +-------------------------------------+----------------------------------+
                                                               |
                                                               v
                                                    +----------+-----------+
                                                    |                      |
                                                    | Events, Checkpoints, |
                                                    | Reports, Screenshots |
                                                    |                      |
                                                    +----------------------+
```

The orchestrator chooses a runner per attempt:

- `deterministic`: use existing site adapter when the site is known and stable.
- `agentic`: use `browser-use` when the site is unknown, selector detection fails, or the site is configured for AI automation.
- `captcha_provider`: use an existing configured CAPTCHA-solving provider only when the site is explicitly authorized for provider handling.
- `restricted_checkpoint`: pause, skip, or fail when login, payment, unsupported verification, or another policy-sensitive action appears.

## Phase 1: Agentic Form Submission MVP

### Goal

Add a controlled `browser-use` runner that can navigate varied public submission forms, fill allowed job data, submit the form, and return structured success/failure/checkpoint results.

### Scope

- Add `browser-use` and LLM configuration.
- Add an agentic runner abstraction beside the current deterministic runner.
- Keep the existing Playwright adapter path working.
- Add per-site runner mode configuration.
- Add structured agent result parsing.
- Add event logging for agent observations, actions, checkpoints, and confidence.
- Reuse the existing manual CAPTCHA challenge flow as the default fallback.
- Add a CAPTCHA provider adapter that can call an existing configured service instead of implementing a solver.
- Add natural pacing controls so actions do not fire instantly or randomly.
- Add smoke tests with fake agent clients so tests do not call an LLM.

### Non-Goals

- No custom CAPTCHA solver implementation.
- No unconditional CAPTCHA solving; provider mode must be enabled per site and treated as an explicit site policy.
- No email verification or inbox access.
- No credential vault beyond environment-backed LLM/API settings.
- No high-volume production scaling.
- No unrestricted web browsing.

### Implementation Tasks

1. Add dependencies and configuration.
   - Add `browser-use` to `requirements.txt`.
   - Add config keys for `AGENTIC_BROWSER_ENABLED`, `AGENTIC_LLM_MODEL`, `AGENTIC_MAX_STEPS`, `AGENTIC_MIN_ACTION_DELAY_SECONDS`, `AGENTIC_MAX_ACTION_DELAY_SECONDS`, `AGENTIC_ALLOWED_DOMAINS`, `CAPTCHA_PROVIDER_ENABLED`, `CAPTCHA_PROVIDER_NAME`, and `CAPTCHA_PROVIDER_API_KEY`.
   - Fail startup clearly when agentic mode is enabled but required LLM credentials are missing.
   - Fail provider mode clearly when CAPTCHA provider config is incomplete.

2. Extend site configuration.
   - Add `runner_mode` to each entry in `config/sites.yaml`.
   - Supported values: `deterministic`, `agentic`, and `deterministic_then_agentic`.
   - Add `captcha_policy` to each site.
   - Supported values: `manual`, `provider`, `skip`, and `fail`.
   - Keep `pingomatic` as `deterministic`.
   - Keep all sites on `manual` or `fail` unless the operator explicitly authorizes provider handling for that site.
   - Use `deterministic_then_agentic` for sites where heuristics are fragile.

3. Add agent result types.
   - Add statuses for `captcha_required`, `captcha_solving`, `captcha_solved`, `captcha_failed`, `login_required`, `operator_review_required`, `restricted_checkpoint`, and `agent_uncertain`.
   - Add event types for `agent_started`, `agent_action`, `agent_checkpoint`, `agent_success`, and `agent_failed`.
   - Add event types for `captcha_provider_requested`, `captcha_provider_solved`, and `captcha_provider_failed`.
   - Store structured evidence in event context: current URL, visible confirmation text, screenshot path, confidence, action summary, provider name, and provider request status.

4. Add `automation/agentic_runner.py`.
   - Build a `BrowserUseAgentRunner` class with a single method: `submit_url(site, submitted_url, attempt_context)`.
   - The method should construct a task prompt that states the objective, allowed data, allowed domains, stop conditions, and checkpoint rules.
   - The method should return a structured result object rather than free-form text.
   - The agent should classify page state before acting: landing page, consent screen, submission form, multi-step form, success confirmation, site error, CAPTCHA, login gate, restricted checkpoint, or uncertain state.
   - The agent should fill form fields by semantic intent using visible labels, placeholders, ARIA names, input types, nearby text, and DOM context instead of relying only on static selectors.
   - The agent should use bounded pacing between actions, waits after navigation, and no random clicks outside the chosen action plan.
   - The agent must return `captcha_required` when CAPTCHA is visible and the site policy is `manual`.
   - The agent must call the CAPTCHA provider adapter when CAPTCHA is visible and the site policy is `provider`.
   - The agent must return `captcha_failed` when provider solving fails, times out, or returns an unusable answer.
   - The agent must stop and return `login_required` when credentials are needed and none are configured.
   - The agent must return `restricted_checkpoint` when email or OTP verification, payment, account creation, or another unsupported flow is required.

5. Add `automation/captcha_provider.py`.
   - Create a `CaptchaProviderClient` interface that wraps an existing external provider or official SDK.
   - The interface should accept only the challenge data needed by the provider: site key, page URL, challenge type, and optional screenshot when supported.
   - The interface should return `solved`, `failed`, or `timeout` with a provider request ID and redacted metadata.
   - Store provider credentials only in environment variables or a secret provider.
   - Do not log provider API keys, raw tokens, or any sensitive challenge payload.
   - Add a fake provider implementation for tests.

6. Add runner orchestration.
   - Modify `AutomationRunner.submit_url` so it can delegate to deterministic or agentic execution based on site config and adapter outcome.
   - In `deterministic_then_agentic` mode, retry with the browser-use runner only after deterministic form detection or success validation fails.
   - Preserve existing retry behavior for network/timeouts.
   - Route CAPTCHA through the configured site policy before marking the attempt complete or failed.

7. Add operator checkpoints.
   - Reuse the CAPTCHA page for CAPTCHA-required checkpoints.
   - Add generic checkpoint events for login and restricted flows.
   - The job detail page should show the checkpoint type and next action.
   - Phase 1 skips or fails email/OTP verification flows instead of trying to solve them.

8. Add tests.
   - Unit test that deterministic sites still use the existing runner.
   - Unit test that `deterministic_then_agentic` falls back to the fake agent after missing form detection.
   - Unit test that fake agent success completes an attempt and records evidence.
   - Unit test that fake agent CAPTCHA returns `captcha_required`.
   - Unit test that `captcha_policy: provider` calls the fake CAPTCHA provider.
   - Unit test that provider timeout records `captcha_failed` and does not retry endlessly.
   - Unit test that fake agent email/OTP verification returns `restricted_checkpoint`.
   - Unit test that fake agent actions include bounded delays through an injected sleeper so tests stay deterministic.

### Phase 1 Acceptance Criteria

- Existing tests still pass.
- A known deterministic site can still complete without the LLM agent.
- A fake unknown-site flow can complete through the agentic runner in tests.
- CAPTCHA follows site policy: manual checkpoint, provider solving, skip, or fail.
- Provider solving uses an existing service through an adapter and never logs secrets.
- Reports include whether the deterministic or agentic runner handled each attempt.
- The system logs enough evidence to explain why the agent marked an attempt successful or failed.

## Phase 2: Memory, Review, and Production Hardening

### Goal

Extend the agentic runner into a reliable low-volume browser automation system that can handle persisted browser state, safer credentials, site-specific learning, stronger operator controls, and richer debugging.

### Scope

- Add browser profiles/session persistence per site/account.
- Add secure credential and secret handling.
- Add proxy/profile configuration for allowed sites where the operator owns or is authorized to automate the account.
- Add site memory for successful agent strategies and known checkpoints.
- Add operator review and approval for sensitive actions.
- Add richer replay/debug artifacts.
- Add live audit scripts for agentic flows.

### Non-Goals

- No custom CAPTCHA solver implementation.
- No stealth or evasion layer designed to hide automation from external sites.
- No email or OTP verification automation.
- No spam or bulk abuse workflow.
- No automatic account creation unless the operator explicitly adds allowed credentials and policy approval.
- No silent submission where the system cannot produce evidence.

### Implementation Tasks

1. Add persisted browser profiles.
   - Add per-site/account browser profile directories.
   - Let approved jobs reuse cookies/session state.
   - Add cleanup controls so profiles can be reset from the dashboard.

2. Add secure data handling.
   - Move credentials, LLM keys, and proxy credentials to environment variables or a secret provider.
   - Pass secrets to the agent only through browser-use sensitive-data mechanisms or tool calls that redact logs.
   - Never write secrets into event context, reports, screenshots, or prompts stored on disk.

3. Add site memory.
   - Store successful strategy summaries per site: required fields, common buttons, known success evidence, checkpoint patterns, and failure reasons.
   - Feed concise memory back into future agent tasks.
   - Require operator approval before promoting new memory from a failed or uncertain run.

4. Add operator review controls.
   - Require manual approval before submitting forms that look like payment, signup, account modification, or irreversible actions.
   - Add a dashboard state showing current page screenshot, agent summary, proposed next action, and approve/deny buttons.

5. Add observability and replay.
   - Save screenshots at start, before submit, after submit, and on every checkpoint/failure.
   - Save compact action traces with redacted inputs.
   - Add a report section for runner mode, agent confidence, checkpoint count, and final evidence.

6. Add live audit flow.
   - Add a low-volume script for one deterministic site and one agentic test site.
   - Run with visible browser mode.
   - Exit successfully only when reports contain accepted evidence and no unresolved checkpoints.

### Phase 2 Acceptance Criteria

- Persisted browser profiles can resume a logged-in session for an approved test site.
- Operator review blocks sensitive actions before the agent clicks submit.
- Site memory improves repeated runs without giving the agent unrestricted authority.
- Reports and logs explain each agentic decision path with screenshots and redacted action traces.
- CAPTCHA handling remains auditable and policy-driven: manual, provider, skip, or fail.

## Safety Rules

- Restrict each agent run to the selected site and its expected domains.
- Give the agent only the job data and secrets needed for the current attempt.
- Treat CAPTCHA according to the configured site policy: manual, provider, skip, or fail.
- Treat login, email/OTP verification, payment, and account changes as checkpoints.
- Skip or fail email/OTP verification flows; they are out of scope.
- Redact all sensitive values from prompts, logs, reports, screenshots where possible, and event context.
- Prefer a failed or paused attempt over an unverified success.
- Keep volume low and operator-visible.

## CAPTCHA Policy

The agent must detect CAPTCHA and route it through the selected site's `captcha_policy`.

- `manual`: create a CAPTCHA challenge and wait for the operator.
- `provider`: call an existing CAPTCHA-solving provider through `CaptchaProviderClient`.
- `skip`: mark the attempt skipped with checkpoint evidence.
- `fail`: mark the attempt failed with checkpoint evidence.

Provider mode is disabled by default and must be configured per site. The product does not implement a CAPTCHA solver; it only integrates with an existing provider selected by the operator. Provider credentials must be redacted from logs, reports, prompts, screenshots, and event context.

## Browser-Use Notes

The plan assumes the open-source `browser-use` package is used for the local agentic browser runner. Relevant capabilities to validate during implementation include:

- Agent task execution with an LLM-backed browser action loop.
- Browser/session configuration for controlled execution.
- Tool/controller extension points for custom checkpoint and reporting tools.
- Structured output so the runner can persist machine-readable results.
- Sensitive data handling and domain restrictions for safer production use.
- Retry, timeout, and action-step limits.

If production proxy or managed-browser behavior is required, evaluate Browser Use Cloud or another approved managed browser provider separately. That evaluation should not change the product rule that CAPTCHA is not bypassed silently.
