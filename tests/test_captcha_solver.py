import json
import asyncio
from dataclasses import dataclass

import pytest

from packages.captcha_solver import (
    AWS_CLASSIFICATION_TASK,
    FUNCAPTCHA_CLASSIFICATION_TASK,
    HCAPTCHA_CLASSIFICATION_TASK,
    IMAGE_TO_TEXT_TASK,
    NO_CAPTCHA_TASK,
    RECAPTCHA_V2,
    RECAPTCHA_V2_CLASSIFICATION_TASK,
    RECAPTCHA_V3,
    RECAPTCHA_V3_TASK,
    RECAPTCHA_V2_TASK,
    TURNSTILE,
    TURNSTILE_TASK,
    TURNSTILE_TASK_M1,
    CaptchaSolveResult,
    CaptchaSolverApiError,
    CaptchaSolverTimeoutError,
    CaptchaTask,
    OhMyCaptchaClient,
    OhMyCaptchaSettings,
    detect_captcha,
    detect_browser_use_captcha_metadata,
    detect_captcha_metadata,
    fill_captcha_answer,
    solve_browser_use_captcha,
    solve_detected_captcha,
)


class FakeLocator:
    def __init__(self, count, attributes=None):
        self._count = count
        self.attributes = attributes or {}
        self.filled_values = []
        self.first = self

    def count(self):
        return self._count

    def fill(self, value):
        self.filled_values.append(value)

    def get_attribute(self, name):
        return self.attributes.get(name)


class FakePage:
    def __init__(
        self,
        selector_counts,
        selector_attributes=None,
        url="https://example.com/form",
    ):
        self.url = url
        selector_attributes = selector_attributes or {}
        self.locators = {
            selector: FakeLocator(count, selector_attributes.get(selector))
            for selector, count in selector_counts.items()
        }

    def locator(self, selector):
        return self.locators.get(selector, FakeLocator(0))


@dataclass
class FakeAdapter:
    captcha_selectors: tuple[str, ...]


def test_detect_captcha_returns_first_matching_selector():
    page = FakePage({".h-captcha": 1})

    assert detect_captcha(page) == ".h-captcha"


def test_detect_captcha_includes_adapter_selectors():
    page = FakePage({"#custom-captcha": 1})
    adapter = FakeAdapter(captcha_selectors=("#custom-captcha",))

    assert detect_captcha(page, adapter=adapter) == "#custom-captcha"


def test_detect_captcha_includes_turnstile_widget_selector():
    page = FakePage({".cf-turnstile": 1})

    assert detect_captcha(page) == ".cf-turnstile"


def test_fill_captcha_answer_uses_first_answer_selector():
    selector = 'input[name*="captcha" i]'
    page = FakePage({selector: 1})

    assert fill_captcha_answer(page, "42") is True
    assert page.locators[selector].filled_values == ["42"]


def test_detect_captcha_metadata_builds_recaptcha_task_from_site_key():
    site_key_selector = ".g-recaptcha[data-sitekey]"
    page = FakePage(
        {
            ".g-recaptcha": 1,
            site_key_selector: 1,
        },
        {
            site_key_selector: {"data-sitekey": "site-key-123"},
        },
    )

    metadata = detect_captcha_metadata(page)

    assert metadata.kind == RECAPTCHA_V2
    assert metadata.selector == ".g-recaptcha"
    assert metadata.task == CaptchaTask(
        type=RECAPTCHA_V2_TASK,
        website_url="https://example.com/form",
        website_key="site-key-123",
    )


def test_detect_captcha_metadata_builds_recaptcha_v3_task_from_render_script():
    selector = 'script[src*="recaptcha/api.js?render"]'
    page = FakePage(
        {selector: 1},
        {
            selector: {
                "src": "https://www.google.com/recaptcha/api.js?render=v3-site-key"
            },
        },
    )

    metadata = detect_captcha_metadata(page)

    assert metadata.kind == RECAPTCHA_V3
    assert metadata.selector == selector
    assert metadata.task == CaptchaTask(
        type=RECAPTCHA_V3_TASK,
        website_url="https://example.com/form",
        website_key="v3-site-key",
    )


