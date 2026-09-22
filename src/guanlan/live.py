"""Real-case launch command; --check never connects or mutates."""
import argparse
import json
import ipaddress
import threading
from pathlib import Path

from guanlan.liveweb import create_server
from guanlan.session import Session
from guanlan.session.profile import load_profile, worker_command


def main():
    parser = argparse.ArgumentParser(description='Guanlan real OpenFOAM case page')
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--state', type=Path, default=Path(__file__).resolve().parents[2] / 'state' / 'live')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    address = ipaddress.ip_address(args.bind)
    if not (address.is_loopback or address.is_private) or address.is_unspecified:
        parser.error('bind must be an explicit loopback or private-network IP, not a public or wildcard address')
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    profile = load_profile(args.profile)
    if args.check:
        print(json.dumps({'case': profile['case_directory'], 'worker_command': worker_command(profile),
                          'remote_writes': [profile['remote_workspace']], 'bind': args.bind}, indent=2))
        return
    session = Session(profile, args.state)
    server = create_server(session, args.bind, args.port)
    def launch():
        try:
            session.start()
        except Exception as error:
            with session.lock:
                session.status, session.message = 'unavailable', 'Worker launch failed: ' + str(error)
    try:
        threading.Thread(target=launch, daemon=True).start()
        print(f"Case page: http://{args.bind}:{args.port}/case/{profile['case_id']}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        session.close()


if __name__ == '__main__':
    main()
