"""Explicit source deployment and bounded media-only retrieval over existing SSH."""
import io
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import uuid
import zipfile

from guanlan.media.contract import MAX_BYTES, digest, validate, validate_manifest

PROJECT = Path(__file__).resolve().parents[3]
SSH = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=60']


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 2*1024*1024: raise ValueError('metadata exceeds 2 MiB')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def profile(path):
    p = read_json(path)
    case_path = Path(p['case_profile'])
    c = read_json(case_path if case_path.is_absolute() else PROJECT / case_path)
    for v in (p['ssh_alias'], c['partition']):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', v): raise ValueError('invalid alias/partition')
    for v in (p['remote_runtime'], p['image'], c['case_directory'], c['remote_workspace']):
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', v) or '..' in v.split('/'):
            raise ValueError('expected absolute simple remote paths')
    if '/guanlan/' not in c['remote_workspace']: raise ValueError('workspace must be under guanlan')
    for k, lo, hi in [('cpus', 1, 16), ('memory_mb', 1024, 65536)]:
        if type(c[k]) is not int or not lo <= c[k] <= hi: raise ValueError('resource limit out of bounds: '+k)
    return p, c


def ssh(alias, command):
    return subprocess.run(['ssh', *SSH, alias, command], check=True, capture_output=True, text=True, timeout=150).stdout.strip()


def scp(source, target):
    subprocess.run(['scp', '-q', *SSH, str(source), str(target)], check=True, timeout=180)


def submit(profile_path, preset_path, state_path, minutes=20):
    p, c = profile(profile_path)
    preset = validate(read_json(preset_path))
    if not 5 <= minutes <= 60: raise ValueError('walltime must be 5-60 minutes')
    state = Path(state_path).resolve()
    if state.exists(): raise ValueError('state exists; inspect status instead of duplicate submission')
    state.mkdir(parents=True)
    remote = c['remote_workspace'].rstrip('/') + '/media-' + uuid.uuid4().hex[:12]
    record = {'alias': p['ssh_alias'], 'remote': remote, 'job_id': None, 'phase': 'deploying'}
    write_json(state / 'operation.local.json', record)
    bundle = state / 'worker.tar'
    with tarfile.open(bundle, 'w') as archive:
        for module in ('worker', 'media'):
            for source in sorted((PROJECT / 'src/guanlan' / module).glob('*.py')):
                archive.add(source, arcname='src/guanlan/'+module+'/'+source.name)
        archive.add(PROJECT / 'src/guanlan/__init__.py', arcname='src/guanlan/__init__.py')
        for filename, payload in [('preset.json', json.dumps(preset).encode()),
                                  ('run.sh', (PROJECT / 'infrastructure/paraview/run.sh').read_bytes().replace(b'\r\n', b'\n'))]:
            info = tarfile.TarInfo(filename); info.size = len(payload); info.mode = 0o600
            archive.addfile(info, io.BytesIO(payload))
    alias = p['ssh_alias']
    ssh(alias, 'mkdir ' + shlex.quote(remote))
    scp(bundle, alias+':'+remote+'/worker.tar')
    ssh(alias, 'tar -xf '+shlex.quote(remote+'/worker.tar')+' -C '+shlex.quote(remote))
    command = ['sbatch', '--parsable', '--job-name=guanlan-media', '--partition='+c['partition'],
               '--nodes=1', '--ntasks=1', '--cpus-per-task='+str(c['cpus']), '--mem='+str(c['memory_mb'])+'M',
               '--time='+str(minutes), '--chdir='+remote, '--output='+remote+'/job-%j.log',
               '--error='+remote+'/job-%j.err', '--export=ALL,GUANLAN_SCRATCH_ROOT=/tmp',
               remote+'/run.sh', 'media', p['image'], c['case_directory'], remote,
               '--preset', remote+'/preset.json']
    record['phase'] = 'submitting'; write_json(state/'operation.local.json', record)
    result = ssh(alias, shlex.join(command))
    if not re.fullmatch(r'\d+(;\S+)?', result): raise ValueError('ambiguous sbatch result; inspect queue before retrying')
    record.update(job_id=result.split(';')[0], phase='submitted')
    write_json(state/'operation.local.json', record)
    return record


def operation(state):
    o = read_json(Path(state)/'operation.local.json')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', o['alias']) or not re.fullmatch(r'/[A-Za-z0-9_./-]+/media-[a-f0-9]{12}', o['remote']) or '..' in o['remote'].split('/'):
        raise ValueError('invalid saved operation')
    if not o['job_id'] or not re.fullmatch(r'\d+', o['job_id']):
        raise ValueError('submission has no confirmed job ID; inspect remote queue/logs, do not resubmit blindly')
    return o


def status(state, cancel=False):
    o = operation(state)
    queue = ssh(o['alias'], "squeue -h -j "+o['job_id']+" -o '%T|%j|%Z'")
    if queue and not queue.endswith('|guanlan-media|'+o['remote']): raise ValueError('job identity mismatch')
    if cancel and queue: ssh(o['alias'], 'scancel '+o['job_id'])
    accounting = ssh(o['alias'], 'sacct -j '+o['job_id']+' --noheader --parsable2 --format=JobID,State,ExitCode,Elapsed,MaxRSS')
    return {'job_id': o['job_id'], 'queue': queue, 'accounting': accounting, 'cancel_requested': bool(cancel and queue)}


def unpack(manifest, archive_path, destination):
    validate_manifest(manifest)
    archive_path, destination = Path(archive_path), Path(destination)
    expected = {f['file']: f for f in manifest['frames']}
    if archive_path.stat().st_size != manifest['bundle']['bytes'] or archive_path.stat().st_size > MAX_BYTES + 1024*1024:
        raise ValueError('bundle size mismatch')
    if digest(archive_path.read_bytes()) != manifest['bundle']['sha256']: raise ValueError('bundle hash mismatch')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if len(entries) != len(expected) or {i.filename for i in entries} != set(expected): raise ValueError('unexpected archive entries')
        for item in entries:
            frame = expected[item.filename]
            if item.file_size != frame['bytes']: raise ValueError('decoded size mismatch')
            payload = archive.read(item)
            if not payload.startswith(b'\x89PNG\r\n\x1a\n') or digest(payload) != frame['sha256']: raise ValueError('PNG integrity mismatch')
        destination.mkdir(exist_ok=False)
        for item in entries: (destination/item.filename).write_bytes(archive.read(item))


def fetch(state_path):
    state = Path(state_path); o = operation(state)
    if (state/'manifest.json').exists(): raise ValueError('already fetched; use package or a new state directory')
    # Read bounded metadata through SSH before selecting any binary transfer.
    raw = ssh(o['alias'], 'head -c 2097153 '+shlex.quote(o['remote']+'/output/manifest.json'))
    if len(raw.encode()) > 2*1024*1024: raise ValueError('metadata exceeds budget')
    manifest = validate_manifest(json.loads(raw))
    size = manifest['bundle']['bytes']
    if type(size) is not int or not 0 < size <= MAX_BYTES+1024*1024: raise ValueError('bundle exceeds budget')
    actual = ssh(o['alias'], 'stat -c%s '+shlex.quote(o['remote']+'/output/media.zip'))
    if actual != str(size): raise ValueError('remote bundle size mismatch')
    scp(o['alias']+':'+o['remote']+'/output/media.zip', state/'media.zip')
    unpack(manifest, state/'media.zip', state/'frames')
    write_json(state/'manifest.json', manifest)
    return {'frames': len(manifest['frames']), 'transferred_png_bundle_bytes': size, 'metadata_bytes': len(raw.encode())}
