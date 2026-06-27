def run_submission_job(job_id, app=None, runner=None):
    if app is None:
        from app import create_app

        app = create_app()

    with app.app_context():
        if runner is None:
            from automation.runner import AutomationRunner

            runner = AutomationRunner()
        return runner.run_job(job_id).to_dict(include_attempts=True)
