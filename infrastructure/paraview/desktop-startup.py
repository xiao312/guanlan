"""Run inside the visible ParaView desktop after --url connects; leave it open."""
import json
import os
from pathlib import Path
from paraview import servermanager

# ParaView's GUI executes startup scripts without guaranteeing __file__.
request = json.loads(Path(os.environ['GUANLAN_DESKTOP_REQUEST']).read_text(encoding='utf-8-sig'))
try:
    connection = servermanager.ActiveConnection
    remote = bool(connection and connection.IsRemote())
    result = {'ok': remote, 'remote': remote, 'job_id': request['job_id'],
              'expected_url': request['expected_url'], 'connection': str(connection)}
except Exception as error:
    remote = False
    result = {'ok': False, 'remote': False, 'error': str(error)}
Path(request['receipt']).write_text(json.dumps(result, indent=2), encoding='utf-8')
if not remote:
    raise RuntimeError('Desktop launched but has no active remote connection; inspect tunnel/server')
