from __future__ import annotations

from alien_finger.actions import Action
from alien_finger.config import Config
from alien_finger.safety import SafetyResult, should_auto_approve


def test_auto_approve_low_risk_only() -> None:
    cfg = Config(auto_approve=True, auto_approve_max_risk=25)
    action = Action(type="shell", command="ls -la", purpose="inspect")
    safety = SafetyResult(10, "safe", ["read-only"], can_auto_approve=True)

    assert should_auto_approve(action, safety, cfg) is True


def test_dangerous_not_auto_approved() -> None:
    cfg = Config(auto_approve=True, auto_approve_max_risk=100)
    action = Action(type="shell", command="sudo apt update", purpose="update")
    safety = SafetyResult(70, "dangerous", ["Privilege escalation via sudo"], can_auto_approve=False)

    assert should_auto_approve(action, safety, cfg) is False


def test_blocked_not_auto_approved() -> None:
    cfg = Config(auto_approve=True, auto_approve_max_risk=100)
    action = Action(type="shell", command="rm -rf /", purpose="bad idea")
    safety = SafetyResult(95, "blocked", ["blocked"], hard_block=True, can_auto_approve=False)

    assert should_auto_approve(action, safety, cfg) is False
