from pathlib import Path

from trevoga.services.text_cleaner import clean_text, detect_keywords, format_post_html


RULES = [(("бпла",), Path("missing.jpg"), "БПЛА/Шахеди")]


def test_clean_text_removes_links_and_watermark():
    assert clean_text("Новина 🛰\nhttps://example.com\nOpenTrevoga 🕊") == "Новина"


def test_format_post_highlights_keywords_and_escapes_html():
    assert (
        format_post_html("БПЛА <тест>", RULES)
        == "<blockquote><b>БПЛА</b> &lt;тест&gt;</blockquote>"
    )


def test_detect_keywords():
    assert detect_keywords("Виявлено БПЛА", RULES) == ["БПЛА/Шахеди"]
