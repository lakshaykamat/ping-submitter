import json
import asyncio
from dataclasses import dataclass

import pytest

from packages.captcha_solver import (
    RECAPTCHA_V2,
    RECAPTCHA_V2_TASK,
    TURNSTILE,
    TURNSTILE_TASK,
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

        raise AssertionError(f"Unexpected script: {page_function}")
