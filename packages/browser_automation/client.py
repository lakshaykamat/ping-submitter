import asyncio

from packages.browser_automation.artifacts import copy_history_screenshots
from packages.browser_automation.checkpoints import (
    detect_restricted_checkpoint,
    result_with_restricted_checkpoint,
)
from packages.browser_automation.config import (
    BrowserAgentSettings,
    DEFAULT_BROWSER_ARGS,
    DEFAULT_BROWSER_HEADERS,
    DEFAULT_USER_AGENT,
    SESSION_TIMEOUT_SECONDS,
    browser_args,
    detected_screen_size,
)
from packages.browser_automation.errors import BrowserUseAgentError
from packages.browser_automation.prompts import build_agent_task
from packages.browser_automation.results import parse_agent_result, result_with_history_metadata
from packages.browser_automation.types import DEFAULT_CAPTCHA_POLICY
from packages.captcha_solver import OhMyCaptchaClient, solve_browser_use_captcha

STEALTH_INIT_SCRIPT_ID_ATTR = "_job_assessment_playwright_stealth_init_script_id"
SOLVED_CAPTCHA_URLS_ATTR = "_job_assessment_solved_captcha_urls"
RESTRICTED_CHECKPOINT_ATTR = "_job_assessment_restricted_checkpoint"


class BrowserUseAgentRunner:
    def __init__(self, agent_client=None, sleep=None, settings=None, session_event_recorder=None):
        self.agent_client = agent_client
        self.sleep = sleep
        self.settings = settings
        self.session_event_recorder = session_event_recorder

    def submit_url(self, site, submitted_url, attempt_context):
        settings = self.current_settings()
        min_delay, max_delay = settings.action_delay_bounds()
        if self.sleep:
            self.sleep(min_delay)

        task = build_agent_task(
            site=site,
            submitted_url=submitted_url,
            attempt_context=attempt_context,
            min_delay=min_delay,
            max_delay=max_delay,
        )
        raw_result = self.run_agent(task, site, attempt_context, settings)
        return parse_agent_result(raw_result)

    def current_settings(self):
        if self.settings is None:
            raise BrowserUseAgentError("BrowserAgentSettings must be provided.")
        return self.settings

    def run_agent(self, task, site, attempt_context, settings):
        if self.agent_client:
            return self.agent_client.run(task=task, site=site)
        return asyncio.run(self.run_browser_use(task, site, attempt_context, settings))

    async def run_browser_use(self, task, site, attempt_context, settings):
        try:
            from browser_use.beta import Agent, BrowserProfile, BrowserSession, ChatOpenAI
        except ImportError:
            try:
                from browser_use import Agent, BrowserProfile, BrowserSession, ChatOpenAI
            except ImportError as fallback_error:
                raise BrowserUseAgentError(
                    "local browser-use is not installed. Run pip install -r requirements.txt."
                ) from fallback_error

        model = settings.agentic_llm_model
        if not model:
            raise BrowserUseAgentError("AGENTIC_LLM_MODEL must be set for local browser-use.")

        if self.session_event_recorder:
            self.session_event_recorder(site, attempt_context, settings)

        browser_size = detected_screen_size()
        browser_profile = BrowserProfile(**browser_profile_options(settings, attempt_context))
        captcha_client = captcha_solver_client(settings, attempt_context)
        browser_session_class = browser_session_with_headers(
            BrowserSession,
            captcha_policy=(attempt_context or {}).get("captcha_policy", DEFAULT_CAPTCHA_POLICY),
            captcha_client=captcha_client,
        )
        browser_session = browser_session_class(browser_profile=browser_profile)
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model=model),
            browser_session=browser_session,
            use_vision=True,
            vision_detail_level="high",
            llm_screenshot_size=(browser_size["width"], browser_size["height"]),
            max_actions_per_step=1,
        )
        history = await asyncio.wait_for(
            agent.run(max_steps=settings.agentic_max_steps),
            timeout=SESSION_TIMEOUT_SECONDS,
        )
        artifact_recorder = lambda found_history, found_context: copy_history_screenshots(
            found_history,
            found_context,
            settings.artifact_dir,
        )
        raw_result = result_with_history_metadata(history, attempt_context, artifact_recorder)
        checkpoint = getattr(browser_session, RESTRICTED_CHECKPOINT_ATTR, None)
        return result_with_restricted_checkpoint(raw_result, checkpoint)


