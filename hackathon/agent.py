"""Pulse agent — orchestrates the MVP end-to-end and triggers the action.

Flow (per docs/HACKATHON_PLAN.md):
  videos -> [ingest] -> [visual_events] -> [reactions] -> [fuse]
         -> [index] -> {search , ACTION: clip + Brief on the top moment}

CLI:
  python -m hackathon.agent --videos hackathon/videos.txt
  python -m hackathon.agent --videos hackathon/videos.txt --query "where does it talk to the player"

Runs fully in MOCK mode (default) with no sponsor endpoints, so the pipeline and
demo work offline. Set PULSE_MOCK=0 + endpoint envs to go live.
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .schemas import NotableMoment, Brief
from . import visual_events, reactions, fuse, llm
from .index_search import MomentIndex


def _video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([\w-]{11})", url)
    return m.group(1) if m else url.strip()


def _read_videos(path: Path) -> List[str]:
    ids = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#")[0].strip()
        if ln:
            ids.append(_video_id(ln))
    return ids


def _local_video_path(video_id: str) -> Optional[str]:
    """Find an already-ingested mp4 (video_ingest writes data/{set}/video/{id}.mp4)."""
    for p in config.DATA_DIR.glob(f"**/video/{video_id}.*"):
        return str(p)
    return None


def build(video_ids: List[str]) -> tuple[MomentIndex, Dict[str, List[NotableMoment]]]:
    index = MomentIndex()
    by_video: Dict[str, List[NotableMoment]] = {}
    for vid in video_ids:
        path = _local_video_path(vid) or ""     # MOCK ignores path
        try:
            events = visual_events.detect_events(path, vid, limit_secs=config.LIMIT_SECS)
        except Exception as e:
            print(f"[skip] {vid}: {str(e)[:90]}")
            continue
        rxns = reactions.reaction_timeline(vid)
        moments = fuse.find_notable_moments(events, rxns)
        by_video[vid] = moments
        print(f"[OK] {vid}: {len(events)} events, {len(rxns)} reactions, "
              f"{len(moments)} moments")
    fuse.cross_video_synchrony(by_video)
    for moments in by_video.values():
        index.add(moments)
    return index, by_video


def _template_brief(m: NotableMoment) -> str:
    react = (f" The audience reacted with {m.reaction_emotion} "
             f"(intensity {m.reaction_intensity:.0%})." if m.reaction_emotion else "")
    sync = (f" This pattern recurred across {m.synchrony:.0%} of the corpus."
            if m.synchrony else "")
    return (f"At {m.t_start:.0f}s: {m.visual.description}{react}{sync} "
            f"Notability score {m.score:.2f}.")


def make_brief(m: NotableMoment) -> Brief:
    """The ACTION: a studio-facing insight card for a top moment.

    Written by NVIDIA Nemotron (CoreWeave serverless) from the moment's facts;
    falls back to a deterministic template if the LLM is unavailable (MOCK or
    network), so the demo never breaks."""
    facts = (f"timestamp={m.t_start:.0f}s; on_screen=\"{m.visual.description}\"; "
             f"audience_reaction={m.reaction_emotion or 'n/a'}; "
             f"reaction_intensity={m.reaction_intensity:.0%}; "
             f"cross_video_synchrony={m.synchrony:.0%}; notability={m.score:.2f}")
    if config.MOCK:
        return Brief(m.video_id, m, _template_brief(m))
    try:
        text = llm.chat(
            "Write a 2-sentence insight brief for a game studio about this moment "
            "in a creator's video. Say what happened and why it matters to the "
            "studio (design/marketing). Be specific, no preamble.\n\n" + facts)
    except Exception as e:
        print(f"[warn] Nemotron brief failed ({str(e)[:80]}); using template")
        text = _template_brief(m)
    return Brief(video_id=m.video_id, moment=m, text=text)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the Pulse video agent end-to-end.")
    ap.add_argument("--videos", default="hackathon/videos.txt")
    ap.add_argument("--query", help="optional plain-language search to run")
    args = ap.parse_args()

    mode = "MOCK" if config.MOCK else "LIVE"
    print(f"[..] Pulse agent ({mode})")
    video_ids = _read_videos(Path(args.videos))
    index, by_video = build(video_ids)

    if args.query:
        res = index.search(args.query)
        print(f"\n[SEARCH] {args.query!r}")
        for i, m in enumerate(res.moments, 1):
            print(f"  {i}. [{m.video_id} @ {m.t_start:.0f}s] {m.title} (score {m.score:.2f})")

    # ACTION: brief the single most notable moment in the corpus
    top = max((m for ms in by_video.values() for m in ms),
              key=lambda m: m.score, default=None)
    if top:
        brief = make_brief(top)
        print(f"\n[ACTION] auto-brief on top moment:\n  {brief.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
