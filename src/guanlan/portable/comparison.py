"""Build same-fixture offline candidates and VTP files; never connects to a cluster."""
import argparse
import base64
import gzip
import hashlib
import html
import json
from pathlib import Path
import re

from guanlan.portable import MAX_SCENE_BYTES, snapshot_html, validate_scene
from guanlan.portable.assets import prepare_assets
from guanlan.portable.vtk_export import vtp_bytes

GLANCE_SHA256 = '66e227b9ba025d138c9101941b71f8f00b519dcc224a4c77e017b45154ef065b'


def glance_html(scene, vendor, controls, license_text, vtp_files, prepared=None):
    if hashlib.sha256(vendor).hexdigest() != GLANCE_SHA256:
        raise ValueError('Glance bundle differs from qualified source hash; review/update pin explicitly')
    manifest, _ = prepared or prepare_assets(scene)
    manifest = dict(manifest)
    manifest['viewer_sha256'] = GLANCE_SHA256
    manifest['wrapper_sha256'] = hashlib.sha256(controls.encode()).hexdigest()
    manifest['vtp_files'] = [{'name': name, 'bytes': len(data)} for name, data in vtp_files.items()]
    raw = vendor.decode('utf-8')
    # These optional plugins are not used for VTP; no remote scripts may remain.
    raw = re.sub(r'<script\s+src="glance-external-(?:ITKReader|Workbox)\.[^"]+"\s*></script>', '', raw)
    if re.search(r'<script[^>]+src=', raw, re.I):
        raise ValueError('unexpected external Glance script; cannot promise a local-only candidate')
    bootstrap = re.compile(r"const container = document.querySelector\('#root-container'\);\s*const glanceInstance = Glance.createViewer\(container\);\s*glanceInstance.processURLArgs\(\);")
    if len(bootstrap.findall(raw)) != 1:
        raise ValueError('Glance bootstrap changed; inspect it before packaging')
    raw = bootstrap.sub('', raw)
    csp = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
           'script-src \'unsafe-inline\' \'unsafe-eval\'; style-src \'unsafe-inline\'; '
           'img-src data: blob:; font-src data:; connect-src \'none\'; worker-src blob:">')
    raw = raw.replace('<head>', '<head>' + csp, 1)
    fields = ''.join('<option>' + html.escape(name) + '</option>' for name in scene['datasets']['xy']['fields'])
    bar = ('<div id="comparison-bar" style="position:fixed;z-index:99999;left:0;right:0;top:0;background:#f4f3ef;color:#26343e;padding:8px;font:12px system-ui">'
           '<b>Guanlan · Glance comparison</b> <select disabled id="comparison-mode"><option value="geometry">Geometry</option>'
           '<option value="mesh">Original mesh edges</option><option value="slice">XY scalar slice</option></select> '
           '<select disabled id="comparison-field">' + fields + '</select> <button disabled id="comparison-reset">Reset XY</button> '
           '<button id="measure">Start measurement</button> <button id="report">Download measurements</button> '
           '<span id="measurement-state">Not measuring</span><div id="comparison-status">Loading frozen fixture…</div></div>'
           '<div id="blocks" class="glance-single-view"></div><style>body{padding-top:65px!important}#root-container{height:calc(100vh - 65px)}</style>')
    embedded = '<script id="manifest" type="application/json">' + json.dumps(manifest).replace('<', '\\u003c') + '</script>'
    for name, data in vtp_files.items():
        encoded = base64.b64encode(gzip.compress(data, mtime=0)).decode()
        embedded += '<script type="application/octet-stream" id="vtp-' + name + '">' + encoded + '</script>'
    embedded += '<script>' + controls.replace('</script', '<\\/script') + '</script>'
    embedded += '<!-- Glance license\n' + license_text.replace('--', '—') + '\n-->'
    raw = raw.replace('<body>', '<body>' + bar, 1).replace('</body>', embedded + '</body>', 1)
    return raw.encode('utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--glance',type=Path,required=True)
    parser.add_argument('--glance-license',type=Path,required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.scene.stat().st_size > MAX_SCENE_BYTES:parser.error('scene exceeds budget')
    scene=validate_scene(json.loads(args.scene.read_text(encoding='utf-8')))
    if set(scene['datasets']) != {'surface','xy'}:parser.error('comparison requires the surface + XY baseline')
    physical = scene.get('metrics', {}).get('physical_patch_faces', {})
    if (not physical or any(type(count) is not int or count < 0 for count in physical.values())
            or sum(physical.values()) != scene['datasets']['surface']['cell_count']):
        parser.error('comparison requires a physical-boundary fixture with matching face counts; merge-first diagnostic scenes are not accepted')
    project=Path(__file__).resolve().parents[3]
    bundle=(project/'state/portable/viewer.js').read_text(encoding='utf-8')
    controls=(project/'state/portable/glance-controls.js').read_text(encoding='utf-8')
    files={name:vtp_bytes(data) for name,data in scene['datasets'].items()}
    files['surface-edges']=vtp_bytes(scene['datasets']['surface'],edges=True)
    manifest,assets=prepare_assets(scene)
    guanlan=snapshot_html(scene,bundle,(manifest,assets))
    glance=glance_html(scene,args.glance.read_bytes(),controls,args.glance_license.read_text(),files,(manifest,assets))
    outputs={**{name+'.vtp':data for name,data in files.items()},'guanlan.html':guanlan,'glance.html':glance,
             'manifest.json':json.dumps(manifest,indent=2).encode(),
             'Glance-LICENSE.txt':args.glance_license.read_bytes()}
    for key,item in assets.items():outputs['assets/'+key+'.gz']=base64.b64decode(item['payload'])
    record={'fixture_sha256':manifest['fixture_sha256'],'simulation_time':scene['simulation_time'],
            'preparation':scene['metrics'],'datasets':{k:{p:d[p] for p in ('point_count','cell_count')} for k,d in scene['datasets'].items()},
            'artifacts':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in outputs.items()},
            'browser_performance':None,'gpu_memory':None,'visual_verification':'NOT_MEASURED',
            'notes':['Generated candidates, not browser-qualified results.','Glance single-view and Guanlan multi-block are separate workloads.']}
    outputs['qualification.json']=json.dumps(record,indent=2).encode()
    if not args.check:
        for name,data in outputs.items():
            target=args.output_dir/name;target.parent.mkdir(parents=True,exist_ok=True)
            pending=target.with_suffix(target.suffix+'.pending');pending.write_bytes(data);pending.replace(target)
    print(json.dumps({'check_only':args.check,'output':str(args.output_dir),'fixture':record['fixture_sha256'],
                      'html_bytes':{'guanlan':len(guanlan),'glance':len(glance)}}))


if __name__=='__main__':main()
