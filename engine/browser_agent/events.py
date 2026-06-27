def record_browser_session_event(site, attempt_context, settings):
    context = {
        "backend": "local_browser_use",
        "playwright_headless": settings.headless,
        "stealth_or_evasion": False,
        "browser_profile_directory": attempt_context.get("browser_profile_directory"),
    }

    from app.models import get_session
    from app.services import record_event

    db_session = get_session()
    record_event(
        db_session,
        attempt_context["job_id"],
        "agent_checkpoint",
        "Local Browser Use agent started.",
        attempt_id=attempt_context["attempt_id"],
        site_id=site.get("id"),
        submitted_url=attempt_context.get("submitted_url"),
        context=context,
    )
    db_session.commit()


def record_screenshot_artifact(attempt_context, screenshot_path, index):
    from app.models import get_session
    from app.services import record_event

    record_event(
        get_session(),
        attempt_context["job_id"],
        "artifact_saved",
        f"Saved agent visual observation {index}.",
        attempt_id=attempt_context["attempt_id"],
        site_id=attempt_context.get("site_id"),
        submitted_url=attempt_context.get("submitted_url"),
        context={"stage": f"agent_step_{index:02d}", "screenshot_path": str(screenshot_path)},
    )
