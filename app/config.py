import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    REPORT_DIR = os.environ.get("REPORT_DIR", str(BASE_DIR / "reports"))
    ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", str(BASE_DIR / "reports" / "artifacts"))
    BROWSER_PROFILE_DIR = os.environ.get("BROWSER_PROFILE_DIR", str(BASE_DIR / "browser_profiles"))
    SITES_CONFIG_PATH = os.environ.get("SITES_CONFIG_PATH", str(BASE_DIR / "config" / "sites.yaml"))
    CAPTCHA_POLICY_DEFAULT = os.environ.get("CAPTCHA_POLICY_DEFAULT", "solve")
    AGENTIC_PRE_ATTEMPT_DELAY_SECONDS = float(os.environ.get("AGENTIC_PRE_ATTEMPT_DELAY_SECONDS", "1.0"))
    SKYVERN_BASE_URL = os.environ.get("SKYVERN_BASE_URL", "http://localhost:8001")
    SKYVERN_API_KEY = os.environ.get("SKYVERN_API_KEY", "")
    SKYVERN_MAX_STEPS = int(os.environ.get("SKYVERN_MAX_STEPS", "50"))
    SKYVERN_POLL_INTERVAL_SECONDS = float(os.environ.get("SKYVERN_POLL_INTERVAL_SECONDS", "5.0"))
    SKYVERN_TASK_TIMEOUT_SECONDS = float(os.environ.get("SKYVERN_TASK_TIMEOUT_SECONDS", "3600.0"))
    TESTING = False
