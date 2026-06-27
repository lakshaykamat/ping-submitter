import json
from pathlib import Path

import pytest

from app import create_app
from app.models import JobReport, get_session
from automation.types import REQUIRED_LOG_FIELDS


@pytest.fixture
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "LOG_DIR": str(tmp_path / "logs"),
            "REPORT_DIR": str(tmp_path / "reports"),
        }
    )
    with app.test_client() as test_client:
        yield test_client


def create_job(client, urls=None, sites=None, max_attempts=3):
    payload = {
        "urls": urls or ["https://example.com/post-1"],
        "sites": sites or ["pingomatic"],
        "max_attempts": max_attempts,
    }
    return client.post("/api/jobs", json=payload)


def test_api_accepts_valid_urls(client):
    response = create_job(client, urls=["https://example.com/post-1"])

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "queued"
    assert data["url_count"] == 1
    assert data["site_count"] == 1
    assert data["attempts"][0]["submitted_url"] == "https://example.com/post-1"


def test_api_rejects_invalid_urls(client):
    response = create_job(client, urls=["not-a-url"])

    assert response.status_code == 400
    assert "invalid URL" in response.get_json()["error"]


def test_api_rejects_disabled_guestbook_sites(client):
    response = create_job(client, sites=["wdso_guestbook"])

    assert response.status_code == 400
    assert response.get_json()["error"] == "site is disabled: wdso_guestbook"


def test_job_creation_creates_one_attempt_per_url_site_pair(client):
    response = create_job(
        client,
        urls=["https://example.com/post-1", "https://example.com/post-2"],
        sites=["pingomatic", "pingmyurls"],
    )

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["attempts"]) == 4
    assert {(attempt["submitted_url"], attempt["site_id"]) for attempt in data["attempts"]} == {
        ("https://example.com/post-1", "pingomatic"),
        ("https://example.com/post-1", "pingmyurls"),
        ("https://example.com/post-2", "pingomatic"),
        ("https://example.com/post-2", "pingmyurls"),
    }


def test_job_status_endpoint_returns_job_and_attempts(client):
    create_response = create_job(client, sites=["pingomatic", "pingmyurls"])
    job_id = create_response.get_json()["id"]

    status_response = client.get(f"/api/jobs/{job_id}")

    assert status_response.status_code == 200
    data = status_response.get_json()
    assert data["id"] == job_id
    assert data["status"] == "queued"
    assert len(data["attempts"]) == 2


def test_log_file_contains_required_fields(client, tmp_path):
    response = create_job(client)
    job_id = response.get_json()["id"]
    log_file = tmp_path / "logs" / f"{job_id}.jsonl"

    log_entries = [json.loads(line) for line in log_file.read_text().splitlines()]

    assert log_entries
    for field in REQUIRED_LOG_FIELDS:
        assert field in log_entries[0]


def test_report_endpoint_returns_valid_json(client):
    create_response = create_job(client, sites=["pingomatic", "pingmyurls"])
    job_id = create_response.get_json()["id"]

    report_response = client.get(f"/api/jobs/{job_id}/report.json")

    assert report_response.status_code == 200
    report = report_response.get_json()
    assert report["job_id"] == job_id
    assert report["job"]["id"] == job_id
    assert len(report["attempts"]) == 2


def test_job_creation_stores_report_in_database_and_files(client, tmp_path):
    create_response = create_job(client)
    job_id = create_response.get_json()["id"]

    with client.application.app_context():
        report_record = get_session().query(JobReport).filter_by(job_id=job_id).one()

        assert report_record.json_data()["job_id"] == job_id
        assert f"# Job {job_id} Report" in report_record.markdown_content
        assert Path(report_record.json_path).exists()
        assert Path(report_record.markdown_path).exists()
        assert Path(report_record.markdown_path).suffix == ".md"


def test_markdown_report_endpoint_returns_text(client):
    create_response = create_job(client)
    job_id = create_response.get_json()["id"]

    report_response = client.get(f"/api/jobs/{job_id}/report.md")

    assert report_response.status_code == 200
    assert f"# Job {job_id} Report" in report_response.text


def test_dashboard_renders_with_job_form(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Submission Jobs" in response.text
    assert 'name="urls"' in response.text
    assert "Create job" in response.text


def test_job_detail_shows_activity_and_stored_report(client):
    create_response = create_job(client)
    job_id = create_response.get_json()["id"]

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert "Activity" in response.text
    assert "Stored report" in response.text
    assert "job_reports #" in response.text
    assert f"# Job {job_id} Report" in response.text


def test_job_creation_logs_to_cli(client, caplog):
    create_job(client)

    assert "job_created" in caplog.text
