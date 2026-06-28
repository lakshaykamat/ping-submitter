import shutil
from pathlib import Path

from packages.browser_automation.results import browser_history_metadata


def copy_history_screenshots(history, attempt_context, artifact_dir):
    job_id = attempt_context.get("job_id")
    attempt_id = attempt_context.get("attempt_id")
    if not job_id or not attempt_id:
        return []

    screenshot_paths = browser_history_metadata(history).get("screenshot_paths") or []
    unique_paths = deduplicate_paths(screenshot_paths)
    if not unique_paths:
        return []

    destination_dir = Path(artifact_dir) / str(job_id) / str(attempt_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied_paths = []
    for index, screenshot_path in enumerate(unique_paths, start=1):
        source = Path(screenshot_path)
        if not source.exists():
            continue
        destination = destination_dir / f"agent_step_{index:02d}{source.suffix or '.png'}"
        shutil.copy2(source, destination)
        copied_paths.append(str(destination))
    return copied_paths


def deduplicate_paths(paths):
    unique_paths = []
    seen = set()
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        unique_paths.append(path)
    return unique_paths
