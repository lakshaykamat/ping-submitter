import asyncio

from packages.browser_automation.checkpoints import (
    RESTRICTED_CHECKPOINT_REASON,
    detect_restricted_checkpoint,
    result_with_restricted_checkpoint,
)


def test_detect_restricted_checkpoint_from_cloudflare_body_text():
    page = FakeCheckpointPage(
        title="Just a moment...",
        body_text="Checking if the site connection is secure. Verify you are human.",
    )

    checkpoint = asyncio.run(detect_restricted_checkpoint(page))

    assert checkpoint.reason == RESTRICTED_CHECKPOINT_REASON
    assert checkpoint.url == "https://example.com/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page"


def test_restricted_checkpoint_result_preserves_success():
    checkpoint = FakeCheckpoint(
        reason=RESTRICTED_CHECKPOINT_REASON,
        url="https://example.com/block",
    )

    result = result_with_restricted_checkpoint(
        {"status": "success", "message": "Accepted.", "evidence": {}},
        checkpoint,
    )

    assert result["status"] == "success"


def test_restricted_checkpoint_result_marks_uncertain_agent_result():
    checkpoint = FakeCheckpoint(
        reason=RESTRICTED_CHECKPOINT_REASON,
        url="https://example.com/block",
    )

    result = result_with_restricted_checkpoint(
        {"status": "agent_uncertain", "message": "", "evidence": {}},
        checkpoint,
    )

    assert result["status"] == "restricted_checkpoint"
    assert result["message"] == RESTRICTED_CHECKPOINT_REASON
    assert result["evidence"] == {
        "reason": RESTRICTED_CHECKPOINT_REASON,
        "restricted_checkpoint_url": "https://example.com/block",
    }


class FakeCheckpoint:
    def __init__(self, reason, url):
        self.reason = reason
        self.url = url


class FakeCheckpointPage:
    def __init__(self, title="", body_text="", url=None):
        self.title = title
        self.body_text = body_text
        self.url = url or "https://example.com/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page"

    async def get_url(self):
        return self.url

    async def evaluate(self, script):
        if "document.title" in script:
            return self.title
        if "document.body" in script:
            return self.body_text
        raise AssertionError(f"Unexpected script: {script}")
