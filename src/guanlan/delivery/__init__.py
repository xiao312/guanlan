"""Loopback-only HTTP fixture. No production publication or remote execution."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from guanlan.contracts import digest, validate_recipe
from guanlan.preview import render


def create_server(recipes, port):
    for recipe in recipes.values():
        validate_recipe(recipe)
    started = time.monotonic()
    assets = Path(__file__).parent

    class Handler(BaseHTTPRequestHandler):
        def send_payload(self, payload, content_type, download=None):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, value):
            self.send_payload(json.dumps(value).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            parsed = urlsplit(self.path)
            static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                      "/style.css": ("style.css", "text/css")}
            if parsed.path in static:
                filename, content_type = static[parsed.path]
                self.send_payload((assets / filename).read_bytes(), content_type + "; charset=utf-8")
                return
            if parsed.path == "/api/views":
                self.send_json(list(recipes.values()))
                return
            if parsed.path not in ("/api/preview", "/image", "/snapshot"):
                self.send_error(404, "Unknown route")
                return
            try:
                query = parse_qs(parsed.query, max_num_fields=4)
                view_id = query.get("view", [""])[0]
                if view_id not in recipes:
                    self.send_error(404, "Unknown saved view")
                    return
                recipe = recipes[view_id]
                interval = recipe["refresh"]["interval_seconds"]
                if parsed.path == "/api/preview":
                    frame = int((time.monotonic() - started) / interval)
                    self.send_json({"schema_version": 1, "view_id": view_id,
                                    "recipe_digest": digest(recipe), "case_id": recipe["case_id"],
                                    "frame_id": frame, "simulation_time": frame * 0.001,
                                    "simulation_time_units": "s", "source_kind": "synthetic",
                                    "image_url": f"/image?view={view_id}&frame={frame}",
                                    "poll_interval_seconds": interval})
                    return
                frame = int(query.get("frame", [""])[0])
                payload = render(recipe, frame)
                filename = f"guanlan-{view_id}-{frame}.svg" if parsed.path == "/snapshot" else None
                self.send_payload(payload, "image/svg+xml; charset=utf-8", filename)
            except ValueError as error:
                self.send_error(400, str(error))

        def log_message(self, format, *args):
            # Keep frequent fixture polling out of console logs.
            pass

    return HTTPServer(("127.0.0.1", port), Handler)
