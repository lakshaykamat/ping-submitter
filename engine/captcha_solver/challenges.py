from datetime import timedelta
from pathlib import Path

from flask import current_app

from app.models import CaptchaChallenge, get_session, utc_now


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
    path = Path(current_app.config["ARTIFACT_DIR"]) / str(job_id) / str(attempt_id) / "captcha.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return path
