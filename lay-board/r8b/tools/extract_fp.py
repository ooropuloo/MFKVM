# -*- coding: utf-8 -*-
"""Pulls pad geometry for named references out of a .kicad_pcb, so reused footprints stay exact."""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
PAD = re.compile(r'\(pad\s+"([^"]*)"\s+(\w+)\s+(\w+)\s+(?:locked\s+)?\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)\s+(?:locked\s+)?\(size\s+([-\d.]+)\s+([-\d.]+)\)(?:\s+\(drill\s+(oval\s+)?([-\d.]+)(?:\s+([-\d.]+))?\))?', re.S)
REF = re.compile(r'(?:\(property\s+"Reference"\s+|\(fp_text\s+reference\s+)"([^"]+)"')


def blocks(s):
    starts = [m.start() for m in re.finditer(r'\n\s*\(footprint\s+"', s)] + [len(s)]
    out = {}
    for a, b in zip(starts, starts[1:]):
        t = s[a:b]
        r = REF.search(t)
        if r:
            out[r.group(1)] = t
    return out


def pads(t):
    at = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)', t)
    rot = float(at.group(3) or 0)
    layer = re.search(r'\(layer\s+"([^"]+)"\)', t).group(1)
    lib = re.search(r'\(footprint\s+"([^"]+)"', t).group(1)
    res = []
    for m in PAD.finditer(t):
        n, k, sh, x, y, a, w, h, ov, d1, d2 = m.groups()
        res.append(dict(n=n, kind=k, shape=sh, x=float(x), y=float(y), a=float(a or 0) - rot, w=float(w), h=float(h), oval=bool(ov), d1=float(d1 or 0), d2=float(d2 or 0)))
    return dict(lib=lib, rot=rot, layer=layer, pads=res)


src, out, want = sys.argv[1], sys.argv[2], sys.argv[3:]
b = blocks(open(src, encoding='utf-8').read())
res = {w: pads(b[w]) for w in want}
for w, v in res.items():
    print(w, v['lib'], 'rot', v['rot'], v['layer'], 'pads', len(v['pads']))
json.dump(res, open(out, 'w', encoding='utf-8'), indent=0)
