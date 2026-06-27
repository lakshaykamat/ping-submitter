import asyncio

from flask import current_app

from engine.browser_agent.artifacts import copy_history_screenshots
from engine.browser_agent.config import (
    BrowserAgentSettings,
    DEFAULT_BROWSER_ARGS,
    DEFAULT_BROWSER_HEADERS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
    SESSION_TIMEOUT_SECONDS,
)
from engine.browser_agent.errors import BrowserUseAgentError
from engine.browser_agent.events import record_browser_session_event
from engine.browser_agent.results import parse_agent_result, result_with_history_metadata
from engine.prompts import build_agent_task


class BrowserUseAgentRunner:
    def __init__(self, agent_client=None, sleep=None, settings=None):
        self.agent_client = agent_client
        self.sleep = sleep
        self.settings = settings

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
        return self.settings or BrowserAgentSettings.from_flask_config(current_app.config)

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

        record_browser_session_event(site, attempt_context, settings)
        browser_profile = BrowserProfile(**browser_profile_options(settings, attempt_context))
        browser_session = browser_session_with_headers(BrowserSession)(browser_profile=browser_profile)
        agent = Agent(
            task=task,
            llm=ChatOpenAI(model=model),
            browser_session=browser_session,
            use_vision=True,
            vision_detail_level="high",
            llm_screenshot_size=(DEFAULT_VIEWPORT["width"], DEFAULT_VIEWPORT["height"]),
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
        return result_with_history_metadata(history, attempt_context, artifact_recorder)


def browser_profile_options(settings, attempt_context):
    return {
        "headless": settings.headless,
        "use_cloud": False,
        "user_data_dir": attempt_context.get("browser_profile_directory"),
        "user_agent": DEFAULT_USER_AGENT,
        "headers": dict(DEFAULT_BROWSER_HEADERS),
        "viewport": DEFAULT_VIEWPORT,
        "screen": DEFAULT_VIEWPORT,
        "window_size": DEFAULT_VIEWPORT,
        "accept_downloads": False,
        "permissions": [],
        "captcha_solver": False,
        "args": list(DEFAULT_BROWSER_ARGS),
    }


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


def browser_session_with_headers(base_session_class):
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
            await apply_cdp_request_headers(cdp_session)
            return await super()._navigate_and_wait(
                url,
                target_id,
                timeout=timeout,
                wait_until=wait_until,
                nav_timeout=nav_timeout,
            )

    return BrowserSessionWithHeaders
