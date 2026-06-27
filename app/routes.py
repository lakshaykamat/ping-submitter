from threading import Thread

from flask import jsonify, redirect, render_template, request, send_file, url_for

from app.models import SubmissionJob, get_session
from app.services import (
    ValidationError,
    create_submission_job,
    get_browser_profiles,
    get_job,
    get_job_events,
    get_markdown_report,
    get_markdown_report_text,
    get_recent_events,
    get_report,
    get_report_record,
    load_sites,
    reset_browser_profile,
    status_values,
)
from worker.tasks import run_submission_job


def start_background_submission_job(app, job_id):
    thread = Thread(
        target=run_submission_job,
        kwargs={"job_id": job_id, "app": app},
        daemon=True,
        name=f"submission-job-{job_id}",
    )
    thread.start()
    return thread


def register_routes(app):
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def dashboard():
        session = get_session()
        jobs = session.query(SubmissionJob).order_by(SubmissionJob.created_at.desc()).all()
        sites = [site for site in load_sites().values() if site.get("enabled", True)]
        events = get_recent_events()
        return render_template(
            "dashboard.html",
            jobs=jobs,
            sites=sites,
            events=events,
            profiles=get_browser_profiles(),
        )

    @app.post("/jobs")
    def create_job_from_form():
        try:
            max_attempts = int(request.form.get("max_attempts", "3"))
        except ValueError:
            max_attempts = 0
        payload = {
            "urls": request.form.get("urls", "").splitlines(),
            "sites": request.form.getlist("sites"),
            "max_attempts": max_attempts,
        }
        try:
            job = create_submission_job(payload)
        except ValidationError as error:
            session = get_session()
            jobs = session.query(SubmissionJob).order_by(SubmissionJob.created_at.desc()).all()
            sites = [site for site in load_sites().values() if site.get("enabled", True)]
            events = get_recent_events()
            return render_template(
                "dashboard.html",
                jobs=jobs,
                sites=sites,
                events=events,
                profiles=get_browser_profiles(),
                error=str(error),
                form_data=payload,
            ), 400
        start_background_submission_job(app, job.id)
        return redirect(url_for("job_detail", job_id=job.id))

    @app.post("/jobs/<job_id>/run")
    def run_job_from_page(job_id):
        if get_job(job_id) is None:
            return render_template("job_detail.html", job=None), 404
        start_background_submission_job(app, job_id)
        return redirect(url_for("job_detail", job_id=job_id))

    @app.get("/jobs/<job_id>")
    def job_detail(job_id):
        job = get_job(job_id)
        if job is None:
            return render_template("job_detail.html", job=None), 404
        events = get_job_events(job_id)
        report = get_report(job_id)
        report_record = get_report_record(job_id)
        report_markdown = get_markdown_report_text(job_id)
        return render_template(
            "job_detail.html",
            job=job,
            events=events,
            report=report,
            report_record=report_record,
            report_markdown=report_markdown,
        )

    @app.post("/profiles/<site_id>/reset")
    def reset_profile(site_id):
        account_label = request.form.get("account_label", "default")
        reset_browser_profile(site_id, account_label)
        return redirect(request.referrer or url_for("dashboard"))

    @app.post("/api/jobs")
    def create_job():
        payload = request.get_json(silent=True) or {}
        try:
            job = create_submission_job(payload)
        except ValidationError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(job.to_dict(include_attempts=True)), 201

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id):
        job = get_job(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job.to_dict(include_attempts=True))

    @app.get("/api/jobs/<job_id>/events")
    def job_events(job_id):
        if get_job(job_id) is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify({"events": [event.to_dict() for event in get_job_events(job_id)]})

    @app.get("/api/jobs/<job_id>/report.json")
    def job_report(job_id):
        report = get_report(job_id)
        if report is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify(report)

    @app.get("/api/jobs/<job_id>/report.md")
    def job_markdown_report(job_id):
        if get_job(job_id) is None:
            return jsonify({"error": "job not found"}), 404
        path = get_markdown_report(job_id)
        if path is None:
            return jsonify({"error": "report not ready"}), 409
        return send_file(path, mimetype="text/markdown")

    @app.post("/api/jobs/<job_id>/run")
    def run_job_now(job_id):
        if get_job(job_id) is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify(run_submission_job(job_id, app=app))

    @app.get("/api/status-values")
    def api_status_values():
        return jsonify(status_values())