def test_detect_captcha_metadata_builds_turnstile_task_from_iframe_url():
    selector = 'iframe[src*="challenges.cloudflare.com"]'
    page = FakePage(
        {selector: 1},
        {
            selector: {
                "src": "https://challenges.cloudflare.com/turnstile/v0/api.js?k=turnstile-key"
            },
        },
    )

    metadata = detect_captcha_metadata(page)

    assert metadata.kind == TURNSTILE
    assert metadata.task.type == TURNSTILE_TASK
    assert metadata.task.website_key == "turnstile-key"


def test_detect_captcha_metadata_builds_turnstile_task_from_widget_site_key():
    page = FakePage(
        {
            ".cf-turnstile": 1,
            ".cf-turnstile[data-sitekey]": 1,
        },
        {
            ".cf-turnstile[data-sitekey]": {"data-sitekey": "turnstile-widget-key"},
        },
    )

    metadata = detect_captcha_metadata(page)

    assert metadata.kind == TURNSTILE
    assert metadata.selector == ".cf-turnstile"
    assert metadata.task.type == TURNSTILE_TASK
    assert metadata.task.website_key == "turnstile-widget-key"


def test_solve_detected_captcha_uses_detected_task():
    site_key_selector = ".g-recaptcha[data-sitekey]"
    page = FakePage(
        {
            ".g-recaptcha": 1,
            site_key_selector: 1,
        },
        {
            site_key_selector: {"data-sitekey": "site-key-123"},
        },
    )
    client = FakeCaptchaClient()

    result = solve_detected_captcha(page, client=client)

    assert result.token == "solution-token"
    assert client.tasks == [
        CaptchaTask(
            type=RECAPTCHA_V2_TASK,
            website_url="https://example.com/form",
            website_key="site-key-123",
        )
    ]


def test_browser_use_captcha_solver_detects_solves_and_injects_token():
    page = FakeBrowserUsePage(
        {
            ".g-recaptcha": {},
            ".g-recaptcha[data-sitekey]": {"data-sitekey": "site-key-123"},
        }
    )
    client = FakeCaptchaClient()

    result = asyncio.run(solve_browser_use_captcha(page, client=client))

    assert result.waited is True
    assert result.result == "success"
    assert result.vendor == RECAPTCHA_V2
    assert client.tasks == [
        CaptchaTask(
            type=RECAPTCHA_V2_TASK,
            website_url="https://example.com/form",
            website_key="site-key-123",
        )
    ]
    assert page.injected_tokens == {
        "g-recaptcha-response": "solution-token",
    }


def test_browser_use_captcha_solver_handles_turnstile_script_key_and_callback():
    script_selector = 'script[src*="challenges.cloudflare.com/turnstile"]'
    page = FakeBrowserUsePage(
        {
            script_selector: {
                "src": "https://challenges.cloudflare.com/turnstile/v0/api.js?render=turnstile-script-key"
            },
            ".cf-turnstile[data-callback]": {"data-callback": "onTurnstileSolved"},
        }
    )
    client = FakeCaptchaClient()

    result = asyncio.run(solve_browser_use_captcha(page, client=client))

    assert result.waited is True
    assert result.result == "success"
    assert result.vendor == TURNSTILE
    assert client.tasks == [
        CaptchaTask(
            type=TURNSTILE_TASK,
            website_url="https://example.com/form",
            website_key="turnstile-script-key",
        )
    ]
    assert page.injected_tokens == {
        "cf-turnstile-response": "solution-token",
        "turnstile-response": "solution-token",
    }
    assert page.callback_invocations == ["solution-token"]


