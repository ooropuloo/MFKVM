# -*- coding: utf-8 -*-
"""Reads the vendor footprint behind an LCSC number from EasyEDA's public parts API and saves its pads. Data only."""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = sys.argv[1]
res = {}
for code in sys.argv[2:]:
    try:
        req = urllib.request.Request(f'https://easyeda.com/api/products/{code}/components?version=6.4.19.5', headers={'User-Agent': 'easyeda2kicad v0.8.0', 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        print(code, 'ERR', e)
        continue
    r = d.get('result') or {}
    pkg = r.get('packageDetail') or {}
    data = pkg.get('dataStr') or {}
    head = data.get('head') or {}
    ox, oy = float(head.get('x', 0)), float(head.get('y', 0))
    pads = []
    box = [1e9, 1e9, -1e9, -1e9]
    for sh in data.get('shape', []):
        f = sh.split('~')
        if f[0] != 'PAD':
            continue
        # PAD~shape~x~y~w~h~layer~net~number~holeR~points~rot~id~holeLen
        x, y = (float(f[2]) - ox) * 0.254, (float(f[3]) - oy) * 0.254
        w, h = float(f[4]) * 0.254, float(f[5]) * 0.254
        rot = float(f[11] or 0) if len(f) > 11 else 0
        pads.append(dict(n=f[8], shape=f[1], x=round(x, 3), y=round(y, 3), w=round(w, 3), h=round(h, 3), layer=f[6], hole_d=round(float(f[9] or 0) * 2 * 0.254, 3), rot=rot, hole_len=round(float(f[13] or 0) * 0.254, 3) if len(f) > 13 and f[13] else 0))
    lc = r.get('lcsc') or {}
    res[code] = dict(title=r.get('title'), pkg=pkg.get('title'), pads=pads)
    print(code, r.get('title'), '|', pkg.get('title'), '| pads', len(pads))
json.dump(res, open(OUT, 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
