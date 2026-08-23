from dataclasses import dataclass, field


@dataclass
class ForwardedPost:
    source_message_id: int
    main: dict[str, int] = field(default_factory=dict)
    comments: list[tuple[str, int]] = field(default_factory=list)
