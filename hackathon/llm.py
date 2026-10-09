"""Text LLM — NVIDIA Nemotron via CoreWeave serverless (your $100 W&B credits).

OpenAI-compatible /chat/completions at CW_TEXT_URL, auth = W&B API key. Used for the
agent's reasoning: writing insight briefs and (optionally) parsing queries.

stdlib HTTP (no openai dep). Set WANDB_ENTITY_PROJECT if the endpoint requires
team/project routing for a service-account key.
"""

import json
import os
import urllib.request
import urllib.error

from . import config


def chat(prompt: str, system: str = "You are a concise video-insights analyst.",
         max_tokens: int = 2048, temperature: float = 0.3, think: bool = False) -> str:
    """Single-turn completion from Nemotron (a reasoning model).

    Nemotron toggles its chain-of-thought via a "detailed thinking on/off" system
    directive. We default think=False to get the final answer directly in
    `content` (otherwise the trace lands in `reasoning` and eats the token budget).
    Raises RuntimeError with a clear hint on auth/project failures."""
    key = os.getenv("WANDB_API_KEY", "")   # CoreWeave serverless auth = W&B key
    if not key:
        raise RuntimeError("WANDB_API_KEY not set (needed for CoreWeave serverless)")

    sys_prompt = ("detailed thinking off\n" + system) if not think else system
    payload = {
        "model": config.NEMOTRON_MODEL,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json",
               "User-Agent": "sentiment-engine/0.1 (+https://github.com/)"}
    if config.WANDB_ENTITY_PROJECT:
        headers["OpenAI-Project"] = config.WANDB_ENTITY_PROJECT
    req = urllib.request.Request(
        config.CW_TEXT_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        out = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content")
        if not out:
            raise RuntimeError(f"Nemotron returned empty output: {json.dumps(msg)[:200]}")
        return out.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        hint = ""
        if "project" in body.lower() or e.code in (401, 403):
            hint = ("  -> set WANDB_ENTITY_PROJECT=<team>/<project> in .env "
                    "(service-account keys need team routing)")
        raise RuntimeError(f"Nemotron call failed {e.code}: {body}{hint}")
