from urllib.parse import parse_qs, urlparse

from packages.captcha_solver.detection import detect_captcha, selector_exists
from packages.captcha_solver.types import (
    HCAPTCHA,
    RECAPTCHA_V2,
    TASK_TYPE_BY_CAPTCHA_KIND,
    TURNSTILE,
    CaptchaMetadata,
    CaptchaTask,
)


SITE_KEY_SELECTORS_BY_KIND = {
    RECAPTCHA_V2: (
        ".g-recaptcha[data-sitekey]",
        '[data-sitekey][class*="g-recaptcha" i]',
        'iframe[src*="recaptcha"]',
    ),
    HCAPTCHA: (
        ".h-captcha[data-sitekey]",
        '[data-sitekey][class*="h-captcha" i]',
        'iframe[src*="hcaptcha"]',
    ),
    TURNSTILE: (
        ".cf-turnstile[data-sitekey]",
        '[data-sitekey][class*="cf-turnstile" i]',
        'iframe[src*="challenges.cloudflare.com"]',
    ),
}

SITE_KEY_QUERY_FIELDS = ("k", "sitekey", "render")


def detect_captcha_metadata(page, adapter=None):
    selector = detect_captcha(page, adapter=adapter)
    if not selector:
        return None

    kind = captcha_kind_for_selector(selector) or detect_captcha_kind_from_page(page)
    if not kind:
        return None

    website_key = find_site_key(page, kind)
    if not website_key:
        return None

    task = CaptchaTask(
        type=TASK_TYPE_BY_CAPTCHA_KIND[kind],
        website_url=current_page_url(page),
        website_key=website_key,
    )
    return CaptchaMetadata(kind=kind, selector=selector, task=task)


def captcha_kind_for_selector(selector):
    normalized_selector = selector.lower()
    if "hcaptcha" in normalized_selector or "h-captcha" in normalized_selector:
        return HCAPTCHA
    if "turnstile" in normalized_selector or "challenges.cloudflare.com" in normalized_selector:
        return TURNSTILE
    if "recaptcha" in normalized_selector or "g-recaptcha" in normalized_selector:
        return RECAPTCHA_V2
    return None


def detect_captcha_kind_from_page(page):
    for kind, selectors in SITE_KEY_SELECTORS_BY_KIND.items():
        if any(selector_exists(page, selector) for selector in selectors):
            return kind
    return None


def find_site_key(page, kind):
    for selector in SITE_KEY_SELECTORS_BY_KIND[kind]:
        site_key = first_attribute(page, selector, "data-sitekey")
        if site_key:
            return site_key

        frame_source = first_attribute(page, selector, "src")
        site_key = site_key_from_url(frame_source)
        if site_key:
            return site_key

    return None


def first_attribute(page, selector, attribute_name):
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return None
        first = getattr(locator, "first", locator)
        return first.get_attribute(attribute_name)
    except Exception:
        return None


def site_key_from_url(url):
    if not url:
        return None

    query = parse_qs(urlparse(url).query)
    for field_name in SITE_KEY_QUERY_FIELDS:
        values = query.get(field_name)
        if values and values[0] not in {"explicit", "onload"}:
            return values[0]
    return None


def current_page_url(page):
    page_url = getattr(page, "url", "")
    return page_url or ""
