"""List a VLM endpoint's model catalog and flag vision-capable ids.

Defaults to NVIDIA build.nvidia.com (VLM_URL), which hosts Cosmos-Reason. Point it
elsewhere by setting VLM_URL. stdlib-only.

  export NVIDIA_API_KEY=<free nvapi- key from https://build.nvidia.com>
  python -m hackathon.list_models
"""

import json
import sys
import urllib.request
import urllib.error

from . import config

VISION_HINTS = ("vl", "vision", "cosmos", "llava", "pixtral", "multimodal",
                "qwen2-vl", "qwen2.5-vl", "intern", "molmo", "-v-", "janus")


def main() -> int:
    # Lists the VLM endpoint's catalog (default: NVIDIA build.nvidia.com).
    # Set VLM_URL + NVIDIA_API_KEY to target NVIDIA; the key is separate from W&B.
    if not config.VLM_API_KEY:
        print("[ERROR] set NVIDIA_API_KEY (free nvapi- key from https://build.nvidia.com)")
        return 2
    url = config.VLM_URL.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {config.VLM_API_KEY}",
        # Cloudflare in front of the endpoint bans the default urllib UA (err 1010)
        "User-Agent": "pulse/0.1 (+https://github.com/)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[ERROR] {e.code} {e.reason}: {e.read().decode('utf-8', 'ignore')[:300]}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    models = [m.get("id", "?") for m in data.get("data", [])]
    if not models:
        print("[WARN] no models returned:", json.dumps(data)[:300])
        return 0

    vision = [m for m in models if any(h in m.lower() for h in VISION_HINTS)]
    print(f"[OK] {len(models)} models at {url}\n")
    for m in sorted(models):
        tag = "  <-- VISION?" if m in vision else ""
        print(f"  {m}{tag}")
    print(f"\n[{'OK' if vision else 'MISS'}] vision-capable candidates: "
          f"{vision if vision else 'none found -- use CoreWeave GPU self-host or NVIDIA NIM'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
