JOB_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "canceled",
}

RUNNABLE_JOB_STATUSES = {
    "queued",
    "running",
}

TERMINAL_JOB_STATUSES = {
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
    "captcha_failed",
    "captcha_timeout",
    "login_required",
    "restricted_checkpoint",
    "agent_uncertain",
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
    "agent_started",
    "agent_action",
    "agent_checkpoint",
    "agent_success",
    "agent_failed",
    "polite_delay",
    "artifact_saved",
    "browser_profile_reset",
    "site_memory_recorded",
    "retry_scheduled",
    "worker_error",
    "job_completed",
    "report_generated",
}

RETRY_BACKOFF_SECONDS = {
    1: 5,
    2: 15,
}

SITE_MEMORY_STATUSES = {"pending", "approved", "rejected"}
