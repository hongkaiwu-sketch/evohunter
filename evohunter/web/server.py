from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from evohunter.ai import AIConfigurationError
from evohunter.core.protocol import ValidationError
from evohunter.data_scraper import ScrapeError
from evohunter.llm_parser import LLMParserError
from evohunter.outreach import OutreachDraftError
from evohunter.web.api import ApiError, handle_api_request

STATIC_DIR = Path(__file__).with_name("static")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), WorkbenchRequestHandler)
    print(f"EvoHunter workbench running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    server_version = "EvoHunterWorkbench/0.1"

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send_static_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path.startswith("/static/"):
            file_path = STATIC_DIR / self.path.removeprefix("/static/")
            self._send_static_file(file_path, _content_type(file_path))
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self.path.startswith("/api/"):
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json_body()
            response = handle_api_request(self.path, payload)
        except (
            ApiError,
            AIConfigurationError,
            LLMParserError,
            OutreachDraftError,
            ScrapeError,
            ValidationError,
        ) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except json.JSONDecodeError:
            self._send_json({"error": "request body must be valid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(response, HTTPStatus.OK)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        payload = json.loads(raw_body or "{}")
        if not isinstance(payload, dict):
            raise ApiError("request body must be a JSON object")
        return payload

    def _send_static_file(self, file_path: Path, content_type: str) -> None:
        resolved = file_path.resolve()
        if STATIC_DIR.resolve() not in (resolved, *resolved.parents) or not resolved.is_file():
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        content = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def _content_type(file_path: Path) -> str:
    if file_path.suffix == ".css":
        return "text/css; charset=utf-8"
    if file_path.suffix == ".js":
        return "text/javascript; charset=utf-8"
    if file_path.suffix == ".json":
        return "application/json; charset=utf-8"
    return "application/octet-stream"
