"""Prepare near the case; retrieve PNGs; package offline engineer blocks."""
import argparse
import json
from pathlib import Path
import sys
from guanlan.media import remote
from guanlan.media.contract import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    for command in ('check', 'submit'):
        sub = commands.add_parser(command)
        sub.add_argument('--profile', required=True, type=Path)
        sub.add_argument('--preset', required=True, type=Path)
        if command == 'submit':
            sub.add_argument('--state', required=True, type=Path)
            sub.add_argument('--minutes', type=int, default=20)
    for command in ('status', 'cancel', 'fetch', 'package', 'video'):
        sub = commands.add_parser(command)
        sub.add_argument('--state', required=True, type=Path)
        if command in ('package', 'video'): sub.add_argument('--output', required=True, type=Path)
        if command == 'package': sub.add_argument('--videos', type=Path)
        if command == 'video':
            sub.add_argument('--ffmpeg', default='ffmpeg')
            sub.add_argument('--fps', type=int, default=4)
    args = parser.parse_args()
    if args.action == 'check':
        p, c = remote.profile(args.profile)
        preset = validate(remote.read_json(args.preset))
        if c.get('source_format') == 'fluent-cff':
            from guanlan.media.fluent import validate_index
            validate_index(remote.read_json(c['source_index']), preset)
        result = {'preset': preset, 'source_format': c.get('source_format', 'openfoam'), 'alias': p['ssh_alias'],
                  'case': c['case_directory'], 'cpus': c['cpus'], 'memory_mb': c['memory_mb'], 'mutates': False}
    elif args.action == 'submit': result = remote.submit(args.profile, args.preset, args.state, args.minutes)
    elif args.action in ('status', 'cancel'): result = remote.status(args.state, args.action == 'cancel')
    elif args.action == 'fetch': result = remote.fetch(args.state)
    elif args.action == 'package':
        from guanlan.media.package import package
        result = package(args.state, args.output, args.videos)
    else:
        from guanlan.media.video import video
        result = video(args.state, args.output, args.ffmpeg, args.fps)
    print(json.dumps({'ok': True, 'data': result}, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error': {'message': str(error), 'type': type(error).__name__}}), file=sys.stderr)
        raise SystemExit(1)
