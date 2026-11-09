# -*- coding: utf-8 -*-
"""usage: edge_search.py <pcb> x0 x1 y0 y1: free GND via spots in a box: 0.1 mm from other-net copper on F, In2, B, 0.2 from holes, not on a pad of any net."""
import sys

from shapely.geometry import Point
from shapely.ops import unary_union

import brd

B = brd.load(sys.argv[1])
x0, x1, y0, y1 = map(float, sys.argv[2:6])
obs = unary_union([p for ly in ('F.Cu', 'In2.Cu', 'B.Cu') for n, k, p, l in brd.copper(B, ly, exclude={'GND'})])
gndp = unary_union([brd.pad_poly(q) for q in B['pads'] if q['net'] == 'GND' and q['kind'] != 'thru_hole'])
vs = [(v['x'], v['y']) for v in B['vias']]
out = []
y = y0
while y <= y1:
    x = x0
    while x <= x1:
        c = Point(x, y)
        if c.distance(obs) >= 0.3 and c.distance(gndp) >= 0.2 and all(c.distance(Point(v)) >= 0.55 for v in vs):
            out.append((round(x, 2), round(y, 2), round(c.distance(obs), 3)))
        x += 0.05
    y += 0.05
print(len(out))
last = None
for o in out:
    if last is None or abs(o[1] - last) >= 0.5:
        print(o)
        last = o[1]
