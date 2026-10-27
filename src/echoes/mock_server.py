"""Local stand-in for the Qloo API, for offline development and tests ONLY.

Everything it returns is fabricated and labelled "[MOCK]". Never present its output
as Qloo data. Run standalone:  python -m echoes.mock_server --port 8765
then set QLOO_BASE_URL=http://127.0.0.1:8765 and any non-empty QLOO_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def _entity(name: str, etype: str, popularity: float = 0.5) -> dict:
    short = etype.split(":")[-1]
    return {
        "entity_id": f"MOCK-{short}-{zlib.crc32(name.encode()) % 10**6:06d}",
        "name": name,
        "types": [etype],
        "popularity": popularity,
        "tags": [{"name": "mock-tag", "id": "urn:tag:mock"}],
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        pass

    def _send(self, code: int, body: dict, headers: dict | None = None) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.server.recorded.append((u.path, q))  # type: ignore[attr-defined]
        if not self.headers.get("X-Api-Key"):
            return self._send(403, {"error": "missing api key"})

        if u.path == "/search":
            query = q.get("query", "")
            if query == "badrequest":
                return self._send(400, {"error": "bad request"})
            state = self.server.state  # type: ignore[attr-defined]
            if query == "ratelimit" and not state.get("ratelimit_served"):
                state["ratelimit_served"] = True
                return self._send(429, {"error": "slow down"}, {"Retry-After": "0"})
            etype = (q.get("types") or "urn:entity:artist").split(",")[0]
            take = int(q.get("take", 5))
            hits = [_entity(query, etype, 0.9)] + [
                _entity(f"[MOCK] {query} alt {i}", etype, 0.2) for i in range(1, take)
            ]
            return self._send(200, {"results": hits[:take]})

        if u.path == "/v2/insights":
            etype = q.get("filter.type", "urn:entity:artist")
            short = etype.split(":")[-1]
            take = int(q.get("take", 10))
            ents = [_entity(f"[MOCK] {short} neighbour {i + 1}", etype, 0.5) for i in range(take)]
            return self._send(200, {"success": True, "results": {"entities": ents}})

        if u.path == "/v2/tags":
            query = q.get("filter.query", "")
            tags = [{"id": f"urn:tag:mock:{query}", "name": f"[MOCK] {query}"}]
            return self._send(200, {"results": {"tags": tags}})

        if u.path == "/entities":
            ids = (q.get("entity_ids") or "").split(",")
            return self._send(200, {"results": [_entity(f"[MOCK] {i}", "urn:entity:artist") for i in ids if i]})

        return self._send(404, {"error": "not found"})


def start_mock(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Start the mock in a daemon thread. Returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    server.recorded = []  # type: ignore[attr-defined]
    server.state = {}  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    srv, url = start_mock(args.port)
    print(f"[MOCK] Qloo stand-in listening on {url} (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
