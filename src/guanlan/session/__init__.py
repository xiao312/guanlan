"""One case, one warm allocation, coalesced document revisions."""
import copy
import json
import shlex
import subprocess
import threading
import time
from pathlib import Path

from guanlan.casepage import default_document, validate_document
from guanlan.session.profile import worker_command
from guanlan.session.store import Store, write_json


class Session:
    def __init__(self, profile, state_root):
        self.profile = profile
        self.store = Store(state_root)
        binding = {'ssh_alias': profile['ssh_alias'], 'case_directory': profile['case_directory']}
        binding_path = self.store.root / 'binding.json'
        if binding_path.exists() and json.loads(binding_path.read_text(encoding='utf-8')) != binding:
            raise ValueError('state directory is bound to another server case; use a separate --state directory')
        write_json(binding_path, binding)
        self.lock = threading.RLock()
        self.changed = threading.Event()
        self.stop = threading.Event()
        self.document_path = self.store.root / 'document.json'
        self.document = default_document(profile['case_id'])
        if self.document_path.exists():
            self.document = validate_document(json.loads(self.document_path.read_text(encoding='utf-8')))
        if self.document['case_id'] != profile['case_id']:
            raise ValueError('state directory belongs to a different case')
        self.revision = 1
        self.preview = None
        cached = self.store.root / 'preview.json'
        if cached.exists():
            self.preview = json.loads(cached.read_text(encoding='utf-8'))
        self.status = 'starting'
        self.message = 'Preparing a separate rendering allocation'
        self.fields = []
        self.job_id = None
        self.process = None
        self.active_revision = None
        self.last_visit = time.monotonic()
        self.last_sent = 0
        self.retry_after = 0
        self.messages = []
        self.threads = []

    def deploy(self):
        p = self.profile
        target = p['remote_workspace']
        subprocess.run(['ssh', '-o', 'BatchMode=yes', p['ssh_alias'], 'mkdir -p ' + shlex.quote(target + '/src')], check=True, timeout=30)
        # A small code-only package, never local configuration or cached data.
        import tarfile
        package = self.store.root / 'worker.tar'
        source = Path(__file__).resolve().parents[1]
        with tarfile.open(package, 'w') as archive:
            archive.add(source / '__init__.py', arcname='guanlan/__init__.py')
            for module in ('worker', 'casepage', 'portable', 'prepared'):
                for path in sorted((source / module).glob('*.py')):
                    archive.add(path, arcname='guanlan/' + module + '/' + path.name)
        subprocess.run(['scp', '-q', str(package), p['ssh_alias'] + ':' + target + '/worker.tar'], check=True, timeout=60)
        subprocess.run(['ssh', '-o', 'BatchMode=yes', p['ssh_alias'],
                        'tar -xf ' + shlex.quote(target + '/worker.tar') + ' -C ' + shlex.quote(target + '/src')], check=True, timeout=30)

    def start(self):
        self.deploy()
        if self.stop.is_set():
            return
        command = worker_command(self.profile)
        self.process = subprocess.Popen(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=20',
                                         '-o', 'ServerAliveCountMax=3', self.profile['ssh_alias'], command],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8', errors='replace', bufsize=1)
        self.threads = [threading.Thread(target=target, daemon=True)
                        for target in (self.read_messages, self.read_errors, self.send_requests)]
        for thread in self.threads:
            thread.start()

    def reconnect(self):
        with self.lock:
            if self.status not in ('idle', 'unavailable') or (self.process and self.process.poll() is None):
                raise ValueError('the worker is active or still ending; wait before reconnecting')
            self.status, self.message = 'starting', 'Reconnecting a bounded rendering allocation'
        for thread in self.threads:
            thread.join(timeout=2)
        self.stop.clear()
        self.fields = []
        self.job_id = None
        self.last_sent = 0
        self.active_revision = None
        self.last_visit = time.monotonic()
        self.start()

    def read_errors(self):
        for line in self.process.stderr:
            with self.lock:
                self.messages = (self.messages + [line.strip()])[-20:]
                write_json(self.store.root / 'worker-diagnostics.json', self.messages)
                if 'queued' in line:
                    self.status, self.message = 'queued', line.strip()
                elif 'has been allocated resources' in line:
                    self.status, self.message = 'loading', 'Allocation ready; loading ParaView and the case catalog'

    def read_messages(self):
        try:
            for line in self.process.stdout:
                if not line.startswith('GUANLAN '):
                    continue
                event = json.loads(line[8:])
                with self.lock:
                    kind = event['event']
                    if kind == 'loading':
                        self.status, self.message = 'loading', event['message']
                    elif kind == 'ready':
                        self.fields, self.job_id = event['fields'], event['job_id']
                        self.status, self.message = 'ready', 'Reader ready; preparing case blocks'
                    elif kind == 'preview':
                        self.active_revision = None
                        # A changed recipe must never be overwritten by a stale render.
                        if event['revision'] == self.revision:
                            result = event['result']
                            if not result.get('cache_hit') or self.preview is None or self.preview.get('revision') != self.revision:
                                self.preview = self.store.commit(dict(result, revision=self.revision))
                            self.status, self.message = 'following', 'Following latest readable output'
                    elif kind == 'unchanged':
                        self.active_revision = None
                        self.status, self.message = 'following', 'Following latest readable output'
                    elif kind == 'error':
                        self.active_revision = None
                        self.status, self.message = 'waiting', event['message']
                        self.retry_after = time.monotonic() + self.profile['refresh_seconds']
                    elif kind == 'idle':
                        self.status, self.message = 'idle', event['message']
                self.changed.set()
        except Exception as error:
            with self.lock:
                self.status, self.message = 'unavailable', str(error)
        finally:
            with self.lock:
                if self.status != 'idle':
                    self.status = 'unavailable'
                    self.message = 'Worker ended. Last-good previews remain available. Restart the case service to reconnect.'
            self.stop.set()

    def send_requests(self):
        while not self.stop.is_set():
            self.changed.wait(1)
            self.changed.clear()
            with self.lock:
                if not self.fields or self.active_revision is not None:
                    continue
                if time.monotonic() < self.retry_after:
                    continue
                if self.last_sent > 0 and time.monotonic() - self.last_visit > 45:
                    continue
                revision_changed = self.preview is not None and self.preview.get('revision') != self.revision
                if not revision_changed and time.monotonic() - self.last_sent < self.profile['refresh_seconds']:
                    continue
                request = {'revision': self.revision, 'document': self.document}
                self.active_revision = self.revision
                self.last_sent = time.monotonic()
                self.status = 'rendering'
                self.message = 'Preparing updated case blocks; last completed images remain available'
                try:
                    self.process.stdin.write(json.dumps(request) + '\n')
                    self.process.stdin.flush()
                except (OSError, ValueError):
                    self.stop.set()

    def state(self, touch=True):
        with self.lock:
            if touch:
                self.last_visit = time.monotonic()
            return copy.deepcopy({'case_id': self.profile['case_id'], 'title': self.profile['title'],
                                  'case_directory': self.profile['case_directory'], 'revision': self.revision,
                                  'document': self.document, 'preview': self.preview, 'fields': self.fields,
                                  'status': self.status, 'message': self.message, 'job_id': self.job_id})

    def edit(self, document, expected_revision):
        with self.lock:
            if expected_revision != self.revision:
                raise ValueError('page changed in another tab; reload before editing')
            document = validate_document(document, self.fields or None)
            if document['case_id'] != self.profile['case_id']:
                raise ValueError('cannot change the connected case')
            if document == self.document:
                return self.state()
            write_json(self.document_path, document)
            self.document = document
            self.revision += 1
            self.retry_after = 0
            self.last_visit = time.monotonic()
            self.changed.set()
        return self.state()

    def close(self):
        self.stop.set()
        if self.process:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
                if self.job_id and str(self.job_id).isdigit():
                    subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                                    self.profile['ssh_alias'], 'scancel ' + str(self.job_id)],
                                   timeout=15, check=False)
