import pytest

from app import create_app
from app.models import JobEvent, SubmissionJob, get_session
from app.services import create_submission_job
from worker.tasks import SequentialWorker


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "REPORT_DIR": str(tmp_path / "reports"),
            "ARTIFACT_DIR": str(tmp_path / "artifacts"),
            "BROWSER_PROFILE_DIR": str(tmp_path / "profiles"),
        }
    )


def create_test_job(url):
    return create_submission_job(
        {
            "urls": [url],
            "sites": ["pingomatic"],
            "max_attempts": 1,
        }
    )


class CompletingRunner:
    def __init__(self):
        self.job_ids = []

    def run_job(self, job_id):
        session = get_session()
        job = session.get(SubmissionJob, job_id)
        self.job_ids.append(job_id)
        job.status = "completed"
        session.commit()
        return job


class FailingRunner:
    def run_job(self, job_id):
        raise RuntimeError("browser crashed")


def test_run_once_runs_oldest_runnable_job(app):
    with app.app_context():
        first_job = create_test_job("https://example.com/first")
        second_job = create_test_job("https://example.com/second")
        runner = CompletingRunner()

        result = SequentialWorker(app=app, runner=runner).run_once()

        assert result["id"] == first_job.id
        assert runner.job_ids == [first_job.id]
        assert get_session().get(SubmissionJob, first_job.id).status == "completed"
        assert get_session().get(SubmissionJob, second_job.id).status == "queued"


def test_run_once_returns_none_when_no_job_is_runnable(app):
    with app.app_context():
        job = create_test_job("https://example.com/done")
        job.status = "completed"
        get_session().commit()

        result = SequentialWorker(app=app, runner=CompletingRunner()).run_once()

        assert result is None


def test_run_once_marks_job_failed_when_runner_raises(app):
    with app.app_context():
        job = create_test_job("https://example.com/failure")

        result = SequentialWorker(app=app, runner=FailingRunner()).run_once()

        failed_job = get_session().get(SubmissionJob, job.id)
        worker_event = (
            get_session()
            .query(JobEvent)
            .filter(JobEvent.job_id == job.id, JobEvent.event_type == "worker_error")
            .one()
        )
        assert result["id"] == job.id
        assert result["status"] == "failed"
        assert failed_job.status == "failed"
        assert worker_event.level == "error"
        assert worker_event.context["error"] == "browser crashed"
        assert failed_job.report is not None
