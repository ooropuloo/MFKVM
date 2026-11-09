# -*- coding: utf-8 -*-
"""usage: widen.py <pcb> <net> <target mm> <out.json> [--min-clear 0.1]: for each routed segment of a net, the width it can take with the given clearance to
every other-net track, via and pad on its layer. Same-layer pours are ignored, they refill around it. Writes rows for ses_patch_r6.py's widen list, in design mm."""
import json
import sys

import brd
from shapely.geometry import LineString

pcb, net, target, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
clear = float(sys.argv[sys.argv.index('--min-clear') + 1]) if '--min-clear' in sys.argv else 0.1
B = brd.load(pcb)
rows = []
tot = {}
for s in [s for s in B['segs'] if s['net'] == net]:
    line = LineString([s['a'], s['b']])
    L = line.length
    if L < 1e-6:
        continue
    dmin, who = 9, ''
    for n, kind, poly, lab in brd.copper(B, s['layer'], exclude={net}):
        d = line.distance(poly)
        if d < dmin:
            dmin, who = d, f'{n} {kind} {lab}'
    w = min(target, 2 * (dmin - clear))
    w = max(round(w - 0.0005, 3), s['w'])
    w = s['w'] if w < s['w'] + 0.005 else w
    a = (round(s['a'][0] - 100, 4), round(s['a'][1] - 100, 4))
    b = (round(s['b'][0] - 100, 4), round(s['b'][1] - 100, 4))
    if w > s['w']:
        rows.append([s['layer'], a, b, w])
    tot.setdefault((s['layer'], s['w'], w), 0)
    tot[(s['layer'], s['w'], w)] += L
    print(f"{s['layer']:7s} L {L:6.2f} w {s['w']:.3f} -> {w:.3f}  nearest {dmin:.3f} {who[:60]}  ({a[0]},{a[1]})-({b[0]},{b[1]})")
print('length by layer, old width, new width:', {k: round(v, 2) for k, v in tot.items()})
json.dump({net: rows}, open(out, 'w', encoding='utf-8'))
