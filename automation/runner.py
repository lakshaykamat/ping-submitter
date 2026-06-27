import time
from urllib.parse import urlparse

from flask import current_app

from automation.adapters import get_adapter
from automation.browser import BrowserManager
from automation.captcha import create_captcha_challenge, detect_captcha, fill_captcha_answer
from automation.forms import (
    FormDetectionError,
    fill_url_input,
    find_submit_control,
    find_url_input,
    selector_exists,
    submit_form,
)
from automation.types import RETRY_BACKOFF_SECONDS
from app.models import CaptchaChallenge, SubmissionAttempt, SubmissionJob, get_session, utc_now
from app.services import build_report, record_event, write_report


class AutomationError(Exception):
    recoverable = False


class RecoverableAutomationError(AutomationError):
    recoverable = True


class SiteValidationError(AutomationError):
    pass


class CaptchaPaused(AutomationError):
    pass


class AutomationRunner:
    def __init__(
        self,
        browser_manager_factory=None,
        sleep=None,
        captcha_wait_seconds="config",
        navigation_timeout_ms=30000,
    ):
        self.browser_manager_factory = browser_manager_factory
        self.sleep = sleep or time.sleep
        self.captcha_wait_seconds = captcha_wait_seconds
        self.navigation_timeout_ms = navigation_timeout_ms

    def run_job(self, job_id):
        session = get_session()
        job = session.get(SubmissionJob, job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")

        job.status = "running"
        record_event(session, job.id, "job_started", "Submission job started.")
        session.commit()

        with self.create_browser_manager() as browser_manager:
            for attempt in list(job.attempts):
                if attempt.status in {"queued", "running"}:
                    self.run_attempt(job, attempt, browser_manager)
                    session.commit()
                if job.status == "waiting_for_captcha":
                    write_report(job.id, build_report(job))
                    return job

        self.finish_job(job)
        session.commit()
        return job

    def create_browser_manager(self):
        if self.browser_manager_factory:
            return self.browser_manager_factory()
        return BrowserManager(headless=current_app.config["PLAYWRIGHT_HEADLESS"])

    def run_attempt(self, job, attempt, browser_manager):
        adapter = get_adapter(attempt.site_id)
        if adapter is None:
            self.fail_attempt(job, attempt, "failed", f"Unsupported site adapter: {attempt.site_id}")
            return

        while attempt.attempt_number <= job.max_attempts:
            page = browser_manager.new_page()
            attempt.status = "running"
            attempt.started_at = attempt.started_at or utc_now()
            record_event(
                get_session(),
                job.id,
                "attempt_started",
                "Submission attempt started.",
                attempt_id=attempt.id,
                site_id=attempt.site_id,
                submitted_url=attempt.submitted_url,
                context={"attempt_number": attempt.attempt_number},
            )

            try:
                self.submit_url(page, adapter, job, attempt)
                self.complete_attempt(job, attempt)
                return
            except CaptchaPaused:
                return
            except Exception as error:
                if self.should_retry(error, attempt, job.max_attempts):
                    self.schedule_retry(job, attempt, error)
                    continue
                status = "failed"
                if isinstance(error, CaptchaTimeoutError):
                    status = "captcha_timeout"
                self.fail_attempt(job, attempt, status, str(error))
                return

    def submit_url(self, page, adapter, job, attempt):
        try:
            response = page.goto(
                adapter.page_url,
                wait_until="domcontentloaded",
                timeout=self.navigation_timeout_ms,
            )
        except Exception as error:
            if is_recoverable_error(error):
                raise RecoverableAutomationError(str(error)) from error
            raise

        if response and getattr(response, "status", 200) >= 500:
            raise RecoverableAutomationError(f"Temporary server error: {response.status}")

        captcha_selector = detect_captcha(page, adapter)
        if captcha_selector:
            self.handle_captcha(job, attempt, page, captcha_selector)

        url_selector = self.find_input_or_raise(page, adapter)
        fill_url_input(page, url_selector, attempt.submitted_url)
        self.fill_adapter_fields(page, adapter, attempt.submitted_url)
        self.select_adapter_checkboxes(page, adapter)
        submit_selector = find_submit_control(page, adapter)
        submit_form(page, submit_selector)
        self.raise_for_site_response(page, adapter)

    def find_input_or_raise(self, page, adapter):
        try:
            return find_url_input(page, adapter)
        except FormDetectionError as error:
            raise SiteValidationError(str(error)) from error

    def handle_captcha(self, job, attempt, page, selector):
        session = get_session()
        wait_seconds = self.captcha_wait_seconds
        if wait_seconds == "config":
            wait_seconds = current_app.config["CAPTCHA_WAIT_SECONDS"]

        challenge = create_captcha_challenge(job, attempt, page, wait_seconds)
        attempt.status = "captcha_required"
        job.status = "waiting_for_captcha"
        record_event(
            session,
            job.id,
            "captcha_detected",
            "CAPTCHA detected. Waiting for manual answer.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"selector": selector, "challenge_id": challenge.id},
        )
        session.commit()

        if wait_seconds is None:
            raise CaptchaPaused("CAPTCHA requires manual input.")

        answer = self.wait_for_captcha_answer(challenge.id, wait_seconds)
        if not answer:
            raise CaptchaTimeoutError("CAPTCHA answer timed out.")

        fill_captcha_answer(page, answer)
        challenge.status = "answered"
        attempt.status = "running"
        job.status = "running"
        record_event(
            session,
            job.id,
            "captcha_answered",
            "CAPTCHA answer received.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"challenge_id": challenge.id},
        )
        session.commit()

    def wait_for_captcha_answer(self, challenge_id, wait_seconds):
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() <= deadline:
            session = get_session()
            session.expire_all()
            challenge = session.get(CaptchaChallenge, challenge_id)
            if challenge and challenge.answer:
                return challenge.answer
            if wait_seconds == 0:
                return None
            self.sleep(1)
        return None

    def raise_for_site_response(self, page, adapter):
        content = page.content().lower()
        for pattern in adapter.error_text_patterns:
            if pattern.lower() in content:
                raise SiteValidationError(f"Site returned validation error: {pattern}")
        if adapter.success_text_patterns and not any(
            pattern.lower() in content for pattern in adapter.success_text_patterns
        ):
            expected = ", ".join(adapter.success_text_patterns)
            raise SiteValidationError(f"Site did not show success confirmation. Expected one of: {expected}")

    def fill_adapter_fields(self, page, adapter, submitted_url):
        if adapter.title_input_selector and selector_exists(page, adapter.title_input_selector):
            page.locator(adapter.title_input_selector).first.fill(site_title(submitted_url))
        if adapter.rss_input_selector and selector_exists(page, adapter.rss_input_selector):
            page.locator(adapter.rss_input_selector).first.fill(rss_url(submitted_url))

    def select_adapter_checkboxes(self, page, adapter):
        for selector in adapter.checkbox_selectors:
            if not selector_exists(page, selector):
                continue
            control = page.locator(selector).first
            if hasattr(control, "check"):
                control.check()
            else:
                control.click()

    def should_retry(self, error, attempt, max_attempts):
        if isinstance(error, CaptchaTimeoutError):
            return False
        if attempt.attempt_number >= max_attempts:
            return False
        if isinstance(error, RecoverableAutomationError):
            return True
        return is_recoverable_error(error)

    def schedule_retry(self, job, attempt, error):
        wait_seconds = RETRY_BACKOFF_SECONDS.get(attempt.attempt_number, 0)
        attempt.retry_count += 1
        attempt.attempt_number += 1
        record_event(
            get_session(),
            job.id,
            "retry_scheduled",
            "Recoverable failure. Retry scheduled.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"reason": str(error), "wait_seconds": wait_seconds},
        )
        get_session().commit()
        if wait_seconds:
            self.sleep(wait_seconds)

    def complete_attempt(self, job, attempt):
        attempt.status = "success"
        attempt.failure_reason = None
        attempt.finished_at = utc_now()
        record_event(
            get_session(),
            job.id,
            "attempt_success",
            "Submission attempt completed successfully.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
        )

    def fail_attempt(self, job, attempt, status, reason):
        attempt.status = status
        attempt.failure_reason = reason
        attempt.finished_at = utc_now()
        record_event(
            get_session(),
            job.id,
            "attempt_failed",
            "Submission attempt failed.",
            level="warning",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"reason": reason, "status": status},
        )

    def finish_job(self, job):
        if any(attempt.status == "captcha_required" for attempt in job.attempts):
            job.status = "waiting_for_captcha"
        elif all(attempt.status == "success" for attempt in job.attempts):
            job.status = "completed"
        else:
            job.status = "failed"

        write_report(job.id, build_report(job))
        record_event(
            get_session(),
            job.id,
            "job_completed",
            "Submission job finished.",
            context={"status": job.status},
        )
        record_event(
            get_session(),
            job.id,
            "report_generated",
            "Report generated.",
            context={"status": job.status},
        )


class CaptchaTimeoutError(AutomationError):
    pass


def is_recoverable_error(error):
    message = str(error).lower()
    class_name = error.__class__.__name__.lower()
    return (
        "timeout" in class_name
        or "timeout" in message
        or "network" in message
        or "detached" in message
        or "temporarily" in message
    )


def site_title(submitted_url):
    parsed_url = urlparse(submitted_url)
    return f"Live smoke test {parsed_url.netloc or submitted_url}"


def rss_url(submitted_url):
    return submitted_url.rstrip("/") + "/feed"
