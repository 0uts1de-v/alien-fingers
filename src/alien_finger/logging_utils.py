from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from alien_finger.config import APP_DIR, Config
from alien_finger.redaction import mask_secrets, truncate_text


class SessionLogger:
    def __init__(self, cfg: Config) -> None:
        self.enabled = cfg.log_sessions
        self.max_chars = cfg.max_output_chars
        self.path: Path | None = None
        if self.enabled:
            log_dir = APP_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.path = log_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"

    def log(self, event: str, data: dict[str, Any]) -> None:
        if not self.enabled or self.path is None:
            return
        safe_data = self._sanitize(data)
        record = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event, **safe_data}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def close(self) -> None:
        return

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            text, _ = truncate_text(mask_secrets(value), self.max_chars)
            return text
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        return value
