from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from packages.captcha_solver import OhMyCaptchaSettings


DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
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
    "--start-fullscreen",
    "--start-maximized",
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
    ohmycaptcha_base_url: str = "http://127.0.0.1:8000"
    ohmycaptcha_client_key: str = ""
    ohmycaptcha_request_timeout_seconds: float = 30.0
    ohmycaptcha_poll_interval_seconds: float = 2.0
    ohmycaptcha_max_wait_seconds: float = 120.0

    @classmethod
    def from_mapping(cls, config):
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
            ohmycaptcha_base_url=config["OHMYCAPTCHA_BASE_URL"],
            ohmycaptcha_client_key=config["OHMYCAPTCHA_CLIENT_KEY"],
            ohmycaptcha_request_timeout_seconds=float(
                config["OHMYCAPTCHA_REQUEST_TIMEOUT_SECONDS"]
            ),
            ohmycaptcha_poll_interval_seconds=float(
                config["OHMYCAPTCHA_POLL_INTERVAL_SECONDS"]
            ),
            ohmycaptcha_max_wait_seconds=float(config["OHMYCAPTCHA_MAX_WAIT_SECONDS"]),
        )

    from_flask_config = from_mapping

    def action_delay_bounds(self):
        min_delay = max(0.0, self.min_action_delay_seconds)
        max_delay = max(0.0, self.max_action_delay_seconds)
        if max_delay < min_delay:
            return max_delay, min_delay
        return min_delay, max_delay

    def captcha_solver_settings(self):
        return OhMyCaptchaSettings(
            base_url=self.ohmycaptcha_base_url,
            client_key=self.ohmycaptcha_client_key,
            request_timeout_seconds=self.ohmycaptcha_request_timeout_seconds,
            poll_interval_seconds=self.ohmycaptcha_poll_interval_seconds,
            max_wait_seconds=self.ohmycaptcha_max_wait_seconds,
        )


@lru_cache(maxsize=1)
def detected_screen_size():
    root = None
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        width = int(root.winfo_screenwidth())
        height = int(root.winfo_screenheight())
    except Exception:
        return dict(DEFAULT_VIEWPORT)
    finally:
        if root is not None:
            root.destroy()

    if width <= 0 or height <= 0:
        return dict(DEFAULT_VIEWPORT)
    return {"width": width, "height": height}


def browser_args(browser_size):
    return [*DEFAULT_BROWSER_ARGS, f"--window-size={browser_size['width']},{browser_size['height']}"]
