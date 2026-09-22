"""Portable, frozen case page with embedded image bytes and exact recipes."""
import base64
import html
import json


def snapshot_html(state, store):
    preview = state['preview']
    if preview is None:
        raise ValueError('no completed preview is available yet')
    esc = html.escape
    cards = []
    for item in preview['blocks']:
        recipe = item['recipe']
        image = base64.b64encode(store.image(preview['generation'], item['id'])).decode()
        caption = recipe['kind'] + (' · ' + recipe['field'] + ' · ' + recipe['plane'] if recipe['field'] else '')
        cards.append('<section><h2>' + esc(caption) + '</h2><img alt="' + esc(caption, quote=True) +
                     '" src="data:image/png;base64,' + image + '"></section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>' + esc(state['title']) + ' · snapshot</title><style>'
            'body{font:14px system-ui;color:#26313e;background:#f5f5f4;margin:32px auto;max-width:1100px;padding:20px}'
            'section{background:white;border:1px solid #ddd;border-radius:8px;margin:18px 0;overflow:hidden}'
            'h2{font-size:15px;padding:12px 18px}img{width:100%}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '</style><h1>' + esc(state['title']) + '</h1><p>Frozen snapshot · t = ' + str(preview['simulation_time']) +
            ' s · OpenFOAM · no live connection</p><code>' + esc(state['case_directory']) + '</code>' + ''.join(cards) +
            '<details><summary>Saved block settings</summary><pre>' + esc(json.dumps(preview['document'], indent=2)) +
            '</pre></details></html>').encode('utf-8')
