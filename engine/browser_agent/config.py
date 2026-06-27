from dataclasses import dataclass
from pathlib import Path


DEFAULT_VIEWPORT = {"width": 1365, "height": 768}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Upgrade-Insecure-Requests": "1",
}
DEFAULT_BROWSER_ARGS = [
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
]
SESSION_TIMEOUT_SECONDS = 14400


@dataclass(frozen=True)
class BrowserAgentSettings:
    headless: bool
    navigation_timeout_ms: int
    action_timeout_ms: int
    slow_mo_ms: int
    agentic_llm_model: str
    agentic_max_steps: int
    min_action_delay_seconds: float
    max_action_delay_seconds: float
    artifact_dir: Path

    @classmethod
    def from_flask_config(cls, config):
        return cls(
            headless=config["PLAYWRIGHT_HEADLESS"],
            navigation_timeout_ms=config["PLAYWRIGHT_NAVIGATION_TIMEOUT_MS"],
            action_timeout_ms=config["PLAYWRIGHT_ACTION_TIMEOUT_MS"],
            slow_mo_ms=config["PLAYWRIGHT_SLOW_MO_MS"],
            agentic_llm_model=config["AGENTIC_LLM_MODEL"],
            agentic_max_steps=config["AGENTIC_MAX_STEPS"],
            min_action_delay_seconds=float(config["AGENTIC_MIN_ACTION_DELAY_SECONDS"]),
            max_action_delay_seconds=float(config["AGENTIC_MAX_ACTION_DELAY_SECONDS"]),
            artifact_dir=Path(config["ARTIFACT_DIR"]),
        )

    def action_delay_bounds(self):
        min_delay = max(0.0, self.min_action_delay_seconds)
        max_delay = max(0.0, self.max_action_delay_seconds)
        if max_delay < min_delay:
            return max_delay, min_delay
        return min_delay, max_delay
