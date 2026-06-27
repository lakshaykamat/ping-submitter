import json
from pathlib import Path

from flask import current_app

from app.models import JobReport, get_session, utc_now
from app.services.jobs import get_job


def get_report_record(job_id):
    session = get_session()
    return session.query(JobReport).filter(JobReport.job_id == job_id).one_or_none()


def json_report_path(job_id):
    return Path(current_app.config["REPORT_DIR"]) / f"{job_id}.json"


def markdown_report_path(job_id):
    return Path(current_app.config["REPORT_DIR"]) / f"{job_id}.md"


def build_report(job):
    attempts = [attempt.to_dict() for attempt in job.attempts]
    events = [event.to_dict() for event in job.events]
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
        "failure_count": count_attempts(
            job.attempts,
            {
                "failed",
                "captcha_failed",
                "captcha_timeout",
                "login_required",
                "restricted_checkpoint",
                "agent_uncertain",
            },
        ),
        "skipped_count": count_attempts(job.attempts, {"skipped"}),
        "captcha_count": count_captcha_attempts(job.attempts),
        "checkpoint_count": count_checkpoint_events(events),
        "runner_modes": sorted(unique_values(attempt.runner_mode for attempt in job.attempts)),
        "agent_confidence": latest_agent_confidence(events),
        "final_evidence": final_evidence(events),
        "artifacts": artifact_events(events),
        "attempts": attempts,
        "events": events,
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
    if is_terminal_job(job):
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
    if not is_terminal_job(job):
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


def is_terminal_job(job):
    return job.status in {"completed", "failed", "canceled"}


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
        f"- Checkpoints: {report['checkpoint_count']}",
        f"- Runner modes: {', '.join(report['runner_modes']) if report['runner_modes'] else 'n/a'}",
        f"- Agent confidence: {report['agent_confidence'] if report['agent_confidence'] is not None else 'n/a'}",
        f"- Started: {report['started_time'] or 'not started'}",
        f"- Finished: {report['finished_time'] or 'not finished'}",
        f"- Duration seconds: {report['duration_seconds'] if report['duration_seconds'] is not None else 'n/a'}",
        "",
        "## Attempts",
        "",
        "| ID | Site | URL | Runner | CAPTCHA | Status | Retries | Failure |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for attempt in report["attempts"]:
        failure = attempt["failure_reason"] or ""
        lines.append(
            f"| {attempt['id']} | {attempt['site_id']} | {attempt['submitted_url']} | "
            f"{attempt['runner_mode']} | {attempt['captcha_policy']} | {attempt['status']} | "
            f"{attempt['retry_count']} | {failure} |"
        )
    if report["final_evidence"]:
        lines.extend(["", "## Final Evidence", ""])
        lines.append("```json")
        lines.append(json.dumps(report["final_evidence"], indent=2, sort_keys=True))
        lines.append("```")
    if report["artifacts"]:
        lines.extend(["", "## Artifacts", ""])
        for artifact in report["artifacts"]:
            lines.append(f"- {artifact['stage']}: {artifact['screenshot_path']}")
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


def count_captcha_attempts(attempts):
    captcha_statuses = {
        "captcha_required",
        "captcha_failed",
        "captcha_timeout",
    }
    return sum(
        1
        for attempt in attempts
        if attempt.status in captcha_statuses or is_captcha_failure(attempt.failure_reason)
    )


def is_captcha_failure(reason):
    return "captcha" in str(reason or "").lower()


def count_checkpoint_events(events):
    return sum(
        1
        for event in events
        if event["event_type"] in {"agent_checkpoint", "captcha_detected"}
    )


def latest_agent_confidence(events):
    for event in reversed(events):
        confidence = event["context"].get("confidence")
        if confidence is not None:
            return confidence
    return None


def final_evidence(events):
    for event in reversed(events):
        if event["event_type"] in {"agent_success", "agent_failed", "agent_checkpoint"}:
            return event["context"]
    return {}


def artifact_events(events):
    artifacts = []
    for event in events:
        if event["event_type"] != "artifact_saved":
            continue
        artifacts.append(
            {
                "stage": event["context"].get("stage"),
                "screenshot_path": event["context"].get("screenshot_path"),
            }
        )
    return artifacts


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
