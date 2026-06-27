from dataclasses import dataclass, field


JOB_STATUSES = {
    "queued",
    "running",
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
    "job_completed",
    "report_generated",
}

RETRY_BACKOFF_SECONDS = {
    1: 5,
    2: 15,
}

SITE_MEMORY_STATUSES = {"pending", "approved", "rejected"}
CAPTCHA_FAILURE_REASON = "CAPTCHA encountered; CAPTCHA solving is not implemented and is reserved for future work."
CAPTCHA_AGENT_STATUSES = {
    "captcha_required",
    "captcha_failed",
    "captcha_timeout",
}
AGENT_SKIP_STATUSES = {
    "login_required",
    "restricted_checkpoint",
    "skipped",
}

AGENT_SUCCESS = "success"
AGENT_FAILURE_STATUSES = {
    "failed",
    "captcha_required",
    "captcha_failed",
    "login_required",
    "restricted_checkpoint",
    "agent_uncertain",
    "skipped",
}
AGENT_OUTPUT_KEYS = ("status", "message", "confidence", "evidence", "screenshot_path")
AGENT_REDACTED_CONTEXT_KEY_TERMS = ("key", "secret", "token")
AGENT_BROWSER_TOOLS = (
    "change the address bar URL",
    "go back",
    "go forward",
    "reload",
    "scroll",
    "close blocking overlays",
    "reopen the target page",
)
AGENT_LOOP_STEPS = (
    "observe the current browser state",
    "decide the next safe action",
    "use one browser tool",
    "check whether the submission is complete",
)
SENSITIVE_ACTION_PATTERNS = {
    "payment": ("payment", "credit card", "card number", "billing"),
    "signup": ("sign up", "signup", "create account", "register account"),
    "account_change": ("change password", "delete account", "account settings"),
    "subscription": ("subscribe", "subscription", "paid plan"),
}


@dataclass(frozen=True)
class AgentResult:
    status: str
    message: str = ""
    confidence: float | None = None
    evidence: dict = field(default_factory=dict)
    screenshot_path: str | None = None
