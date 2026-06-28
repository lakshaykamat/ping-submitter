import json
import re
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
            "Take one browser action, observe, verify the visible result, then choose the next action.",
            "If the form or submit controls are not visible, scroll down in useful increments and inspect after each scroll. If you reach the bottom, scroll back up and inspect earlier sections before deciding the form is unavailable.",
            "Do not do random scrolling, fake mouse movement, or other disguise-only actions.",
            "Text fields: use input with clear=True. If wrong text remains, select-all, Backspace/Delete, then type the exact value once.",
            "URL fields: inspect the current editable value and nearby fixed prefix before typing.",
            "If the editable value is exactly http:// or https://, put the cursor at the end and type only target_url.without_scheme once.",
            "If a fixed uneditable http:// or https:// prefix appears beside the field, clear the editable field and type only target_url.without_scheme.",
            "Otherwise clear the whole editable URL field and type target_url.full. Do not append to any existing domain, path, or partial URL.",
            "Before submit, the field plus any fixed prefix must equal one accepted final URL value with one scheme only.",
            "Fix malformed, duplicated, or appended values such as http:/example.com, http://http://example.com, or example.comexample.com before submitting.",
            "For blog/site/title/name fields, use target_url.default_title, not target_url.hostname or target_url.without_scheme.",
            "For email fields, leave empty unless required and no approved email is available; then return skipped instead of inventing one.",
            "Never fill every text field with the URL, hostname, or example.com. Match each non-URL field to its label, placeholder, type, and required state.",
            "Select required service/category checkboxes.",
            "Recover from wrong pages, redirects, expired pages, blank pages, and intermediate screens.",
            f"Wait at least {min_delay} and at most {max_delay} seconds between browser actions. Do not click randomly.",
            "Before clicking submit, review required fields once more and fix any wrong URL, missing required checkbox, or incomplete required field.",
            "After submit, wait for navigation, redirect, or an in-page update to settle. Observe the resulting page before deciding the status.",
            "Return status success only when the current page visibly confirms acceptance, shows a success/result message, or redirects to a page whose visible content confirms the pings were sent.",
            "If clicking submit leaves you on the same form with no visible confirmation, keep inspecting for validation errors or required confirmation steps instead of assuming success.",
            "Stop once the site confirms acceptance. Do not continue browsing after visible success.",
            captcha_instruction(attempt_context),
            "If rate limiting, automated-traffic blocking, access denied, forbidden, unavailable service, or another anti-abuse checkpoint appears, return status restricted_checkpoint with evidence.reason.",
            "If login is required and credentials are unavailable, return status login_required.",
            "If payment, signup, account changes, deletion, subscription, email/OTP verification, or another unsupported irreversible step is required, return status skipped.",
            "Always include a concise message. Include evidence.reason when status is not success.",
            "When useful, include evidence.strategy_summary with fields reviewed, submit controls, URL value, success evidence, and failure reasons.",
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
    default_title = default_title_from_hostname(hostname)
    return {
        "full": submitted_url,
        "scheme": parsed.scheme,
        "without_scheme": without_scheme,
        "hostname": hostname,
        "default_title": default_title,
    }


def default_title_from_hostname(hostname):
    normalized = str(hostname or "").strip().strip(".").lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]

    labels = [label for label in normalized.split(".") if label]
    if not labels:
        return "Submitted URL"
    if all(label.isdigit() for label in labels):
        return "Submitted URL"

    root_label = root_domain_label(labels)
    words = [word for word in re.split(r"[-_]+", root_label) if word]
    title = " ".join(word.capitalize() for word in words)
    return title or "Submitted URL"


def root_domain_label(labels):
    common_second_level_domains = {"ac", "co", "com", "edu", "gov", "net", "org"}
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in common_second_level_domains:
        return labels[-3]
    if len(labels) >= 2:
        return labels[-2]
    return labels[0]


def accepted_url_value_context(target_url):
    values = [target_url["full"]]
    without_scheme = target_url["without_scheme"]
    for scheme in ("http", "https"):
        value = f"{scheme}://{without_scheme}"
        if value not in values:
            values.append(value)
    return values
