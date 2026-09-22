"""Loopback-only prepared-file preview; no computation or directory listing."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re


def create_server(root, port=0):
    root=Path(root).resolve()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:
                self.send_error(403);return
            relative='index.html' if self.path=='/' else self.path.lstrip('/')
            if relative not in ('index.html','latest.json') and not re.fullmatch(r'(assets/[0-9a-f]{64}\.bin\.gz|runtime/[0-9a-f]{64}\.js)',relative):
                self.send_error(404);return
            path=(root/relative).resolve()
            if root not in path.parents or not path.is_file():
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type','text/html' if relative=='index.html' else 'application/javascript' if relative.endswith('.js') else 'application/octet-stream')
            self.send_header('Content-Length',str(path.stat().st_size))
            self.send_header('Cache-Control','private, max-age=31536000, immutable' if relative.startswith(('assets/','runtime/')) else 'no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            with path.open('rb') as stream:
                while chunk:=stream.read(65536):self.wfile.write(chunk)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    server=create_server(args.root,args.port)
    print(f'Read-only prepared viewer: http://127.0.0.1:{server.server_port}',flush=True)
    server.serve_forever()


if __name__=='__main__':main()
