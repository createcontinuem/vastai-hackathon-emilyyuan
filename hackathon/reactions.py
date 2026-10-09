"""Reaction lane — audience emotion over time (commentary videos only).

INPUT:  game/set slug + video_id
OUTPUT: List[ReactionPoint]  (empty for no-commentary videos like the runway)

Real path: reuse the existing sentiment pipeline (sentiment/) over this video's
captions to get per-window emotion + intensity. For the hackathon we only need the
timeline, not the full report.

MOCK path: canned reactions from fixtures/{video_id}.reactions.json, or [] if none.

The runway video has no reaction lane -> returns [] -> downstream falls back to
pure visual search. That optionality is the "generalizes beyond gaming" story.

TODO(P2): wire sentiment/ (ingest captions -> window -> score) for one video.
"""

import json
from typing import List

from . import config
from .schemas import ReactionPoint

# videos with no commentary track -> no reaction lane
NO_REACTION_VIDEOS = {"T4ZzV7R6GXQ"}   # Schiaparelli runway


def reaction_timeline(video_id: str, game: str = "") -> List[ReactionPoint]:
    if video_id in NO_REACTION_VIDEOS:
        return []
    if config.MOCK:
        return _mock_reactions(video_id)
    return _from_sentiment_pipeline(video_id, game)        # TODO(P2)


def _from_sentiment_pipeline(video_id: str, game: str) -> List[ReactionPoint]:
    """Run sentiment/ over this video's captions -> ReactionPoint[].

    P2 (not yet wired): until the sentiment pipeline is hooked up for a single
    video, degrade gracefully to no reaction lane so a live visual-only run still
    works. Fusion handles empty reactions (score = visual confidence only)."""
    print(f"[warn] {video_id}: reaction lane not wired (P2) -> visual-only")
    return []


def _mock_reactions(video_id: str) -> List[ReactionPoint]:
    fx = config.FIXTURES_DIR / f"{video_id}.reactions.json"
    if fx.exists():
        raw = json.loads(fx.read_text(encoding="utf-8"))
        return [ReactionPoint(**r) for r in raw]
    # synthetic spikes aligned with the mock visual events
    return [
        ReactionPoint(video_id, 30.0, "surprise", 0.85),
        ReactionPoint(video_id, 315.0, "fear", 0.95),
    ]
