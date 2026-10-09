# Pulse — a real-time video agent that finds the moments that matter

**VAST Builders Challenge** (tokens&, NYC · 2026-10-09). Built on the Sentiment Engine.

Pulse ingests video, **understands the footage** (NVIDIA VSS / Cosmos-Reason on
CoreWeave), **fuses it with how the audience reacted**, lets you **search hours of
video in plain language**, and **triggers an action** (cut the clip + write a brief)
when something matters. When there's no commentary (a runway show), it falls back to
pure visual search — so it works on *any* video, not just games.

Full plan, architecture, task scope, KPIs: [../docs/HACKATHON_PLAN.md](../docs/HACKATHON_PLAN.md).

## Quickstart (runs offline in MOCK mode — no GPU/keys needed)

```bash
# run the agent end-to-end (search + auto-brief)
python -m hackathon.agent --videos hackathon/videos.txt --query "something talks to the player"

# serve the search UI
python -m hackathon.app          # http://localhost:8800
```

## Go live (sponsor endpoints)

```bash
export PULSE_MOCK=0
# vision: NVIDIA build.nvidia.com hosts Cosmos-Reason (CoreWeave serverless has no VLM)
export NVIDIA_API_KEY=nvapi-...          # free from build.nvidia.com
# VLM_URL + VLM_MODEL default to NVIDIA Cosmos-Reason; override only to self-host
export WANDB_API_KEY=...                 # CoreWeave serverless (text LLM) + eval
export VAST_ENDPOINT=...  VAST_API_KEY=...
# ingest real video first (video-only, 720p, ephemeral scratch):
python -m src.video_ingest --game shtownfall --urls-file hackathon/videos.txt --max-height 720
python -m hackathon.agent --videos hackathon/videos.txt
```

## Modules (inputs/outputs = hackathon/schemas.py)

| Module | Does | Sponsor |
|---|---|---|
| `src/video_ingest.py` | YouTube → mp4 (video-only, Node runtime) | — |
| `visual_events.py` | mp4 → `VisualEvent[]` | NVIDIA Cosmos + CoreWeave |
| `reactions.py` | captions → `ReactionPoint[]` (empty if no commentary) | — |
| `fuse.py` | align + rank → `NotableMoment[]` + synchrony | — |
| `index_search.py` | embed + semantic search | VAST |
| `agent.py` | orchestrate + ACTION (clip + `Brief`) | — |
| `kpis.py` | eval vs gold + log | W&B |
| `app.py` | search UI | — |

Every module has a MOCK path (fixtures/) so the demo never blocks on an endpoint.
