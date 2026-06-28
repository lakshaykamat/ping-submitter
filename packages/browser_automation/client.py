import logging
import time

import requests

from packages.browser_automation.prompts import build_agent_goal, build_run_goal
from packages.browser_automation.results import parse_skyvern_result


logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {"completed", "failed", "timed_out", "terminated", "canceled"}


class SkyvernRunner:
    def __init__(self, settings=None, sleep=None):
        self.settings = settings
        self.sleep = sleep or time.sleep
        self._agent_id = None

    def submit_url(self, site, submitted_url, attempt_context):
        agent_id = self._ensure_agent()
        run_goal = build_run_goal(site, submitted_url)
        run_id = self._run_agent(agent_id, site["url"], run_goal)
        run = self._poll_until_done(run_id)
        return parse_skyvern_result(run)

    def _headers(self):
        return {"x-api-key": self.settings.api_key, "Content-Type": "application/json"}

    def initialize(self):
        self._agent_id = self._find_or_create_agent()

    def _find_or_create_agent(self):
        logger.info("Checking for existing Skyvern agent.", extra={"event": "skyvern_agent_check"})
        for agent in self._list_agents():
            if agent.get("title") == "URL Submission Agent":
                logger.info(
                    "Found existing Skyvern agent.",
                    extra={"event": "skyvern_agent_found", "agent_id": agent["agent_id"]},
                )
                return agent["agent_id"]
        logger.info("No existing agent found. Building new Skyvern agent.", extra={"event": "skyvern_agent_build"})
        return self._create_agent()

    def _list_agents(self):
        response = requests.get(
            f"{self.settings.base_url}/v1/agents",
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("agents", [])

    def _ensure_agent(self):
        if self._agent_id is None:
            self._agent_id = self._find_or_create_agent()
        return self._agent_id

    def _create_agent(self):
        response = requests.post(
            f"{self.settings.base_url}/v1/agents",
            json={
                "title": "URL Submission Agent",
                "goal": build_agent_goal(),
                "max_steps": self.settings.max_steps,
            },
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        agent_id = response.json()["agent_id"]
        logger.info(
            "Built new Skyvern agent.",
            extra={"event": "skyvern_agent_created", "agent_id": agent_id},
        )
        return agent_id

    def _run_agent(self, agent_id, url, goal):
        response = requests.post(
            f"{self.settings.base_url}/v1/agents/{agent_id}/runs",
            json={
                "url": url,
                "goal": goal,
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
