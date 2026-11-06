# -*- coding: utf-8 -*-
"""Fills page.tpl.html with the real STLs and check results, writes v3.html."""
import base64
import datetime
import html
import json
import os
import re

here = os.path.dirname(os.path.abspath(__file__))
def part_images(page):
    """Replaces each <!--PIMG:key--> with its thumbnail, embedded as a data: URI because the host's CSP blocks external images."""
    base = os.path.join(here, 'parts_img')
    man = json.load(open(os.path.join(base, 'manifest.json'), encoding='utf-8'))

    def one(m):
        q = man[m.group(1)]
        raw = open(os.path.join(base, 'thumb', q['file']), 'rb').read()
        mime = 'image/svg+xml' if q['file'].endswith('.svg') else 'image/webp'
        uri = f'data:{mime};base64,{base64.b64encode(raw).decode()}'
        cap = f'<span class="pcap">{html.escape(q["cap"])}</span>' if q.get('cap') else ''
        return (f'<button type="button" class="pthumb" data-kind="{html.escape(q["kind"], quote=True)}" aria-label="放大：{html.escape(q["alt"], quote=True)}">'
                f'<img src="{uri}" alt="{html.escape(q["alt"], quote=True)}" width="{q["w"]}" height="{q["h"]}" loading="lazy"></button>{cap}')

    used = set(re.findall(r'<!--PIMG:(\w+)-->', page))
    assert used == set(man), used ^ set(man)
    return re.sub(r'<!--PIMG:(\w+)-->', one, page)


t = part_images(open(os.path.join(here, 'page.tpl.html'), encoding='utf-8').read())
for k in ('/*__DATA__*/null', '/*__STL__*/null', "'/*__BUILD__*/'"):
    assert t.count(k) == 1, k
chk = json.load(open(os.path.join(here, 'case', 'check.json'), encoding='utf-8'))
assert not chk['fails'], chk['fails']
lay = json.load(open(os.path.join(here, 'layout.json'), encoding='utf-8'))
B = next(r for r in lay['rows'] if r['key'] == 'B')
data = dict(levels=chk['levels'], overall=chk['overall'], volume=chk['volume'], pairs=len(chk['results']), runner=[B['x'], B['y'], B['z']], runner_real=B['vol_real'], atx=chk['atx'])
files = {k: os.path.join(here, 'case', 'stl', f'mf_kvm_{k}.stl') for k in ('tray', 'lid', 'bridge', 'former')}
files.update({k: os.path.join(here, 'case', 'asm', f'{k}.stl') for k in ('core_board', 'core_parts', 'c790', 'lcd', 'atx', 'fpc')})
stl = {k: base64.b64encode(open(v, 'rb').read()).decode() for k, v in files.items()}
build = 'v3-' + datetime.datetime.now().strftime('%Y%m%d-%H%M')
t = t.replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False)).replace('/*__STL__*/null', json.dumps(stl)).replace("'/*__BUILD__*/'", repr(build)).replace('__TOPBUILD__', build).replace('__HHMM__', build[-4:])
open(os.path.join(here, 'v3.html'), 'w', encoding='utf-8', newline='\n').write(t)
print('ok', build, len(t))
