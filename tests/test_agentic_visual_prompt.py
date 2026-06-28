import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import create_app
from packages.browser_automation import copy_history_screenshots
from packages.browser_automation.client import (
    apply_cdp_request_headers,
    apply_playwright_stealth,
    browser_profile_options,
    browser_session_with_headers,
    captcha_solving_enabled,
    captcha_solver_client,
    playwright_stealth_script,
)
from packages.browser_automation.config import (
    BrowserAgentSettings,
    DEFAULT_BROWSER_ARGS,
    DEFAULT_BROWSER_HEADERS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
    detected_screen_size,
)
from packages.browser_automation.prompts import (
    accepted_url_value_context,
    build_agent_task,
    target_url_context,
)
from packages.browser_automation.types import AGENT_BROWSER_TOOLS
from packages.captcha_solver import (
    CaptchaSolveResult,
    CaptchaTask,
    RECAPTCHA_V2_TASK,
)


class FakeHistory:
    def __init__(self, screenshot_paths):
        self._screenshot_paths = screenshot_paths

    def is_done(self):
        return True

    def is_successful(self):
        return None

    def number_of_steps(self):
        return len(self._screenshot_paths)

    def urls(self):
        return ["https://example.test"]

    def screenshot_paths(self):
        return self._screenshot_paths


def test_target_url_context_includes_without_scheme():
    context = target_url_context("https://example.com/path?a=1#top")

    assert context["full"] == "https://example.com/path?a=1#top"
    assert context["scheme"] == "https"
    assert context["without_scheme"] == "example.com/path?a=1#top"
    assert context["hostname"] == "example.com"
    assert context["default_title"] == "Example"


@pytest.mark.parametrize(
    ("submitted_url", "hostname", "without_scheme", "default_title"),
    [
        ("https://example.com", "example.com", "example.com", "Example"),
        ("http://example.com", "example.com", "example.com", "Example"),
        ("https://www.example.com/path", "www.example.com", "www.example.com/path", "Example"),
        (
            "https://my-example-site.com:8443/a/b?x=1#top",
            "my-example-site.com",
            "my-example-site.com:8443/a/b?x=1#top",
            "My Example Site",
        ),
        ("https://blog.company-name.io", "blog.company-name.io", "blog.company-name.io", "Company Name"),
        ("https://www.example.co.uk/path", "www.example.co.uk", "www.example.co.uk/path", "Example"),
        ("https://service.example.com.au", "service.example.com.au", "service.example.com.au", "Example"),
        ("https://localhost:5000/ping", "localhost", "localhost:5000/ping", "Localhost"),
        ("https://127.0.0.1:5000/ping", "127.0.0.1", "127.0.0.1:5000/ping", "Submitted URL"),
    ],
)
def test_target_url_context_derives_safe_form_values(
    submitted_url,
    hostname,
    without_scheme,
    default_title,
):
    context = target_url_context(submitted_url)

    assert context["full"] == submitted_url
    assert context["hostname"] == hostname
    assert context["without_scheme"] == without_scheme
    assert context["default_title"] == default_title


@pytest.mark.parametrize(
    ("submitted_url", "accepted_values"),
    [
        ("https://example.com", ["https://example.com", "http://example.com"]),
        ("http://example.com", ["http://example.com", "https://example.com"]),
        (
            "https://example.com/path?a=1#top",
            ["https://example.com/path?a=1#top", "http://example.com/path?a=1#top"],
        ),
        (
            "https://my-example-site.com:8443/a/b",
            ["https://my-example-site.com:8443/a/b", "http://my-example-site.com:8443/a/b"],
        ),
    ],
)
def test_accepted_url_values_are_exact_scheme_variants(submitted_url, accepted_values):
    context = target_url_context(submitted_url)

    assert accepted_url_value_context(context) == accepted_values


