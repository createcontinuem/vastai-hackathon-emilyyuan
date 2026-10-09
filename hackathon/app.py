"""Minimal Sentiment Engine UI — plain-language search over the indexed moments.

stdlib-only web server (no Flask dep needed) so it runs anywhere. One page:
a search box, results as cards (timestamp + description + reaction badge), and the
YouTube embed jumps to the moment's start time.

  python -m hackathon.app        # http://localhost:8800

Builds the index once at startup (MOCK by default).
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .agent import build, _read_videos
from . import config

PORT = 8800
_INDEX, _BY_VIDEO = build(_read_videos(Path("hackathon/videos.txt")))

PAGE = """<!doctype html><meta charset=utf-8><title>Sentiment Engine</title>
<style>body{font:16px system-ui;max-width:760px;margin:40px auto;padding:0 16px}
input{width:100%;padding:12px;font-size:18px}
.card{border:1px solid #ddd;border-radius:10px;padding:14px;margin:12px 0}
.t{color:#888;font-size:13px}.badge{background:#eef;border-radius:6px;padding:2px 8px;font-size:12px}
iframe{width:100%;aspect-ratio:16/9;border:0;border-radius:8px;margin-top:8px}</style>
<h1>Sentiment Engine — ask the footage</h1>
<form><input name=q placeholder="e.g. where does something talk to the player"
 value="__Q__" autofocus></form>
<div id=r>__RESULTS__</div>"""


def _results_html(query: str) -> str:
    if not query:
        return "<p style=color:#888>Type a question to search hours of video.</p>"
    res = _INDEX.search(query)
    if not res.moments:
        return "<p>No moments matched.</p>"
    out = []
    for m in res.moments:
        badge = (f"<span class=badge>{m.reaction_emotion} "
                 f"{m.reaction_intensity:.0%}</span>" if m.reaction_emotion else "")
        embed = (f"https://www.youtube.com/embed/{m.video_id}"
                 f"?start={int(m.t_start)}")
        out.append(
            f"<div class=card><div class=t>{m.video_id} @ {m.t_start:.0f}s "
            f"&middot; score {m.score:.2f}</div>"
            f"<b>{m.title}</b> {badge}"
            f"<iframe src='{embed}' allowfullscreen></iframe></div>")
    return "\n".join(out)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
        body = PAGE.replace("__Q__", q).replace("__RESULTS__", _results_html(q))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    print(f"[OK] Sentiment Engine UI on http://localhost:{PORT}  ({'MOCK' if config.MOCK else 'LIVE'})")
    HTTPServer(("", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
