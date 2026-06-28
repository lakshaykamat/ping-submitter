import asyncio
import logging
import time

from packages.captcha_solver.client import OhMyCaptchaClient
from packages.captcha_solver.errors import CaptchaSolverError, CaptchaSolverTimeoutError
from packages.captcha_solver.metadata import (
    SITE_KEY_SELECTORS_BY_KIND,
    captcha_kind_for_selector,
    site_key_from_url,
)
from packages.captcha_solver.types import (
    HCAPTCHA,
    RECAPTCHA_V2,
    RECAPTCHA_V3,
    TASK_TYPE_BY_CAPTCHA_KIND,
    TURNSTILE,
    BrowserUseCaptchaWaitResult,
    CaptchaMetadata,
    CaptchaTask,
)

logger = logging.getLogger(__name__)

CAPTCHA_SELECTORS_BY_KIND = {
    RECAPTCHA_V3: (
        'script[src*="recaptcha/api.js?render"]',
    ),
    RECAPTCHA_V2: (
        'iframe[src*="recaptcha"]',
        ".g-recaptcha",
    ),
    HCAPTCHA: (
        'iframe[src*="hcaptcha"]',
        ".h-captcha",
    ),
    TURNSTILE: (
        'iframe[src*="challenges.cloudflare.com"]',
        ".cf-turnstile",
        'script[src*="challenges.cloudflare.com/turnstile"]',
    ),
}

RESPONSE_FIELDS_BY_KIND = {
    RECAPTCHA_V2: ("g-recaptcha-response",),
    RECAPTCHA_V3: ("g-recaptcha-response",),
    HCAPTCHA: ("h-captcha-response",),
    TURNSTILE: ("cf-turnstile-response", "turnstile-response"),
}


async def solve_browser_use_captcha(page, client=None):
    metadata = await detect_browser_use_captcha_metadata(page)
    if metadata is None:
        return None

    started_at = time.monotonic()
    solver_client = client or OhMyCaptchaClient()
    logger.info("Detected %s CAPTCHA on %s.", metadata.kind, metadata.task.website_url)
    try:
        solve_result = await asyncio.to_thread(solver_client.solve_task, metadata.task)
    except CaptchaSolverTimeoutError:
        logger.warning("CAPTCHA solver timed out for %s.", metadata.task.website_url)
        return captcha_wait_result(metadata, started_at, "timeout")
    except CaptchaSolverError as error:
        logger.warning("CAPTCHA solver failed for %s: %s", metadata.task.website_url, error)
        return captcha_wait_result(metadata, started_at, "failed")

    injected_count = await inject_solution_token(page, metadata.kind, solve_result.token)
    if metadata.kind == TURNSTILE:
        injected_count += await notify_turnstile_callback(page, solve_result.token)
    duration_ms = int((time.monotonic() - started_at) * 1000)

    if solve_result.solved and injected_count > 0:
        result = "success"
    else:
        result = "failed"

    logger.info(
        "CAPTCHA solver result for %s: %s with %s updated fields.",
        metadata.task.website_url,
        result,
        injected_count,
    )
    return BrowserUseCaptchaWaitResult(
        waited=True,
        vendor=metadata.kind,
        url=metadata.task.website_url,
        duration_ms=duration_ms,
        result=result,
    )


def captcha_wait_result(metadata, started_at, result):
    return BrowserUseCaptchaWaitResult(
        waited=True,
        vendor=metadata.kind,
        url=metadata.task.website_url,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        result=result,
    )


async def detect_browser_use_captcha_metadata(page):
    selector = await first_matching_selector(page)
    if not selector:
        return None

    kind = captcha_kind_for_selector(selector)
    if not kind:
        return None

    website_key = await find_site_key(page, kind)
    if not website_key:
        return None

    website_url = await page.get_url()
    task = CaptchaTask(
        type=TASK_TYPE_BY_CAPTCHA_KIND[kind],
        website_url=website_url,
        website_key=website_key,
    )
    return CaptchaMetadata(kind=kind, selector=selector, task=task)


async def first_matching_selector(page):
    for kind, selectors in CAPTCHA_SELECTORS_BY_KIND.items():
        for selector in selectors:
            if await selector_exists(page, selector):
                return selector
        for selector in SITE_KEY_SELECTORS_BY_KIND[kind]:
            if await selector_exists(page, selector):
                return selector
    return None


async def find_site_key(page, kind):
    for selector in SITE_KEY_SELECTORS_BY_KIND[kind]:
        site_key = await first_attribute(page, selector, "data-sitekey")
        if site_key:
            return site_key

        frame_source = await first_attribute(page, selector, "src")
        site_key = site_key_from_url(frame_source)
        if site_key:
            return site_key

    return None


async def selector_exists(page, selector):
    value = await page.evaluate(
        "(selector) => document.querySelector(selector) ? '1' : ''",
        selector,
    )
    return value == "1"


async def first_attribute(page, selector, attribute_name):
    return await page.evaluate(
        """(selector, attributeName) => {
            const element = document.querySelector(selector);
            return element ? (element.getAttribute(attributeName) || '') : '';
        }""",
        selector,
        attribute_name,
    )


async def inject_solution_token(page, kind, token):
    if not token:
        return 0

    field_names = RESPONSE_FIELDS_BY_KIND[kind]
    count = await page.evaluate(
        """(fieldNames, tokenValue) => {
            let updatedCount = 0;
            const root = document.forms[0] || document.body || document.documentElement;

            for (const fieldName of fieldNames) {
                let fields = document.querySelectorAll(
                    `textarea[name="${fieldName}"], input[name="${fieldName}"]`
                );

                if (fields.length === 0 && root) {
                    const field = document.createElement('textarea');
                    field.name = fieldName;
                    field.style.display = 'none';
                    root.appendChild(field);
                    fields = [field];
                }

                for (const field of fields) {
                    field.value = tokenValue;
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                    field.dispatchEvent(new Event('change', { bubbles: true }));
                    updatedCount += 1;
                }
            }

            return String(updatedCount);
        }""",
        list(field_names),
        token,
    )
    return int(count or "0")


async def notify_turnstile_callback(page, token):
    if not token:
        return 0

    count = await page.evaluate(
        """(tokenValue) => {
            let calledCount = 0;
            const widgets = document.querySelectorAll('.cf-turnstile[data-callback]');
            for (const widget of widgets) {
                const callbackName = widget.getAttribute('data-callback');
                const callback = callbackName && window[callbackName];
                if (typeof callback === 'function') {
                    callback(tokenValue);
                    calledCount += 1;
                }
            }
            return String(calledCount);
        }""",
        token,
    )
    return int(count or "0")
