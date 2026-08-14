from datetime import date

from worker.prompt_builder import build_daily_prompt


def test_daily_prompt_truncates_oversized_source_bodies():
    prompt = build_daily_prompt(
        [
            {
                "source_type": "gmail",
                "source_id": "msg-1",
                "heading": "Large newsletter",
                "body": "A" * 50,
                "item_hash": "abc",
            }
        ],
        run_date=date(2026, 8, 14),
        max_item_body_chars=10,
    )

    assert "A" * 10 in prompt
    assert "A" * 11 not in prompt
    assert "[Source body truncated: 40 characters omitted.]" in prompt
    assert "Large newsletter" in prompt
