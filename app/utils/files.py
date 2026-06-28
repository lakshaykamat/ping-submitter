import re
import time


def safe_filename(value):
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-")
    return cleaned or "default"


def remove_old_files(directory, days):
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
