# -*- coding: utf-8 -*-
"""J5 A1B12 on F.Cu vs its twin B1A12: how much zone copper touches each pad, and what else connects them."""
import sys
sys.path.insert(0, sys.argv[1])
import parse
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import unary_union
f, t = parse.load()
zones = []
for c in t:
    if isinstance(c, list) and c and c[0] == 'zone' and parse.get(c, 'layer') and parse.get(c, 'layer')[1] == 'F.Cu':
        for x in c:
            if isinstance(x, list) and x[0] == 'filled_polygon':
                pts = [(float(p[1]), float(p[2])) for p in parse.get(x, 'pts')[1:] if p[0] == 'xy']
                zones.append(Polygon(pts).buffer(0))
Z = unary_union(zones)
print('filled F.Cu GND area mm2', round(Z.area, 2), 'pieces', len(zones))
for n in ('A1B12', 'B1A12', 'A4B9', 'B4A9'):
    q = [p for p in f['J5']['pads'] if p['n'] == n][0]
    r = box(q['x'] - q['w'] / 2, q['y'] - q['h'] / 2, q['x'] + q['w'] / 2, q['y'] + q['h'] / 2)
    ring = r.buffer(0.21, join_style=2).difference(r.buffer(0.0))
    hit = Z.intersection(r.buffer(0.02, join_style=2)).difference(r)
    print(n, q['net'], 'pad', q['w'], 'x', q['h'], 'zone touching perimeter (mm2 in 0.02 ring):', round(hit.area, 4), 'width est mm', round(hit.area / 0.02, 3))
    for g in (hit.geoms if hasattr(hit, 'geoms') else [hit]):
        if g.area > 1e-5:
            print('    spoke at', [round(v, 3) for v in g.bounds])
    for c in t:
        if isinstance(c, list) and c and c[0] == 'segment':
            s, e = parse.get(c, 'start'), parse.get(c, 'end')
            L = LineString([(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))])
            if parse.get(c, 'layer')[1] == 'F.Cu' and L.distance(r) < 0.001:
                print('    track', parse.get(c, 'net')[1], 'w', parse.get(c, 'width')[1], 'len', round(L.length, 3), 'to', s[1:], e[1:])
        if isinstance(c, list) and c and c[0] == 'via':
            a = parse.get(c, 'at')
            if Point(float(a[1]), float(a[2])).distance(r) < 0.6:
                print('    via near', a[1:], parse.get(c, 'net')[1])
