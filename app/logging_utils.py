import logging
import sys
from datetime import datetime, timezone
from logging import LogRecord

from flask.logging import default_handler


HANDLER_NAME = "ping-mvp-structured"
LOG_RECORD_KEYS = set(LogRecord("", 0, "", 0, "", (), None).__dict__)


class LogfmtFormatter(logging.Formatter):
    def format(self, record):
        fields = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields.update(extra_fields(record))
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)
        return " ".join(f"{key}={format_logfmt_value(value)}" for key, value in fields.items())

    def formatTime(self, record, datefmt=None):
        created_at = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def configure_logging(app=None, level=None):
    log_level = resolve_log_level(level or (app.config.get("LOG_LEVEL") if app else None))
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    handler = structured_handler()
    handler.setLevel(log_level)
    handler.setFormatter(LogfmtFormatter())

    if not any(getattr(existing, "name", None) == HANDLER_NAME for existing in root_logger.handlers):
        root_logger.addHandler(handler)

    if app is not None:
        app.logger.setLevel(log_level)
        app.logger.propagate = True
        for existing in list(app.logger.handlers):
            if existing is default_handler or getattr(existing, "name", None) != HANDLER_NAME:
                app.logger.removeHandler(existing)


def structured_handler():
    for handler in logging.getLogger().handlers:
        if getattr(handler, "name", None) == HANDLER_NAME:
            return handler

    handler = logging.StreamHandler(sys.stdout)
    handler.name = HANDLER_NAME
    return handler


def resolve_log_level(value):
    if isinstance(value, int):
        return value
    level_name = str(value or "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def extra_fields(record):
    fields = {}
    for key, value in sorted(record.__dict__.items()):
        if key in LOG_RECORD_KEYS or key.startswith("_"):
            continue
        fields[key] = value
    return fields


def format_logfmt_value(value):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    if not text:
        return '""'
    if any(character.isspace() or character in {'"', "="} for character in text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return text
