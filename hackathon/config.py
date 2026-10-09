"""Central config for Sentiment Engine. Endpoints via env vars; never hardcode keys.

MOCK mode (default ON) lets the whole pipeline + UI run with canned data so the
demo never blocks on a sponsor endpoint. Flip SE_MOCK=0 once endpoints are live.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load repo-root .env (user-managed, gitignored) so keys set there are picked up.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass  # dotenv optional; shell-exported env vars still work
DATA_DIR = ROOT / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"   # canned MOCK data
WORK_DIR = ROOT / "tmp" / "sentiment-engine"                             # clips, intermediates

# --- MOCK switch ------------------------------------------------------------
MOCK = os.getenv("SE_MOCK", "1") == "1"

# --- Vision (VLM): NVIDIA build.nvidia.com hosted Cosmos-Reason ---------------
# CoreWeave serverless has NO vision model (verified via list_models -> 20 text-only
# LLMs), so the visual-understanding stage runs on NVIDIA's OpenAI-compatible NIM
# catalog, which hosts Cosmos-Reason1-7B. Get a free nvapi- key at build.nvidia.com.
# Kept SEPARATE from the W&B key so the two endpoints never cross-wire.
VLM_URL = os.getenv("VLM_URL", "https://integrate.api.nvidia.com/v1")
VLM_API_KEY = os.getenv("NVIDIA_API_KEY") or os.getenv("VLM_API_KEY", "")
# cosmos-reason2-8b & phi-3-vision are listed but 404 "not available for account" on
# the free tier; llama-3.2-11b-vision IS callable (1 image/call). Override if you get
# Cosmos access (e.g. self-hosted on CoreWeave GPU).
VLM_MODEL = os.getenv("VLM_MODEL", "meta/llama-3.2-11b-vision-instruct")
VLM_IMAGES_PER_CALL = int(os.getenv("VLM_IMAGES_PER_CALL", "1"))  # NVIDIA llama-vision caps at 1

# --- CoreWeave serverless (TEXT LLMs incl. NVIDIA Nemotron) ------------------
# OpenAI-compatible; auth = your W&B API key (https://wandb.ai/authorize).
CW_TEXT_URL = os.getenv("CW_TEXT_URL", "https://api.inference.wandb.ai/v1")
WANDB_ENTITY_PROJECT = os.getenv("WANDB_ENTITY_PROJECT", "")  # "<team>/<project>" routing
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B")

# --- run bounds -------------------------------------------------------------
# Cap how much of each video to process on a run (secs). 0 = whole video.
# Start small to prove the live path cheaply, then raise/zero it.
LIMIT_SECS = float(os.getenv("SE_LIMIT_SECS", "0")) or None
FRAME_FPS = float(os.getenv("SE_FRAME_FPS", "0.5"))        # frames/sec sampled for the VLM
CHUNK_SECS = float(os.getenv("SE_CHUNK_SECS", "30"))       # event granularity

# --- VAST (storage + semantic search) --------------------------------------
VAST_ENDPOINT = os.getenv("VAST_ENDPOINT", "")
VAST_API_KEY = os.getenv("VAST_API_KEY", "")
EMBED_MODEL = os.getenv("SE_EMBED_MODEL", "nvidia/llama-3.2-nv-embedqa-1b-v2")

# --- Weights & Biases (eval + tracing) --------------------------------------
WANDB_PROJECT = os.getenv("WANDB_PROJECT", "sentiment-engine-vast-hack")
WANDB_ENABLED = bool(os.getenv("WANDB_API_KEY"))

# --- ingest -----------------------------------------------------------------
MAX_HEIGHT = int(os.getenv("SE_MAX_HEIGHT", "720"))        # VLM needs to read on-screen text
