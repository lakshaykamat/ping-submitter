import argparse

from app import create_app
from worker.tasks import SequentialWorker


def main():
    parser = argparse.ArgumentParser(description="Run the submission worker.")
    parser.add_argument("--once", action="store_true", help="Run at most one queued job and exit.")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds to wait between empty polls.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        worker = SequentialWorker(app=app, poll_interval=args.poll_interval)
        if args.once:
            worker.run_once()
        else:
            worker.run_forever()


if __name__ == "__main__":
    main()
