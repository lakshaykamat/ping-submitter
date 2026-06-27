from pathlib import Path
import logging
import sys

import click
from dotenv import load_dotenv
from flask import Flask
from flask.logging import default_handler

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import Config
from app.models import init_database
from app.routes import register_routes


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
    return app

def configure_logging(app):
    app.logger.setLevel(logging.INFO)
    if default_handler in app.logger.handlers:
        app.logger.removeHandler(default_handler)
    if any(getattr(handler, "name", None) == "ping-mvp-cli" for handler in app.logger.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.name = "ping-mvp-cli"
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    app.logger.addHandler(handler)


def register_cli(app):
    @app.cli.command("cleanup")
    @click.option("--days", default=7, show_default=True, help="Delete generated reports older than this many days.")
    def cleanup(days):
        removed_count = remove_old_files(Path(app.config["REPORT_DIR"]), days)
        click.echo(f"Removed {removed_count} generated files.")


def remove_old_files(directory, days):
    import time

    if not directory.exists():
        return 0
    cutoff = time.time() - days * 24 * 60 * 60
    removed_count = 0
    for path in directory.iterdir():
        if path.name == ".gitkeep" or not path.is_file():
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed_count += 1
    return removed_count
