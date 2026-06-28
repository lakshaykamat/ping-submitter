import asyncio
from pathlib import Path
from types import SimpleNamespace

from app import create_app
from packages.browser_automation import copy_history_screenshots
from packages.browser_automation.client import (
    apply_cdp_request_headers,
    apply_playwright_stealth,
    browser_profile_options,
    browser_session_with_headers,
    playwright_stealth_script,
)
from packages.browser_automation.config import (
    BrowserAgentSettings,
    DEFAULT_BROWSER_ARGS,
    DEFAULT_BROWSER_HEADERS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
)
from packages.browser_automation.prompts import build_agent_task, target_url_context


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
    assert context["default_title"] == "example.com"


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
    assert "composed value must equal the target URL exactly once" in task
    assert "For blog/site/title/name fields" in task


def test_agent_task_allows_clear_and_replace_for_existing_field_values():
    task = build_agent_task(
        site={"url": "https://pingomatic.com/"},
        submitted_url="https://example.com",
        attempt_context={},
        min_delay=0.6,
        max_delay=2.0,
    )

    assert "input text with clear=True" in task
    assert "send keys such as select-all, Backspace, Delete, Enter" in task
    assert "use input with clear=True and the full replacement value" in task
    assert "If the field still has the wrong value" in task
    assert "select-all, Backspace/Delete" in task
    assert "type the exact value once" in task


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


def test_browser_profile_options_use_normal_local_browser_defaults(tmp_path):
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
        {"browser_profile_directory": str(tmp_path / "profile")},
    )

    assert options["headless"] is True
    assert options["use_cloud"] is False
    assert options["user_data_dir"] == str(tmp_path / "profile")
    assert options["user_agent"] == DEFAULT_USER_AGENT
    assert options["headers"] == DEFAULT_BROWSER_HEADERS
    assert options["headers"] is not DEFAULT_BROWSER_HEADERS
    assert options["headers"]["Accept-Language"] == "en-US,en;q=0.9"
    assert options["viewport"] == DEFAULT_VIEWPORT
    assert options["screen"] == DEFAULT_VIEWPORT
    assert options["window_size"] == DEFAULT_VIEWPORT
    assert options["accept_downloads"] is False
    assert options["permissions"] == []
    assert options["captcha_solver"] is False
    assert options["args"] == DEFAULT_BROWSER_ARGS


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
