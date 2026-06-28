from packages.browser_automation.types import (
    AGENT_FAILURE_STATUSES,
    CAPTCHA_AGENT_STATUSES,
    CAPTCHA_FAILURE_REASON,
)


def agent_context(result):
    context = {
        "status": result.status,
        "confidence": result.confidence,
        "screenshot_path": result.screenshot_path,
    }
    context.update(result.evidence or {})
    return context


def agent_reason(result):
    evidence = result.evidence or {}
    return result.message or evidence.get("reason") or evidence.get("failure_reason")


def agent_failure_status(status):
    if status in AGENT_FAILURE_STATUSES:
        return status
    return "agent_uncertain"


def failure_reason(result, status):
    if result.status in CAPTCHA_AGENT_STATUSES:
        return agent_reason(result) or CAPTCHA_FAILURE_REASON
    return agent_reason(result) or f"Agent returned {status}."
