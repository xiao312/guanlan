"""Retrieve selected prepared files; never launches a solver or extraction."""
import argparse
import base64
import json
import hashlib
from pathlib import Path
import re
import shlex
import subprocess
from guanlan.prepared import plan_assets, select
from guanlan.prepared.store import verify, valid_cached, reserve, atomic, DEFAULT_QUOTA
from guanlan.portable import prepared_html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True)
    parser.add_argument('--host')
    parser.add_argument('--select', nargs='+', required=True, help='block:p,T or geometry:')
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--quota', type=int, default=DEFAULT_QUOTA)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.host and not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}', args.host):
        parser.error('host must be an existing SSH alias')
    if args.quota <= 0:
        parser.error('quota must be positive')
    metadata_bytes = 0

    def read(relative, limit):
        if args.host:
            target = args.store.rstrip('/') + '/' + relative
            command = 'head -c ' + str(limit+1) + ' -- ' + shlex.quote(target)
            data = subprocess.run(['ssh','-T','-o','BatchMode=yes',args.host,command],
                                  check=True,stdout=subprocess.PIPE,timeout=120).stdout
        else:
            with (Path(args.store)/relative).open('rb') as stream:
                data = stream.read(limit+1)
        if len(data) > limit:
            raise ValueError('prepared file exceeds declared budget')
        return data

    raw = read('latest.json', 1024*1024)
    metadata_bytes += len(raw)
    manifest = json.loads(raw)
    selection = {}
    for entry in args.select:
        block, fields = entry.split(':',1)
        if block in selection:
            parser.error('duplicate selected block')
        selection[block] = fields.split(',') if fields else []
    chosen = select(manifest, selection)
    chosen, plan = plan_assets(manifest, selection, valid_cached(args.cache, chosen))
    plan['metadata_bytes'] = metadata_bytes
    if plan['decoded_bytes'] > 64*1024*1024:
        raise ValueError('selection exceeds browser decoded budget')
    if plan['retained_bytes'] > args.quota:
        raise ValueError('selection exceeds local cache quota')
    if not args.check:
        plan['evicted'] = reserve(args.cache, chosen, args.quota)
        batch = None
        if args.host and plan['missing']:
            # Concatenate exactly the selected immutable gzip files in one SSH
            # request. Manifest lengths frame the stream; no tar/base64 overhead.
            paths = [args.store.rstrip('/') + '/assets/' + key + '.bin.gz' for key in plan['missing']]
            command = 'cat -- ' + ' '.join(shlex.quote(path) for path in paths)
            command += ' | head -c ' + str(plan['transfer_bytes'] + 1)
            batch = subprocess.run(['ssh','-T','-o','BatchMode=yes',args.host,command],
                                   check=True,stdout=subprocess.PIPE,timeout=120).stdout
            if len(batch) != plan['transfer_bytes']:
                raise ValueError('selected transfer size mismatch')
        cursor = 0
        for key in plan['missing']:
            meta = chosen['assets'][key]
            size = meta['compressed_bytes']
            content = batch[cursor:cursor+size] if batch is not None else read('assets/'+key+'.bin.gz',size)
            cursor += size
            verify(key, meta, content)
            atomic(args.cache/'assets'/f'{key}.bin.gz', content)
        atomic(args.cache/'latest.json', json.dumps(chosen).encode())
        payloads = {key:{**meta,'payload':base64.b64encode((args.cache/'assets'/f'{key}.bin.gz').read_bytes()).decode()}
                    for key,meta in chosen['assets'].items()}
        bundle = (Path(__file__).resolve().parents[3]/'state/portable/viewer.js').read_text(encoding='utf-8')
        offline = prepared_html(chosen, payloads, bundle)
        atomic(args.output, offline)
        connected = dict(chosen, asset_base='assets/')
        runtime_bytes = bundle.encode()
        if len(runtime_bytes)>4*1024*1024:
            raise ValueError('runtime exceeds connected cache budget')
        runtime_id = hashlib.sha256(runtime_bytes).hexdigest()
        runtime_path = args.cache/'runtime'/f'{runtime_id}.js'
        if runtime_path.parent.exists() and runtime_path.parent.resolve().parent != args.cache.resolve():
            raise ValueError('runtime cache redirects outside its root')
        atomic(runtime_path,runtime_bytes)
        page = prepared_html(connected, {}, bundle, 'runtime/'+runtime_id+'.js').replace(b"connect-src 'none'", b"connect-src 'self'")
        atomic(args.cache/'index.html', page)
        old_runtimes = sorted((p for p in runtime_path.parent.glob('*.js') if p!=runtime_path),key=lambda p:p.stat().st_mtime,reverse=True)
        for obsolete in old_runtimes[1:]:
            if re.fullmatch('[0-9a-f]{64}.js',obsolete.name) and not obsolete.is_symlink():obsolete.unlink()
        plan.update(runtime_bytes=len(bundle.encode()), offline_html_bytes=len(offline),
                    connected_html_bytes=len(page), byte_scope='payload bytes; excludes SSH/HTTP framing')
        plan['cache_total_compressed_bytes'] = sum(p.stat().st_size for p in (args.cache/'assets').glob('*.bin.gz'))
        plan['runtime_cache_bytes'] = sum(p.stat().st_size for p in runtime_path.parent.glob('*.js'))
        atomic(args.cache/'transfer.json', json.dumps(plan,indent=2).encode())
    print(json.dumps({'check_only':args.check, **plan}))


if __name__ == '__main__':
    main()
