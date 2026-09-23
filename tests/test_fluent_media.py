import json
from pathlib import Path
import unittest

from guanlan.media.contract import validate
from guanlan.media.fluent import validate_index


ROOT = Path(__file__).resolve().parents[1]


class FluentMediaTests(unittest.TestCase):
    def fixture(self):
        preset = validate(json.loads((ROOT/'examples/media-preset.json').read_text()))
        preset['times'] = ['0.00249', '0.00269']
        preset['blocks'] = [
            {'id': 'temperature', 'kind': 'slice', 'title': 'Temperature',
             'plane': 'xy', 'offset': 0.5, 'fields': ['T'], 'palette': 'Viridis',
             'range': [85, 3500], 'camera': 'xy'}]
        index = {'version': 1, 'format': 'fluent-cff',
                 'frames': [
                     {'time': '0.00249', 'case': 'step-002000.cas.h5', 'data': 'step-002000.dat.h5'},
                     {'time': '0.00269', 'case': 'step-002400.cas.h5', 'data': 'step-002400.dat.h5'}],
                 'fields': {'T': {'array': 'SV_T', 'units': 'K'}}}
        return preset, index

    def test_matching_pairs_and_fields(self):
        preset, index = self.fixture()
        self.assertEqual(validate_index(index, preset), index)

    def test_rejects_wrong_pair_or_field(self):
        preset, index = self.fixture()
        index['frames'][0]['data'] = 'step-002400.dat.h5'
        with self.assertRaises(ValueError): validate_index(index, preset)
        _, index = self.fixture()
        index['fields']['T']['array'] = '../SV_T'
        with self.assertRaises(ValueError): validate_index(index, preset)

    def test_rejects_unsupported_plane_and_private_path(self):
        preset, index = self.fixture()
        preset['blocks'][0]['plane'] = 'xz'
        with self.assertRaises(ValueError): validate_index(index, preset)
        preset, index = self.fixture()
        index['frames'][0]['case'] = '/private/step-002000.cas.h5'
        with self.assertRaises(ValueError): validate_index(index, preset)


if __name__ == '__main__':
    unittest.main()
