import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    REPORT_DIR = os.environ.get("REPORT_DIR", str(BASE_DIR / "reports"))
    ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", str(BASE_DIR / "reports" / "artifacts"))
    BROWSER_PROFILE_DIR = os.environ.get("BROWSER_PROFILE_DIR", str(BASE_DIR / "browser_profiles"))
    SITES_CONFIG_PATH = os.environ.get("SITES_CONFIG_PATH", str(BASE_DIR / "config" / "sites.yaml"))
    CAPTCHA_WAIT_SECONDS = int(os.environ.get("CAPTCHA_WAIT_SECONDS", "120"))
    PLAYWRIGHT_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    PLAYWRIGHT_NAVIGATION_TIMEOUT_MS = int(os.environ.get("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS", "30000"))
    PLAYWRIGHT_ACTION_TIMEOUT_MS = int(os.environ.get("PLAYWRIGHT_ACTION_TIMEOUT_MS", "10000"))
    PLAYWRIGHT_SLOW_MO_MS = int(os.environ.get("PLAYWRIGHT_SLOW_MO_MS", "0"))
    AGENTIC_LLM_MODEL = os.environ.get("AGENTIC_LLM_MODEL", "")
    AGENTIC_MAX_STEPS = int(os.environ.get("AGENTIC_MAX_STEPS", "80"))
    AGENTIC_MIN_ACTION_DELAY_SECONDS = float(os.environ.get("AGENTIC_MIN_ACTION_DELAY_SECONDS", "0.6"))
    AGENTIC_MAX_ACTION_DELAY_SECONDS = float(os.environ.get("AGENTIC_MAX_ACTION_DELAY_SECONDS", "2.0"))
    AGENTIC_PRE_ATTEMPT_DELAY_SECONDS = float(os.environ.get("AGENTIC_PRE_ATTEMPT_DELAY_SECONDS", "1.0"))
    TESTING = False
