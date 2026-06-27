import json
from urllib.parse import urlparse

from engine.types import (
    AGENT_BROWSER_TOOLS,
    AGENT_LOOP_STEPS,
    AGENT_OUTPUT_KEYS,
    AGENT_REDACTED_CONTEXT_KEY_TERMS,
    CAPTCHA_FAILURE_REASON,
)


def build_agent_task(site, submitted_url, attempt_context, min_delay, max_delay):
    context = redacted_context(attempt_context)
    target_url = target_url_context(submitted_url)
    return "\n".join(
        [
            f"Goal: open {site['url']} and submit this URL: {submitted_url}",
            f"Target URL variants: {json.dumps(target_url, sort_keys=True)}",
            profile_instruction(context.get("browser_profile_directory")),
            f"Approved site memory: {json.dumps(context.get('approved_site_memory') or [], sort_keys=True)}",
            f"Loop until done: {', '.join(AGENT_LOOP_STEPS)}.",
            f"Use browser tools when needed: {', '.join(AGENT_BROWSER_TOOLS)}.",
            "Take all required browser actions yourself. Do not wait for user permission, operator review, manual CAPTCHA entry, or human confirmation.",
            "Use the screenshot/visual state first, then visible labels, placeholders, ARIA names, input types, nearby text, and DOM context to choose form fields.",
            "Make exactly one browser action at a time, then observe the next screenshot before deciding the next action.",
            "Scroll only when a task-relevant field, button, confirmation, or error message may be outside the visible viewport.",
            "Do not perform random scrolling, fake mouse movement, or other actions whose purpose is to imitate a human or disguise automation.",
            "For URL fields, visually inspect prefixes and placeholders before typing. If a field already shows a fixed http:// or https:// prefix beside or inside it, type only the target_url.without_scheme value from Target URL variants. Otherwise type the target_url.full value exactly once.",
            "After typing any URL, visually verify the composed value is the target URL exactly once. If it shows a duplicated scheme such as https://https://, clear the field and correct it before submitting.",
            "Fill required companion fields needed for submission. For blog/site/title/name fields, use target_url.default_title unless a better value is visible. Leave optional RSS/feed/email fields empty unless the page requires them.",
            "Select required service/category checkboxes when the form presents them as part of the submission workflow.",
            "Recover from wrong pages, redirects, expired pages, blank pages, and intermediate screens.",
            "Classify the page before acting: landing page, consent screen, submission form, multi-step form, success confirmation, site error, CAPTCHA, login gate, rate limit, access block, restricted checkpoint, or uncertain state.",
            f"Wait at least {min_delay} and at most {max_delay} seconds between browser actions. Do not click randomly.",
            "After clicking submit, wait for the visible page to settle, inspect the screenshot and page text, and continue only if another required confirmation step is visible.",
            "Stop once the site confirms acceptance. Do not continue browsing after success.",
            f"If CAPTCHA appears, return status failed with evidence.reason set to: {CAPTCHA_FAILURE_REASON}",
            "If the page indicates rate limiting, automated-traffic blocking, access denied, forbidden, unavailable service, or another anti-abuse checkpoint, return status restricted_checkpoint with evidence.reason explaining the visible block.",
            "If login is required and credentials are unavailable, return status login_required.",
            "If payment, signup, account changes, deletion, subscription, email/OTP verification, or another unsupported irreversible step is required, return status skipped.",
            "Do not request human review, a human checkpoint, manual browser control, or out-of-band assistance.",
            "Always include a concise message explaining success, failure, skip, or uncertainty. Include evidence.reason when the status is not success.",
            "When useful, include evidence.strategy_summary with required fields, common buttons, success evidence, checkpoint patterns, and failure reasons.",
            f"Return compact JSON only with keys: {', '.join(AGENT_OUTPUT_KEYS)}.",
            f"Attempt context: {json.dumps(context, sort_keys=True)}",
        ]
    )


def profile_instruction(profile_directory):
    if profile_directory:
        return f"Use the approved persisted browser profile directory: {profile_directory}"
    return "No persisted browser profile is approved for this run."


def redacted_context(context):
    return {
        key: value
        for key, value in (context or {}).items()
        if not contains_sensitive_term(key)
    }


def contains_sensitive_term(value):
    normalized = str(value).lower()
    return any(term in normalized for term in AGENT_REDACTED_CONTEXT_KEY_TERMS)


def target_url_context(submitted_url):
    parsed = urlparse(submitted_url)
    without_scheme = submitted_url
    if parsed.netloc:
        without_scheme = parsed.netloc + parsed.path
        if parsed.params:
            without_scheme += f";{parsed.params}"
        if parsed.query:
            without_scheme += f"?{parsed.query}"
        if parsed.fragment:
            without_scheme += f"#{parsed.fragment}"

    hostname = parsed.hostname or parsed.netloc or submitted_url
    default_title = hostname.replace("www.", "", 1) or "Submitted URL"
    return {
        "full": submitted_url,
        "scheme": parsed.scheme,
        "without_scheme": without_scheme,
        "hostname": hostname,
        "default_title": default_title,
    }
