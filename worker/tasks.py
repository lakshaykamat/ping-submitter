import logging
import time

from flask import has_app_context

from app.models import SubmissionJob, get_session
from app.services import build_report, record_event, write_report
from app.services.statuses import RUNNABLE_JOB_STATUSES, TERMINAL_JOB_STATUSES


logger = logging.getLogger(__name__)


def run_submission_job(job_id, app=None, runner=None):
    if app is None:
        if has_app_context():
            return _run_submission_job(job_id, runner)

        from app import create_app
        app = create_app()

    with app.app_context():
        return _run_submission_job(job_id, runner)


def _run_submission_job(job_id, runner=None):
    if runner is None:
        from worker.execution import AutomationRunner

        runner = AutomationRunner()
    return runner.run_job(job_id).to_dict(include_attempts=True)


class SequentialWorker:
    def __init__(self, app=None, runner=None, poll_interval=5.0, sleep=time.sleep):
        from worker.execution import AutomationRunner

        self.app = app
        self.poll_interval = poll_interval
        self.sleep = sleep
        if runner is None:
            self.runner = AutomationRunner()
            self.runner.initialize()
        else:
            self.runner = runner

    def run_once(self):
        job = next_runnable_job()
        if job is None:
            logger.debug("No runnable job found.", extra={"event": "worker_idle"})
            return None

        logger.info("Running submission job.", extra={"event": "job_run_started", "job_id": job.id})
        try:
            result = run_submission_job(job.id, app=self.app, runner=self.runner)
            logger.info(
                "Submission job finished.",
                extra={"event": "job_run_finished", "job_id": job.id, "status": result["status"]},
            )
            return result
        except Exception as error:
            logger.exception(
                "Submission job failed in worker.",
                extra={"event": "job_run_error", "job_id": job.id, "error": str(error)},
            )
            return mark_job_failed(job.id, error)

    def run_forever(self):
        logger.info(
            "Worker loop started.",
            extra={"event": "worker_started", "poll_interval": self.poll_interval},
        )
        while True:
            result = self.run_once()
            if result is None:
                self.sleep(self.poll_interval)


def next_runnable_job():
    session = get_session()
    return (
        session.query(SubmissionJob)
        .filter(SubmissionJob.status.in_(sorted(RUNNABLE_JOB_STATUSES)))
        .order_by(SubmissionJob.created_at.asc())
        .first()
    )


def mark_job_failed(job_id, error):
    session = get_session()
    job = session.get(SubmissionJob, job_id)
    if job is None:
        return None

    if job.status not in TERMINAL_JOB_STATUSES:
        job.status = "failed"

    record_event(
        session=session,
        job_id=job.id,
        event_type="worker_error",
        message="Worker failed while running submission job.",
        level="error",
        context={"error": str(error)},
    )
    write_report(job.id, build_report(job))
    session.commit()
    return job.to_dict(include_attempts=True)
