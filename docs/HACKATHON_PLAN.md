# HACKATHON_PLAN.md — VAST Builders Challenge (tokens&, NYC, 2026-10-09)

**Sentiment Engine** — a real-time video agent that understands footage, finds the
moments that matter, and acts on them.

> One idea. Working. Shipped by end of day. Use 3+ sponsor tools. Demos > slides.

---

## 1. The pitch (Idea)

**Problem.** Every video — a 104-minute horror playthrough, a runway show — is an
opaque wall of footage. Finding *what happened* and *what mattered* means scrubbing
a timeline by hand. At scale (a game launch = hundreds of hours across dozens of
creators) that's impossible.

**Sentiment Engine** turns footage into a **queryable, time-indexed understanding** you can ask
in plain language — and, when the video has an audience reacting, it fuses *what
happened on screen* with *how people reacted* to surface the moments that actually
landed, then **triggers an action** (cut the clip + write the brief) when something
matters.

**Why it's more than "find the jumpscare":** it's population-scale video
intelligence — design/marketing/live-ops questions answered from footage that
already exists. See [docs/METHOD.md](METHOD.md) and the use-case framing in the repo
README.

## 2. Test corpus (3 videos — deliberately diverse)

`hackathon/videos.txt`

| id | title | type | reaction lane? |
|---|---|---|---|
| `hvPRP72dpow` | Silent Hill Townfall Pt.1 (Hollow) | horror + commentary | yes |
| `RhWykEeyBwc` | Threshold "DID IT JUST TALK TO ME?!" (xKarutaClanx) | horror reaction | yes |
| `T4ZzV7R6GXQ` | Schiaparelli SS2027 runway | fashion, no commentary | **no → pure visual search** |

The runway is the **generalization proof**: same agent, no gaming assumptions.

## 3. What we demo (2-min script — Presentation)

1. **Plain-language search** across 2+ hours: *"where does something talk to the player?"* → jumps to the Threshold moment, plays the clip. (search)
2. **Ask what happened** on the runway: *"show the most dramatic entrance"* → returns the timestamped moment. (understanding + generality)
3. **The agent acts**: on the Silent Hill video it auto-surfaces the top "notable moment" (visual scare × reaction spike) and emits a **clip + one-paragraph brief** — no prompt. (spot events + trigger an action)

Three videos, three capabilities, one agent.

## 4. Architecture (MVP)

```
hackathon/videos.txt
      │
      ▼
[ingest]  src/video_ingest.fetch_video  ──►  data/{set}/video/{id}.mp4   (DONE, verified)
      │         (video-only, <=720p, Node JS runtime, ephemeral scratch)
      │
      ├───────────────────────────────┐
      ▼                                ▼
[visual_events]                   [reactions]           (game videos only)
 VSS / Cosmos-Reason on CoreWeave  captions/audio ─► emotion timeline
 mp4 ─► VisualEvent[] (t, label,   (reuse sentiment/ pipeline)
        description, embedding)     ReactionPoint[]
      │                                │
      └──────────────┬─────────────────┘
                     ▼
                  [fuse]   align visual ↔ reaction on time
                     │     ─► NotableMoment[]  (+ cross-video synchrony)
                     ▼
              [index_search]  embeddings ─► VAST   (semantic search)
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
   plain-language query      [agent] action trigger:
   ─► ranked moments + clip   top moment ─► cut clip + Brief
                     │
                     ▼
                  [app]  search box → clip player + event/reaction timeline
                     │
                  [kpis]  eval harness + tracing ─► W&B
```

**Data contracts** live in `hackathon/schemas.py` (`VisualEvent`, `ReactionPoint`,
`NotableMoment`, `SearchResult`, `Brief`) — the single source of truth for
inputs/outputs (Technical-Implementation rubric: *clear docs of inputs/outputs*).

## 5. Sponsor-tool mapping (Impact — need ≥3, target 4)

| Sponsor | Where it's load-bearing | Module |
|---|---|---|
| **NVIDIA VSS / Cosmos-Reason** | visual understanding — mp4 → timestamped events | `visual_events.py` |
| **CoreWeave** | GPU hosting the VLM inference endpoint | `visual_events.py` (runtime) |
| **VAST** | store event captions + embeddings; semantic retrieval | `index_search.py` |
| **W&B (Weave)** | agent tracing + KPI/eval dashboard | `kpis.py` |
| Cursor | dev speed | — |

## 6. Task scope (time-boxed; cut lines below)

| # | Task | Est | Owner | Status |
|---|---|---|---|---|
| P0 | Env + sponsor creds + `videos.txt`; confirm ingest | 30m | | ingest ✅ |
| P1 | `visual_events`: CoreWeave Cosmos/VSS client → VisualEvent[] | 90m | | |
| P2 | `reactions`: captions → emotion timeline (reuse `sentiment/`) | 45m | | |
| P3 | `fuse`: align + rank NotableMoment[] + synchrony | 45m | | |
| P4 | `index_search`: embeddings into VAST + query | 60m | | |
| P5 | `agent`: action trigger → clip cut + Brief | 30m | | |
| P6 | `app`: minimal search UI (clip + timeline) | 60m | | |
| P7 | `kpis`: eval harness + W&B dashboard + hero numbers | 30m | | |
| P8 | Record 2-min demo + finalize `hackathon/README.md` | 45m | | |

**Build order = thin vertical slice first:** P0 → P1 → P4 → P6 (one video,
end-to-end search + UI) *then* layer P2/P3/P5 (the reaction differentiator).

**Cut lines (if the clock wins):**
- **Must** (satisfies the challenge): 1 video → visual events → plain-language search → UI → demo.
- **Should** (the differentiator): reaction fusion on the 2 game videos.
- **Nice**: cross-video synchrony, real VAST vectors (fall back to local cosine), Brief generation.

**Risk hedge:** every module has a `MOCK` path (reads a fixture, returns canned
data) so the UI + demo work even if a sponsor endpoint is down. Wire real endpoints
behind env vars; never block the demo on an external service.

## 7. KPIs (presented in the W&B panel; hero four on the slide)

**Hero four:** hours-in → moments-out compression · cost to structure 1 hr of video
· event-detection precision@5 vs. a hand gold set · query→answer latency.

Full set + criteria mapping: see "KPIs" section of the pitch — logged live to W&B
(doubles as a sponsor tool and the reproducibility evidence).

**30-min investment that pays off:** hand-label ~10 real events + "moments that
mattered" per video → turns every quality KPI from assertion into measurement.

## 8. Reproduce (judging: easy to follow/reproduce)

```bash
# 1. ingest video (video-only, 720p, into scratch)
python -m src.video_ingest --game shtownfall --urls-file hackathon/videos.txt --max-height 720

# 2. run the agent pipeline end-to-end (uses MOCK endpoints unless envs set)
python -m hackathon.agent --videos hackathon/videos.txt

# 3. serve the UI
python -m hackathon.app     # http://localhost:8800

# env vars (real endpoints): COREWEAVE_VLM_URL, COSMOS_MODEL, VAST_* , WANDB_API_KEY
# see hackathon/config.py
```

## 9. Out of scope for today (explicitly)

Production R2 retention of video, multi-game directory, the full MAP→REDUCE
collective report, auth, cost-model re-ranking. Video stays ephemeral scratch
(`data/{set}/video/`, gitignored) — not `raw/`. These are real but deferred; noted
in the Lead-DE review.
