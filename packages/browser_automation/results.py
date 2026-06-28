from packages.browser_automation.types import AgentResult, CAPTCHA_FAILURE_REASON


_SKYVERN_STATUS_MAP = {
    "completed": "success",
    "canceled": "skipped",
}

_FAILURE_REASON_KEYWORDS = [
    (("captcha", "recaptcha"), "captcha_failed"),
    (("login required", "sign in", "signin", "authentication required"), "login_required"),
    (("rate limit", "too many requests", "access denied", "forbidden", "blocked", "cloudflare", "just a moment"), "restricted_checkpoint"),
    (("payment", "subscribe", "sign up", "signup", "email verification", "otp"), "skipped"),
]


def parse_skyvern_result(task):
    skyvern_status = task.get("status", "")
    failure_reason = task.get("failure_reason") or ""

    status = _map_status(skyvern_status, failure_reason)
    message = _build_message(skyvern_status, failure_reason, status)
    evidence = {"skyvern_run_id": task.get("run_id"), "skyvern_status": skyvern_status}
    if failure_reason:
        evidence["reason"] = failure_reason

    screenshot_urls = task.get("screenshot_urls") or []
    screenshot_path = screenshot_urls[0] if screenshot_urls else None

    return AgentResult(status=status, message=message, evidence=evidence, screenshot_path=screenshot_path)


def _map_status(skyvern_status, failure_reason):
    if skyvern_status in _SKYVERN_STATUS_MAP:
        return _SKYVERN_STATUS_MAP[skyvern_status]

    if skyvern_status == "timed_out":
        return "failed"

    if skyvern_status in ("failed", "terminated"):
        return _classify_failure(failure_reason)

    return "agent_uncertain"


def _classify_failure(reason):
    lower = reason.lower()
    for keywords, status in _FAILURE_REASON_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return status
    return "failed"


def _build_message(skyvern_status, failure_reason, mapped_status):
    if mapped_status == "success":
        return "Skyvern completed the submission successfully."
    if skyvern_status == "timed_out":
        return "Skyvern task timed out before completing."
    if mapped_status == "captcha_failed":
        return failure_reason or CAPTCHA_FAILURE_REASON
    if failure_reason:
        return failure_reason
    return f"Skyvern task ended with status: {skyvern_status}."
