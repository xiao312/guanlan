import json
import re
import shlex
from pathlib import Path, PurePosixPath


def load_profile(path):
    profile = json.loads(Path(path).read_text(encoding='utf-8'))
    expected = set('case_id title ssh_alias case_directory remote_workspace pvpython partition cpus memory_mb walltime_minutes idle_seconds refresh_seconds'.split())
    if not isinstance(profile, dict) or set(profile) != expected:
        raise ValueError('live profile has unexpected or missing properties')
    for key in ('case_id', 'ssh_alias', 'partition'):
        if not isinstance(profile[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', profile[key]):
            raise ValueError('invalid ' + key)
    if not re.fullmatch(r'[a-z0-9-]{1,64}', profile['case_id']):
        raise ValueError('case_id must use lowercase letters, digits and hyphens')
    for key in ('case_directory', 'remote_workspace', 'pvpython'):
        value = profile[key]
        if not isinstance(value, str) or not value.startswith('/') or '..' in PurePosixPath(value).parts or any(c in value for c in '\n\r\0'):
            raise ValueError(key + ' must be an explicit absolute remote path')
    if 'guanlan' not in PurePosixPath(profile['remote_workspace']).parts:
        raise ValueError('remote_workspace must be inside a dedicated guanlan directory')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', profile['remote_workspace']):
        raise ValueError('remote_workspace must be a simple absolute path suitable for SCP')
    case, work = map(PurePosixPath, (profile['case_directory'], profile['remote_workspace']))
    if work == case or case in work.parents or work in case.parents:
        raise ValueError('worker workspace must be separate from the solver case')
    limits = {'cpus': (1, 8), 'memory_mb': (512, 28000), 'walltime_minutes': (5, 120),
              'idle_seconds': (60, 900), 'refresh_seconds': (10, 300)}
    for key, (low, high) in limits.items():
        if type(profile[key]) is not int or not low <= profile[key] <= high:
            raise ValueError(f'{key} must be an integer between {low} and {high}')
    if not isinstance(profile['title'], str) or not 1 <= len(profile['title']) <= 160:
        raise ValueError('title must be 1–160 characters')
    return profile


def worker_command(profile):
    p = profile
    args = ['srun', '--job-name=guanlan-view', '--partition=' + p['partition'], '--nodes=1', '--ntasks=1',
            '--cpus-per-task=' + str(p['cpus']), '--mem=' + str(p['memory_mb']) + 'M',
            '--time=' + str(p['walltime_minutes']), '--immediate=180',
            'env', 'PYTHONPATH=' + p['remote_workspace'] + '/src', 'PYTHONDONTWRITEBYTECODE=1',
            'MPLCONFIGDIR=' + p['remote_workspace'] + '/mpl', 'OMP_NUM_THREADS=' + str(p['cpus']),
            p['pvpython'], '-m', 'guanlan.worker.main', '--case', p['case_directory'],
            '--workspace', p['remote_workspace'], '--idle', str(p['idle_seconds'])]
    return ' '.join(shlex.quote(a) for a in args)
