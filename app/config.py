import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))
    REPORT_DIR = os.environ.get("REPORT_DIR", str(BASE_DIR / "reports"))
    SITES_CONFIG_PATH = os.environ.get("SITES_CONFIG_PATH", str(BASE_DIR / "config" / "sites.yaml"))
    CAPTCHA_WAIT_SECONDS = int(os.environ.get("CAPTCHA_WAIT_SECONDS", "120"))
    PLAYWRIGHT_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    TESTING = False
