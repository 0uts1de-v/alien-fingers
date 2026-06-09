from __future__ import annotations

import json
import re
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from alien_finger.actions import Action
from alien_finger.config import Config
from alien_finger.prompts import SAFETY_EVALUATION_PROMPT, build_safety_messages
from alien_finger.providers.base import ChatProvider


RISK_ORDER = {"safe": 0, "caution": 1, "dangerous": 2, "blocked": 3}
RISK_BY_ORDER = {value: key for key, value in RISK_ORDER.items()}


@dataclass(slots=True)
class SafetyResult:
    risk_score: int
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    hard_block: bool = False
    can_auto_approve: bool = False
    safer_alternative: str | None = None
    rule_result: dict[str, Any] | None = None
    ai_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clamp_score(score: int) -> int:
    return max(0, min(100, int(score)))


def score_to_level(score: int) -> str:
    if score >= 90:
        return "blocked"
    if score >= 60:
        return "dangerous"
    if score >= 26:
        return "caution"
    return "safe"


def max_level(left: str, right: str) -> str:
    return RISK_BY_ORDER[max(RISK_ORDER.get(left, 0), RISK_ORDER.get(right, 0))]


def rule_based_evaluate(action: Action) -> SafetyResult:
    if action.type == "final":
        return SafetyResult(0, "safe", ["Final answer only"], can_auto_approve=True)
    if action.type == "read_file":
        return evaluate_read_file(action.path or "")
    if action.type == "python":
        return evaluate_python(action.code or "")
    if action.type == "web_search":
        return SafetyResult(15, "safe", ["Web search query only; network access occurs after approval"])
    return evaluate_shell(action.command or "")


def evaluate_shell(command: str) -> SafetyResult:
    normalized = command.strip()
    lowered = normalized.lower()
    reasons: list[str] = []
    score = 10
    hard_block = False

    blocked_patterns = [
        (r"\brm\s+-[^\n]*r[^\n]*f[^\n]*(?:\s+/|\s+~(?:\s|$)|\s+\$home(?:\s|$))", "Recursive force delete of root or home"),
        (r"\bmkfs(?:\.|\s|$)", "Filesystem formatting command"),
        (r"\bdd\s+[^|&;]*\bif=", "Raw disk copy with dd"),
        (r":\(\)\s*\{\s*:\|:&\s*\};:", "Fork bomb pattern"),
        (r"\bchmod\s+-r\s+777\s+/", "Recursive world-writable permissions on root"),
        (r"\bcat\b.*\|\s*(curl|nc|netcat)\b", "Possible secret exfiltration through pipe"),
    ]
    dangerous_patterns = [
        (r"\bsudo\b", "Privilege escalation via sudo"),
        (r"(^|\s)su(\s|$)", "Privilege escalation via su"),
        (r"\bchown\s+-r\b", "Recursive ownership change"),
        (r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh|python)\b", "Remote script execution"),
        (r"\brm\b", "File deletion"),
        (r"\bmv\b", "File move or overwrite risk"),
        (r"\bchmod\b", "Permission change"),
        (r"\bchown\b", "Ownership change"),
        (r"\b(pip|npm|pnpm|yarn|brew|apt|apt-get|dnf|yum)\s+(install|add|upgrade|update)\b", "Package or system install/update"),
        (r"\b(curl|wget|scp|ssh|rsync)\b", "Network or remote access"),
        (r"\b>\s*/", "Potential overwrite through redirection"),
    ]
    secret_patterns = [
        (r"\.ssh\b", "SSH credential path"),
        (r"\.aws\b", "AWS credential path"),
        (r"\.env\b", "Environment secret file"),
        (r"id_rsa|id_ed25519", "Private key filename"),
        (r"gcloud\s+.*credentials", "Cloud credential access"),
        (r"token|credential|secret|api[_-]?key", "Secret-like term"),
    ]

    for pattern, reason in blocked_patterns:
        if re.search(pattern, lowered):
            reasons.append(reason)
            score = max(score, 95)
            hard_block = True

    for pattern, reason in dangerous_patterns:
        if re.search(pattern, lowered):
            reasons.append(reason)
            score = max(score, 70)

    for pattern, reason in secret_patterns:
        if re.search(pattern, lowered):
            reasons.append(reason)
            score = max(score, 75)

    if re.search(r"\b(ls|pwd|find|du|df|git status|git diff|cat|head|tail|wc)\b", lowered) and score < 26:
        reasons.append("Appears to be read-only inspection")
        score = min(score, 18)

    if not reasons:
        reasons.append("No destructive, credential, network, or privilege pattern detected")

    level = "blocked" if hard_block else score_to_level(score)
    return SafetyResult(clamp_score(score), level, reasons, hard_block=hard_block, can_auto_approve=level == "safe")


def evaluate_read_file(path: str) -> SafetyResult:
    lowered = path.lower()
    reasons = ["File read only"]
    score = 12
    secret_terms = [".env", ".ssh", ".aws", "id_rsa", "id_ed25519", "token", "credential", "secret", "api_key", "apikey"]
    if any(term in lowered for term in secret_terms):
        reasons.append("Path appears to contain secrets or credentials")
        score = 75
    if Path(path).anchor == str(Path(path)):
        reasons.append("Path points to filesystem root")
        score = max(score, 60)
    level = score_to_level(score)
    return SafetyResult(score, level, reasons, can_auto_approve=level == "safe")