def test_agent_task_requires_visual_url_prefix_handling():
    task = build_agent_task(
        site={"url": "https://service.test/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "Use the screenshot first" in task
    assert "Take one browser action, observe" in task
    assert "target_url.without_scheme" in task
    assert '"without_scheme": "example.com"' in task
    assert "Accepted final URL field values" in task
    assert "URL fields: inspect the current editable value and nearby fixed prefix before typing" in task
    assert "If the editable value is exactly http:// or https://" in task
    assert "type only target_url.without_scheme once" in task
    assert "Do not append to any existing domain, path, or partial URL" in task
    assert "must equal one accepted final URL value with one scheme only" in task
    assert "http:/example.com" in task
    assert "http://http://example.com" in task
    assert "example.comexample.com" in task
    assert "For blog/site/title/name fields" in task
    assert "use target_url.default_title, not target_url.hostname or target_url.without_scheme" in task
    assert "For email fields, leave empty unless required and no approved email is available" in task
    assert "Never fill every text field with the URL, hostname, or example.com" in task


def test_agent_task_embeds_readable_title_not_domain_for_non_url_fields():
    task = build_agent_task(
        site={"url": "https://service.test/"},
        submitted_url="https://my-example-site.com/path",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert '"default_title": "My Example Site"' in task
    assert '"hostname": "my-example-site.com"' in task
    assert '"without_scheme": "my-example-site.com/path"' in task
    assert "For blog/site/title/name fields, use target_url.default_title" in task
    assert "Never fill every text field with the URL, hostname, or example.com" in task


def test_agent_task_lists_every_browser_tool_for_form_access_and_rewriting():
    task = build_agent_task(
        site={"url": "https://service.test/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    for tool_name in AGENT_BROWSER_TOOLS:
        assert tool_name in task


def test_agent_task_exposes_approved_memory_but_redacts_sensitive_context():
    task = build_agent_task(
        site={"url": "https://service.test/"},
        submitted_url="https://example.com",
        attempt_context={
            "approved_site_memory": [{"email": "approved@example.test", "name": "Approved User"}],
            "api_key": "secret-key",
            "session_token": "secret-token",
            "site_note": "safe note",
        },
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "approved@example.test" in task
    assert "Approved User" in task
    assert "safe note" in task
    assert "secret-key" not in task
    assert "secret-token" not in task


def test_agent_task_keeps_clear_and_replace_for_non_url_field_values():
    task = build_agent_task(
        site={"url": "https://pingomatic.com/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "input text with clear=True" in task
    assert "inspect DOM/input values" in task
    assert "send keys such as select-all, Backspace, Delete, Enter" in task
    assert "Text fields: use input with clear=True" in task
    assert "If wrong text remains" in task
    assert "select-all, Backspace/Delete" in task
    assert "type the exact value once" in task


def test_agent_task_requires_review_before_submit_and_visible_success_after_submit():
    task = build_agent_task(
        site={"url": "https://pingomatic.com/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "verify the visible result" in task
    assert "Before clicking submit, review required fields once more" in task
    assert "After submit, wait for navigation, redirect, or an in-page update to settle" in task
    assert "Return status success only when the current page visibly confirms acceptance" in task
    assert "If clicking submit leaves you on the same form with no visible confirmation" in task


def test_agent_task_allows_scrolling_to_find_hidden_forms():
    task = build_agent_task(
        site={"url": "https://pingomatic.com/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "scroll down/up" in task
    assert "If the form or submit controls are not visible" in task
    assert "scroll down in useful increments" in task
    assert "scroll back up and inspect earlier sections" in task


def test_agent_task_uses_solver_instruction_when_captcha_policy_is_solve():
    task = build_agent_task(
        site={"url": "https://pingomatic.com/"},
        submitted_url="https://example.com",
        attempt_context={"captcha_policy": "solve"},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "wait for the configured solver to finish" in task
    assert "CAPTCHA solving is not implemented" not in task


def test_copy_history_screenshots_deduplicates_and_records_events(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"fake image")
    history = FakeHistory([None, str(source), str(source)])
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "REPORT_DIR": str(tmp_path / "reports"),
            "ARTIFACT_DIR": str(tmp_path / "artifacts"),
            "BROWSER_PROFILE_DIR": str(tmp_path / "profiles"),
        }
    )

    with app.app_context():
        copied = copy_history_screenshots(
            history,
            {
                "job_id": "job-1",
                "attempt_id": 12,
                "site_id": "site-1",
                "submitted_url": "https://example.com",
            },
            app.config["ARTIFACT_DIR"],
        )

    assert copied == [str(Path(app.config["ARTIFACT_DIR"]) / "job-1" / "12" / "agent_step_01.png")]
    assert Path(copied[0]).read_bytes() == b"fake image"


def test_browser_profile_options_use_detected_fullscreen_browser_size(tmp_path, monkeypatch):
    detected_screen_size.cache_clear()
    monkeypatch.setattr(
        "packages.browser_automation.client.detected_screen_size",
        lambda: {"width": 2560, "height": 1440},
    )
    settings = BrowserAgentSettings(
        headless=True,
        navigation_timeout_ms=30000,
        action_timeout_ms=10000,
        slow_mo_ms=0,
        agentic_llm_model="gpt-test",
        agentic_max_steps=80,
        min_action_delay_seconds=0.6,
        max_action_delay_seconds=2.0,
        artifact_dir=tmp_path / "artifacts",
    )

    options = browser_profile_options(
        settings,
        {"browser_profile_directory": str(tmp_path / "profile"), "captcha_policy": "none"},
    )

    assert options["headless"] is True
    assert options["use_cloud"] is False
    assert options["user_data_dir"] == str(tmp_path / "profile")
    assert options["user_agent"] == DEFAULT_USER_AGENT
    assert options["headers"] == DEFAULT_BROWSER_HEADERS
    assert options["headers"] is not DEFAULT_BROWSER_HEADERS
    assert options["headers"]["Accept-Language"] == "en-US,en;q=0.9"
    assert options["viewport"] == {"width": 2560, "height": 1440}
    assert options["screen"] == {"width": 2560, "height": 1440}
    assert options["window_size"] == {"width": 2560, "height": 1440}
    assert options["accept_downloads"] is False
    assert options["permissions"] == []
    assert options["captcha_solver"] is False
    assert options["args"][: len(DEFAULT_BROWSER_ARGS)] == DEFAULT_BROWSER_ARGS
    assert "--start-fullscreen" in options["args"]
    assert "--start-maximized" in options["args"]
    assert "--window-size=2560,1440" in options["args"]


def test_detected_screen_size_falls_back_to_default_viewport(monkeypatch):
    detected_screen_size.cache_clear()

    class FailingTkinter:
        class Tk:
            def __init__(self):
                raise RuntimeError("no display")

    monkeypatch.setitem(__import__("sys").modules, "tkinter", FailingTkinter)

    assert detected_screen_size() == DEFAULT_VIEWPORT


def test_browser_profile_options_enable_captcha_solver_for_solve_policy(tmp_path):
    settings = BrowserAgentSettings(
        headless=True,
        navigation_timeout_ms=30000,
        action_timeout_ms=10000,
        slow_mo_ms=0,
        agentic_llm_model="gpt-test",
        agentic_max_steps=80,
        min_action_delay_seconds=0.6,
        max_action_delay_seconds=2.0,
        artifact_dir=tmp_path / "artifacts",
    )

    options = browser_profile_options(
        settings,
        {
            "browser_profile_directory": str(tmp_path / "profile"),
            "captcha_policy": "solve",
        },
    )

    assert captcha_solving_enabled({"captcha_policy": "solve"}) is True
    assert captcha_solving_enabled({}) is True
    assert captcha_solving_enabled({"captcha_policy": "none"}) is False
    assert options["captcha_solver"] is True


def test_captcha_solver_client_uses_browser_agent_settings(tmp_path):
    settings = BrowserAgentSettings(
        headless=True,
        navigation_timeout_ms=30000,
        action_timeout_ms=10000,
        slow_mo_ms=0,
        agentic_llm_model="gpt-test",
        agentic_max_steps=80,
        min_action_delay_seconds=0.6,
        max_action_delay_seconds=2.0,
        artifact_dir=tmp_path / "artifacts",
        ohmycaptcha_base_url="http://127.0.0.1:8000",
        ohmycaptcha_client_key="client-key",
    )

    client = captcha_solver_client(settings, {"captcha_policy": "solve"})

    assert client.settings.base_url == "http://127.0.0.1:8000"
    assert client.settings.client_key == "client-key"
    assert captcha_solver_client(settings, {"captcha_policy": "none"}) is None


class FakeNetworkCommands:
    def __init__(self):
        self.calls = []

    async def enable(self, session_id):
        self.calls.append(("enable", session_id))

    async def setUserAgentOverride(self, params, session_id):
        self.calls.append(("setUserAgentOverride", params, session_id))

    async def setExtraHTTPHeaders(self, params, session_id):
        self.calls.append(("setExtraHTTPHeaders", params, session_id))


class FakePageCommands:
    def __init__(self):
        self.calls = []

    async def addScriptToEvaluateOnNewDocument(self, params, session_id):
        self.calls.append(("addScriptToEvaluateOnNewDocument", params, session_id))
        return {"identifier": "stealth-script-1"}


class FakeCdpSession:
    def __init__(self):
        self.session_id = "cdp-session-1"
        self.network = FakeNetworkCommands()
        self.page = FakePageCommands()
        self.cdp_client = SimpleNamespace(send=SimpleNamespace(Network=self.network, Page=self.page))


def test_apply_cdp_request_headers_sets_user_agent_and_headers():
    cdp_session = FakeCdpSession()

    asyncio.run(apply_cdp_request_headers(cdp_session))

    assert cdp_session.network.calls == [
        ("enable", "cdp-session-1"),
        (
            "setUserAgentOverride",
            {
                "userAgent": DEFAULT_USER_AGENT,
                "acceptLanguage": DEFAULT_BROWSER_HEADERS["Accept-Language"],
                "platform": "macOS",
            },
            "cdp-session-1",
        ),
        (
            "setExtraHTTPHeaders",
            {"headers": DEFAULT_BROWSER_HEADERS},
            "cdp-session-1",
        ),
    ]


def test_playwright_stealth_script_uses_mac_browser_overrides():
    script = playwright_stealth_script()

    assert "navigator.webdriver" in script
    assert '"navigator_platform": "MacIntel"' in script
    assert DEFAULT_USER_AGENT in script
    assert "HeadlessChrome" in script


def test_apply_playwright_stealth_adds_init_script_once():
    cdp_session = FakeCdpSession()

    asyncio.run(apply_playwright_stealth(cdp_session, script="(() => window.__stealth = true)();"))
    asyncio.run(apply_playwright_stealth(cdp_session, script="(() => window.__stealth = true)();"))

    assert cdp_session.page.calls == [
        (
            "addScriptToEvaluateOnNewDocument",
            {"source": "(() => window.__stealth = true)();", "runImmediately": True},
            "cdp-session-1",
        )
    ]


def test_browser_session_wrapper_applies_headers_before_navigation():
    calls = []
    cdp_session = FakeCdpSession()

    class FakeBrowserSession:
        async def get_or_create_cdp_session(self, target_id, focus=False):
            calls.append(("get_or_create_cdp_session", target_id, focus))
            return cdp_session

        async def _navigate_and_wait(
            self,
            url,
            target_id,
            timeout=None,
            wait_until="load",
            nav_timeout=None,
        ):
            calls.append(("navigate", url, target_id, timeout, wait_until, nav_timeout))
            return "navigated"

    WrappedSession = browser_session_with_headers(FakeBrowserSession)
    result = asyncio.run(
        WrappedSession()._navigate_and_wait(
            "https://example.test",
            "target-1",
            timeout=3,
            wait_until="domcontentloaded",
            nav_timeout=5,
        )
    )

    assert result == "navigated"
    assert calls == [
        ("get_or_create_cdp_session", "target-1", False),
        ("navigate", "https://example.test", "target-1", 3, "domcontentloaded", 5),
    ]
    assert cdp_session.page.calls[0][0] == "addScriptToEvaluateOnNewDocument"
    assert cdp_session.page.calls[0][1]["runImmediately"] is True
    assert cdp_session.network.calls[0] == ("enable", "cdp-session-1")
    assert cdp_session.network.calls[1][0] == "setUserAgentOverride"
    assert cdp_session.network.calls[2] == (
        "setExtraHTTPHeaders",
        {"headers": DEFAULT_BROWSER_HEADERS},
        "cdp-session-1",
    )


def test_browser_session_wrapper_solves_visible_captcha_with_configured_client():
    class FakeBrowserSession:
        async def wait_if_captcha_solving(self, timeout=None):
            return None

        async def get_current_page(self):
            return FakeBrowserUsePage(
                {
                    ".g-recaptcha": {},
                    ".g-recaptcha[data-sitekey]": {"data-sitekey": "site-key-123"},
                }
            )

    client = FakeCaptchaClient()
    WrappedSession = browser_session_with_headers(
        FakeBrowserSession,
        captcha_policy="solve",
        captcha_client=client,
    )

    result = asyncio.run(WrappedSession().wait_if_captcha_solving())

    assert result.waited is True
    assert result.result == "success"
    assert client.tasks == [
        CaptchaTask(
            type=RECAPTCHA_V2_TASK,
            website_url="https://example.com/form",
            website_key="site-key-123",
        )
    ]


def test_browser_session_wrapper_does_not_solve_captcha_when_policy_is_none():
    class FakeBrowserSession:
        async def wait_if_captcha_solving(self, timeout=None):
            return None

        async def get_current_page(self):
            return FakeBrowserUsePage(
                {
                    ".g-recaptcha": {},
                    ".g-recaptcha[data-sitekey]": {"data-sitekey": "site-key-123"},
                }
            )

    client = FakeCaptchaClient()
    WrappedSession = browser_session_with_headers(
        FakeBrowserSession,
        captcha_policy="none",
        captcha_client=client,
    )

    assert asyncio.run(WrappedSession().wait_if_captcha_solving()) is None
    assert client.tasks == []


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


class FakeBrowserUsePage:
    def __init__(self, elements, url="https://example.com/form"):
        self.elements = elements
        self.url = url

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
            field_names, _token = args
            return str(len(field_names))

        if "data-callback" in page_function:
            return "0"

        if "document.title" in page_function:
            return ""

        if "document.body" in page_function:
            return ""

        raise AssertionError(f"Unexpected script: {page_function}")
