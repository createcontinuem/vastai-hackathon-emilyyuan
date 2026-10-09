"""Index + plain-language search over moments (VAST-backed).

INPUT:  List[NotableMoment] (with visual.description text)
OUTPUT: SearchResult for a natural-language query

Real path: embed each moment's description (EMBED_MODEL) + store in VAST; query is
embedded and matched by vector similarity.

MOCK path: keyword/overlap scoring over descriptions — zero deps, good enough to
demo plain-language search and to develop the UI against.

TODO(P4): VAST client (upsert + vector query) + embedding calls.
"""

from typing import List

from . import config
from .schemas import NotableMoment, SearchResult


class MomentIndex:
    def __init__(self) -> None:
        self._moments: List[NotableMoment] = []
        # Use VAST only when it's actually configured; otherwise local keyword
        # search (independent of PULSE_MOCK, so live runs work without VAST creds).
        self._use_vast = bool(config.VAST_ENDPOINT and config.VAST_API_KEY)

    def add(self, moments: List[NotableMoment]) -> None:
        self._moments.extend(moments)
        if self._use_vast:
            self._upsert_vast(moments)                     # TODO(P4)

    def search(self, query: str, k: int = 5) -> SearchResult:
        ranked = self._vector_search(query, k) if self._use_vast else self._keyword_rank(query)
        return SearchResult(query=query, moments=ranked[:k])

    # --- MOCK keyword ranking ----------------------------------------------
    def _keyword_rank(self, query: str) -> List[NotableMoment]:
        terms = {t for t in query.lower().split() if len(t) > 2}
        def overlap(m: NotableMoment) -> float:
            text = (m.visual.description + " " + m.visual.label).lower()
            hits = sum(1 for t in terms if t in text)
            return hits + 0.1 * m.score      # tie-break by notability
        return sorted(self._moments, key=overlap, reverse=True)

    # --- real VAST ---------------------------------------------------------
    def _upsert_vast(self, moments: List[NotableMoment]) -> None:
        raise NotImplementedError("P4: embed + upsert to VAST")

    def _vector_search(self, query: str, k: int) -> List[NotableMoment]:
        raise NotImplementedError("P4: embed query + VAST vector search")
