import os
from dataclasses import dataclass, field


RECAPTCHA_V2 = "recaptcha_v2"
HCAPTCHA = "hcaptcha"
TURNSTILE = "turnstile"

RECAPTCHA_V2_TASK = "RecaptchaV2TaskProxyless"
HCAPTCHA_TASK = "HCaptchaTaskProxyless"
TURNSTILE_TASK = "TurnstileTaskProxyless"

TASK_TYPE_BY_CAPTCHA_KIND = {
    RECAPTCHA_V2: RECAPTCHA_V2_TASK,
    HCAPTCHA: HCAPTCHA_TASK,
    TURNSTILE: TURNSTILE_TASK,
}

SOLUTION_TOKEN_FIELDS = (
    "gRecaptchaResponse",
    "token",
    "text",
)


@dataclass(frozen=True)
class OhMyCaptchaSettings:
    base_url: str = "http://127.0.0.1:8000"
    client_key: str = ""
    request_timeout_seconds: float = 30.0
    poll_interval_seconds: float = 2.0
    max_wait_seconds: float = 120.0

    @classmethod
    def from_env(cls, environ=None):
        values = environ or os.environ
        return cls(
            base_url=values.get("OHMYCAPTCHA_BASE_URL", cls.base_url),
            client_key=values.get("OHMYCAPTCHA_CLIENT_KEY", values.get("CLIENT_KEY", "")),
            request_timeout_seconds=float(
                values.get(
                    "OHMYCAPTCHA_REQUEST_TIMEOUT_SECONDS",
                    cls.request_timeout_seconds,
                )
            ),
            poll_interval_seconds=float(
                values.get(
                    "OHMYCAPTCHA_POLL_INTERVAL_SECONDS",
                    cls.poll_interval_seconds,
                )
            ),
            max_wait_seconds=float(
                values.get("OHMYCAPTCHA_MAX_WAIT_SECONDS", cls.max_wait_seconds)
            ),
        )


@dataclass(frozen=True)
class CaptchaTask:
    type: str
    website_url: str
    website_key: str
    page_action: str | None = None

    def to_payload(self):
        payload = {
            "type": self.type,
            "websiteURL": self.website_url,
            "websiteKey": self.website_key,
        }
        if self.page_action:
            payload["pageAction"] = self.page_action
        return payload


@dataclass(frozen=True)
class CaptchaMetadata:
    kind: str
    selector: str
    task: CaptchaTask


@dataclass(frozen=True)
class BrowserUseCaptchaWaitResult:
    waited: bool
    vendor: str
    url: str
    duration_ms: int
    result: str


@dataclass(frozen=True)
class CaptchaSolveResult:
    task_id: str
    status: str
    solution: dict = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict = field(default_factory=dict)

    @property
    def solved(self):
        return self.status == "ready" and bool(self.solution)

    @property
    def token(self):
        for field_name in SOLUTION_TOKEN_FIELDS:
            token = self.solution.get(field_name)
            if token:
                return token
        return None
