from __future__ import annotations

from alien_finger.redaction import mask_secrets, truncate_text


def test_token_masking() -> None:
    text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"
    masked = mask_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in masked
    assert "<redacted>" in masked


def test_max_output_truncation() -> None:
    clipped, truncated = truncate_text("x" * 100, 20)
    assert truncated is True
    assert len(clipped) > 20
    assert "truncated" in clipped
