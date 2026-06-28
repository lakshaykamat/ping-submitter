import logging

from app.logging_utils import HANDLER_NAME, LogfmtFormatter, configure_logging


def test_logfmt_formatter_outputs_stable_key_value_fields():
    formatter = LogfmtFormatter()
    record = logging.LogRecord(
        name="worker.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Worker loop started.",
        args=(),
        exc_info=None,
    )
    record.event = "worker_started"
    record.poll_interval = 5.0

    output = formatter.format(record)

    assert "level=INFO" in output
    assert "logger=worker.tasks" in output
    assert 'message="Worker loop started."' in output
    assert "event=worker_started" in output
    assert "poll_interval=5.0" in output


def test_configure_logging_reuses_existing_structured_handler():
    root_logger = logging.getLogger()
    existing_handlers = list(root_logger.handlers)
    try:
        root_logger.handlers = []

        configure_logging(level="INFO")
        configure_logging(level="DEBUG")

        structured_handlers = [
            handler for handler in root_logger.handlers if getattr(handler, "name", None) == HANDLER_NAME
        ]
        assert len(structured_handlers) == 1
        assert structured_handlers[0].level == logging.DEBUG
    finally:
        root_logger.handlers = existing_handlers
