import re
from urllib.parse import urlparse


def build_prompt(site, submitted_url):
    target = _parse_url(submitted_url)
    return "\n".join([
        f"Submit the URL {submitted_url} using the submission form on this page.",
        "",
        f"Exact URL to submit: {submitted_url}",
        "",
        "URL field rules:",
        f"- If the field already contains exactly {submitted_url}, leave it untouched.",
        f"- If the field shows http:// or https:// as a fixed prefix, type only: {target['without_scheme']}",
        f"- Otherwise clear the field and type: {submitted_url}",
        "- Never produce a doubled scheme such as http://http://example.com.",
        "",
        "Other fields:",
        f'- Name / title / blog name fields: use "{target["default_title"]}"',
        "- Email fields: leave empty unless required.",
        "- Any other optional fields: leave empty.",
        "",
        "After submitting, wait for the page to show a success message or confirmation.",
        "Return success only when the page visibly confirms the submission was accepted.",
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
