JOB_STATUSES = {
    "queued",
    "running",
    "waiting_for_captcha",
    "completed",
    "failed",
    "canceled",
}

ATTEMPT_STATUSES = {
    "queued",
    "running",
    "success",
    "failed",
    "skipped",
    "captcha_required",
    "captcha_timeout",
    "canceled",
}

EVENT_TYPES = {
    "job_created",
    "job_started",
    "attempt_created",
    "attempt_started",
    "attempt_success",
    "attempt_failed",
    "captcha_detected",
    "captcha_answered",
    "retry_scheduled",
    "job_completed",
    "report_generated",
}

REQUIRED_LOG_FIELDS = (
    "timestamp",
    "level",
    "job_id",
    "attempt_id",
    "site_id",
    "submitted_url",
    "event_type",
    "message",
    "context",
)

RETRY_BACKOFF_SECONDS = {
    1: 5,
    2: 15,
}
