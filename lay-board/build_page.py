# -*- coding: utf-8 -*-
"""Fills page.tpl.html from layout.json and writes kvm-mini.html."""
import base64, datetime, html, json, os, re
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
for k in ('/*__LAYOUT__*/null', '/*__BUILD__*/'):
    assert t.count(k) == 1, k
L = json.load(open(os.path.join(here, 'layout.json'), encoding='utf-8'))
# The page draws the routed board. KiCad's frame is left-handed (x right, y down seen from the top side, z toward the viewer).
# The page is the case frame in three.js: x = case x, y up, z = -case y, with the I/O face at +z. Case x = -design x and case y = design y
# (see case/gen_case.py), so a design point lands at page x = -design x, page z = -design y. Bottom-side parts use the same map.
D = json.load(open(os.path.join(here, 'out', 'design.json'), encoding='utf-8'))
B = {x['ref']: x for x in D['parts']}


def page_xy(x, y):
    return -x, -y


def page_box(refs, z0, z1, inset=0.0):
    c = [page_xy(x, y) for r in refs for x, y in ((B[r]['bbox'][0], B[r]['bbox'][1]), (B[r]['bbox'][2], B[r]['bbox'][3]))]
    return [min(p[0] for p in c) + inset, max(p[0] for p in c) - inset, min(p[1] for p in c) + inset, max(p[1] for p in c) - inset, z0, z1]


zb, zt = L['z_bot'], L['z_top']
L['hdmi_cx'] = page_xy(B['J2']['x'], 0)[0]
L['usb_cx'] = page_xy(B['J3']['x'], 0)[0]
L['j5_z'] = page_xy(0, B['J5']['y'])[1]
L['silk'] = page_xy(-8.0, -14.8)  # midway between the two silk lines at design y -16.2 and -13.4, gen_mini.py
ux, uz = page_xy(B['U1']['x'], B['U1']['y'])
L['top'] = {'P4 module': [ux - 12.5, ux + 12.5, uz - 12.5, uz + 12.5, zt, zt + 3.3], 'LCD socket': page_box(['J6'], zt, zt + 4.25)}
L['bottom'] = {'microSD': page_box(['J7'], zb - 1.42, zb), 'ATX 6P': page_box(['J4'], zb - 4.25, zb)}
# envelope inset by the courtyard margin, so the smaller parts read as parts
HEIGHT = {'BGA-64_6x6': 1.2, 'SOT-23-5': 1.45, 'SOT-23': 1.2, 'MSOP-8': 1.1, 'OSC3225': 1.2, 'SSOP-4_1.27': 2.0, 'IND4020': 2.0, 'C0805': 1.4, 'C0603': 1.0, 'R0402': 0.6, 'USON-10': 0.6, 'TP_1.0': 0.1}
KIND = {'IND4020': 'ind', 'SSOP-4_1.27': 'opto', 'C0805': 'cap', 'C0603': 'cap', 'R0402': 'cap', 'TP_1.0': 'tp'}
L['smd'] = []
for r, q in B.items():
    if r in ('U1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7'):
        continue
    ht = HEIGHT[q['lib']]
    bx = page_box([r], zt, zt + ht, 0.2) if q['side'] == 'F' else page_box([r], zb - ht, zb, 0.2)
    L['smd'].append([KIND.get(q['lib'], 'ic')] + bx)
L['lcd'] = {'d': 39.0, 't': 3.6}
t = t.replace('/*__LAYOUT__*/null', json.dumps(L, ensure_ascii=False))
t = t.replace('/*__STL__*/null', json.dumps({k: base64.b64encode(open(os.path.join(here, 'case', 'stl', f'mf_kvm_{k}.stl'), 'rb').read()).decode() for k in ('tray', 'lid')}))
build = 'mini-' + datetime.datetime.now().strftime('%Y%m%d-%H%M')
t = t.replace('/*__BUILD__*/', build).replace('__TOPBUILD__', build).replace('__HHMM__', build[-4:])
open(os.path.join(here, 'kvm-mini.html'), 'w', encoding='utf-8', newline='\n').write(t)
print('ok', build, len(t))
