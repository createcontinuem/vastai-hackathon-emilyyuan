"""Video ingest — fetch the VIDEO stream for the VSS/Cosmos visual-event stage.

Counterpart to `audio_ingest.py`, but with inverted retention. Video is large and
*reproducible from the video_id*, so it is treated as an ephemeral intermediate,
NOT an append-only `raw/` archive. The mp4 lands in local scratch; only the derived
event JSON (produced downstream) is durable, and that belongs in `build/`.

Key decisions (see the Lead-DE review):
  - VIDEO-ONLY stream: we already have audio via `audio_ingest.py`, so skipping the
    audio track halves the bytes and avoids an ffmpeg merge (no mux step).
  - https-preferred format: dodges YouTube's SABR/m3u8 path that 403s on download.
  - Node JS runtime pinned explicitly (yt-dlp needs a JS runtime for extraction;
    we don't rely on ambient Deno/PATH discovery).
  - Resolution capped: VLMs only need enough to read on-screen text/UI. 480p is a
    sane default for real games; bump for text-heavy titles.

Requires yt-dlp >= 2026.8.x (older versions 403 on SABR) and Node on PATH.

CLI:
    python -m src.video_ingest --game she-was-98 --url https://youtu.be/XXXX
    python -m src.video_ingest --game she-was-98 --urls-file urls.txt --max-height 720
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# video is ephemeral scratch, NOT raw/ source-of-truth (reproducible from video_id)
DEFAULT_MAX_HEIGHT = 480
# yt-dlp Python API expects a dict {runtime: {config}} (the CLI --js-runtimes node
# parses to this). Node ships on PATH; avoids the deprecated no-JS-runtime path.
JS_RUNTIMES = {"node": {}}


def _probe(url: str) -> Dict:
    """Cheap metadata-only fetch (no download): id + duration + title."""
    try:
        import yt_dlp
    except Exception:
        raise RuntimeError("yt_dlp is required. Install with `pip install -U yt-dlp`")
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "js_runtimes": JS_RUNTIMES}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {"video_id": info.get("id"), "duration": info.get("duration", 0) or 0,
            "title": info.get("title", "")}


def fetch_video(
    game: str,
    url: str,
    out_root: Optional[Path] = None,
    max_height: int = DEFAULT_MAX_HEIGHT,
    force: bool = False,
) -> Dict:
    """Download the video-only stream for one URL into local scratch.

    Returns a record: {video_id, path, ext, duration_secs, size_mb, downloaded,
    height, elapsed_secs}. Idempotent: skips the download if an mp4 for this
    video_id already exists locally (unless force=True). Video is intentionally
    NOT uploaded to R2 — it is an ephemeral input to the visual-event stage.
    """
    t0 = time.time()
    video_dir = (Path(out_root) if out_root else DATA_DIR) / game / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    meta = _probe(url)
    vid = meta["video_id"]
    if not vid:
        raise RuntimeError(f"Could not resolve a video id for {url!r}")

    target = video_dir / f"{vid}.mp4"
    if target.exists() and not force:
        path, downloaded = target, False
    else:
        import yt_dlp
        # Video-only, https-preferred (avoids SABR/m3u8 403), capped height.
        # Fall back progressively so we always get *something* playable.
        fmt = (
            f"bestvideo[protocol^=https][height<={max_height}][ext=mp4]/"
            f"bestvideo[protocol^=https][height<={max_height}]/"
            f"bestvideo[height<={max_height}]/best[height<={max_height}]"
        )
        opts = {
            "format": fmt,
            "outtmpl": str(video_dir / "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "js_runtimes": JS_RUNTIMES,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        # yt-dlp may land .webm/.mp4 depending on the chosen stream; normalize name.
        if not target.exists():
            produced = list(video_dir.glob(f"{vid}.*"))
            if not produced:
                raise RuntimeError(f"expected a video file for {vid}, none found")
            path = produced[0]
        else:
            path = target
        downloaded = True

    rec: Dict = {
        "video_id": vid,
        "path": str(path),
        "ext": path.suffix.lstrip("."),
        "duration_secs": meta["duration"],
        "size_mb": round(path.stat().st_size / 1e6, 2) if path.exists() else 0.0,
        "downloaded": downloaded,
        "height": max_height,
        "elapsed_secs": round(time.time() - t0, 1),
    }

    tag = "downloaded" if downloaded else "cached"
    print(f"[OK] video {tag}: {vid} ({rec['size_mb']} MB, {rec['duration_secs']}s, "
          f"<={max_height}p) -> {path.name}")
    return rec


def fetch_batch(
    game: str,
    urls: List[str],
    out_root: Optional[Path] = None,
    max_height: int = DEFAULT_MAX_HEIGHT,
    force: bool = False,
) -> List[Dict]:
    """Fetch video for many URLs. Failures are recorded, not fatal (launch-scale)."""
    results: List[Dict] = []
    for i, url in enumerate(urls, 1):
        print(f"[..] ({i}/{len(urls)}) {url}")
        try:
            results.append(fetch_video(game, url, out_root, max_height, force))
        except Exception as e:
            print(f"[ERROR] {url}: {e}")
            results.append({"url": url, "error": str(e)})
    ok = sum(1 for r in results if not r.get("error"))
    print(f"\n[OK] video ingest: {ok}/{len(urls)} succeeded")
    return results


def _read_urls_file(path: Path) -> List[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch video-only streams for the VSS/Cosmos visual-event stage "
                    "(ephemeral scratch under data/{game}/video/, not R2 raw/).")
    ap.add_argument("--game", required=True, help="game slug, e.g. she-was-98")
    ap.add_argument("--url", action="append", default=[], help="YouTube URL (repeatable)")
    ap.add_argument("--urls-file", help="file with one URL per line")
    ap.add_argument("--max-height", type=int, default=DEFAULT_MAX_HEIGHT,
                    help=f"cap video height (default {DEFAULT_MAX_HEIGHT}p; raise for text-heavy games)")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    ap.add_argument("--out-root", help="override local data root (default: data/)")
    args = ap.parse_args()

    urls = list(args.url)
    if args.urls_file:
        urls += _read_urls_file(Path(args.urls_file))
    if not urls:
        print("[ERROR] provide --url and/or --urls-file")
        return 2

    out_root = Path(args.out_root) if args.out_root else None
    fetch_batch(args.game, urls, out_root=out_root,
                max_height=args.max_height, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
