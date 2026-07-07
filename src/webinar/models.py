"""Data models for webinars and prizes."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any

# Prize types (한글 라벨은 홈페이지에서 매핑)
PRIZE_TYPES = ("survey", "question", "consult", "attendance")


@dataclass
class Prize:
    """A giveaway attached to a webinar."""

    type: str  # one of PRIZE_TYPES
    item: str = ""  # 경품 품목, e.g. "스타벅스 아메리카노"
    condition: str = ""  # 지급 조건, e.g. "설문 참여자 추첨 20명"

    def __post_init__(self) -> None:
        if self.type not in PRIZE_TYPES:
            # keep data, but normalize unknowns to 'attendance' as a safe default
            self.type = "attendance"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Prize":
        return cls(
            type=d.get("type", "attendance"),
            item=d.get("item", ""),
            condition=d.get("condition", ""),
        )


@dataclass
class Webinar:
    """A single webinar/seminar session."""

    source: str  # site key, e.g. "ddtube"
    title: str
    url: str  # canonical/detail url
    start_kst: str | None = None  # ISO 8601 e.g. "2026-07-08T14:00:00+09:00"
    end_kst: str | None = None
    host: str = ""  # 주최/주관
    register_url: str = ""  # where to sign up (may == url)
    description: str = ""
    thumbnail: str = ""
    tags: list[str] = field(default_factory=list)
    registered: bool = False
    prizes: list[Prize] = field(default_factory=list)
    prize_images: list[str] = field(default_factory=list)  # 경품 안내 배너 이미지 URL
    id: str = ""  # stable hash; filled in __post_init__

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.make_id(self.source, self.url or self.title)

    @staticmethod
    def make_id(source: str, key: str) -> str:
        digest = hashlib.sha1(f"{source}:{key}".encode("utf-8")).hexdigest()[:12]
        return f"{source}-{digest}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["prizes"] = [p if isinstance(p, dict) else p.to_dict() for p in self.prizes]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Webinar":
        prizes = [Prize.from_dict(p) for p in d.get("prizes", [])]
        return cls(
            source=d["source"],
            title=d.get("title", ""),
            url=d.get("url", ""),
            start_kst=d.get("start_kst"),
            end_kst=d.get("end_kst"),
            host=d.get("host", ""),
            register_url=d.get("register_url", ""),
            description=d.get("description", ""),
            thumbnail=d.get("thumbnail", ""),
            tags=list(d.get("tags", [])),
            registered=bool(d.get("registered", False)),
            prizes=prizes,
            prize_images=list(d.get("prize_images", [])),
            id=d.get("id", ""),
        )
