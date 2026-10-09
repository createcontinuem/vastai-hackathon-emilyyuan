"""Visual understanding — mp4 -> VisualEvent[] via a VLM (Cosmos-Reason) on an
OpenAI-compatible endpoint (CoreWeave serverless / self-hosted vLLM / NVIDIA NIM).

INPUT:  local video path + video_id   (optionally limit_secs to bound a demo run)
OUTPUT: List[VisualEvent] (timestamped on-screen events with VLM descriptions)

Real path (PULSE_MOCK=0):
  1. ffmpeg samples frames at FRAME_FPS, grouped into CHUNK_SECS windows
  2. a few representative frames per window are sent to the VLM (OpenAI vision
     chat format, base64 JPEG data URIs) with a "describe the salient event" prompt
  3. one VisualEvent per window (label = slug of the caption)

Endpoint-agnostic: works against any OpenAI-compatible /chat/completions as long
as COREWEAVE_VLM_URL + COREWEAVE_API_KEY + COSMOS_MODEL are set.

MOCK path (default): canned events from fixtures/{video_id}.events.json.

Deps: ffmpeg on PATH (verified). stdlib-only HTTP (no openai package needed).
"""

import base64
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional, Tuple

from . import config
from .schemas import VisualEvent

JPEG_WIDTH = 512              # downscale frames to keep payload/cost sane
PROMPT = (
    "These frames are consecutive moments from a video. In ONE concise sentence, "
    "describe the single most salient thing happening on screen (an action, an "
    "appearance, a dramatic or surprising moment). Be concrete and specific; do "
    "not mention that these are frames or a video."
)


def detect_events(video_path: str, video_id: str,
                  limit_secs: Optional[float] = None) -> List[VisualEvent]:
    if config.MOCK:
        return _mock_events(video_id)
    if not video_path or not Path(video_path).exists():
        raise RuntimeError(f"video not found for {video_id}: {video_path!r} "
                           f"(run src.video_ingest first)")
    frames_by_chunk = _sample_frames(video_path, video_id, limit_secs)
    events: List[VisualEvent] = []
    for (t_start, t_end), frames in frames_by_chunk:
        caption = _call_vlm(frames)
        events.append(VisualEvent(
            video_id=video_id, t_start=t_start, t_end=t_end,
            label=_slug(caption), description=caption, confidence=0.7,
        ))
        print(f"  [{video_id}] {t_start:.0f}-{t_end:.0f}s: {caption[:70]}")
    return events


# --- frame sampling (ffmpeg) -----------------------------------------------

def _sample_frames(video_path: str, video_id: str,
                   limit_secs: Optional[float]) -> List[Tuple[Tuple[float, float], List[Path]]]:
    out_dir = config.WORK_DIR / "frames" / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f_*.jpg"):
        old.unlink()
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if limit_secs:
        cmd += ["-t", str(limit_secs)]
    cmd += ["-i", video_path,
            "-vf", f"fps={config.FRAME_FPS},scale={JPEG_WIDTH}:-1",
            str(out_dir / "f_%05d.jpg")]
    subprocess.run(cmd, check=True)

    frames = sorted(out_dir.glob("f_*.jpg"))
    frames_per_window = max(1, int(round(config.CHUNK_SECS * config.FRAME_FPS)))
    chunks = []
    for i in range(0, len(frames), frames_per_window):
        window = frames[i:i + frames_per_window]
        t_start = (i / config.FRAME_FPS)
        t_end = t_start + config.CHUNK_SECS
        chunks.append(((t_start, t_end), _thin(window, config.VLM_IMAGES_PER_CALL)))
    return chunks


def _thin(frames: List[Path], n: int) -> List[Path]:
    """Pick up to n representative frames from a window (centered for n==1)."""
    if not frames:
        return []
    if n <= 1:
        return [frames[len(frames) // 2]]       # middle keyframe
    if len(frames) <= n:
        return frames
    step = len(frames) / n
    return [frames[int(i * step)] for i in range(n)]


# --- VLM call (OpenAI-compatible, stdlib HTTP) ------------------------------

def _call_vlm(frames: List[Path]) -> str:
    content = [{"type": "text", "text": PROMPT}]
    for fp in frames:
        b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    payload = {
        "model": config.VLM_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 80,
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {config.VLM_API_KEY}",
               "Content-Type": "application/json",
               # Cloudflare in front of some endpoints bans the default urllib UA
               "User-Agent": "pulse/0.1 (+https://github.com/)"}
    req = urllib.request.Request(
        config.VLM_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"VLM call failed {e.code}: "
                           f"{e.read().decode('utf-8', 'ignore')[:200]}")


def _slug(caption: str) -> str:
    words = [w for w in caption.lower().replace(".", "").split() if w.isalpha()]
    return "_".join(words[:3]) if words else "event"


# --- MOCK -------------------------------------------------------------------

def _mock_events(video_id: str) -> List[VisualEvent]:
    fx = config.FIXTURES_DIR / f"{video_id}.events.json"
    if fx.exists():
        raw = json.loads(fx.read_text(encoding="utf-8"))
        return [VisualEvent(**e) for e in raw]
    return [
        VisualEvent(video_id, 12.0, 42.0, "entity_speaks",
                    "A shadowy figure turns and appears to address the player.", 0.8),
        VisualEvent(video_id, 300.0, 330.0, "sudden_appearance",
                    "A creature lunges into frame from the dark.", 0.9),
    ]
