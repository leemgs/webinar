"""Best-effort prize (경품) extraction + manual override merge.

Prize info is frequently only on detail pages or behind login, so extraction is
intentionally conservative. Curated entries in config/prizes_override.yaml are
merged on top (override wins per prize type).
"""
from __future__ import annotations

import re

from .config import load_prize_overrides
from .models import Prize, Webinar

# keyword -> prize type. Order matters (first match wins per sentence).
_KEYWORDS = [
    ("survey", ["설문조사", "설문"]),
    ("question", ["질문", "댓글", "채팅 참여", "라이브 질문"]),
    ("consult", ["상담 신청", "상담신청", "1:1 상담", "무료 상담", "상담"]),
    ("attendance", ["시청 인증", "생방송 시청", "출석", "참석", "시청", "경품"]),
]

# sentence fragments that likely describe a giveaway
_PRIZE_HINT = re.compile(r"(경품|추첨|기프티콘|상품권|커피|아메리카노|백화점|이벤트)")


def extract_prizes(text: str) -> list[Prize]:
    """Scan free text for giveaway hints and classify them by type."""
    if not text:
        return []
    found: dict[str, Prize] = {}
    # split into rough sentences/clauses
    for chunk in re.split(r"[.\n·•;]|(?<=다)\s", text):
        chunk = chunk.strip()
        if not chunk or not _PRIZE_HINT.search(chunk):
            continue
        ptype = _classify(chunk)
        if ptype and ptype not in found:
            found[ptype] = Prize(type=ptype, item="", condition=chunk[:120])
    return list(found.values())


def _classify(chunk: str) -> str | None:
    for ptype, words in _KEYWORDS:
        if any(w in chunk for w in words):
            return ptype
    # has a prize hint but no explicit trigger -> attendance (참석/시청)
    return "attendance"


def apply(webinar: Webinar) -> Webinar:
    """Populate webinar.prizes from scraped text + overrides (override wins)."""
    scraped = extract_prizes(
        " ".join(filter(None, [webinar.title, webinar.description]))
    )
    by_type: dict[str, Prize] = {p.type: p for p in scraped}

    overrides = load_prize_overrides()
    for key in (webinar.id, f"{webinar.source}:{webinar.url}", webinar.url):
        if key and key in overrides:
            for entry in overrides[key]:
                p = Prize.from_dict(entry)
                by_type[p.type] = p  # override wins
            break

    webinar.prizes = list(by_type.values())
    return webinar
