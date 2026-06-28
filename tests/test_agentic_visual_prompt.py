import pytest

from packages.browser_automation.prompts import _default_title, _parse_url, build_prompt
from packages.browser_automation.results import parse_skyvern_result
from packages.browser_automation.types import AgentResult


# --- URL parsing ---

@pytest.mark.parametrize(
    ("url", "hostname", "without_scheme", "default_title"),
    [
        ("https://example.com", "example.com", "example.com", "Example"),
        ("http://example.com", "example.com", "example.com", "Example"),
        ("https://www.example.com/path", "www.example.com", "www.example.com/path", "Example"),
        ("https://my-example-site.com:8443/a/b?x=1#top", "my-example-site.com", "my-example-site.com:8443/a/b?x=1#top", "My Example Site"),
        ("https://blog.company-name.io", "blog.company-name.io", "blog.company-name.io", "Company Name"),
        ("https://www.example.co.uk/path", "www.example.co.uk", "www.example.co.uk/path", "Example"),
        ("https://service.example.com.au", "service.example.com.au", "service.example.com.au", "Example"),
        ("https://localhost:5000/ping", "localhost", "localhost:5000/ping", "Localhost"),
        ("https://127.0.0.1:5000/ping", "127.0.0.1", "127.0.0.1:5000/ping", "Submitted URL"),
    ],
)
def test_parse_url_derives_correct_fields(url, hostname, without_scheme, default_title):
    result = _parse_url(url)

    assert result["full"] == url
    assert result["hostname"] == hostname
    assert result["without_scheme"] == without_scheme
    assert result["default_title"] == default_title


# --- Navigation goal ---

def test_navigation_goal_contains_full_url():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com")

    assert "https://example.com" in goal


def test_navigation_goal_contains_without_scheme_for_prefix_fields():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com/path")

    assert "example.com/path" in goal


def test_navigation_goal_uses_default_title_for_name_fields():
    goal = build_prompt({"url": "https://service.test/"}, "https://my-blog-site.com")

    assert "My Blog Site" in goal
    assert "my-blog-site.com" in goal


def test_navigation_goal_warns_against_doubled_scheme():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com")

    assert "http://http://" in goal


def test_navigation_goal_instructs_not_to_retype_correct_url():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com")

    assert "leave it untouched" in goal or "already contains" in goal


def test_navigation_goal_instructs_email_empty():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com")

    assert "Email" in goal or "email" in goal


def test_navigation_goal_instructs_success_confirmation():
    goal = build_prompt({"url": "https://service.test/"}, "https://example.com")

    assert "success" in goal.lower() or "confirm" in goal.lower()


# --- Result parsing ---

def test_parse_skyvern_result_completed_maps_to_success():
    result = parse_skyvern_result({"run_id": "tsk_1", "status": "completed", "failure_reason": None})

    assert isinstance(result, AgentResult)
    assert result.status == "success"
    assert result.evidence["skyvern_run_id"] == "tsk_1"


def test_parse_skyvern_result_canceled_maps_to_skipped():
    result = parse_skyvern_result({"run_id": "tsk_2", "status": "canceled", "failure_reason": None})

    assert result.status == "skipped"


def test_parse_skyvern_result_timed_out_maps_to_failed():
    result = parse_skyvern_result({"run_id": "tsk_3", "status": "timed_out", "failure_reason": None})

    assert result.status == "failed"
    assert "timed out" in result.message.lower()


def test_parse_skyvern_result_failed_with_captcha_reason():
    result = parse_skyvern_result({
        "run_id": "tsk_4",
        "status": "failed",
        "failure_reason": "reCAPTCHA was detected and could not be solved",
    })

    assert result.status == "captcha_failed"


def test_parse_skyvern_result_failed_with_login_reason():
    result = parse_skyvern_result({
        "run_id": "tsk_5",
        "status": "failed",
        "failure_reason": "Login required to access this page",
    })

    assert result.status == "login_required"


def test_parse_skyvern_result_failed_with_rate_limit_reason():
    result = parse_skyvern_result({
        "run_id": "tsk_6",
        "status": "failed",
        "failure_reason": "Access denied: too many requests",
    })

    assert result.status == "restricted_checkpoint"


def test_parse_skyvern_result_failed_with_generic_reason():
    result = parse_skyvern_result({
        "run_id": "tsk_7",
        "status": "failed",
        "failure_reason": "Could not find the submission form",
    })

    assert result.status == "failed"
    assert result.evidence["reason"] == "Could not find the submission form"


def test_parse_skyvern_result_terminated_maps_to_failed():
    result = parse_skyvern_result({"run_id": "tsk_8", "status": "terminated", "failure_reason": None})

    assert result.status == "failed"


def test_parse_skyvern_result_unknown_status_maps_to_agent_uncertain():
    result = parse_skyvern_result({"run_id": "tsk_9", "status": "unknown_future_status", "failure_reason": None})

    assert result.status == "agent_uncertain"