def browser_profile_options(settings, attempt_context):
    attempt_context = attempt_context or {}
    browser_size = detected_screen_size()
    return {
        "headless": settings.headless,
        "use_cloud": False,
        "user_data_dir": attempt_context.get("browser_profile_directory"),
        "user_agent": DEFAULT_USER_AGENT,
        "headers": dict(DEFAULT_BROWSER_HEADERS),
        "viewport": browser_size,
        "screen": browser_size,
        "window_size": browser_size,
        "accept_downloads": False,
        "permissions": [],
        "captcha_solver": captcha_solving_enabled(attempt_context),
        "args": browser_args(browser_size),
    }


def captcha_solving_enabled(attempt_context):
    return (attempt_context or {}).get("captcha_policy", DEFAULT_CAPTCHA_POLICY) == "solve"


def captcha_solver_client(settings, attempt_context):
    if not captcha_solving_enabled(attempt_context):
        return None
    return OhMyCaptchaClient(settings=settings.captcha_solver_settings())


async def apply_cdp_request_headers(cdp_session, headers=None):
    request_headers = dict(headers or DEFAULT_BROWSER_HEADERS)
    await cdp_session.cdp_client.send.Network.enable(session_id=cdp_session.session_id)
    await cdp_session.cdp_client.send.Network.setUserAgentOverride(
        params={
            "userAgent": DEFAULT_USER_AGENT,
            "acceptLanguage": request_headers["Accept-Language"],
            "platform": "macOS",
        },
        session_id=cdp_session.session_id,
    )
    await cdp_session.cdp_client.send.Network.setExtraHTTPHeaders(
        params={"headers": request_headers},
        session_id=cdp_session.session_id,
    )


def playwright_stealth_script():
    try:
        from playwright_stealth import Stealth
    except ImportError as import_error:
        raise BrowserUseAgentError(
            "playwright-stealth is not installed. Run pip install -r requirements.txt."
        ) from import_error

    stealth = Stealth(
        navigator_platform_override="MacIntel",
        navigator_user_agent_override=DEFAULT_USER_AGENT,
        webgl_renderer_override="Intel Iris OpenGL Engine",
        webgl_vendor_override="Intel Inc.",
    )
    return stealth.script_payload


async def apply_playwright_stealth(cdp_session, script=None):
    if getattr(cdp_session, STEALTH_INIT_SCRIPT_ID_ATTR, None):
        return

    stealth_script = script if script is not None else playwright_stealth_script()
    if not stealth_script:
        return

    result = await cdp_session.cdp_client.send.Page.addScriptToEvaluateOnNewDocument(
        params={"source": stealth_script, "runImmediately": True},
        session_id=cdp_session.session_id,
    )
    script_identifier = result.get("identifier") if isinstance(result, dict) else None
    setattr(cdp_session, STEALTH_INIT_SCRIPT_ID_ATTR, script_identifier or True)


def browser_session_with_headers(
    base_session_class,
    captcha_policy=DEFAULT_CAPTCHA_POLICY,
    captcha_client=None,
):
    class BrowserSessionWithHeaders(base_session_class):
        async def _navigate_and_wait(
            self,
            url,
            target_id,
            timeout=None,
            wait_until="load",
            nav_timeout=None,
        ):
            cdp_session = await self.get_or_create_cdp_session(target_id, focus=False)
            await apply_playwright_stealth(cdp_session)
            await apply_cdp_request_headers(cdp_session)
            return await super()._navigate_and_wait(
                url,
                target_id,
                timeout=timeout,
                wait_until=wait_until,
                nav_timeout=nav_timeout,
            )

        async def wait_if_captcha_solving(self, timeout=None):
            browser_use_result = await super().wait_if_captcha_solving(timeout=timeout)
            if browser_use_result is not None:
                return browser_use_result

            page = await self.get_current_page()
            if page is None:
                return None

            checkpoint = await detect_restricted_checkpoint(page)
            if checkpoint is not None:
                setattr(self, RESTRICTED_CHECKPOINT_ATTR, checkpoint)

            if captcha_policy != "solve":
                return None

            page_url = await page.get_url()
            solved_urls = getattr(self, SOLVED_CAPTCHA_URLS_ATTR, set())
            if page_url in solved_urls:
                return None

            captcha_result = await solve_browser_use_captcha(page, client=captcha_client)
            if captcha_result is None:
                return None

            if captcha_result.result == "success":
                solved_urls.add(page_url)
                setattr(self, SOLVED_CAPTCHA_URLS_ATTR, solved_urls)

            return captcha_result

    return BrowserSessionWithHeaders
