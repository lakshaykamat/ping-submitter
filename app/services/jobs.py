import uuid
from urllib.parse import urlparse

from app.models import JobEvent, SubmissionAttempt, SubmissionJob, get_session
from app.services.events import record_event
from app.services.exceptions import ValidationError
from app.services.sites import load_sites
from engine.types import ATTEMPT_STATUSES, JOB_STATUSES


def create_submission_job(payload):
    urls = validate_urls(payload.get("urls"))
    sites = validate_sites(payload.get("sites"))
    max_attempts = validate_max_attempts(payload.get("max_attempts", 3))

    session = get_session()
    job = SubmissionJob(
        id=str(uuid.uuid4()),
        status="queued",
        max_attempts=max_attempts,
        url_count=len(urls),
        site_count=len(sites),
    )
    session.add(job)
    session.flush()

    record_event(
        session=session,
        job_id=job.id,
        event_type="job_created",
        message="Submission job created.",
        context={"url_count": len(urls), "site_count": len(sites), "max_attempts": max_attempts},
    )

    for submitted_url in urls:
        for site in sites:
            attempt = SubmissionAttempt(
                job_id=job.id,
                site_id=site["id"],
                site_name=site["name"],
                submitted_url=submitted_url,
                status="queued",
                runner_mode=site["runner_mode"],
                captcha_policy=site["captcha_policy"],
                attempt_number=1,
            )
            session.add(attempt)
            session.flush()
            record_event(
                session=session,
                job_id=job.id,
                attempt_id=attempt.id,
                site_id=attempt.site_id,
                submitted_url=attempt.submitted_url,
                event_type="attempt_created",
                message="Submission attempt created.",
                context={"attempt_number": attempt.attempt_number},
            )

    session.commit()
    return job


def validate_urls(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("urls must be a non-empty list")

    valid_urls = []
    for submitted_url in value:
        if not isinstance(submitted_url, str):
            raise ValidationError("each URL must be a string")
        parsed_url = urlparse(submitted_url.strip())
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValidationError(f"invalid URL: {submitted_url}")
        valid_urls.append(submitted_url.strip())
    return valid_urls


def validate_sites(value):
    all_sites = load_sites()
    selected_site_ids = value if value else enabled_site_ids(all_sites)
    if not isinstance(selected_site_ids, list) or not selected_site_ids:
        raise ValidationError("sites must be a non-empty list")

    selected_sites = []
    for site_id in selected_site_ids:
        site = all_sites.get(site_id)
        if site is None:
            raise ValidationError(f"unknown site: {site_id}")
        if not site.get("enabled", True):
            raise ValidationError(f"site is disabled: {site_id}")
        selected_sites.append(site)
    return selected_sites


def enabled_site_ids(sites):
    return [site_id for site_id, site in sites.items() if site.get("enabled", True)]


def validate_max_attempts(value):
    if not isinstance(value, int) or value < 1:
        raise ValidationError("max_attempts must be a positive integer")
    return value


def get_job(job_id):
    return get_session().get(SubmissionJob, job_id)


def get_job_events(job_id):
    session = get_session()
    return (
        session.query(JobEvent)
        .filter(JobEvent.job_id == job_id)
        .order_by(JobEvent.id.asc())
        .all()
    )


def get_recent_events(limit=25):
    session = get_session()
    return session.query(JobEvent).order_by(JobEvent.id.desc()).limit(limit).all()


def status_values():
    return {
        "job_statuses": sorted(JOB_STATUSES),
        "attempt_statuses": sorted(ATTEMPT_STATUSES),
    }
