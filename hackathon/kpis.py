"""KPIs — eval harness + W&B logging (judging: evaluable + Impact/sponsor tool).

Computes the hero metrics against a small hand-labeled gold set and logs them to
Weights & Biases. Falls back to console if WANDB is not configured.

gold set format (hackathon/fixtures/{video_id}.gold.json):
  {"events":[{"t_start":..,"t_end":..,"label":".."}, ...]}
"""

import json
from typing import Dict, List

from . import config
from .schemas import NotableMoment


def precision_at_k(predicted: List[NotableMoment], gold: List[dict], k: int = 5,
                   tol: float = 15.0) -> float:
    """Fraction of top-k predicted moments that match a gold event within tol secs."""
    top = predicted[:k]
    if not top:
        return 0.0
    hits = 0
    for m in top:
        if any(abs(m.t_start - g["t_start"]) <= tol for g in gold):
            hits += 1
    return hits / len(top)


def compression_ratio(total_video_secs: float, n_moments: int) -> float:
    """Hours of footage per surfaced moment — the 'we watched so you don't' number."""
    return (total_video_secs / 3600.0) / max(1, n_moments)


def evaluate(by_video: Dict[str, List[NotableMoment]],
             total_video_secs: float) -> Dict[str, float]:
    p_at_5 = []
    for vid, moments in by_video.items():
        fx = config.FIXTURES_DIR / f"{vid}.gold.json"
        if fx.exists():
            gold = json.loads(fx.read_text(encoding="utf-8")).get("events", [])
            p_at_5.append(precision_at_k(moments, gold))
    n_moments = sum(len(m) for m in by_video.values())
    metrics = {
        "event_precision_at_5": round(sum(p_at_5) / len(p_at_5), 3) if p_at_5 else 0.0,
        "hours_per_moment": round(compression_ratio(total_video_secs, n_moments), 2),
        "n_videos": len(by_video),
        "n_moments": n_moments,
        "sponsor_tools_used": 4,   # NVIDIA, CoreWeave, VAST, W&B
    }
    return metrics


def log_wandb(metrics: Dict[str, float]) -> None:
    if not config.WANDB_ENABLED:
        print("[kpi] (W&B not configured) " +
              " ".join(f"{k}={v}" for k, v in metrics.items()))
        return
    try:
        import wandb
        wandb.init(project=config.WANDB_PROJECT, config={"mock": config.MOCK})
        wandb.log(metrics)
        wandb.finish()
        print("[kpi] logged to W&B:", metrics)
    except Exception as e:
        print(f"[kpi] W&B log failed ({e}); metrics: {metrics}")
