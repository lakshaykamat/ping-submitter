import json
import logging
import re

from flask import current_app

from app.models import JobEvent, utc_now
from app.services.statuses import EVENT_TYPES


def record_event(
    session,
    job_id,
    event_type,
    message,
    level="info",
    attempt_id=None,
    site_id=None,
    submitted_url=None,
    context=None,
):
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type}")

    event = JobEvent(
        job_id=job_id,
        attempt_id=attempt_id,
        site_id=site_id,
        submitted_url=submitted_url,
        event_type=event_type,
        level=level,
        message=message,
        context_json=json.dumps(redact_sensitive_data(context or {}), sort_keys=True),
        created_at=utc_now(),
    )
    session.add(event)
    session.flush()
    log_to_terminal(event.to_dict())
    return event


def redact_sensitive_data(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if is_sensitive_key(key) else redact_sensitive_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


def is_sensitive_key(key):
    return bool(re.search(r"(api[_-]?key|secret|token|password|credential|captcha|answer)", str(key), re.I))


def log_to_terminal(log_entry):
    level = getattr(logging, log_entry["level"].upper(), logging.INFO)
    current_app.logger.log(
        level,
        log_entry["message"],
        extra={
            "event": log_entry["event_type"],
            "job_id": log_entry["job_id"],
            "attempt_id": log_entry["attempt_id"],
            "site_id": log_entry["site_id"],
            "submitted_url": log_entry["submitted_url"],
        },
    )