def evaluate_python(code: str) -> SafetyResult:
    lowered = code.lower()
    reasons = ["Python code execution in dedicated venv"]
    score = 20
    patterns = [
        (r"\b(open|write_text|write_bytes|remove|unlink|rmtree|rename|replace)\b", "May write, delete, or move files"),
        (r"\brequests\.|httpx\.|urllib|socket\b", "May perform network access"),
        (r"\bsubprocess|os\.system|pty\b", "May spawn subprocesses"),
        (r"\btoken|secret|credential|api_key|\.env|\.ssh\b", "May access secrets"),
        (r"\bpip\s+install\b", "May install packages"),
    ]
    for pattern, reason in patterns:
        if re.search(pattern, lowered):
            reasons.append(reason)
            score = max(score, 55)
    level = score_to_level(score)
    return SafetyResult(score, level, reasons, can_auto_approve=level == "safe")


def parse_ai_safety_response(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Safety response did not contain JSON")
    data = json.loads(text[start : end + 1])
    return {
        "risk_score": clamp_score(int(data.get("risk_score", 50))),
        "risk_level": str(data.get("risk_level", "caution")),
        "can_auto_approve": bool(data.get("can_auto_approve", False)),
        "reasons": list(data.get("reasons") or []),
        "safer_alternative": data.get("safer_alternative"),
    }


def ai_evaluate(
    action: Action,
    user_request: str,
    provider: ChatProvider,
    timeout: float = 60.0,
) -> dict[str, Any]:
    action_json = json.dumps(action.raw or _action_to_dict(action), ensure_ascii=False)
    text = provider.chat(
        build_safety_messages(action_json, user_request),
        system_prompt=SAFETY_EVALUATION_PROMPT,
        temperature=0,
        timeout=timeout,
    )
    return parse_ai_safety_response(text)


def combined_safety(
    action: Action,
    user_request: str,
    provider: ChatProvider | None = None,
) -> SafetyResult:
    rule = rule_based_evaluate(action)
    ai_data: dict[str, Any] | None = None
    if provider is not None and action.type != "final":
        try:
            ai_data = ai_evaluate(action, user_request, provider)
        except Exception as exc:  # Keep approval gate conservative if AI review fails.
            ai_data = {
                "risk_score": max(rule.risk_score, 40),
                "risk_level": max_level(rule.risk_level, "caution"),
                "can_auto_approve": False,
                "reasons": [f"AI safety evaluation failed: {exc}"],
                "safer_alternative": None,
            }
    if not ai_data:
        result = rule
        result.rule_result = _compact(rule)
        return result

    score = max(rule.risk_score, clamp_score(int(ai_data["risk_score"])))
    level = max_level(rule.risk_level, str(ai_data["risk_level"]))
    reasons = [*rule.reasons, *list(ai_data.get("reasons") or [])]
    result = SafetyResult(
        risk_score=score,
        risk_level=level,
        reasons=reasons,
        hard_block=rule.hard_block,
        can_auto_approve=bool(ai_data.get("can_auto_approve")) and rule.can_auto_approve and level == "safe",
        safer_alternative=ai_data.get("safer_alternative"),
        rule_result=_compact(rule),
        ai_result=ai_data,
    )
    return result


def requires_manual_by_policy(action: Action, safety: SafetyResult, cfg: Config) -> bool:
    if safety.hard_block or safety.risk_level in {"dangerous", "blocked"}:
        return True
    if safety.risk_score > cfg.auto_approve_max_risk:
        return True
    if action.type not in cfg.auto_approve_action_types:
        return True
    body = action.display_body().lower()
    for token in cfg.always_require_manual_approval_for:
        try:
            parts = shlex.split(body, posix=False)
        except ValueError:
            parts = body.split()
        if token.lower() in parts or re.search(rf"\b{re.escape(token.lower())}\b", body):
            return True
    sensitive_reason = " ".join(safety.reasons).lower()
    manual_terms = [
        "secret",
        "credential",
        "external",
        "network",
        "privilege",
        "destructive",
        "delete",
        "package",
        "install",
        "permission",
        "ownership",
    ]
    return any(term in sensitive_reason for term in manual_terms)


def should_auto_approve(action: Action, safety: SafetyResult, cfg: Config, session_auto: bool = False) -> bool:
    if not cfg.auto_approve and not session_auto:
        return False
    if requires_manual_by_policy(action, safety, cfg):
        return False
    return safety.can_auto_approve and safety.risk_level == "safe"


def _compact(result: SafetyResult) -> dict[str, Any]:
    return {
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "reasons": result.reasons,
        "hard_block": result.hard_block,
    }


def _action_to_dict(action: Action) -> dict[str, Any]:
    return {
        "type": action.type,
        "purpose": action.purpose,
        "command": action.command,
        "path": action.path,
        "code": action.code,
        "query": action.query,
        "message": action.message,
    }
