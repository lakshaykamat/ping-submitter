from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import Config
from app.logging_utils import configure_logging
from app.models import init_database
from app.routes import register_routes
from app.utils.files import remove_old_files


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.config["REPORT_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["ARTIFACT_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BROWSER_PROFILE_DIR"]).mkdir(parents=True, exist_ok=True)

    configure_logging(app)
    init_database(app)
    register_routes(app)
    register_cli(app)
    app.logger.info(
        "Application configured.",
        extra={
            "event": "server_configured",
            "database_url": app.config["DATABASE_URL"],
            "sites_config_path": app.config["SITES_CONFIG_PATH"],
            "log_level": app.config["LOG_LEVEL"],
            "testing": app.config["TESTING"],
        },
    )
    return app


def register_cli(app):
    @app.cli.command("cleanup")
    @click.option("--days", default=7, show_default=True, help="Delete generated reports older than this many days.")
    def cleanup(days):
        removed_count = remove_old_files(Path(app.config["REPORT_DIR"]), days)
        click.echo(f"Removed {removed_count} generated files.")

    @app.cli.command("worker")
    @click.option("--once", is_flag=True, help="Run at most one queued job and exit.")
    @click.option("--poll-interval", default=5.0, show_default=True, help="Seconds to wait between empty polls.")
    def worker(once, poll_interval):
        from worker.tasks import SequentialWorker

        app.logger.info(
            "Worker command invoked.",
            extra={"event": "worker_command_started", "once": once, "poll_interval": poll_interval},
        )
        submission_worker = SequentialWorker(app=app, poll_interval=poll_interval)
        if once:
            result = submission_worker.run_once()
            if result is None:
                click.echo("No runnable jobs.")
            else:
                click.echo(f"Ran job {result['id']} with status {result['status']}.")
            return

        submission_worker.run_forever()
