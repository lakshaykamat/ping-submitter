import logging

from packages.browser_automation.types import AGENT_SUCCESS, RestrictedCheckpoint


logger = logging.getLogger(__name__)

RESTRICTED_CHECKPOINT_REASON = "Restricted checkpoint encountered; target site blocked automated access."
RESTRICTED_CHECKPOINT_PHRASES = (
    "access denied",
    "automated traffic",
    "checking if the site connection is secure",
    "just a moment",
    "rate limit",
    "too many requests",
    "verify you are human",
)
RESTRICTED_CHECKPOINT_URL_PARTS = (
    "/cdn-cgi/challenge-platform/",
)


async def detect_restricted_checkpoint(page):
    url = await page_url(page)
    text = " ".join(
        value
        for value in [
            url,
            await document_title(page),
            await document_body_text(page),
        ]
        if value
    )

    if is_restricted_checkpoint(text):
        logger.info("Detected restricted checkpoint on %s.", url or "current page")
        return RestrictedCheckpoint(reason=RESTRICTED_CHECKPOINT_REASON, url=url)

    return None


def is_restricted_checkpoint(text):
    normalized = str(text or "").lower()
    return any(phrase in normalized for phrase in RESTRICTED_CHECKPOINT_PHRASES) or any(
        part in normalized for part in RESTRICTED_CHECKPOINT_URL_PARTS
    )


def result_with_restricted_checkpoint(raw_result, checkpoint):
    if checkpoint is None:
        return raw_result

    data = dict(raw_result or {})
    if data.get("status") == AGENT_SUCCESS:
        return data

    evidence = dict(data.get("evidence") or {})
    evidence.setdefault("reason", checkpoint.reason)
    evidence["restricted_checkpoint_url"] = checkpoint.url

    data["status"] = "restricted_checkpoint"
    data["message"] = data.get("message") or checkpoint.reason
    data["evidence"] = evidence
    return data


async def page_url(page):
    try:
        return await page.get_url()
    except Exception:
        logger.debug(
            "Could not read page URL while checking for restricted checkpoint.",
            exc_info=True,
        )
        return ""


async def document_title(page):
    return await evaluate_text(page, "() => document.title || ''")


async def document_body_text(page):
    return await evaluate_text(
        page,
        "() => document.body ? document.body.innerText.slice(0, 4000) : ''",
    )


async def evaluate_text(page, script):
    try:
        value = await page.evaluate(script)
    except Exception:
        logger.debug(
            "Could not evaluate page text while checking for restricted checkpoint.",
            exc_info=True,
        )
        return ""
    return str(value or "")
