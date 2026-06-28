import argparse
import logging

from app import create_app
from worker.tasks import SequentialWorker


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the submission worker.")
    parser.add_argument("--once", action="store_true", help="Run at most one queued job and exit.")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds to wait between empty polls.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        worker = SequentialWorker(app=app, poll_interval=args.poll_interval)
        logger.info(
            "Worker process started.",
            extra={"event": "worker_process_started", "once": args.once, "poll_interval": args.poll_interval},
        )
        if args.once:
            result = worker.run_once()
            logger.info(
                "Worker one-shot finished.",
                extra={
                    "event": "worker_once_finished",
                    "job_id": result["id"] if result else None,
                    "status": result["status"] if result else "idle",
                },
            )
        else:
            worker.run_forever()


if __name__ == "__main__":
    main()
