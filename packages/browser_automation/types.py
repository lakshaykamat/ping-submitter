from dataclasses import dataclass, field


DEFAULT_CAPTCHA_POLICY = "solve"
CAPTCHA_FAILURE_REASON = (
    "CAPTCHA encountered; solving is disabled or unavailable for this site. "
    "Enable captcha_policy: solve with the configured local solver, or submit manually."
)
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
    "navigate",
    "click",
    "input text with clear=True",
    "send keys such as select-all, Backspace, Delete, Enter",
    "scroll down/up",
    "go back/forward",
    "reload",
    "close overlays",
)
AGENT_LOOP_STEPS = (
    "observe the current browser state and review the previous action outcome",
    "decide the next safe action",
    "use one browser tool",
    "verify required fields before submit and check whether the submission is complete",
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


@dataclass(frozen=True)
class RestrictedCheckpoint:
    reason: str
    url: str = ""
