from trevoga.services.text_cleaner import WATERMARK
from trevoga.storage.repositories import StatisticsRepository


class StatisticsService:
    def __init__(self, repository: StatisticsRepository):
        self.repository = repository

    def build_report(self, hours: int) -> str:
        counter = self.repository.keyword_counts(hours)
        lines = [f"--- За {hours} год ---"]
        lines.extend(
            (f"<b>{label}</b> - {count}" for label, count in counter.most_common())
            if counter
            else ["Ключових слів не знайдено"]
        )
        return "\n".join(lines)

    def build_text(self) -> str:
        body = self.build_report(12) + "\n\n" + self.build_report(24)
        return f"<blockquote>=== СТАТИСТИКА ===\n\n{body}\n\n{WATERMARK}</blockquote>"
