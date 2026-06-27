import json
import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse

import yaml
from flask import current_app

from automation.types import ATTEMPT_STATUSES, EVENT_TYPES, JOB_STATUSES, REQUIRED_LOG_FIELDS
from app.models import (
    CaptchaChallenge,
    JobEvent,
    JobReport,
    SubmissionAttempt,
    SubmissionJob,
    get_session,
    utc_now,
)


class ValidationError(Exception):
    pass


def load_sites():
    config_path = Path(current_app.config["SITES_CONFIG_PATH"])
    data = yaml.safe_load(config_path.read_text()) or {}
    sites = data.get("sites", [])
    return {site["id"]: site for site in sites}


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

    report = build_report(job)
    write_report(job.id, report)
    record_event(
        session=session,
        job_id=job.id,
        event_type="report_generated",
        message="Initial report generated.",
        context={"report_path": str(report_path(job.id))},
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


def get_report_record(job_id):
    session = get_session()
    return session.query(JobReport).filter(JobReport.job_id == job_id).one_or_none()


def get_recent_events(limit=25):
    session = get_session()
    return session.query(JobEvent).order_by(JobEvent.id.desc()).limit(limit).all()


def get_captcha_challenge(challenge_id):
    return get_session().get(CaptchaChallenge, challenge_id)


def save_captcha_answer(challenge_id, answer):
    if not answer or not answer.strip():
        raise ValidationError("captcha answer is required")

    session = get_session()
    challenge = session.get(CaptchaChallenge, challenge_id)
    if challenge is None:
        return None

    challenge.answer = answer.strip()
    challenge.status = "answered"
    attempt = session.get(SubmissionAttempt, challenge.attempt_id)
    job = session.get(SubmissionJob, challenge.job_id)
    if attempt and attempt.status == "captcha_required":
        attempt.status = "queued"
    if job and job.status == "waiting_for_captcha":
        job.status = "queued"
    record_event(
        session=session,
        job_id=challenge.job_id,
        attempt_id=challenge.attempt_id,
        site_id=attempt.site_id if attempt else None,
        submitted_url=attempt.submitted_url if attempt else None,
        event_type="captcha_answered",
        message="CAPTCHA answer submitted by operator.",
        context={"challenge_id": challenge.id},
    )
    session.commit()
    return challenge


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
        context_json=json.dumps(context or {}, sort_keys=True),
        created_at=utc_now(),
    )
    session.add(event)
    session.flush()
    append_job_log(event)
    return event


def append_job_log(event):
    log_entry = event.to_dict()
    missing_fields = [field for field in REQUIRED_LOG_FIELDS if field not in log_entry]
    if missing_fields:
        raise ValueError(f"log entry missing fields: {', '.join(missing_fields)}")

    log_dir = Path(current_app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)
    with log_path(event.job_id).open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_entry, sort_keys=True) + "\n")
    log_to_terminal(log_entry)


def log_to_terminal(log_entry):
    level = getattr(logging, log_entry["level"].upper(), logging.INFO)
    current_app.logger.log(
        level,
        "%s job=%s attempt=%s site=%s url=%s %s",
        log_entry["event_type"],
        log_entry["job_id"],
        log_entry["attempt_id"],
        log_entry["site_id"],
        log_entry["submitted_url"],
        log_entry["message"],
    )


def log_path(job_id):
    return Path(current_app.config["LOG_DIR"]) / f"{job_id}.jsonl"


def report_path(job_id):
    return json_report_path(job_id)


def json_report_path(job_id):
    return Path(current_app.config["REPORT_DIR"]) / f"{job_id}.json"


def markdown_report_path(job_id):
    return Path(current_app.config["REPORT_DIR"]) / f"{job_id}.md"


def build_report(job):
    attempts = [attempt.to_dict() for attempt in job.attempts]
    submitted_urls = unique_values(attempt.submitted_url for attempt in job.attempts)
    selected_sites = unique_sites(job.attempts)
    started_time = job_start_time(job)
    finished_time = job_finish_time(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "submitted_urls": submitted_urls,
        "selected_sites": selected_sites,
        "total_attempts": len(attempts),
        "success_count": count_attempts(job.attempts, {"success"}),
        "failure_count": count_attempts(job.attempts, {"failed"}),
        "skipped_count": count_attempts(job.attempts, {"skipped"}),
        "captcha_count": count_attempts(job.attempts, {"captcha_required", "captcha_timeout"}),
        "attempts": attempts,
        "started_time": started_time.isoformat() if started_time else None,
        "finished_time": finished_time.isoformat() if finished_time else None,
        "duration_seconds": duration_seconds(started_time, finished_time),
        "job": job.to_dict(include_attempts=False),
    }


