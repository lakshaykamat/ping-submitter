from pathlib import Path

import yaml
from flask import current_app


def load_sites():
    config_path = Path(current_app.config["SITES_CONFIG_PATH"])
    data = yaml.safe_load(config_path.read_text()) or {}
    sites = data.get("sites", [])
    return {site["id"]: normalize_site_config(site) for site in sites}


def normalize_site_config(site):
    normalized = dict(site)
    normalized["runner_mode"] = "agentic"
    normalized.setdefault("captcha_policy", current_app.config["CAPTCHA_POLICY_DEFAULT"])
    normalized.setdefault("browser_profile_enabled", True)
    normalized.setdefault("profile_account", "default")
    normalized.setdefault("pre_attempt_delay_seconds", None)
    return normalized
