from pathlib import Path


def save_captcha_screenshot(job_id, attempt_id, page, artifact_dir):
    path = Path(artifact_dir) / str(job_id) / str(attempt_id) / "captcha.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return path
