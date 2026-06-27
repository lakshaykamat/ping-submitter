#!/usr/bin/env python3
import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_STATUSES = {"completed", "failed", "canceled"}


def main():
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}"
    submitted_url = args.url or f"https://example.com/live-smoke-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    server = None
    owns_server = False

    try:
        if args.reuse_server and is_server_ready(base_url):
            print(f"Using existing server at {base_url}")
        else:
            if is_server_ready(base_url):
                args.port = find_open_port(args.host, args.port + 1)
                base_url = f"http://{args.host}:{args.port}"
                print(f"Port {args.port - 1} already has a server. Starting visible-browser server on {base_url}")
            server = start_server(args)
            owns_server = True
            wait_for_server(base_url, args.startup_timeout)

        payload = {"urls": [submitted_url], "sites": [args.site], "max_attempts": args.max_attempts}
        job = request_json("POST", f"{base_url}/api/jobs", payload)
        job_id = job["id"]
        job_url = f"{base_url}/jobs/{job_id}"
        print(f"Created job: {job_id}")
        print(f"Submitted URL: {submitted_url}")
        print(f"Site: {args.site}")
        print(f"Opening local job page: {job_url}")
        webbrowser.open(job_url)

        run_result = {}
        run_thread = threading.Thread(
            target=run_job_request,
            args=(base_url, job_id, run_result),
            daemon=True,
        )
        run_thread.start()

        final_job = monitor_job(base_url, job_id, args.timeout, run_thread)
        run_thread.join(timeout=1)
        if "error" in run_result:
            print(f"Run request failed: {run_result['error']}", file=sys.stderr)
            return 1

        report = request_json("GET", f"{base_url}/api/jobs/{job_id}/report.json")
        print_summary(report, final_job)
        return 0 if is_success(report) else 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Live flow test failed: {error}", file=sys.stderr)
        return 1
    finally:
        if owns_server and server:
            stop_server(server)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a visible, live end-to-end submission against a real external ping site."
    )
    parser.add_argument("url", nargs="?", help="URL to submit. Defaults to a random example.com URL.")
    parser.add_argument("--site", default="pingomatic", help="Configured site id to submit to.")
    parser.add_argument("--max-attempts", type=int, default=1, help="Maximum attempts for this live run.")
    parser.add_argument("--host", default="127.0.0.1", help="Flask host.")
    parser.add_argument("--port", type=int, default=5000, help="Flask port.")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds to wait for completion/CAPTCHA.")
    parser.add_argument("--startup-timeout", type=int, default=30, help="Seconds to wait for Flask startup.")
    parser.add_argument(
        "--reuse-server",
        action="store_true",
        help="Use an existing Flask server instead of starting one with PLAYWRIGHT_HEADLESS=false.",
    )
    return parser.parse_args()


def start_server(args):
    env = os.environ.copy()
    env["PLAYWRIGHT_HEADLESS"] = "false"
    env["CAPTCHA_WAIT_SECONDS"] = str(args.timeout)
    env["PYTHONUNBUFFERED"] = "1"
    command = [
        sys.executable,
        "-m",
        "flask",
        "--app",
        "app:create_app",
        "run",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    print(f"Starting Flask server with visible Playwright browser support on {args.host}:{args.port}")
    return subprocess.Popen(command, env=env)


def stop_server(server):
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def wait_for_server(base_url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_server_ready(base_url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"server did not become ready within {timeout} seconds")


def is_server_ready(base_url):
    try:
        data = request_json("GET", f"{base_url}/health", timeout=2)
        return data.get("status") == "ok"
    except Exception:
        return False


def find_open_port(host, start_port):
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) != 0:
                return port
        port += 1
    raise RuntimeError(f"could not find an open port starting at {start_port}")


def run_job_request(base_url, job_id, result):
    try:
        result["data"] = request_json("POST", f"{base_url}/api/jobs/{job_id}/run", timeout=None)
    except Exception as error:
        result["error"] = str(error)


def monitor_job(base_url, job_id, timeout, run_thread):
    opened_challenges = set()
    seen_events = set()
    deadline = time.monotonic() + timeout
    latest_job = None

    while time.monotonic() < deadline:
        latest_job = request_json("GET", f"{base_url}/api/jobs/{job_id}")
        events = request_json("GET", f"{base_url}/api/jobs/{job_id}/events")["events"]
        for event in events:
            event_id = event["id"]
            if event_id in seen_events:
                continue
            seen_events.add(event_id)
            print_event(event)
            if event["event_type"] == "captcha_detected":
                challenge_id = event["context"].get("challenge_id")
                if challenge_id and challenge_id not in opened_challenges:
                    opened_challenges.add(challenge_id)
                    captcha_url = f"{base_url}/captcha/{challenge_id}"
                    print("CAPTCHA detected.")
                    print("Solve it in the visible Playwright browser if it is interactive.")
                    print(f"Then open/submit the local CAPTCHA page to resume: {captcha_url}")
                    webbrowser.open(captcha_url)

        if latest_job["status"] in TERMINAL_STATUSES and not run_thread.is_alive():
            return latest_job
        time.sleep(2)

    raise TimeoutError(f"job did not finish within {timeout} seconds")


def print_event(event):
    context = event.get("context") or {}
    reason = context.get("reason") or context.get("status") or ""
    suffix = f" ({reason})" if reason else ""
    print(f"[{event['event_type']}] attempt={event['attempt_id']} site={event['site_id']} {event['message']}{suffix}")


def request_json(method, url, payload=None, timeout=30):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url} returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"{method} {url} failed: {error}") from error


def is_success(report):
    attempts = report.get("attempts", [])
    return (
        report.get("status") == "completed"
        and report.get("total_attempts", 0) > 0
        and report.get("success_count") == report.get("total_attempts")
        and all(attempt.get("status") == "success" for attempt in attempts)
    )


def print_summary(report, job):
    print("")
    print("Final result")
    print(f"Job: {report['job_id']}")
    print(f"Status: {report['status']} (API job status: {job['status']})")
    print(f"Attempts: {report['success_count']} success / {report['failure_count']} failed / {report['captcha_count']} captcha")
    for attempt in report["attempts"]:
        failure = f" failure={attempt['failure_reason']}" if attempt["failure_reason"] else ""
        print(f"- {attempt['site_id']} {attempt['submitted_url']} -> {attempt['status']}{failure}")
    if is_success(report):
        print("SUCCESS: external site accepted the submission flow.")
    else:
        print("FAILED: one or more attempts did not reach success.")


if __name__ == "__main__":
    raise SystemExit(main())