def test_browser_use_captcha_metadata_builds_recaptcha_v3_task_from_render_script():
    selector = 'script[src*="recaptcha/api.js?render"]'
    page = FakeBrowserUsePage(
        {
            selector: {
                "src": "https://www.google.com/recaptcha/api.js?render=v3-site-key"
            },
        }
    )

    metadata = asyncio.run(detect_browser_use_captcha_metadata(page))

    assert metadata.kind == RECAPTCHA_V3
    assert metadata.task == CaptchaTask(
        type=RECAPTCHA_V3_TASK,
        website_url="https://example.com/form",
        website_key="v3-site-key",
    )


def test_browser_use_captcha_solver_returns_timeout_result_when_solver_times_out():
    page = FakeBrowserUsePage(
        {
            ".g-recaptcha": {},
            ".g-recaptcha[data-sitekey]": {"data-sitekey": "site-key-123"},
        }
    )

    result = asyncio.run(solve_browser_use_captcha(page, client=TimeoutCaptchaClient()))

    assert result.waited is True
    assert result.result == "timeout"
    assert result.vendor == RECAPTCHA_V2
    assert page.injected_tokens == {}


def test_browser_use_captcha_metadata_returns_none_without_supported_captcha():
    page = FakeBrowserUsePage({})

    assert asyncio.run(detect_browser_use_captcha_metadata(page)) is None


def test_ohmycaptcha_client_solves_task_by_polling():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "processing"},
            {"status": "ready", "solution": {"gRecaptchaResponse": "solution-token"}},
        ],
        calls,
    )
    settings = OhMyCaptchaSettings(
        base_url="http://solver.test",
        client_key="client-key",
        poll_interval_seconds=0,
        max_wait_seconds=10,
    )
    client = OhMyCaptchaClient(
        settings=settings,
        opener=opener,
        sleep=lambda seconds: None,
    )

    result = client.solve_task(
        CaptchaTask(
            type=RECAPTCHA_V2_TASK,
            website_url="https://example.com/form",
            website_key="site-key-123",
        )
    )

    assert result.solved is True
    assert result.token == "solution-token"
    assert calls[0]["url"] == "http://solver.test/createTask"
    assert calls[0]["payload"] == {
        "clientKey": "client-key",
        "task": {
            "type": RECAPTCHA_V2_TASK,
            "websiteURL": "https://example.com/form",
            "websiteKey": "site-key-123",
        },
    }
    assert calls[1]["url"] == "http://solver.test/getTaskResult"
    assert calls[1]["payload"] == {"clientKey": "client-key", "taskId": "task-1"}


def test_ohmycaptcha_client_uses_explicit_recaptcha_v2_task_type_and_invisible_option():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "ready", "solution": {"gRecaptchaResponse": "solution-token"}},
        ],
        calls,
    )
    settings = OhMyCaptchaSettings(
        base_url="http://solver.test",
        client_key="client-key",
        poll_interval_seconds=0,
        max_wait_seconds=10,
    )
    client = OhMyCaptchaClient(settings=settings, opener=opener, sleep=lambda seconds: None)

    result = client.solve_task(
        CaptchaTask(
            type=NO_CAPTCHA_TASK,
            website_url="https://example.com/form",
            website_key="site-key-123",
            is_invisible=True,
        )
    )

    assert result.token == "solution-token"
    assert calls[0]["payload"]["task"] == {
        "type": NO_CAPTCHA_TASK,
        "websiteURL": "https://example.com/form",
        "websiteKey": "site-key-123",
        "isInvisible": True,
    }


def test_ohmycaptcha_client_builds_recaptcha_v3_payload():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "ready", "solution": {"gRecaptchaResponse": "v3-token"}},
        ],
        calls,
    )
    client = OhMyCaptchaClient(
        settings=OhMyCaptchaSettings(
            base_url="http://solver.test",
            client_key="client-key",
            poll_interval_seconds=0,
            max_wait_seconds=10,
        ),
        opener=opener,
        sleep=lambda seconds: None,
    )

    result = client.solve_task(
        CaptchaTask(
            type=RECAPTCHA_V3_TASK,
            website_url="https://example.com/form",
            website_key="v3-site-key",
            page_action="homepage",
        )
    )

    assert result.token == "v3-token"
    assert calls[0]["payload"]["task"] == {
        "type": RECAPTCHA_V3_TASK,
        "websiteURL": "https://example.com/form",
        "websiteKey": "v3-site-key",
        "pageAction": "homepage",
    }


