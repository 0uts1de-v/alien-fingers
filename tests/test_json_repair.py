from __future__ import annotations

from alien_finger.actions import parse_action_response, repair_json_locally


def test_local_json_repair_trailing_comma() -> None:
    broken = """
    ```json
    {
      "thought_summary": "done",
      "actions": [{"type": "final", "message": "ok",}],
    }
    ```
    """
    repaired = repair_json_locally(broken)
    response = parse_action_response(repaired)

    assert response.actions[0].message == "ok"
