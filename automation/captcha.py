from datetime import timedelta
from pathlib import Path

from flask import current_app

from app.models import CaptchaChallenge, get_session, utc_now


CAPTCHA_SELECTORS = (
    'iframe[src*="recaptcha"]',
    ".g-recaptcha",
    'iframe[src*="hcaptcha"]',
    ".h-captcha",
    'iframe[src*="challenges.cloudflare.com"]',
    '[id*="captcha" i]',
    '[class*="captcha" i]',
    '[name*="captcha" i]',
    'img[src*="captcha" i]',
)

CAPTCHA_ANSWER_SELECTORS = (
    'input[name*="captcha" i]',
    'input[id*="captcha" i]',
    'textarea[name*="captcha" i]',
)


def detect_captcha(page, adapter=None):
    selectors = list(CAPTCHA_SELECTORS)
    if adapter:
        selectors.extend(adapter.captcha_selectors)

    for selector in selectors:
        if selector_exists(page, selector):
            return selector
    return None


def create_captcha_challenge(job, attempt, page, wait_seconds):
    screenshot_path = save_captcha_screenshot(job.id, attempt.id, page)
    challenge = CaptchaChallenge(
        job_id=job.id,
        attempt_id=attempt.id,
        status="captcha_required",
        screenshot_path=str(screenshot_path),
        expires_at=utc_now() + timedelta(seconds=wait_seconds) if wait_seconds is not None else None,
    )
    session = get_session()
    session.add(challenge)
    session.flush()
    return challenge


def save_captcha_screenshot(job_id, attempt_id, page):
    path = Path(current_app.config["LOG_DIR"]) / f"{job_id}-{attempt_id}-captcha.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return path


def fill_captcha_answer(page, answer):
    for selector in CAPTCHA_ANSWER_SELECTORS:
        if selector_exists(page, selector):
            page.locator(selector).first.fill(answer)
            return True
    return False


def selector_exists(page, selector):
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False
