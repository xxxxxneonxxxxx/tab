from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_HOST, DEFAULT_PORT
from .logging_config import configure_logging
from .service import SongService

logger = logging.getLogger(__name__)
FRONTEND = Path(__file__).resolve().parent / "frontend" / "index.html"


class Handler(BaseHTTPRequestHandler):
    service = SongService()

    def _send(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        logger.info("request method=GET path=%s", parsed.path)
        if parsed.path == "/health":
            return self._send({"status": "ok", "service": "newbec"})
        if parsed.path == "/api/sources":
            return self._send({"status": "ok", "sources": self.service.sources()})
        if parsed.path == "/api/song":
            title = parse_qs(parsed.query).get("title", [""])[0]
            result = self.service.convert(title)
            return self._send(result, 400 if result["status"] == "invalid" else 200)
        if parsed.path in {"/", "/index.html"}:
            body = FRONTEND.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send({"status": "not_found", "message": "use GET /api/song?title=..."}, 404)

    def log_message(self, format: str, *args) -> None:
        return


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    configure_logging()
    server = ThreadingHTTPServer((host, port), Handler)
    logger.info("newbec listening on http://%s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run()
