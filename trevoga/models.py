from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ForwardedPost:
    source_message_id: int
    main: dict[str, int] = field(default_factory=dict)
    comments: list[tuple[str, int]] = field(default_factory=list)


ModerationReason = Literal[
    "advertising",
    "no_local_value",
    "no_specifics",
    "unconfirmed_rumor",
    "irrelevant",
    "other",
    "invalid_response",
]


@dataclass(frozen=True)
class ModerationResult:
    message_id: int
    useful: bool
    reason: ModerationReason | None
    reason_text: str
    confidence: float | None
    raw_response: str
    status: str