def test_ohmycaptcha_client_can_use_turnstile_m1_task_type():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "ready", "solution": {"token": "turnstile-token"}},
        ],
        calls,
    )
    settings = OhMyCaptchaSettings(
        base_url="http://solver.test",
        client_key="client-key",
        poll_interval_seconds=0,
        max_wait_seconds=10,
    )
    client = OhMyCaptchaClient(
        settings=settings,
        opener=opener,
        sleep=lambda seconds: None,
    )

    result = client.solve_task(
        CaptchaTask(
            type=TURNSTILE_TASK_M1,
            website_url="https://example.com/form",
            website_key="turnstile-key",
        )
    )

    assert result.solved is True
    assert result.token == "turnstile-token"
    assert calls[0]["payload"]["task"] == {
        "type": TURNSTILE_TASK_M1,
        "websiteURL": "https://example.com/form",
        "websiteKey": "turnstile-key",
    }


def test_ohmycaptcha_client_builds_image_captcha_payload():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "ready", "solution": {"text": "abc123"}},
        ],
        calls,
    )
    client = OhMyCaptchaClient(
        settings=OhMyCaptchaSettings(
            base_url="http://solver.test",
            client_key="client-key",
            poll_interval_seconds=0,
            max_wait_seconds=10,
        ),
        opener=opener,
        sleep=lambda seconds: None,
    )

    result = client.solve_task(CaptchaTask(type=IMAGE_TO_TEXT_TASK, body="base64-image"))

    assert result.token == "abc123"
    assert calls[0]["payload"]["task"] == {
        "type": IMAGE_TO_TEXT_TASK,
        "body": "base64-image",
    }


def test_captcha_task_builds_classification_payloads():
    recaptcha_task = CaptchaTask(
        type=RECAPTCHA_V2_CLASSIFICATION_TASK,
        image="base64-image",
        question="Select all images with traffic lights",
    )
    hcaptcha_task = CaptchaTask(
        type=HCAPTCHA_CLASSIFICATION_TASK,
        queries=("base64-image-1", "base64-image-2"),
        question="Please click each image containing a bicycle",
    )

    assert recaptcha_task.to_payload() == {
        "type": RECAPTCHA_V2_CLASSIFICATION_TASK,
        "image": "base64-image",
        "question": "Select all images with traffic lights",
    }
    assert hcaptcha_task.to_payload() == {
        "type": HCAPTCHA_CLASSIFICATION_TASK,
        "queries": ["base64-image-1", "base64-image-2"],
        "question": "Please click each image containing a bicycle",
    }


