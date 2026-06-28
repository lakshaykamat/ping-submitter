import os
from dataclasses import dataclass, field


RECAPTCHA_V2 = "recaptcha_v2"
RECAPTCHA_V3 = "recaptcha_v3"
HCAPTCHA = "hcaptcha"
TURNSTILE = "turnstile"
IMAGE_CAPTCHA = "image_captcha"
HCAPTCHA_CLASSIFICATION = "hcaptcha_classification"
RECAPTCHA_V2_CLASSIFICATION = "recaptcha_v2_classification"
FUNCAPTCHA_CLASSIFICATION = "funcaptcha_classification"
AWS_CLASSIFICATION = "aws_classification"

RECAPTCHA_V2_TASK = "RecaptchaV2TaskProxyless"
RECAPTCHA_V2_ENTERPRISE_TASK = "RecaptchaV2EnterpriseTaskProxyless"
NO_CAPTCHA_TASK = "NoCaptchaTaskProxyless"
RECAPTCHA_V3_TASK = "RecaptchaV3TaskProxyless"
HCAPTCHA_TASK = "HCaptchaTaskProxyless"
TURNSTILE_TASK = "TurnstileTaskProxyless"
TURNSTILE_TASK_M1 = "TurnstileTaskProxylessM1"
IMAGE_TO_TEXT_TASK = "ImageToTextTask"
HCAPTCHA_CLASSIFICATION_TASK = "HCaptchaClassification"
RECAPTCHA_V2_CLASSIFICATION_TASK = "ReCaptchaV2Classification"
FUNCAPTCHA_CLASSIFICATION_TASK = "FunCaptchaClassification"
AWS_CLASSIFICATION_TASK = "AwsClassification"

RECAPTCHA_V2_TASK_TYPES = (
    RECAPTCHA_V2_TASK,
    RECAPTCHA_V2_ENTERPRISE_TASK,
    NO_CAPTCHA_TASK,
)
RECAPTCHA_V3_TASK_TYPES = (RECAPTCHA_V3_TASK,)
HCAPTCHA_TASK_TYPES = (HCAPTCHA_TASK,)
TURNSTILE_TASK_TYPES = (TURNSTILE_TASK, TURNSTILE_TASK_M1)
IMAGE_CAPTCHA_TASK_TYPES = (IMAGE_TO_TEXT_TASK,)
HCAPTCHA_CLASSIFICATION_TASK_TYPES = (HCAPTCHA_CLASSIFICATION_TASK,)
RECAPTCHA_V2_CLASSIFICATION_TASK_TYPES = (RECAPTCHA_V2_CLASSIFICATION_TASK,)
FUNCAPTCHA_CLASSIFICATION_TASK_TYPES = (FUNCAPTCHA_CLASSIFICATION_TASK,)
AWS_CLASSIFICATION_TASK_TYPES = (AWS_CLASSIFICATION_TASK,)

TASK_TYPE_BY_CAPTCHA_KIND = {
    RECAPTCHA_V2: RECAPTCHA_V2_TASK,
    RECAPTCHA_V3: RECAPTCHA_V3_TASK,
    HCAPTCHA: HCAPTCHA_TASK,
    TURNSTILE: TURNSTILE_TASK,
    IMAGE_CAPTCHA: IMAGE_TO_TEXT_TASK,
    HCAPTCHA_CLASSIFICATION: HCAPTCHA_CLASSIFICATION_TASK,
    RECAPTCHA_V2_CLASSIFICATION: RECAPTCHA_V2_CLASSIFICATION_TASK,
    FUNCAPTCHA_CLASSIFICATION: FUNCAPTCHA_CLASSIFICATION_TASK,
    AWS_CLASSIFICATION: AWS_CLASSIFICATION_TASK,
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
    website_url: str = ""
    website_key: str = ""
    page_action: str | None = None
    is_invisible: bool | None = None
    body: str | None = None
    image: str | None = None
    queries: tuple[str, ...] = ()
    question: str | None = None

    def to_payload(self):
        payload = {"type": self.type}
        if self.website_url:
            payload["websiteURL"] = self.website_url
        if self.website_key:
            payload["websiteKey"] = self.website_key
        if self.page_action:
            payload["pageAction"] = self.page_action
        if self.is_invisible is not None:
            payload["isInvisible"] = self.is_invisible
        if self.body:
            payload["body"] = self.body
        if self.image:
            payload["image"] = self.image
        if self.queries:
            payload["queries"] = list(self.queries)
        if self.question:
            payload["question"] = self.question
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

    @property
    def objects(self):
        objects = self.solution.get("objects")
        return objects if isinstance(objects, list) else None
