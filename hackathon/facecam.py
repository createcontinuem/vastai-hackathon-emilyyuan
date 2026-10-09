"""Facecam reaction lane — the player's expression at key game events.

For reaction videos, the creator's webcam sits in a FIXED corner. Rather than
per-frame face detection (unreliable on dark horror footage), we:
  1. locate the facecam corner ONCE per video (VLM),
  2. at each key event timestamp, grab the full-res GAME screenshot (ffmpeg),
  3. crop the facecam corner -> the player's FACE at that instant,
  4. read the facial expression -> emotion + intensity (VLM).

This yields the stimulus->response pair: (game screenshot, face crop, expression)
and populates the reaction lane. Videos with no webcam (e.g. a runway) -> corner
is None -> no face crop, visual-only (handled upstream).

Artifacts: tmp/pulse/shots/{video_id}/{game,face}_{t}.jpg
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import config, visual_events
from .schemas import VisualEvent, ReactionPoint

# corner -> (x0frac, y0frac, x1frac, y1frac)
CORNERS = {
    "top-right":    (0.78, 0.0,  1.0,  0.32),
    "top-left":     (0.0,  0.0,  0.22, 0.32),
    "bottom-right": (0.78, 0.68, 1.0,  1.0),
    "bottom-left":  (0.0,  0.68, 0.22, 1.0),
}
EMOTIONS = ("fear", "surprise", "joy", "frustration", "awe", "sadness",
            "disgust", "neutral")


def _shots_dir(video_id: str) -> Path:
    d = config.WORK_DIR / "shots" / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def grab_frame(video_path: str, t: float, out_path: Path) -> Path:
    """Extract one full-resolution frame at time t (the game screenshot)."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
                    "-i", video_path, "-frames:v", "1", str(out_path)], check=True)
    return out_path


def locate_facecam(video_path: str, probe_t: float = 60.0) -> Optional[str]:
    """Ask the VLM which corner holds the streamer's webcam (or None)."""
    tmp = _shots_dir("_probe") / "probe.jpg"
    grab_frame(video_path, probe_t, tmp)
    ans = visual_events._call_vlm([tmp]).lower()  # reuse the VLM HTTP client
    for c in CORNERS:
        if c in ans or c.replace("-", " ") in ans:
            return c
    if "none" in ans or "no webcam" in ans or "no face" in ans:
        return None
    return None  # default to no facecam if unsure


def crop_corner(frame_path: Path, corner: str, out_path: Path) -> Path:
    from PIL import Image
    im = Image.open(frame_path)
    w, h = im.size
    x0, y0, x1, y1 = CORNERS[corner]
    im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1))).save(out_path)
    return out_path


def read_expression(face_path: Path) -> Tuple[str, float]:
    """VLM -> (emotion, intensity) for a webcam face crop."""
    prompt = ("This is a webcam crop of a gaming streamer reacting. Reply ONLY as "
              "EMOTION|INTENSITY where EMOTION is one of "
              "[fear, surprise, joy, frustration, awe, sadness, disgust, neutral] "
              "and INTENSITY is 0.0-1.0 (how strong the reaction looks).")
    raw = visual_events._call_vlm([face_path], prompt=prompt)
    m = re.search(r"(fear|surprise|joy|frustration|awe|sadness|disgust|neutral)"
                  r"\s*\|\s*([01]?\.?\d+)", raw.lower())
    if m:
        return m.group(1), max(0.0, min(1.0, float(m.group(2))))
    for e in EMOTIONS:                      # fallback: first emotion word present
        if e in raw.lower():
            return e, 0.5
    return "neutral", 0.3


def enrich(video_path: str, video_id: str, events: List[VisualEvent]
           ) -> Tuple[List[ReactionPoint], Dict[float, Dict[str, str]]]:
    """For each event: save game screenshot + (if webcam) face crop + expression.

    Returns (reactions, shots_by_tstart) where shots_by_tstart[t_start] =
    {"game_shot": path, "face_shot": path|None, "emotion": e|None}.
    """
    corner = locate_facecam(video_path)
    print(f"[facecam] {video_id}: webcam corner = {corner or 'none (visual-only)'}")
    reactions: List[ReactionPoint] = []
    shots: Dict[float, Dict[str, str]] = {}
    d = _shots_dir(video_id)
    for ev in events:
        t = (ev.t_start + ev.t_end) / 2.0
        game_shot = grab_frame(video_path, t, d / f"game_{int(t)}.jpg")
        rec: Dict[str, str] = {"game_shot": str(game_shot)}
        if corner:
            face_shot = crop_corner(game_shot, corner, d / f"face_{int(t)}.jpg")
            emotion, intensity = read_expression(face_shot)
            reactions.append(ReactionPoint(video_id, t, emotion, intensity))
            rec["face_shot"] = str(face_shot)
            rec["emotion"] = emotion
            print(f"  [face] {t:.0f}s: {emotion} ({intensity:.0%})")
        shots[ev.t_start] = rec
    return reactions, shots
