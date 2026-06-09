from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal


ActionType = Literal["shell", "read_file", "python", "web_search", "final"]


class ActionParseError(ValueError):
    """Raised when an AI action response cannot be parsed safely."""


@dataclass(slots=True)
class Action:
    type: ActionType
    purpose: str = ""
    command: str | None = None
    path: str | None = None
    code: str | None = None
    query: str | None = None
    message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        action_type = data.get("type")
        if action_type not in {"shell", "read_file", "python", "web_search", "final"}:
            raise ActionParseError(f"Unsupported action type: {action_type!r}")

        action = cls(
            type=action_type,
            purpose=str(data.get("purpose") or ""),
            command=_optional_str(data.get("command")),
            path=_optional_str(data.get("path")),
            code=_optional_str(data.get("code")),
            query=_optional_str(data.get("query")),
            message=_optional_str(data.get("message")),
            raw=data,
        )
        action.validate()
        return action

    def validate(self) -> None:
        required: dict[str, str] = {
            "shell": "command",
            "read_file": "path",
            "python": "code",
            "web_search": "query",
            "final": "message",
        }
        field_name = required[self.type]
        if not getattr(self, field_name):
            raise ActionParseError(f"{self.type!r} action requires {field_name!r}")

    def display_body(self) -> str:
        if self.type == "shell":
            return self.command or ""
        if self.type == "read_file":
            return self.path or ""
        if self.type == "python":
            return self.code or ""
        if self.type == "web_search":
            return self.query or ""
        return self.message or ""


@dataclass(slots=True)
class ActionResponse:
    thought_summary: str
    actions: list[Action]
    raw: dict[str, Any]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_action_response(text: str) -> ActionResponse:
    data = _loads_jsonish(text)
    if not isinstance(data, dict):
        raise ActionParseError("Top-level AI response must be a JSON object")
    actions_data = data.get("actions")
    if not isinstance(actions_data, list) or not actions_data:
        raise ActionParseError("AI response must include a non-empty actions array")
    actions: list[Action] = []
    for item in actions_data:
        if not isinstance(item, dict):
            raise ActionParseError("Each action must be an object")
        actions.append(Action.from_dict(item))
    return ActionResponse(
        thought_summary=str(data.get("thought_summary") or ""),
        actions=actions,
        raw=data,
    )


def extract_json_candidate(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _loads_jsonish(text: str) -> Any:
    candidate = extract_json_candidate(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ActionParseError(f"Invalid JSON: {exc}") from exc


def repair_json_locally(text: str) -> str:
    """Best-effort local cleanup before asking the model for repair."""

    candidate = extract_json_candidate(text)
    candidate = candidate.strip()
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    return candidate
