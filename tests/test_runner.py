import pytest

from app import create_app
from app.models import CaptchaChallenge, SubmissionAttempt, SubmissionJob, get_session
from app.services import create_submission_job, save_captcha_answer
from automation.runner import AutomationRunner
from tests.fakes import FakeBrowserManager, FakePage, TemporaryNetworkError
from worker.tasks import run_submission_job


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "LOG_DIR": str(tmp_path / "logs"),
            "REPORT_DIR": str(tmp_path / "reports"),
            "CAPTCHA_WAIT_SECONDS": 0,
        }
    )


def create_test_job(app):
    with app.app_context():
        return create_submission_job(
            {
                "urls": ["https://example.com/post-1"],
                "sites": ["pingomatic"],
                "max_attempts": 3,
            }
        ).id


def run_with_pages(app, job_id, pages, captcha_wait_seconds="config"):
    runner = AutomationRunner(
        browser_manager_factory=lambda: FakeBrowserManager(pages),
        sleep=lambda seconds: None,
        captcha_wait_seconds=captcha_wait_seconds,
    )
    with app.app_context():
        return runner.run_job(job_id)


def get_first_attempt(app, job_id):
    with app.app_context():
        session = get_session()
        return session.query(SubmissionAttempt).filter_by(job_id=job_id).one()


def test_runner_marks_captcha_attempts_as_captcha_required(app):
    job_id = create_test_job(app)
    page = FakePage(selectors={'iframe[src*="recaptcha"]': 1})

    run_with_pages(app, job_id, [page], captcha_wait_seconds=None)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "captcha_required"
    with app.app_context():
        challenge = get_session().query(CaptchaChallenge).filter_by(job_id=job_id).one()
        assert challenge.screenshot_path.endswith(f"{job_id}-{attempt.id}-captcha.png")


def test_runner_marks_timeout_as_captcha_timeout(app):
    job_id = create_test_job(app)
    page = FakePage(selectors={'iframe[src*="recaptcha"]': 1})

    run_with_pages(app, job_id, [page], captcha_wait_seconds=0)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "captcha_timeout"


def test_retry_logic_retries_timeouts(app):
    job_id = create_test_job(app)
    first_page = FakePage(goto_errors=[TemporaryNetworkError("navigation timeout")])
    second_page = FakePage(
        selectors={'input[name="blogurl"]': 1, 'input[type="submit"]': 1},
        html="ping sent",
    )

    run_with_pages(app, job_id, [first_page, second_page], captcha_wait_seconds=0)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "success"
    assert attempt.retry_count == 1
    assert attempt.attempt_number == 2


def test_retry_logic_does_not_retry_missing_form(app):
    job_id = create_test_job(app)
    page = FakePage(selectors={'input[type="submit"]': 1})

    run_with_pages(app, job_id, [page], captcha_wait_seconds=0)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "failed"
    assert attempt.retry_count == 0
    assert "No URL input field found" in attempt.failure_reason


def test_worker_processes_job_and_updates_attempt_status(app):
    job_id = create_test_job(app)
    page = FakePage(
        selectors={'input[name="blogurl"]': 1, 'input[type="submit"]': 1},
        html="ping sent",
    )
    runner = AutomationRunner(
        browser_manager_factory=lambda: FakeBrowserManager([page]),
        sleep=lambda seconds: None,
        captcha_wait_seconds=0,
    )

    result = run_submission_job(job_id, app=app, runner=runner)

    assert result["status"] == "completed"
    assert result["attempts"][0]["status"] == "success"
    with app.app_context():
        job = get_session().get(SubmissionJob, job_id)
        assert job.status == "completed"


def test_runner_fills_pingomatic_fields_and_requires_success_text(app):
    job_id = create_test_job(app)
    page = FakePage(
        selectors={
            'input[name="title"]': 1,
            'input[name="blogurl"]': 1,
            'input[name="rssurl"]': 1,
            'input[type="checkbox"].common': 1,
            "a.bigbutton": 1,
        },
        html="Pinging complete",
    )

    run_with_pages(app, job_id, [page], captcha_wait_seconds=0)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "success"
    assert page.filled['input[name="title"]'] == "Live smoke test example.com"
    assert page.filled['input[name="blogurl"]'] == "https://example.com/post-1"
    assert page.filled['input[name="rssurl"]'] == "https://example.com/post-1/feed"
    assert page.checked == ['input[type="checkbox"].common']
    assert page.clicked == ["a.bigbutton"]


def test_runner_fails_when_success_confirmation_is_missing(app):
    job_id = create_test_job(app)
    page = FakePage(
        selectors={
            'input[name="blogurl"]': 1,
            "a.bigbutton": 1,
        },
        html="Request received without confirmation text",
    )

    run_with_pages(app, job_id, [page], captcha_wait_seconds=0)

    attempt = get_first_attempt(app, job_id)
    assert attempt.status == "failed"
    assert "Site did not show success confirmation" in attempt.failure_reason


def test_manual_captcha_answer_requeues_attempt_for_resume(app):
    job_id = create_test_job(app)
    page = FakePage(selectors={'iframe[src*="recaptcha"]': 1})

    run_with_pages(app, job_id, [page], captcha_wait_seconds=None)

    with app.app_context():
        session = get_session()
        challenge = session.query(CaptchaChallenge).filter_by(job_id=job_id).one()
        save_captcha_answer(challenge.id, "12345")
        attempt = session.query(SubmissionAttempt).filter_by(job_id=job_id).one()
        job = session.get(SubmissionJob, job_id)

        assert attempt.status == "queued"
        assert job.status == "queued"
