import time

import requests

from packages.browser_automation.prompts import build_prompt
from packages.browser_automation.results import parse_skyvern_result


_TERMINAL_STATUSES = {"completed", "failed", "timed_out", "terminated", "canceled"}


class SkyvernRunner:
    def __init__(self, settings=None, sleep=None):
        self.settings = settings
        self.sleep = sleep or time.sleep

    def submit_url(self, site, submitted_url, attempt_context):
        prompt = build_prompt(site, submitted_url)
        run_id = self._create_task(site["url"], prompt)
        task = self._poll_until_done(run_id)
        return parse_skyvern_result(task)

    def _headers(self):
        return {"x-api-key": self.settings.api_key, "Content-Type": "application/json"}

    def _create_task(self, site_url, prompt):
        response = requests.post(
            f"{self.settings.base_url}/v1/run/tasks",
            json={
                "url": site_url,
                "prompt": prompt,
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
            task = response.json()
            if task["status"] in _TERMINAL_STATUSES:
                return task
            self.sleep(self.settings.poll_interval_seconds)
        raise TimeoutError(
            f"Skyvern run {run_id} did not complete within {self.settings.task_timeout_seconds}s"
        )