def write_report(job_id, report):
    json_path = json_report_path(job_id)
    markdown_path = markdown_report_path(job_id)
    markdown_content = build_markdown_report(report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(markdown_content, encoding="utf-8")
    store_report(job_id, report, markdown_content, json_path, markdown_path)


def store_report(job_id, report, markdown_content, json_path, markdown_path):
    session = get_session()
    report_record = get_report_record(job_id)
    if report_record is None:
        report_record = JobReport(job_id=job_id)
        session.add(report_record)

    report_record.json_content = json.dumps(report, indent=2, sort_keys=True)
    report_record.markdown_content = markdown_content
    report_record.json_path = str(json_path)
    report_record.markdown_path = str(markdown_path)
    report_record.generated_at = utc_now()
    session.flush()


def get_report(job_id):
    report_record = get_report_record(job_id)
    if report_record:
        restore_report_files(report_record)
        return report_record.json_data()

    path = json_report_path(job_id)
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        write_report(job_id, report)
        return report

    job = get_job(job_id)
    if job is None:
        return None
    report = build_report(job)
    write_report(job_id, report)
    return report


def get_markdown_report(job_id):
    report_record = get_report_record(job_id)
    if report_record:
        restore_report_files(report_record)
        return Path(report_record.markdown_path)

    path = markdown_report_path(job_id)
    if path.exists():
        report = get_report(job_id)
        if report is not None:
            write_report(job_id, report)
        return path

    job = get_job(job_id)
    if job is None:
        return None
    write_report(job.id, build_report(job))
    return path


def get_markdown_report_text(job_id):
    report_record = get_report_record(job_id)
    if report_record:
        return report_record.markdown_content

    path = get_markdown_report(job_id)
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def restore_report_files(report_record):
    json_path = Path(report_record.json_path)
    markdown_path = Path(report_record.markdown_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    if not json_path.exists():
        json_path.write_text(report_record.json_content, encoding="utf-8")
    if not markdown_path.exists():
        markdown_path.write_text(report_record.markdown_content, encoding="utf-8")


def build_markdown_report(report):
    lines = [
        f"# Job {report['job_id']} Report",
        "",
        f"- Status: {report['status']}",
        f"- Submitted URLs: {len(report['submitted_urls'])}",
        f"- Selected sites: {len(report['selected_sites'])}",
        f"- Total attempts: {report['total_attempts']}",
        f"- Success: {report['success_count']}",
        f"- Failed: {report['failure_count']}",
        f"- Skipped: {report['skipped_count']}",
        f"- CAPTCHA: {report['captcha_count']}",
        f"- Started: {report['started_time'] or 'not started'}",
        f"- Finished: {report['finished_time'] or 'not finished'}",
        f"- Duration seconds: {report['duration_seconds'] if report['duration_seconds'] is not None else 'n/a'}",
        "",
        "## Attempts",
        "",
        "| ID | Site | URL | Status | Retries | Failure |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for attempt in report["attempts"]:
        failure = attempt["failure_reason"] or ""
        lines.append(
            f"| {attempt['id']} | {attempt['site_id']} | {attempt['submitted_url']} | "
            f"{attempt['status']} | {attempt['retry_count']} | {failure} |"
        )
    lines.append("")
    return "\n".join(lines)


def unique_values(values):
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def unique_sites(attempts):
    sites = []
    seen = set()
    for attempt in attempts:
        if attempt.site_id not in seen:
            sites.append({"id": attempt.site_id, "name": attempt.site_name})
            seen.add(attempt.site_id)
    return sites


def count_attempts(attempts, statuses):
    return sum(1 for attempt in attempts if attempt.status in statuses)


def job_start_time(job):
    started_times = [attempt.started_at for attempt in job.attempts if attempt.started_at]
    return min(started_times) if started_times else job.created_at


def job_finish_time(job):
    final_statuses = {"completed", "failed", "canceled"}
    if job.status not in final_statuses:
        return None
    finished_times = [attempt.finished_at for attempt in job.attempts if attempt.finished_at]
    return max(finished_times) if finished_times else job.updated_at


def duration_seconds(started_time, finished_time):
    if not started_time or not finished_time:
        return None
    return round((finished_time - started_time).total_seconds(), 3)


def status_values():
    return {
        "job_statuses": sorted(JOB_STATUSES),
        "attempt_statuses": sorted(ATTEMPT_STATUSES),
    }
