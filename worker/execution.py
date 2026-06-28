import time
from pathlib import Path

from flask import current_app

from app.models import SubmissionJob, get_session, utc_now
from app.lib.agent_results import agent_context, agent_failure_status, agent_reason, failure_reason
from app.services import (
    approved_site_memory,
    build_report,
    get_or_create_browser_profile,
    load_sites,
    record_event,
    record_site_memory,
    write_report,
)
from packages.browser_automation import SkyvernRunner, SkyvernSettings
from packages.browser_automation.types import (
    AGENT_SKIP_STATUSES,
    AGENT_SUCCESS,
)


class AutomationRunner:
    def __init__(self, agentic_runner=None, sleep=None, settings=None):
        self.agentic_runner = agentic_runner
        self.sleep = sleep or time.sleep
        self.settings = settings

    def run_job(self, job_id):
        session = get_session()
        job = session.get(SubmissionJob, job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")

        job.status = "running"
        record_event(session, job.id, "job_started", "Submission job started.")
        session.commit()

        for attempt in list(job.attempts):
            if attempt.status in {"queued", "running"}:
                self.run_attempt(job, attempt)
                session.commit()

        self.finish_job(job)
        session.commit()
        return job

    def run_attempt(self, job, attempt):
        site_config = self.site_config(attempt.site_id)
        attempt.runner_mode = "skyvern"
        attempt.captcha_policy = site_config.get(
            "captcha_policy",
            attempt.captcha_policy or current_app.config["CAPTCHA_POLICY_DEFAULT"],
        )
        site_config["runner_mode"] = "skyvern"
        site_config["captcha_policy"] = attempt.captcha_policy

        try:
            self.run_skyvern_attempt(job, attempt, site_config)
        except Exception as error:
            self.fail_attempt(job, attempt, "failed", f"Skyvern runner failed: {error}")

    def site_config(self, site_id):
        site = load_sites().get(site_id)
        if site is None:
            return {
                "id": site_id,
                "name": site_id,
                "url": "",
                "runner_mode": "skyvern",
                "captcha_policy": current_app.config["CAPTCHA_POLICY_DEFAULT"],
            }
        return site

    def run_skyvern_attempt(self, job, attempt, site_config):
        session = get_session()
        attempt.status = "running"
        attempt.started_at = attempt.started_at or utc_now()
        record_event(
            session,
            job.id,
            "agent_started",
            "Skyvern agent started.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"runner_mode": attempt.runner_mode, "captcha_policy": attempt.captcha_policy},
        )
        session.commit()

        self.wait_before_attempt(job, attempt, site_config)

        profile = get_or_create_browser_profile(site_config)
        site_memory = approved_site_memory(attempt.site_id)
        runner = self.agentic_runner or self.create_runner()
        result = runner.submit_url(
            site_config,
            attempt.submitted_url,
            {
                "job_id": job.id,
                "attempt_id": attempt.id,
                "site_id": attempt.site_id,
                "submitted_url": attempt.submitted_url,
                "captcha_policy": attempt.captcha_policy,
                "browser_profile_directory": profile.directory_path if profile else None,
                "approved_site_memory": site_memory,
            },
        )
        self.apply_agent_result(job, attempt, result)

    def create_runner(self):
        return SkyvernRunner(
            sleep=self.sleep,
            settings=self.settings or SkyvernSettings.from_mapping(current_app.config),
        )

    def wait_before_attempt(self, job, attempt, site_config):
        delay_seconds = pre_attempt_delay_seconds(site_config)
        if delay_seconds <= 0:
            return

        record_event(
            get_session(),
            job.id,
            "polite_delay",
            "Waiting before opening the target service.",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"delay_seconds": delay_seconds},
        )
        self.sleep(delay_seconds)

    def apply_agent_result(self, job, attempt, result):
        if result.status == AGENT_SUCCESS:
            self.record_memory_from_agent_result(attempt, result, approved=True)
            record_event(
                get_session(),
                job.id,
                "agent_success",
                result.message or "Skyvern completed successfully.",
                attempt_id=attempt.id,
                site_id=attempt.site_id,
                submitted_url=attempt.submitted_url,
                context=agent_context(result),
            )
            self.complete_attempt(job, attempt)
            return

        status = agent_failure_status(result.status)
        if status in AGENT_SKIP_STATUSES:
            self.skip_agent_attempt(job, attempt, result)
            self.record_memory_from_agent_result(attempt, result, approved=False)
            return

        record_event(
            get_session(),
            job.id,
            "agent_failed",
            result.message or "Skyvern agent stopped.",
            level="warning",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context=agent_context(result),
        )
        self.fail_attempt(job, attempt, status, failure_reason(result, status))
        self.record_memory_from_agent_result(attempt, result, approved=False)

    def skip_agent_attempt(self, job, attempt, result):
        message = agent_reason(result) or f"Agent returned {result.status}."
        record_event(
            get_session(),
            job.id,
            "agent_failed",
            message,
            level="warning",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context=agent_context(result),
        )
        self.skip_attempt(job, attempt, message)

    def record_memory_from_agent_result(self, attempt, result, approved):
        evidence = result.evidence or {}
        strategy = evidence.get("strategy_summary")
        if not strategy:
            return
        record_site_memory(
            site_id=attempt.site_id,
            attempt_id=attempt.id,
            strategy=strategy,
            approved=approved,
        )

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

    def skip_attempt(self, job, attempt, reason):
        attempt.status = "skipped"
        attempt.failure_reason = reason
        attempt.finished_at = utc_now()
        record_event(
            get_session(),
            job.id,
            "attempt_failed",
            "Submission attempt skipped.",
            level="warning",
            attempt_id=attempt.id,
            site_id=attempt.site_id,
            submitted_url=attempt.submitted_url,
            context={"reason": reason, "status": "skipped"},
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
        if all(attempt.status == "success" for attempt in job.attempts):
            job.status = "completed"
        else:
            job.status = "failed"

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
        write_report(job.id, build_report(job))

def pre_attempt_delay_seconds(site_config):
    site_delay = site_config.get("pre_attempt_delay_seconds")
    if site_delay is not None:
        return max(0.0, float(site_delay))
    return max(0.0, float(current_app.config["AGENTIC_PRE_ATTEMPT_DELAY_SECONDS"]))
