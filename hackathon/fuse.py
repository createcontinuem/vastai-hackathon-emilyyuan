"""Fusion — align visual events with reactions -> ranked NotableMoment[].

INPUT:  List[VisualEvent], List[ReactionPoint] (may be empty)
OUTPUT: List[NotableMoment] ranked by score

Scoring (MVP, transparent on purpose so it's explainable in the demo):
  score = w_conf * visual_confidence
        + w_react * reaction_intensity (if a reaction overlaps the event window)
        + w_sync * synchrony           (cross-video agreement, set by cross_video_synchrony)

No reactions (runway) -> score is visual_confidence only; still fully searchable.
"""

from typing import List, Dict

from .schemas import VisualEvent, ReactionPoint, NotableMoment

W_CONF, W_REACT, W_SYNC = 0.4, 0.4, 0.2


def _overlapping_reaction(ev: VisualEvent, reactions: List[ReactionPoint]):
    hits = [r for r in reactions if ev.t_start <= r.t <= ev.t_end]
    if not hits:
        return None
    return max(hits, key=lambda r: r.intensity)


def find_notable_moments(
    events: List[VisualEvent],
    reactions: List[ReactionPoint],
) -> List[NotableMoment]:
    moments: List[NotableMoment] = []
    for ev in events:
        r = _overlapping_reaction(ev, reactions)
        emotion = r.emotion if r else None
        intensity = r.intensity if r else 0.0
        score = W_CONF * ev.confidence + W_REACT * intensity
        moments.append(NotableMoment(
            video_id=ev.video_id, t_start=ev.t_start, t_end=ev.t_end,
            title=ev.description, visual=ev,
            reaction_emotion=emotion, reaction_intensity=intensity, score=score,
        ))
    moments.sort(key=lambda m: m.score, reverse=True)
    return moments


def cross_video_synchrony(moments_by_video: Dict[str, List[NotableMoment]]) -> None:
    """Boost moments whose event type recurs across videos (universal reactions).

    MVP heuristic: if the same label appears with a strong reaction in >=2 videos,
    bump each one's synchrony and re-fold it into score. Mutates in place.
    """
    label_videos: Dict[str, set] = {}
    for vid, moments in moments_by_video.items():
        for m in moments:
            if m.reaction_intensity >= 0.5:
                label_videos.setdefault(m.visual.label, set()).add(vid)
    for moments in moments_by_video.values():
        for m in moments:
            n = len(label_videos.get(m.visual.label, ()))
            if n >= 2:
                m.synchrony = min(1.0, n / max(1, len(moments_by_video)))
                m.score += W_SYNC * m.synchrony
        moments.sort(key=lambda m: m.score, reverse=True)
