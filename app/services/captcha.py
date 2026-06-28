from datetime import timedelta

from flask import current_app

from app.models import CaptchaChallenge, get_session, utc_now
from packages.captcha_solver import save_captcha_screenshot as save_package_captcha_screenshot


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
    return save_package_captcha_screenshot(job_id, attempt_id, page, current_app.config["ARTIFACT_DIR"])
