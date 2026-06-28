from datetime import timezone


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
    started_time = utc_comparable_datetime(started_time)
    finished_time = utc_comparable_datetime(finished_time)
    return round((finished_time - started_time).total_seconds(), 3)


def utc_comparable_datetime(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
