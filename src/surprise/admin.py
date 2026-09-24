"""Local moderation UI: review collected activities and approve or reject them.

Serves a single page and a small JSON API on 127.0.0.1, backed by the local
SQLite store. Standard library only.
"""

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import unquote, urlsplit

from surprise.local_store import DEFAULT_PATH, STATUSES, LocalStore

PAGE = files("surprise").joinpath("admin.html")


def make_handler(db_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/activities":
                with LocalStore(db_path) as store:
                    self._send_json(HTTPStatus.OK, store.list_for_moderation())
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})

        def do_POST(self) -> None:
            # /api/activities/<source_id>/<external_id>/status
            parts = urlsplit(self.path).path.strip("/").split("/")
            if len(parts) != 5 or parts[:2] != ["api", "activities"] or parts[4] != "status":
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "introuvable"})
            # Requiring JSON forces a CORS preflight, so other sites cannot post here.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON attendu"})
            try:
                status = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0))).get("status")
            except (ValueError, AttributeError):
                status = None
            if status not in STATUSES:
                return self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"statut attendu : {', '.join(STATUSES)}"})
            with LocalStore(db_path) as store:
                found = store.set_status(unquote(parts[2]), unquote(parts[3]), status)
            if not found:
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "activité inconnue"})
            self._send_json(HTTPStatus.OK, {"status": status})

        def _send_json(self, code: HTTPStatus, data: object) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _send(self, code: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_PATH, help=f"base SQLite (défaut : {DEFAULT_PATH})")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db))
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Modération sur {url} (Ctrl+C pour arrêter)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
