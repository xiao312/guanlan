"""Triangle identity, not raw cell order, controls cross-version comparison."""
import importlib.util
from pathlib import Path
import runpy
import tempfile
import unittest
from test_portable import encoded
from guanlan.prepared.store import publish

ROOT = Path(__file__).resolve().parents[1]
TEST_STATE = ROOT/'state/tests'
TEST_STATE.mkdir(parents=True, exist_ok=True)


def fixture(reverse=False, wrong_field=False):
    values = [20,10] if reverse else [10,20]
    if wrong_field:
        values.reverse()
    return {'schema_version':1, 'title':'Synthetic triangles', 'case_directory':'synthetic',
        'simulation_time':1, 'coordinate_units':'m', 'metrics':{},
        'blocks':[{'id':'xy','kind':'slice','dataset':'xy','camera':'xy','field':'p','plane':'xy','offset':0.5}],
        'datasets':{'xy':{'point_count':4,'cell_count':2,
            'points':encoded('f',[0,0,0,1,0,0,1,1,0,0,1,0]),
            'polys':encoded('I',[3,0,2,3,3,0,1,2] if reverse else [3,0,1,2,3,0,2,3]),
            'fields':{'p':{'values':encoded('d',values),'range':[10,20],
                           'association':'cell','units':'Pa','label':'p'}}}}}


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Optional numerical comparison requires NumPy')
class SliceCompareTests(unittest.TestCase):
    def test_reordered_triangles_and_wrong_fields(self):
        compare = runpy.run_path(str(ROOT/'infrastructure/paraview/compare-slices.py'))['compare']
        with tempfile.TemporaryDirectory(dir=TEST_STATE) as temporary:
            cache = Path(temporary)
            old = publish(fixture(), cache)
            new = publish(fixture(reverse=True), cache)
            self.assertTrue(compare(old,new,cache)['xy']['fields']['p']['exact_by_triangle'])
            wrong = publish(fixture(reverse=True,wrong_field=True), cache)
            self.assertFalse(compare(old,wrong,cache)['xy']['fields']['p']['exact_by_triangle'])
