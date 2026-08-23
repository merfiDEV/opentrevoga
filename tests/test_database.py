from trevoga.storage.database import Database
from trevoga.storage.repositories import ForwardedPostRepository, StatisticsRepository


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
