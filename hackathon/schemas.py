"""Data contracts for Pulse — the single source of truth for inputs/outputs.

Every module speaks these types. Keeping them in one place is what makes the
pipeline reproducible and evaluable (judging: clear docs of inputs/outputs).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict


@dataclass
class VisualEvent:
    """One thing that happened on screen, from the VLM (VSS/Cosmos)."""
    video_id: str
    t_start: float               # seconds
    t_end: float
    label: str                   # short slug, e.g. "entity_speaks", "model_entrance"
    description: str             # VLM caption, natural language
    confidence: float = 0.0      # 0..1
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("embedding", None)  # embeddings live in the index, not the record
        return d


@dataclass
class ReactionPoint:
    """How the audience reacted at a moment (game/commentary videos only)."""
    video_id: str
    t: float                     # window-center seconds
    emotion: str                 # joy/surprise/fear/frustration/awe/sadness/disgust/neutral
    intensity: float             # 0..1


@dataclass
class NotableMoment:
    """A fused, ranked moment: what happened x how people reacted."""
    video_id: str
    t_start: float
    t_end: float
    title: str                   # human-facing one-liner
    visual: VisualEvent
    reaction_emotion: Optional[str] = None
    reaction_intensity: float = 0.0
    synchrony: float = 0.0       # cross-video agreement 0..1 (how universal the moment is)
    score: float = 0.0           # final ranking score
    clip_path: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["visual"] = self.visual.to_dict()
        return d


@dataclass
class SearchResult:
    query: str
    moments: List[NotableMoment] = field(default_factory=list)


@dataclass
class Brief:
    """The agent's ACTION output: a short studio-facing insight card."""
    video_id: str
    moment: NotableMoment
    text: str
