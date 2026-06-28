from pathlib import Path


def resolve_db_url(url, base_dir):
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url.startswith(prefix + "/"):
        return url

    relative_path = url[len(prefix):]
    if not relative_path or Path(relative_path).is_absolute():
        return url

    return f"{prefix}{Path(base_dir) / relative_path}"
