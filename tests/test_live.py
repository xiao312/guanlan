import base64
import copy
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from guanlan.casepage import default_document, validate_document
from guanlan.liveweb import create_server
from guanlan.liveweb.snapshot import snapshot_html
from guanlan.session import Session
from guanlan.session.profile import load_profile
from guanlan.session.store import Store
from guanlan.worker.readiness import latest_candidate, unchanged

PROJECT = Path(__file__).resolve().parents[1]
TEMP_ROOT = PROJECT / 'state' / 'tests'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aM1cAAAAASUVORK5CYII=')


class CaseDocumentTests(unittest.TestCase):
    def test_worker_protocol_bypasses_replaced_python_console(self):
        command = ('import io,sys; from guanlan.worker.protocol import emit; '
                   'sys.stdout=io.StringIO(); emit({"event":"preview","revision":7})')
        result = subprocess.run([sys.executable, '-c', command], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout.removeprefix('GUANLAN ')), {'event': 'preview', 'revision': 7})

    def test_rejects_wrong_case_structure_and_fields(self):
        document = default_document('example')
        self.assertEqual(validate_document(document, ['U']), document)
        for mutate in (lambda d: d['blocks'].reverse(),
                       lambda d: d['blocks'][2].update(field='missing'),
                       lambda d: d['blocks'][2].update(offset=float('nan')),
                       lambda d: d['blocks'][2].update(range=[2, 1])):
            candidate = copy.deepcopy(document)
            mutate(candidate)
            with self.assertRaises(ValueError):
                validate_document(candidate, ['U'])

    def test_geometry_and_mesh_cannot_be_removed(self):
        document = default_document('example')
        document['blocks'].pop(0)
        with self.assertRaises(ValueError):
            validate_document(document)


class ReadinessTests(unittest.TestCase):
    def test_incomplete_newest_partition_does_not_hide_complete_output(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            root = Path(directory)
            for partition in ('processor0', 'processor1'):
                for step in ('0.1', '0.2'):
                    target = root / partition / step
                    target.mkdir(parents=True)
                    if not (partition == 'processor1' and step == '0.2'):
                        (target / 'U').write_bytes(b'field data')
                        os.utime(target / 'U', (time.time() - 60, time.time() - 60))
            selected, signature = latest_candidate(root, ['U'], settle_seconds=0)
            self.assertEqual(selected, '0.1')
            with self.assertRaisesRegex(ValueError, 'waiting'):
                latest_candidate(root, ['U'], settle_seconds=0, time_name='0.2')
            self.assertTrue(unchanged(signature))
            (root / 'processor0' / '0.1' / 'U').write_bytes(b'changed data size')
            self.assertFalse(unchanged(signature))

    def test_recent_output_waits(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            target = Path(directory) / 'processor0' / '0.1'
            target.mkdir(parents=True)
            (target / 'U').write_bytes(b'field')
            with self.assertRaisesRegex(ValueError, 'waiting'):
                latest_candidate(directory, ['U'], settle_seconds=10)


class CaseDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        profile = load_profile(PROJECT / 'config' / 'live.example.json')
        self.session = Session(profile, self.temp.name)
        self.session.fields = ['U', 'p', 'T']
        document = self.session.document
        self.session.preview = self.session.store.commit({
            'simulation_time': 0.1, 'document': document, 'revision': 1,
            'blocks': [{'id': b['id'], 'recipe': b, 'bytes': len(PNG),
                        'png': base64.b64encode(PNG).decode()} for b in document['blocks']]})
        self.server = create_server(self.session, '127.0.0.1', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_snapshot_embeds_exact_images_without_live_dependencies(self):
        snapshot = snapshot_html(self.session.state(), self.session.store)
        edited = copy.deepcopy(self.session.document)
        edited['blocks'][2]['field'] = 'p'
        self.session.edit(edited, 1)
        self.assertEqual(snapshot, snapshot_html(self.session.state(), self.session.store))
        self.assertIn(b'data:image/png;base64,', snapshot)
        self.assertNotIn(b'<script', snapshot)

    def test_edit_requires_origin_and_rejects_stale_revision(self):
        edited = copy.deepcopy(self.session.document)
        edited['blocks'][2]['field'] = 'p'
        body = json.dumps({'document': edited, 'revision': 1}).encode()
        request = Request(self.base + '/api/document', data=body, headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)
        request.add_header('Origin', self.base)
        with urlopen(request) as response:
            self.assertEqual(json.load(response)['revision'], 2)
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)

    def test_image_traversal_is_rejected(self):
        with self.assertRaises(HTTPError):
            urlopen(self.base + '/image/../document.png')

    def test_reconnect_cannot_start_duplicate_allocations(self):
        request = Request(self.base + '/api/reconnect', data=b'', headers={'Origin': self.base})
        self.session.status = 'unavailable'
        with patch.object(self.session, 'start') as start:
            with urlopen(request) as response:
                self.assertTrue(json.load(response)['reconnecting'])
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 409)
            start.assert_called_once()

    def test_only_two_image_generations_retained(self):
        for _ in range(3):
            self.session.store.commit({'blocks': [{'id': 'geometry', 'png': base64.b64encode(PNG).decode()}]})
        self.assertEqual(len(list(self.session.store.previews.iterdir())), 2)


if __name__ == '__main__':
    unittest.main()
