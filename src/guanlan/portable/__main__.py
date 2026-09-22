import argparse
import json
from pathlib import Path
from guanlan.portable import MAX_SCENE_BYTES, snapshot_html


def main():
    parser = argparse.ArgumentParser(description='Package an existing scene; no SSH or worker startup')
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parents[3] / 'state/portable/viewer.js')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.scene.stat().st_size > MAX_SCENE_BYTES:
        parser.error('scene exceeds 64 MiB budget')
    if not args.bundle.exists():
        parser.error('viewer bundle missing; run npm ci and npm run build in viewer/')
    if args.output.resolve() in (args.scene.resolve(), args.bundle.resolve()):
        parser.error('output must not overwrite scene or viewer bundle')
    scene = json.loads(args.scene.read_text(encoding='utf-8'))
    payload = snapshot_html(scene, args.bundle.read_text(encoding='utf-8'))
    if not args.check:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        pending = args.output.with_suffix('.pending')
        pending.write_bytes(payload)
        pending.replace(args.output)
    print(json.dumps({'check_only': args.check, 'bytes': len(payload), 'output': str(args.output),
                      'simulation_time': scene['simulation_time'], 'blocks': len(scene['blocks'])}))


if __name__ == '__main__':
    main()
