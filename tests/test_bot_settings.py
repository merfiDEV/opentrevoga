from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from botsrc.broadcast import Broadcaster, card_label, fold_homoglyphs, strip_card_links
from botsrc.storage import SubscriptionStore


def _store(tmp_path) -> SubscriptionStore:
    return SubscriptionStore(tmp_path / "test.db")


def _bot() -> SimpleNamespace:
    return SimpleNamespace(
        send_photo=AsyncMock(),
        send_video=AsyncMock(),
        send_document=AsyncMock(),
        send_message=AsyncMock(),
        send_media_group=AsyncMock(),
    )


def _message(html_text: str, photo: bool = True):
    return SimpleNamespace(
        html_text=html_text,
        caption=html_text,
        text=html_text,
        photo=[SimpleNamespace(file_id="file")] if photo else None,
        video=None,
        document=None,
        media_group_id=None,
    )


CARD_CAPTION = (
    "<blockquote>Швидкісна ціль над Одесою\n\n"
    '<a href="https://uk.wikipedia.org/wiki/Крилата_ракета">Швидкісна ціль</a>'
    "</blockquote>"
)


def test_hint_settings_default_on(tmp_path):
    store = _store(tmp_path)
    assert store.hint_settings(1) == (True, True)


def test_hint_settings_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.set_hint_settings(1, photo_on=False, wiki_on=False)
    assert store.hint_settings(1) == (False, False)
    store.set_hint_settings(1, photo_on=True, wiki_on=False)
    assert store.hint_settings(1) == (True, False)
    assert store.hint_settings(2) == (True, True)


def test_card_label_matches_wiki_url():
    message = SimpleNamespace(
        html_text=CARD_CAPTION,
        caption=None,
        text=None,
    )
    assert card_label(message) == "Швидкісна ціль"


def test_card_label_none_for_plain_message():
    message = SimpleNamespace(html_text="Звичайна новина про БПЛА", caption=None, text=None)
    assert card_label(message) is None


def test_strip_card_links_removes_wiki_line():
    caption = (
        "<blockquote>Виявлено швидкісну ціль над Одесою\n\n"
        '<a href="https://uk.wikipedia.org/wiki/Крилата_ракета">Швидкісна ціль</a>\n\n'
        "#OpenTrevoga 🕊</blockquote>"
    )
    stripped = strip_card_links(caption, "Швидкісна ціль")
    assert "Крилата_ракета" not in stripped
    assert "Виявлено швидкісну ціль над Одесою" in stripped
    assert "#OpenTrevoga" in stripped


@pytest.mark.asyncio
async def test_broadcaster_keeps_photo_by_default(tmp_path):
    store = _store(tmp_path)
    bot = _bot()
    broadcaster = Broadcaster(bot, store, group_c=0)
    await broadcaster._send_to_user(2, [_message(CARD_CAPTION)])
    bot.send_photo.assert_awaited_once()
    bot.send_message.assert_not_awaited()
    assert "Крилата_ракета" in bot.send_photo.await_args.kwargs["caption"]


@pytest.mark.asyncio
async def test_broadcaster_photo_off(tmp_path):
    store = _store(tmp_path)
    store.set_hint_settings(1, photo_on=False, wiki_on=True)
    bot = _bot()
    broadcaster = Broadcaster(bot, store, group_c=0)
    await broadcaster._send_to_user(1, [_message(CARD_CAPTION)])
    bot.send_message.assert_awaited_once()
    bot.send_photo.assert_not_awaited()
    sent_text = bot.send_message.await_args.args[1]
    assert "Крилата_ракета" in sent_text
    assert "над Одесою" in sent_text


@pytest.mark.asyncio
async def test_broadcaster_wiki_off(tmp_path):
    store = _store(tmp_path)
    store.set_hint_settings(1, photo_on=True, wiki_on=False)
    bot = _bot()
    broadcaster = Broadcaster(bot, store, group_c=0)
    await broadcaster._send_to_user(1, [_message(CARD_CAPTION)])
    bot.send_photo.assert_awaited_once()
    sent_caption = bot.send_photo.await_args.kwargs["caption"]
    assert "Крилата_ракета" not in sent_caption
    assert "над Одесою" in sent_caption


def test_fold_homoglyphs_matches_layout():
    # латиница и кириллица сводятся к одной форме
    assert fold_homoglyphs("odesa") == fold_homoglyphs("одеса")
    assert fold_homoglyphs("izmail") == fold_homoglyphs("ізмаїл")
    assert fold_homoglyphs("izmail") == fold_homoglyphs("Измаил")


def test_fold_homoglyphs_keeps_latin():
    assert fold_homoglyphs("FPV") == "fpv"


@pytest.mark.asyncio
async def test_dispatch_matches_latin_subscription_to_cyrillic_post(tmp_path):
    store = _store(tmp_path)
    with store._connect() as connection:
        connection.execute(
            "CREATE TABLE subscriptions ("
            "user_id INTEGER NOT NULL, keyword TEXT NOT NULL, "
            "created_at REAL NOT NULL, PRIMARY KEY (user_id, keyword))"
        )
    store.add(1, "odesa")
    bot = _bot()
    broadcaster = Broadcaster(bot, store, group_c=0)
    await broadcaster._dispatch([_message("Атака FPV на Одесу, Одеса без світла")])
    bot.send_photo.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcaster_photo_and_wiki_off(tmp_path):
    store = _store(tmp_path)
    store.set_hint_settings(1, photo_on=False, wiki_on=False)
    bot = _bot()
    broadcaster = Broadcaster(bot, store, group_c=0)
    await broadcaster._send_to_user(1, [_message(CARD_CAPTION)])
    bot.send_message.assert_awaited_once()
    bot.send_photo.assert_not_awaited()
    sent_text = bot.send_message.await_args.args[1]
    assert "Крилата_ракета" not in sent_text
    assert "над Одесою" in sent_text
