import re
from urllib.parse import urlparse


def build_agent_goal():
    return "\n".join([
        "You are a URL submission agent for web ping and indexing services.",
        "Each run provides a specific URL to submit and instructions for the target service.",
        "Follow the run instructions exactly: fill in the form, handle any CAPTCHA, and confirm success.",
    ])


def build_run_goal(site, submitted_url, captcha_policy="solve"):
    target = _parse_url(submitted_url)
    email = site.get("submission_email") or ""
    email_instruction = (
        f'- Email fields: always enter "{email}" in any email input on the page.'
        if email
        else "- Email fields: leave empty."
    )
    return "\n".join([
        f"Submit the URL {submitted_url} using the submission form on this page.",
        "",
        f"Exact URL to submit: {submitted_url}",
        "",
        "URL field rules:",
        f"- If the field already contains exactly {submitted_url}, leave it untouched.",
        f"- If the URL field has a non-editable prefix element (a read-only label or span outside the input) showing http:// or https://, type only: {target['without_scheme']}",
        f"- Otherwise clear the field completely and type the full URL: {submitted_url}",
        "- Never produce a doubled scheme such as http://http://example.com.",
        "- If the field contains only a placeholder like 'https://' or 'http://' that is part of the editable input, clear it and type the full URL.",
        "",
        "Other fields:",
        f'- Name / title / blog name fields: use "{target["default_title"]}"',
        email_instruction,
        "- Any other optional fields: leave empty.",
        "",
        *_captcha_instructions(captcha_policy),
        "",
        "After submitting, wait for the page to show confirmation that the submission was accepted.",
        "Success indicators vary by service — any of the following count as success:",
        "- A visible success or thank-you message.",
        "- A progress screen saying the submission is being processed (e.g. 'Submitting Your Website...').",
        "- A list or table of URLs/directories being pinged or indexed on your behalf.",
        "- Redirection to a results or status page showing your URL being processed.",
        "Do not require an explicit 'success' text — if the page clearly moved past the form and is processing the submission, that is success.",
    ])


def _parse_url(url):
    parsed = urlparse(url)
    without_scheme = url
    if parsed.netloc:
        without_scheme = parsed.netloc + parsed.path
        if parsed.params:
            without_scheme += f";{parsed.params}"
        if parsed.query:
            without_scheme += f"?{parsed.query}"
        if parsed.fragment:
            without_scheme += f"#{parsed.fragment}"
    hostname = parsed.hostname or parsed.netloc or url
    return {
        "full": url,
        "without_scheme": without_scheme,
        "hostname": hostname,
        "default_title": _default_title(hostname),
    }


def _captcha_instructions(captcha_policy):
    if captcha_policy == "solve":
        return [
            "CAPTCHA handling:",
            "- If any CAPTCHA appears (Cloudflare Turnstile, reCAPTCHA, hCAPTCHA, or similar), use the solve_captcha action — do NOT click or interact with the widget manually.",
            "- The solve_captcha action automatically obtains and injects a valid token; wait for it to confirm success before submitting.",
            "- Do not proceed to submit until any CAPTCHA on the page has been resolved.",
        ]
    return [
        "CAPTCHA handling:",
        '- If a checkbox labelled "Verify you are human", "I\'m not a robot", or similar appears, click it ONCE and then wait.',
        "- After clicking, wait at least 3-5 seconds for verification to complete — do NOT click again while it is processing.",
        "- Do not proceed to submit until any CAPTCHA has been completed.",
    ]


def _default_title(hostname):
    normalized = str(hostname or "").strip().strip(".").lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    labels = [label for label in normalized.split(".") if label]
    if not labels or all(label.isdigit() for label in labels):
        return "Submitted URL"
    root = _root_label(labels)
    words = [w for w in re.split(r"[-_]+", root) if w]
    return " ".join(w.capitalize() for w in words) or "Submitted URL"


def _root_label(labels):
    common_second_level = {"ac", "co", "com", "edu", "gov", "net", "org"}
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in common_second_level:
        return labels[-3]
    if len(labels) >= 2:
        return labels[-2]
    return labels[0]
