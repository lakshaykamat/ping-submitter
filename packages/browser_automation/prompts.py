import json
from urllib.parse import urlparse

from packages.browser_automation.types import (
    AGENT_BROWSER_TOOLS,
    AGENT_LOOP_STEPS,
    AGENT_OUTPUT_KEYS,
    AGENT_REDACTED_CONTEXT_KEY_TERMS,
    CAPTCHA_FAILURE_REASON,
    DEFAULT_CAPTCHA_POLICY,
)


def build_agent_task(site, submitted_url, attempt_context, min_delay, max_delay):
    context = redacted_context(attempt_context)
    target_url = target_url_context(submitted_url)
    accepted_url_values = accepted_url_value_context(target_url)
    return "\n".join(
        [
            f"Goal: open {site['url']} and submit this URL: {submitted_url}",
            f"Target URL variants: {json.dumps(target_url, sort_keys=True)}",
            f"Accepted final URL field values: {json.dumps(accepted_url_values, sort_keys=True)}",
            profile_instruction(context.get("browser_profile_directory")),
            f"Approved site memory: {json.dumps(context.get('approved_site_memory') or [], sort_keys=True)}",
            f"Loop until done: {', '.join(AGENT_LOOP_STEPS)}.",
            f"Use browser tools when needed: {', '.join(AGENT_BROWSER_TOOLS)}.",
            "Act independently. Do not wait for human review, manual CAPTCHA entry, or permission to continue.",
            "Use the screenshot first, then visible labels, placeholders, ARIA names, input types, nearby text, and DOM context.",
            "Take one browser action, observe, review whether that action produced the expected visible result, then decide the next action.",
            "If the form or submit controls are not visible, scroll down in useful increments and inspect after each scroll. If you reach the bottom, scroll back up and inspect earlier sections before deciding the form is unavailable.",
            "Do not do random scrolling, fake mouse movement, or other disguise-only actions.",
            "When replacing text in non-URL fields, use input with clear=True and the full replacement value. If the field still has the wrong value, use send keys: select-all, Backspace/Delete, then type the exact value once.",
            "For URL fields: first decide whether any http:// or https:// prefix is editable text inside the input or an uneditable label next to it.",
            "If a URL input already contains editable text exactly like http:// or https://, preserve that prefix, place the cursor after it, and type target_url.without_scheme. Do not clear that prefix or type another scheme into that field.",
            "If a fixed uneditable http:// or https:// prefix is shown beside the URL field, enter target_url.without_scheme in the editable input. Otherwise enter target_url.full.",
            "After entering a URL, review the field value and nearby prefix before submitting. The visible/composed URL must be one of the accepted final URL field values, with exactly one scheme prefix.",
            "Never submit malformed or duplicated schemes such as http:/example.com, https:/example.com, http://http://example.com, or https://https://example.com. If you see one, correct it before clicking submit.",
            "For blog/site/title/name fields, use target_url.default_title unless a better visible value is required. Leave optional RSS/feed/email fields empty unless required.",
            "Select required service/category checkboxes.",
            "Recover from wrong pages, redirects, expired pages, blank pages, and intermediate screens.",
            f"Wait at least {min_delay} and at most {max_delay} seconds between browser actions. Do not click randomly.",
            "Before clicking a submit control on any page, review required fields one more time and fix any wrong URL value, missing required checkbox, or incomplete required field.",
            "After submit, wait for navigation, redirect, or an in-page update to settle. Observe the resulting page before deciding the status.",
            "Return status success only when the current page visibly confirms acceptance, shows a success/result message, or redirects to a page whose visible content confirms the pings were sent.",
            "If clicking submit leaves you on the same form with no visible confirmation, keep inspecting for validation errors or required confirmation steps instead of assuming success.",
            "Stop once the site confirms acceptance. Do not continue browsing after visible success.",
            captcha_instruction(attempt_context),
            "If rate limiting, automated-traffic blocking, access denied, forbidden, unavailable service, or another anti-abuse checkpoint appears, return status restricted_checkpoint with evidence.reason.",
            "If login is required and credentials are unavailable, return status login_required.",
            "If payment, signup, account changes, deletion, subscription, email/OTP verification, or another unsupported irreversible step is required, return status skipped.",
            "Always include a concise message. Include evidence.reason when status is not success.",
            "When useful, include evidence.strategy_summary with required fields, submit controls, URL value reviewed, success evidence, and failure reasons.",
            f"Return compact JSON only with keys: {', '.join(AGENT_OUTPUT_KEYS)}.",
            f"Attempt context: {json.dumps(context, sort_keys=True)}",
        ]
    )


def captcha_instruction(attempt_context):
    if (attempt_context or {}).get("captcha_policy", DEFAULT_CAPTCHA_POLICY) == "solve":
        return (
            "If CAPTCHA appears, wait for the configured solver to finish, then continue with the visible "
            "submission flow. If the solver fails or the CAPTCHA remains unsolved, return status captcha_failed "
            "with evidence.reason."
        )
    return f"If CAPTCHA appears, return status failed with evidence.reason set to: {CAPTCHA_FAILURE_REASON}"


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


def accepted_url_value_context(target_url):
    values = [target_url["full"]]
    without_scheme = target_url["without_scheme"]
    for scheme in ("http", "https"):
        value = f"{scheme}://{without_scheme}"
        if value not in values:
            values.append(value)
    return values
