from __future__ import annotations

import re


SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{8,})"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_=-]{20,}\.[A-Za-z0-9_=-]{20,}\.[A-Za-z0-9_=-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
]


def mask_secrets(text: str) -> str:
    masked = text
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            masked = pattern.sub(lambda m: f"{m.group(1)}=<redacted>", masked)
        else:
            masked = pattern.sub("<redacted>", masked)
    return masked


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    half = max_chars // 2
    omitted = len(text) - max_chars
    clipped = (
        text[:half]
        + f"\n\n... <truncated {omitted} characters; middle omitted> ...\n\n"
        + text[-(max_chars - half) :]
    )
    return clipped, True
