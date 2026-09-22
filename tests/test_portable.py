import base64
import copy
import gzip
import json
import re
import struct
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from guanlan.portable import snapshot_html, validate_scene
from guanlan.portable.assets import original_edges, prepare_assets
from guanlan.portable.vtk_export import vtp_bytes
from guanlan.portable.comparison import glance_html
from guanlan.worker.boundaries import parse_boundary


def encoded(fmt, values):
    return base64.b64encode(struct.pack('<' + fmt*len(values), *values)).decode()


def fixture():
    data = {'point_count':4, 'cell_count':1,
            'points':encoded('f',[0,0,0,1,0,0,1,1,0,0,1,0]),
            'polys':encoded('I',[4,0,1,2,3]),
            'fields':{'p':{'values':encoded('d',[5.2e6]), 'range':[5.2e6,5.2e6],
                           'units':'Pa', 'label':'p', 'association':'cell'}}}
    return {'schema_version':1,'title':'Fixture <test>','case_directory':'/example/case',
            'coordinate_units':'m','simulation_time':.1,'datasets':{'surface':data},
            'metrics':{'source':'synthetic test fixture'},
            'blocks':[{'id':'geometry','kind':'geometry','dataset':'surface','camera':'xy'},
                      {'id':'mesh','kind':'mesh','dataset':'surface','camera':'xy'},
                      {'id':'slice','kind':'slice','dataset':'surface','camera':'xy','plane':'xy','field':'p'}]}


class PortableTests(unittest.TestCase):
    def test_boundary_metadata_keeps_patch_type_and_face_count(self):
        result=parse_boundary('wall { type wall; nFaces 4; startFace 10; }\nprocBoundary0to1 { type processor; nFaces 2; startFace 14; }')
        self.assertEqual(result['wall'],{'type':'wall','faces':4})
        self.assertEqual(result['procBoundary0to1']['type'],'processor')
        with self.assertRaises(ValueError):parse_boundary('not a supported patch dictionary')
    def test_glance_wrapper_rejects_unpinned_runtime(self):
        with self.assertRaisesRegex(ValueError,'hash'):
            glance_html(fixture(),b'changed runtime','', '', {})

    def test_template_markers_in_title_are_not_reinterpreted(self):
        scene=fixture();scene['title']='__VIEWER__ </script>'
        page=snapshot_html(scene,'console.log("viewer");').decode()
        self.assertIn('<title>__VIEWER__ &lt;/script&gt;',page)
        self.assertEqual(page.count('console.log("viewer");'),1)

    def test_independent_assets_and_shared_topology(self):
        scene=fixture()
        manifest, assets=prepare_assets(validate_scene(scene))
        dataset=manifest['datasets']['surface']
        self.assertEqual(len(assets),4)
        for name in ('points','polys'):
            self.assertEqual(gzip.decompress(base64.b64decode(assets[dataset[name]]['payload'])),
                             base64.b64decode(scene['datasets']['surface'][name]))
        field=assets[dataset['fields']['p']['asset']]
        self.assertEqual(gzip.decompress(base64.b64decode(field['payload'])),struct.pack('<d',5.2e6))
        self.assertEqual(prepare_assets(scene)[0]['fixture_sha256'],manifest['fixture_sha256'])

    def test_original_edges_have_no_triangulation_diagonals(self):
        raw=original_edges(base64.b64decode(fixture()['datasets']['surface']['polys']))
        edges=list(struct.iter_unpack('<III',raw))
        self.assertEqual(edges,[(2,0,1),(2,0,3),(2,1,2),(2,2,3)])

    def test_vtp_preserves_original_topology_and_field_bytes(self):
        data=fixture()['datasets']['surface']
        root=ET.fromstring(vtp_bytes(data))
        piece=root.find('./PolyData/Piece')
        self.assertEqual(piece.attrib['NumberOfPolys'],'1')
        field=base64.b64decode(piece.find('./CellData/DataArray').text)
        self.assertEqual(field[8:],base64.b64decode(data['fields']['p']['values']))
        edges=ET.fromstring(vtp_bytes(data,edges=True)).find('./PolyData/Piece')
        self.assertEqual(edges.attrib['NumberOfLines'],'4')
        self.assertEqual(edges.attrib['NumberOfPolys'],'0')

    def test_offline_html_has_manifest_and_independent_payloads(self):
        page=snapshot_html(fixture(),'console.log("local viewer");').decode()
        self.assertIn('Fixture &lt;test&gt;',page)
        self.assertNotRegex(page,r'<script[^>]+src=')
        manifest=json.loads(re.search(r'id="manifest" type="application/json">(.*?)</script>',page).group(1))
        self.assertEqual(manifest['schema_version'],2)
        self.assertEqual(page.count('type="application/octet-stream"'),4)
        self.assertIn("connect-src 'none'",page)

    def test_rejects_invalid_topology_fields_and_cameras(self):
        mutations=[lambda d:d['datasets']['surface'].update(polys=encoded('I',[4,0,1,2,9])),
                   lambda d:d['datasets']['surface'].update(cell_count=500001),
                   lambda d:d['datasets']['surface']['fields']['p'].update(values=encoded('d',[float('nan')])),
                   lambda d:d['datasets']['surface']['fields']['p'].update(range=[0,1]),
                   lambda d:d['blocks'][2].update(field='missing'),
                   lambda d:d['blocks'][0].update(camera='unknown')]
        for mutate in mutations:
            scene=copy.deepcopy(fixture());mutate(scene)
            with self.assertRaises(ValueError):validate_scene(scene)


if __name__=='__main__':
    unittest.main()
