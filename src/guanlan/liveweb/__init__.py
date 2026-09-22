"""Case-scoped HTTP delivery; read-only share links and portable snapshots."""
import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from guanlan.liveweb.snapshot import snapshot_html


def create_server(session, bind, port):
    assets = Path(__file__).parent
    case_path = '/case/' + session.profile['case_id']

    class Handler(BaseHTTPRequestHandler):
        def payload(self, content, kind, filename=None):
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'")
            if filename:
                self.send_header('Content-Disposition', 'attachment; filename="' + filename + '"')
            self.end_headers()
            self.wfile.write(content)

        def json(self, value):
            self.payload(json.dumps(value, allow_nan=False).encode(), 'application/json; charset=utf-8')

        def editable(self):
            return ipaddress.ip_address(self.client_address[0]).is_loopback

        def do_GET(self):
            path = urlsplit(self.path).path
            static = {case_path: ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                      '/style.css': ('style.css', 'text/css')}
            try:
                if path == '/':
                    self.send_response(302)
                    self.send_header('Location', case_path)
                    self.end_headers()
                elif path in static:
                    filename, content_type = static[path]
                    self.payload((assets / filename).read_bytes(), content_type + '; charset=utf-8')
                elif path == '/api/state':
                    self.json(dict(session.state(), editable=self.editable(), case_url=case_path))
                elif path.startswith('/image/'):
                    _, _, generation, filename = path.split('/')
                    if not filename.endswith('.png'):
                        raise ValueError('invalid image')
                    self.payload(session.store.image(generation, filename[:-4]), 'image/png')
                elif path == '/snapshot.html':
                    with session.lock:
                        self.payload(snapshot_html(session.state(), session.store), 'text/html; charset=utf-8',
                                     session.profile['case_id'] + '-snapshot.html')
                else:
                    self.send_error(404, 'Unknown case or resource')
            except FileNotFoundError:
                self.send_error(404, 'Preview expired; refresh the case page')
            except (ValueError, OSError) as error:
                self.send_error(400, str(error))

        def do_POST(self):
            # The initial LAN/VPN sharing mode is read-only; only local owner edits.
            origin = self.headers.get('Origin')
            expected = 'http://' + self.headers.get('Host', '')
            host = urlsplit(expected).hostname
            if not self.editable() or host not in ('127.0.0.1', 'localhost') or origin != expected:
                self.send_error(403, 'Edits require the local case owner and matching origin')
                return
            if self.path == '/api/reconnect':
                try:
                    session.reconnect()
                    self.json({'reconnecting': True})
                except ValueError as error:
                    self.send_error(409, str(error))
                except Exception as error:
                    with session.lock:
                        session.status, session.message = 'unavailable', str(error)
                    self.send_error(503, 'Could not reconnect; inspect local worker diagnostics')
                return
            if self.path != '/api/document':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 65536:
                    raise ValueError('request must be between 1 and 65536 bytes')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {'document', 'revision'}:
                    raise ValueError('expected document and revision')
                self.json(session.edit(body['document'], body['revision']))
            except (ValueError, KeyError) as error:
                self.send_error(400, str(error))

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((bind, port), Handler)
