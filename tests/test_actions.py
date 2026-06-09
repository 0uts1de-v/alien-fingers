from __future__ import annotations

import pytest

from alien_finger.actions import ActionParseError, parse_action_response


def test_parse_action_json() -> None:
    response = parse_action_response(
        """
        {
          "thought_summary": "READMEを確認します。",
          "actions": [
            {"type": "read_file", "path": "README.md", "purpose": "セットアップ確認"}
          ]
        }
        """
    )
    assert response.thought_summary == "READMEを確認します。"
    assert response.actions[0].type == "read_file"
    assert response.actions[0].path == "README.md"


def test_parse_rejects_schema_violation() -> None:
    with pytest.raises(ActionParseError):
        parse_action_response('{"thought_summary":"x","actions":[{"type":"shell"}]}')
