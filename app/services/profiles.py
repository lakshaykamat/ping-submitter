import json
import shutil
from pathlib import Path

from flask import current_app

from app.models import BrowserProfile, SiteMemory, SubmissionAttempt, get_session, utc_now
from app.services.events import record_event
from app.services.exceptions import ValidationError
from app.services.statuses import SITE_MEMORY_STATUSES
from app.utils.files import safe_filename
from app.utils.redaction import redact_sensitive_data


def get_browser_profiles():
    session = get_session()
    return session.query(BrowserProfile).order_by(BrowserProfile.site_id, BrowserProfile.account_label).all()


def get_or_create_browser_profile(site):
    if not site.get("browser_profile_enabled"):
        return None

    session = get_session()
    account_label = site.get("profile_account") or "default"
    profile = (
        session.query(BrowserProfile)
        .filter(BrowserProfile.site_id == site["id"], BrowserProfile.account_label == account_label)
        .one_or_none()
    )
    if profile is None:
        profile = BrowserProfile(
            site_id=site["id"],
            account_label=account_label,
            directory_path=str(profile_directory(site["id"], account_label)),
            approved_for_reuse=1,
        )
        session.add(profile)
        session.flush()

    Path(profile.directory_path).mkdir(parents=True, exist_ok=True)
    profile.last_used_at = utc_now()
    return profile


def reset_browser_profile(site_id, account_label="default"):
    session = get_session()
    profile = (
        session.query(BrowserProfile)
        .filter(BrowserProfile.site_id == site_id, BrowserProfile.account_label == account_label)
        .one_or_none()
    )
    directory = profile_directory(site_id, account_label) if profile is None else Path(profile.directory_path)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if profile:
        profile.last_used_at = None
        profile.updated_at = utc_now()
    return str(directory)


def profile_directory(site_id, account_label="default"):
    return Path(current_app.config["BROWSER_PROFILE_DIR"]) / safe_filename(site_id) / safe_filename(account_label)


def approved_site_memory(site_id):
    session = get_session()
    memories = (
        session.query(SiteMemory)
        .filter(SiteMemory.site_id == site_id, SiteMemory.status == "approved")
        .order_by(SiteMemory.id.desc())
        .limit(3)
        .all()
    )
    return [memory.strategy for memory in memories]


def record_site_memory(site_id, attempt_id, strategy, approved=False):
    status = "approved" if approved else "pending"
    if status not in SITE_MEMORY_STATUSES:
        raise ValidationError(f"invalid site memory status: {status}")

    session = get_session()
    memory = SiteMemory(
        site_id=site_id,
        source_attempt_id=attempt_id,
        status=status,
        strategy_json=json.dumps(redact_sensitive_data(strategy or {}), sort_keys=True),
        promoted_at=utc_now() if approved else None,
    )
    session.add(memory)
    session.flush()
    attempt = session.get(SubmissionAttempt, attempt_id) if attempt_id else None
    if attempt is None:
        return memory
    record_event(
        session=session,
        job_id=attempt.job_id,
        attempt_id=attempt_id,
        site_id=site_id,
        event_type="site_memory_recorded",
        message="Site memory recorded.",
        context={"memory_id": memory.id, "status": status},
    )
    return memory
