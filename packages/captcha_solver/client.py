import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.captcha_solver.errors import (
    CaptchaSolverApiError,
    CaptchaSolverTimeoutError,
)
from packages.captcha_solver.types import CaptchaSolveResult, OhMyCaptchaSettings


logger = logging.getLogger(__name__)


class OhMyCaptchaClient:
    def __init__(self, settings=None, opener=None, sleep=None, monotonic=None):
        self.settings = settings or OhMyCaptchaSettings.from_env()
        self.opener = opener or urlopen
        self.sleep = sleep or time.sleep
        self.monotonic = monotonic or time.monotonic

    def health(self):
        return self._request_json("GET", "/api/v1/health")

    def get_balance(self):
        return self._request_json("POST", "/getBalance", self._auth_payload())

    def create_task(self, task):
        response = self._request_json(
            "POST",
            "/createTask",
            {
                **self._auth_payload(),
                "task": task.to_payload(),
            },
        )
        self._raise_for_error_response(response)

        task_id = response.get("taskId")
        if not task_id:
            raise CaptchaSolverApiError(
                "OhMyCaptcha did not return a taskId.",
                response=response,
            )

        logger.info("Created OhMyCaptcha task %s for %s.", task_id, task.type)
        return str(task_id)

    def get_task_result(self, task_id):
        response = self._request_json(
            "POST",
            "/getTaskResult",
            {
                **self._auth_payload(),
                "taskId": task_id,
            },
        )
        return CaptchaSolveResult(
            task_id=str(task_id),
            status=response.get("status", ""),
            solution=response.get("solution") or {},
            error_code=response.get("errorCode"),
            error_message=response.get("errorDescription") or response.get("errorMessage"),
            raw_response=response,
        )

    def solve_task(self, task):
        task_id = self.create_task(task)
        deadline = self.monotonic() + self.settings.max_wait_seconds

        while self.monotonic() <= deadline:
            result = self.get_task_result(task_id)
            if result.solved:
                logger.info("OhMyCaptcha task %s solved.", task_id)
                return result
            if result.status == "failed" or result.error_code:
                message = result.error_message or f"OhMyCaptcha task {task_id} failed."
                raise CaptchaSolverApiError(message, response=result.raw_response)

            logger.debug("OhMyCaptcha task %s is %s.", task_id, result.status or "pending")
            self.sleep(self.settings.poll_interval_seconds)

        raise CaptchaSolverTimeoutError(f"OhMyCaptcha task {task_id} timed out.")

    def _auth_payload(self):
        return {"clientKey": self.settings.client_key}

    def _request_json(self, method, path, payload=None):
        request = Request(
            self._url(path),
            data=self._json_bytes(payload) if payload is not None else None,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with self.opener(
                request,
                timeout=self.settings.request_timeout_seconds,
            ) as response:
                return self._decode_response(response.read())
        except HTTPError as error:
            response = self._decode_response(error.read())
            message = (
                response.get("errorDescription")
                or response.get("errorMessage")
                or str(error)
            )
            raise CaptchaSolverApiError(message, response=response) from error
        except URLError as error:
            raise CaptchaSolverApiError(f"Could not reach OhMyCaptcha: {error.reason}") from error

    def _url(self, path):
        return f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _json_bytes(self, payload):
        return json.dumps(payload).encode("utf-8")

    def _decode_response(self, body):
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise CaptchaSolverApiError("OhMyCaptcha returned invalid JSON.") from error

    def _raise_for_error_response(self, response):
        if not response.get("errorId"):
            return

        message = (
            response.get("errorDescription")
            or response.get("errorMessage")
            or "OhMyCaptcha API error."
        )
        raise CaptchaSolverApiError(message, response=response)
