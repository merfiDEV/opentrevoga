from trevoga.storage.database import Database
from trevoga.storage.repositories import ForwardedPostRepository, StatisticsRepository
from trevoga.models import ModerationResult
from trevoga.storage.repositories import ModerationRepository


def test_forwarded_messages_and_statistics(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    posts = ForwardedPostRepository(database)
    posts.save_main(10, {"-1": 20})
    assert posts.exists(10)
    assert posts.get(10).main == {"-1": 20}
    stats = StatisticsRepository(database)
    stats.record("to_c", keywords=["FPV"])
    assert stats.keyword_counts(24)["FPV"] == 1


def test_moderation_result_is_persisted(tmp_path):
    database = Database(tmp_path / "moderation.db")
    database.initialize()
    repository = ModerationRepository(database)
    repository.save(
        ModerationResult(
            12, False, "no_specifics", "Немає конкретики", 0.8, "{}", "rejected"
        )
    )
    result = repository.get(12)
    assert result is not None
    assert result.reason == "no_specifics"