def test_ohmycaptcha_client_builds_all_classification_payloads():
    calls = []
    opener = fake_opener(
        [
            {"errorId": 0, "taskId": "task-1"},
            {"status": "ready", "solution": {"objects": [1, 4]}},
            {"errorId": 0, "taskId": "task-2"},
            {"status": "ready", "solution": {"objects": [0, 3, 6]}},
            {"errorId": 0, "taskId": "task-3"},
            {"status": "ready", "solution": {"objects": [3]}},
            {"errorId": 0, "taskId": "task-4"},
            {"status": "ready", "solution": {"objects": [1]}},
        ],
        calls,
    )
    client = OhMyCaptchaClient(
        settings=OhMyCaptchaSettings(
            base_url="http://solver.test",
            client_key="client-key",
            poll_interval_seconds=0,
            max_wait_seconds=10,
        ),
        opener=opener,
        sleep=lambda seconds: None,
    )

    hcaptcha_result = client.solve_task(
        CaptchaTask(
            type=HCAPTCHA_CLASSIFICATION_TASK,
            queries=("base64-image-1", "base64-image-2"),
            question="Please click each image containing a bicycle",
        )
    )
    recaptcha_result = client.solve_task(
        CaptchaTask(
            type=RECAPTCHA_V2_CLASSIFICATION_TASK,
            image="base64-grid",
            question="Select all images with traffic lights",
        )
    )
    funcaptcha_result = client.solve_task(
        CaptchaTask(
            type=FUNCAPTCHA_CLASSIFICATION_TASK,
            image="base64-grid",
            question="Pick the image that shows a boat facing left",
        )
    )
    aws_result = client.solve_task(
        CaptchaTask(
            type=AWS_CLASSIFICATION_TASK,
            image="base64-image",
            question="Select the image that matches",
        )
    )

    assert hcaptcha_result.objects == [1, 4]
    assert recaptcha_result.objects == [0, 3, 6]
    assert funcaptcha_result.objects == [3]
    assert aws_result.objects == [1]
    assert calls[0]["payload"]["task"] == {
        "type": HCAPTCHA_CLASSIFICATION_TASK,
        "queries": ["base64-image-1", "base64-image-2"],
        "question": "Please click each image containing a bicycle",
    }
    assert calls[2]["payload"]["task"] == {
        "type": RECAPTCHA_V2_CLASSIFICATION_TASK,
        "image": "base64-grid",
        "question": "Select all images with traffic lights",
    }
    assert calls[4]["payload"]["task"] == {
        "type": FUNCAPTCHA_CLASSIFICATION_TASK,
        "image": "base64-grid",
        "question": "Pick the image that shows a boat facing left",
    }
    assert calls[6]["payload"]["task"] == {
        "type": AWS_CLASSIFICATION_TASK,
        "image": "base64-image",
        "question": "Select the image that matches",
    }


def test_ohmycaptcha_client_raises_api_errors():
    opener = fake_opener(
        [{"errorId": 1, "errorDescription": "bad task"}],
        [],
    )
    client = OhMyCaptchaClient(settings=OhMyCaptchaSettings(), opener=opener)

    with pytest.raises(CaptchaSolverApiError, match="bad task"):
        client.create_task(
            CaptchaTask(
                type=RECAPTCHA_V2_TASK,
                website_url="https://example.com/form",
                website_key="site-key-123",
            )
        )


class FakeCaptchaClient:
    def __init__(self):
        self.tasks = []

    def solve_task(self, task):
        self.tasks.append(task)
        return CaptchaSolveResult(
            task_id="task-1",
            status="ready",
            solution={"gRecaptchaResponse": "solution-token"},
        )


class TimeoutCaptchaClient:
    def solve_task(self, task):
        raise CaptchaSolverTimeoutError("task timed out")


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def fake_opener(responses, calls):
    queued_responses = list(responses)

    def open_request(request, timeout):
        payload = json.loads(request.data.decode("utf-8")) if request.data else None
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "payload": payload,
                "timeout": timeout,
            }
        )
        return FakeHttpResponse(queued_responses.pop(0))

    return open_request


class FakeBrowserUsePage:
    def __init__(self, elements, url="https://example.com/form"):
        self.elements = elements
        self.url = url
        self.injected_tokens = {}
        self.callback_invocations = []

    async def get_url(self):
        return self.url

    async def evaluate(self, page_function, *args):
        if "document.querySelector(selector) ? '1' : ''" in page_function:
            selector = args[0]
            return "1" if selector in self.elements else ""

        if "getAttribute(attributeName)" in page_function:
            selector, attribute_name = args
            return self.elements.get(selector, {}).get(attribute_name, "")

        if "updatedCount" in page_function:
            field_names, token = args
            for field_name in field_names:
                self.injected_tokens[field_name] = token
            return str(len(field_names))

        if "data-callback" in page_function:
            token = args[0]
            selector = ".cf-turnstile[data-callback]"
            if selector in self.elements:
                self.callback_invocations.append(token)
                return "1"
            return "0"

        raise AssertionError(f"Unexpected script: {page_function}")
