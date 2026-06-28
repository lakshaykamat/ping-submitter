# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Flask application for running ping submission jobs through reusable browser automation packages.

- `app/` contains the Flask app factory, configuration, database models, routes, templates, and service modules.
- `app/services/` holds application workflows such as jobs, reports, events, profiles, files, statuses, and site config access.
- `packages/browser_automation/` contains reusable browser automation, prompt construction, runner logic, result parsing, and automation types.
- `packages/captcha_solver/` contains reusable CAPTCHA detection helpers.
- `worker/` contains background task entrypoints and app-specific job execution orchestration.
- `config/sites.yaml` defines supported submission targets.
- `tests/` contains pytest tests. Generated reports, screenshots, browser profiles, logs, `.env`, and `app.db` are local artifacts and should stay out of git.

## Build, Test, and Development Commands

Create and prepare a local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Run the app locally:

```bash
flask --app app:create_app run
```

Run the test suite:

```bash
pytest -q
```

Clean old generated reports:

```bash
flask --app app:create_app cleanup --days 7
```

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation and clear, descriptive names. Prefer snake_case for functions, variables, modules, and test files. Keep route handlers thin and put business logic in `app/services/` or `worker/` modules. Keep reusable automation logic in `packages/` free of Flask, SQLAlchemy, and worker dependencies. Follow the existing style: small focused modules, explicit dataclasses or typed structures where useful, and minimal comments unless they clarify non-obvious behavior.

## Testing Guidelines

Tests use `pytest` with `pythonpath = .` configured in `pytest.ini`. Name tests `test_*.py` and test functions `test_<behavior>`. Add focused tests near the behavior being changed, especially for prompt generation, captcha detection, runner decisions, and service-level job/report behavior. Run `pytest -q` before committing.

## Automation Behavior & Guardrails

The browser automation package (`packages/browser_automation/`) is designed to handle common anti-bot guardrails (e.g., CAPTCHA challenges, rate‑limiting walls, JavaScript detection) and use realistic browser settings where appropriate. This includes:

- Introducing random delays between keystrokes and mouse movements.
- Using realistic viewport sizes and scrolling patterns.
- Varying request headers and TLS fingerprints (where possible).
- Handling ephemeral popups, cookie banners, and session timeouts gracefully.

**Important**: Disabling guardrails and simulating human actions may violate the terms of service of target sites. Use this automation only for legitimate, authorized purposes and always respect robots.txt. The repository maintainers are not liable for misuse or any consequences resulting from automated interactions.

## Commit & Pull Request Guidelines

The current history uses short, imperative commit messages such as `Refactor browser automation engine`. Keep commits focused and avoid mixing generated artifacts with source changes.

Pull requests should include a concise summary, test results, linked issues when applicable, and screenshots only for visible UI/template changes. Note any configuration changes to `.env.example`, `config/sites.yaml`, or Playwright/browser-use behavior.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local settings. Do not commit real API keys, browser profiles, reports, screenshots, logs, or databases. Keep `OPENAI_API_KEY` and other credentials in `.env` or the deployment secret store.
