import base64
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import threading
from urllib.request import urlopen
from urllib.error import HTTPError
from test_portable import fixture, encoded
from guanlan.portable import validate_scene, prepared_html
from guanlan.portable.assets import prepare_assets
from guanlan.prepared import select, plan_assets
from guanlan.prepared.store import publish, verify, valid_cached, reserve
from guanlan.prepared.serve import create_server
from guanlan.worker.extract import slice_block

TEST_STATE=Path(__file__).resolve().parents[1]/'state'/'tests'
TEST_STATE.mkdir(parents=True,exist_ok=True)


def scene():
    value=fixture()
    value['datasets']['slice']=copy.deepcopy(value['datasets']['surface'])
    value['datasets']['slice']['fields']['T']=dict(value['datasets']['slice']['fields']['p'],
        values=encoded('d',[300]),range=[300,300],units='K',label='T')
    value['blocks'][2]['dataset']='slice'
    return value


class PreparedTests(unittest.TestCase):
    def test_temperature_only_default(self):
        self.assertEqual(slice_block('xz',['T'],.25)['field'],'T')
    def test_read_only_binary_endpoint(self):
        with tempfile.TemporaryDirectory(dir=TEST_STATE) as temp:
            root=Path(temp);manifest=publish(scene(),root)
            server=create_server(root);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                key=next(iter(manifest['assets']))
                with urlopen(f'http://127.0.0.1:{server.server_port}/assets/{key}.bin.gz') as response:
                    self.assertIsNone(response.headers.get('Content-Encoding'))
                    verify(key,manifest['assets'][key],response.read())
                    self.assertIn('private',response.headers['Cache-Control'])
                with self.assertRaises(HTTPError):urlopen(f'http://127.0.0.1:{server.server_port}/assets/')
            finally:server.shutdown();server.server_close();thread.join()
    def test_slice_only_dependencies(self):
        manifest, assets=prepare_assets(scene())
        chosen,plan=plan_assets(manifest,{'slice':['p']})
        self.assertEqual(set(chosen['datasets']),{'slice'})
        self.assertEqual(set(chosen['datasets']['slice']['fields']),{'p'})
        self.assertNotIn('edges',chosen['datasets']['slice'])
        self.assertEqual(len(plan['required']),3)
        both,_=plan_assets(manifest,{'slice':['p','T']})
        self.assertEqual(len(both['assets']),4)
        reduced=scene();reduced['blocks']=reduced['blocks'][2:]
        reduced['datasets']={'slice':reduced['datasets']['slice']}
        validate_scene(reduced)

    def test_camera_and_next_frame_reuse(self):
        original=scene();manifest,_=prepare_assets(original)
        chosen,first=plan_assets(manifest,{'slice':['p']})
        original['simulation_time']=.2
        original['blocks'][2]['camera']='xz'
        updated,_=prepare_assets(original)
        _,same=plan_assets(updated,{'slice':['p']},first['required'])
        self.assertEqual(same['transfer_bytes'],0)
        original['datasets']['slice']['fields']['p'].update(values=encoded('d',[6e6]),range=[6e6,6e6])
        updated,_=prepare_assets(original)
        _,delta=plan_assets(updated,{'slice':['p']},first['required'])
        self.assertEqual(len(delta['missing']),1)
        self.assertEqual(delta['by_category']['geometry'],0)
        _,temperature=plan_assets(manifest,{'slice':['p','T']},first['required'])
        self.assertEqual(len(temperature['missing']),1)

    def test_binding_and_same_length_tampering(self):
        manifest,assets=prepare_assets(scene())
        broken=copy.deepcopy(manifest)
        broken['datasets']['slice']['fields']['p']['geometry_id']='0'*64
        with self.assertRaisesRegex(ValueError,'binding'):select(broken,{'slice':['p']})
        key=manifest['datasets']['slice']['fields']['p']['asset']
        meta=copy.deepcopy(assets[key]);raw=base64.b64decode(scene()['datasets']['slice']['fields']['p']['values'])
        altered=gzip.compress(bytes([raw[0]^1])+raw[1:])
        meta['compressed_bytes']=len(altered)
        with self.assertRaisesRegex(ValueError,'hash'):verify(key,meta,altered)

    def test_reordered_geometry_cannot_keep_old_field_binding(self):
        original=scene();manifest,_=prepare_assets(original)
        original['datasets']['slice']['points']=encoded('f',[1,0,0,0,0,0,1,1,0,0,1,0])
        updated,_=prepare_assets(original)
        self.assertNotEqual(manifest['datasets']['slice']['geometry_id'],updated['datasets']['slice']['geometry_id'])
        updated['datasets']['slice']['fields']['p']=manifest['datasets']['slice']['fields']['p']
        with self.assertRaisesRegex(ValueError,'binding'):select(updated,{'slice':['p']})

    def test_store_cache_and_quota(self):
        with tempfile.TemporaryDirectory(dir=TEST_STATE) as temp:
            root=Path(temp)
            manifest=publish(scene(),root)
            chosen,plan=plan_assets(manifest,{'slice':['p']},valid_cached(root,manifest))
            self.assertEqual(plan['transfer_bytes'],0)
            before=set((root/'assets').iterdir())
            with self.assertRaises(ValueError):reserve(root,chosen,1)
            self.assertEqual(before,set((root/'assets').iterdir()))
            reserve(root,chosen,plan['retained_bytes'])
            self.assertLessEqual(sum(p.stat().st_size for p in (root/'assets').iterdir()),plan['retained_bytes'])
            with self.assertRaisesRegex(ValueError,'count'):reserve(root,chosen,999999,max_assets=2)
            with self.assertRaises(ValueError):publish(scene(),root,quota=1)

    def test_offline_selected_assets_only(self):
        manifest,assets=prepare_assets(scene())
        chosen=select(manifest,{'slice':['p']})
        page=prepared_html(chosen,{k:assets[k] for k in chosen['assets']},'').decode()
        self.assertEqual(page.count('application/octet-stream'),3)
        self.assertIn("connect-src 'none'",page)
        connected=prepared_html(chosen,{},'test runtime','runtime/'+'a'*64+'.js').decode()
        self.assertNotIn('<script>test runtime</script>',connected)
        self.assertIn('<script src="runtime/',connected)
        self.assertIn("script-src 'self'",connected)


if __name__=='__main__':unittest.main()
