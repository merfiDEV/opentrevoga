from trevoga.services.moderation import parse_result


def test_parse_rejected_result_with_reason():
    result = parse_result(
        42,
        '{"useful": false, "reason": "advertising", "reason_text": "Реклама", "confidence": 0.94}',
    )
    assert result.message_id == 42
    assert result.status == "rejected"
    assert result.reason == "advertising"
    assert result.confidence == 0.94


def test_invalid_ai_result_is_not_approved():
    result = parse_result(42, "ДА")
    assert result.useful is False
    assert result.status == "invalid_response"
    assert result.reason == "invalid_response"
