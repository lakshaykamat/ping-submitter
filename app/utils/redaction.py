import re


def redact_sensitive_data(value):
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if is_sensitive_key(key) else redact_sensitive_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


def is_sensitive_key(key):
    return bool(re.search(r"(api[_-]?key|secret|token|password|credential|captcha|answer)", str(key), re.I))
