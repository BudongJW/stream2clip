"""An OBS browser source for the stream recorder: viewers see the !clip votes and the markers.

The recorder serves two addresses on this PC only (127.0.0.1):

* ``/widget`` - a transparent page for OBS (Sources > Browser, width 400, height 120)
* ``/state`` - what the page shows, as JSON: votes so far, votes needed, markers left,
  the time of the last marker

The page asks for ``/state`` every second; nothing reaches the internet.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

__all__ = ["WidgetServer", "PAGE", "DEFAULT_PORT"]

DEFAULT_PORT = 8790

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>stream2clip</title>
<style>
html,body{margin:0;background:transparent;font-family:"Pretendard","Noto Sans KR","Noto Sans JP",sans-serif;color:#F7F4FA}
#box{display:inline-flex;align-items:center;gap:12px;margin:8px;padding:10px 16px;border-radius:14px;background:rgba(21,19,31,.82)}
#word{font-weight:800;font-size:22px}
#bar{width:160px;height:12px;border-radius:6px;background:#3A3550;overflow:hidden}
#fill{height:100%;width:0;background:#FF4F8B}
#count{font-size:20px;font-variant-numeric:tabular-nums}
#box.marked{background:rgba(255,79,139,.92)}
</style></head>
<body><div id="box"><span id="word">!clip</span><div id="bar"><div id="fill"></div></div><span id="count"></span></div>
<script>
const box = document.getElementById("box"), fill = document.getElementById("fill"), count = document.getElementById("count");
let seen = null;
async function look() {
  try {
    const s = await (await fetch("state", {cache: "no-store"})).json();
    const need = Math.max(1, s.needed || 1);
    fill.style.width = Math.min(100, 100 * s.votes / need) + "%";
    count.textContent = s.needed ? s.votes + " / " + s.needed : "";
    box.style.display = s.needed || s.markers ? "inline-flex" : "none";
    if (seen !== null && s.markers > seen) {
      box.classList.add("marked");
      setTimeout(() => box.classList.remove("marked"), 3000);
    }
    seen = s.markers;
  } catch (e) {}
}
setInterval(look, 1000);
look();
</script></body></html>
"""


class WidgetServer:
    """Serve the widget page and ``state()`` on ``127.0.0.1:port`` (port 0: any free port) in a thread."""

    def __init__(self, state: Callable[[], dict[str, Any]], *, port: int = DEFAULT_PORT) -> None:
        reader = state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server API
                path = self.path.split("?", 1)[0]
                if path in ("/", "/widget"):
                    body, kind, code = PAGE.encode("utf-8"), "text/html; charset=utf-8", 200
                elif path == "/state":
                    body, kind, code = json.dumps(reader()).encode("utf-8"), "application/json", 200
                else:
                    body, kind, code = b"not found", "text/plain", 404
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, name="stream2clip-widget", daemon=True)
        self._thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/widget"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
