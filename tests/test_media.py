import base64
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from guanlan.media.contract import digest, validate, validate_manifest
from guanlan.media.remote import unpack, write_json
from guanlan.media.package import package

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class MediaTests(unittest.TestCase):
    def preset(self):
        p = json.loads((ROOT/'examples/media-preset.json').read_text(encoding='utf-8'))
        p['blocks'] = [p['blocks'][2]]
        return validate(p)

    def fixture(self, root):
        p = self.preset()
        frames = [{'block': 'xy', 'field': field, 'time': t, 'file': digest(PNG)+'.png',
                   'sha256': digest(PNG), 'bytes': len(PNG), 'range': [0, 1], 'data_range': [0, 1],
                   'units': 'Pa', 'plane': {'origin': [0, 0, 0], 'normal': [0, 0, 1]}}
                  for field in p['blocks'][0]['fields'] for t in p['times']]
        archive = root/'media.zip'
        with zipfile.ZipFile(archive, 'w') as z: z.writestr(digest(PNG)+'.png', PNG)
        return {'preset': p, 'frames': frames, 'bundle': {'bytes': archive.stat().st_size, 'sha256': digest(archive.read_bytes())}}

    def test_slice_only_and_fixed_range(self):
        p = self.preset()
        p['blocks'][0]['range'] = [10, 20]
        self.assertEqual(validate(p)['blocks'][0]['range'], [10, 20])

    def test_invalid_presets(self):
        for mutate in [lambda p: p.update(times=['0.2', '0.1']), lambda p: p.update(times=['nan']),
                       lambda p: p.update(size=[4096, 4096]), lambda p: p['blocks'][0].update(fields=['../p']),
                       lambda p: p['blocks'][0].update(offset=0), lambda p: p['blocks'][0].update(range=[1, 1]),
                       lambda p: p['blocks'][0].update(camera='guess'), lambda p: p.update(source_path='/secret')]:
            p = self.preset(); mutate(p)
            with self.assertRaises(ValueError): validate(p)

    def test_frame_budget(self):
        p = self.preset(); p['times'] = [str(i) for i in range(1, 25)]
        p['blocks'] *= 2
        p['blocks'] = [dict(b, id='block'+str(i), fields=['a','b','c','d','e']) for i, b in enumerate(p['blocks'])]
        with self.assertRaises(ValueError): validate(p)

    def test_complete_frame_set(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            m = self.fixture(Path(d))
            validate_manifest(m)
            m['frames'].pop()
            with self.assertRaises(ValueError): validate_manifest(m)

    def test_archive_integrity_and_safe_html(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            root = Path(d); m = self.fixture(root)
            m['preset']['title'] = '</script><img src=x onerror=alert(1)> __DATA__'
            m['private_source'] = '/private/source/path'
            unpack(m, root/'media.zip', root/'frames')
            write_json(root/'manifest.json', m)
            package(root, root/'snapshot.html')
            text = (root/'snapshot.html').read_text(encoding='utf-8')
            self.assertNotIn('/private/source/path', text)
            self.assertNotIn('<img src=x', text)
            self.assertIn("connect-src 'none'", text)
            self.assertIn('data:image/png;base64,', text)
            with self.assertRaises(ValueError): package(root, root/'snapshot.html')
            (root/'frames'/m['frames'][0]['file']).write_bytes(PNG[:-1]+b'0')
            with self.assertRaises(ValueError): package(root, root/'changed.html')

    def test_reject_bundle_tamper_and_extra_entries(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            root = Path(d); m = self.fixture(root)
            with zipfile.ZipFile(root/'media.zip', 'a') as z: z.writestr('../escape', 'no')
            with self.assertRaises(ValueError): unpack(m, root/'media.zip', root/'frames')
            m['bundle'] = {'bytes': (root/'media.zip').stat().st_size, 'sha256': digest((root/'media.zip').read_bytes())}
            with self.assertRaises(ValueError): unpack(m, root/'media.zip', root/'frames')
            self.assertFalse((root/'frames').exists())

    def test_wrong_field_binding(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            m = self.fixture(Path(d)); m['frames'][0]['field'] = 'unknown'
            with self.assertRaises(ValueError): validate_manifest(m)

    def test_reject_bad_range_and_repeated_asset_metadata(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            m = self.fixture(Path(d)); m['frames'][0]['range'] = [0, float('nan')]
            with self.assertRaises(ValueError): validate_manifest(m)
            m['frames'][0]['range'] = [0, 1]
            m['frames'][0]['bytes'] += 1
            with self.assertRaises(ValueError): validate_manifest(m)

    def test_video_binding_and_integrity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'state/tests') as d:
            root = Path(d); m = self.fixture(root)
            unpack(m, root/'media.zip', root/'frames'); write_json(root/'manifest.json', m)
            videos = root/'videos'; videos.mkdir()
            content = b'synthetic test encoder output'
            entries = []
            for field in ['p', 'T']:
                filename = 'xy-'+field+'.mp4'
                (videos/filename).write_bytes(content)
                entries.append({'block': 'xy', 'field': field, 'file': filename, 'bytes': len(content), 'sha256': digest(content)})
            write_json(videos/'videos.json', {'preset': m['preset'], 'videos': entries})
            result = package(root, root/'video.html', videos)
            self.assertEqual(result['video_bytes'], len(content)*2)
            self.assertIn('data:video/mp4;base64,', (root/'video.html').read_text(encoding='utf-8'))
            (videos/'xy-p.mp4').write_bytes(b'changed')
            with self.assertRaises(ValueError): package(root, root/'bad-video.html', videos)


if __name__ == '__main__': unittest.main()
