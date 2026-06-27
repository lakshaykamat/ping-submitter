import json

from engine.types import AgentResult


def result_with_history_metadata(history, attempt_context=None, artifact_recorder=None):
    output = history.final_result() if hasattr(history, "final_result") else None
    if isinstance(output, dict):
        data = dict(output)
    elif output:
        data = parse_json_result(str(output))
    else:
        data = {
            "status": "agent_uncertain",
            "message": "Local Browser Use agent ended without a final result.",
            "evidence": {},
        }

    evidence = data.get("evidence") or {}
    evidence.update(browser_history_metadata(history))
    if artifact_recorder:
        artifact_paths = artifact_recorder(history, attempt_context or {})
        if artifact_paths:
            evidence["screenshot_paths"] = artifact_paths
            data["screenshot_path"] = artifact_paths[-1]
    data["evidence"] = evidence
    return data


def browser_history_metadata(history):
    def call_history_method(name, default):
        method = getattr(history, name, None)
        if not callable(method):
            return default
        value = method()
        return default if value is None else value

    return {
        "browser_use_backend": "local",
        "browser_use_is_done": call_history_method("is_done", None),
        "browser_use_is_successful": call_history_method("is_successful", None),
        "browser_use_steps": call_history_method("number_of_steps", None),
        "browser_use_urls": call_history_method("urls", []),
        "screenshot_paths": call_history_method("screenshot_paths", []),
    }


def parse_agent_result(raw_result):
    if isinstance(raw_result, AgentResult):
        return raw_result
    if isinstance(raw_result, dict):
        data = raw_result
    else:
        data = parse_json_result(str(raw_result))

    return AgentResult(
        status=data.get("status", "agent_uncertain"),
        message=data.get("message", ""),
        confidence=data.get("confidence"),
        evidence=data.get("evidence") or {},
        screenshot_path=data.get("screenshot_path"),
    )


def parse_json_result(value):
    normalized = strip_json_markdown(value)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return {
            "status": "agent_uncertain",
            "message": value,
            "evidence": {},
        }


def strip_json_markdown(value):
    stripped = str(value).strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
