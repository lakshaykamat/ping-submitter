from dataclasses import dataclass, field


AGENT_SUCCESS = "success"
AGENT_SKIP_STATUSES = {
    "login_required",
    "restricted_checkpoint",
    "skipped",
}
AGENT_FAILURE_STATUSES = {
    "failed",
    "captcha_required",
    "captcha_failed",
    "login_required",
    "restricted_checkpoint",
    "agent_uncertain",
    "skipped",
}
CAPTCHA_AGENT_STATUSES = {
    "captcha_required",
    "captcha_failed",
    "captcha_timeout",
}
CAPTCHA_FAILURE_REASON = "CAPTCHA encountered and could not be solved automatically."


@dataclass(frozen=True)
class AgentResult:
    status: str
    message: str = ""
    confidence: float | None = None
    evidence: dict = field(default_factory=dict)
    screenshot_path: str | None = None
