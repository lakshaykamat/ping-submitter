import logging
import time

import requests

from packages.browser_automation.prompts import build_run_goal
from packages.browser_automation.results import parse_skyvern_result


logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"completed", "failed", "timed_out", "terminated", "canceled"}


class SkyvernRunner:
    def __init__(self, settings=None, sleep=None):
        self.settings = settings
        self.sleep = sleep or time.sleep

    def submit_url(self, site, submitted_url, attempt_context):
        captcha_policy = (attempt_context or {}).get("captcha_policy", "solve")
        prompt = build_run_goal(site, submitted_url, captcha_policy=captcha_policy)
        run_id = self._run_task(site["url"], prompt)
        run = self._poll_until_done(run_id)
        return parse_skyvern_result(run)

    def ping(self):
        response = requests.get(
            f"{self.settings.base_url}/v1/version",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _headers(self):
        return {"x-api-key": self.settings.api_key, "Content-Type": "application/json"}

    def _run_task(self, url, prompt):
        response = requests.post(
            f"{self.settings.base_url}/v1/run/tasks",
            json={
                "prompt": prompt,
                "url": url,
                "max_steps": self.settings.max_steps,
            },
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["run_id"]

    def _poll_until_done(self, run_id):
        deadline = time.time() + self.settings.task_timeout_seconds
        while time.time() < deadline:
            response = requests.get(
                f"{self.settings.base_url}/v1/runs/{run_id}",
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
            run = response.json()
            if run["status"] in _TERMINAL_STATUSES:
                return run
            self.sleep(self.settings.poll_interval_seconds)
        raise TimeoutError(
            f"Skyvern run {run_id} did not complete within {self.settings.task_timeout_seconds}s"
        )
