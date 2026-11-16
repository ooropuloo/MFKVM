# -*- coding: utf-8 -*-
"""usage: gerber_check.py <r6 gerber dir> [<r5 gerber dir>]: measured from the plotted files only, no board file and no generator.
Outline from Edge_Cuts, pours and copper from each copper Gerber, holes read straight from the Excellon text. Design coordinates x right, y down: board y = -(Gerber y)."""
import math
import os
import re
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import maskcheck

G = sys.argv[1]
OLD = sys.argv[2] if len(sys.argv) > 2 else None
NAME = 'p4_kvm_mini-'


def objs(d, layer):
    return maskcheck.parse(open(f'{d}/{NAME}{layer}.gbr', encoding='utf-8', errors='replace').read())


def outline(d):
    t = open(f'{d}/{NAME}Edge_Cuts.gbr', encoding='utf-8', errors='replace').read()
    scale = 1e6 if '%FSLAX46Y46*%' in t else 1e5
    pts = [(int(a) / scale, int(b) / scale, c) for a, b, c in re.findall(r'X(-?\d+)Y(-?\d+)D0([12])', t)]
    lines = []
    for p, q in zip(pts, pts[1:]):
        if q[2] == '1':
            lines.append(LineString([p[:2], q[:2]]))
    return list(polygonize(unary_union(lines)))[0]


def drills(path):
    tools, cur, out = {}, None, []
    for ln in open(path, errors='replace'):
        m = re.match(r'T(\d+)C([\d.]+)', ln)
        if m:
            tools[m[1]] = float(m[2])
            continue
        m = re.match(r'T(\d+)\s*$', ln)
        if m:
            cur = m[1]
            continue
        m = re.match(r'X(-?[\d.]+)Y(-?[\d.]+)\s*$', ln)
        if m and cur:
            out.append((float(m[1]), -float(m[2]), tools[cur]))
    return out


edge = outline(G)
print('outline bounds', [round(x, 3) for x in edge.bounds], 'area', round(edge.area, 1))
print('\nPour to edge (zone regions) and any copper to edge, per layer, mm:')
for ly in ('F_Cu', 'In1_Cu', 'In3_Cu', 'In4_Cu', 'B_Cu', 'In2_Cu'):
    o = objs(G, ly)
    reg = [x['geom'] for x in o if x['kind'] == 'region']
    other = [x for x in o if x['kind'] != 'region']
    dz = min((edge.exterior.distance(g) for g in reg), default=None)
    near = sorted(((edge.exterior.distance(x['geom']), x['pad'] or x['func'] or x['kind'], x['net']) for x in other), key=lambda r: r[0])[:4]
    outside = sum(not edge.contains(x['geom']) for x in other)
    print(f"  {ly}: {len(reg)} regions, min pour-to-edge {dz if dz is None else round(dz, 4)}; nearest non-pour {[(round(a, 3), str(b), str(c)) for a, b, c in near]}; non-pour objects crossing the edge {outside}")
    if OLD:
        oo = objs(OLD, ly)
        rr = [x['geom'] for x in oo if x['kind'] == 'region']
        if rr:
            print(f'     r5 min pour-to-edge {min(edge.exterior.distance(g) for g in rr):.4f}; pour area r5 {sum(g.area for g in rr):.1f} r6 {sum(g.area for g in reg):.1f} mm2')

print('\nHoles from the Excellon files:')
pth, npth = drills(f'{G}/{NAME}PTH.drl'), drills(f'{G}/{NAME}NPTH.drl')
print(f'  PTH {len(pth)} NPTH {len(npth)}')
if OLD:
    opth = drills(f'{OLD}/{NAME}PTH.drl')
    oset = {(round(a, 3), round(b, 3), c) for a, b, c in opth}
    nset = {(round(a, 3), round(b, 3), c) for a, b, c in pth}
    add, rem = sorted(nset - oset), sorted(oset - nset)
    print(f'  r5 PTH {len(opth)}; added {len(add)}, removed {len(rem)}')
    print('  added (board mm):', [(a, b, c) for a, b, c in add])
    print('  removed:', rem)
    for a, b, c in rem:
        pass
# hole to hole, hole to edge, for every plated and non-plated round hole
allh = pth + npth
mind = sorted((math.hypot(a[0] - b[0], a[1] - b[1]) - (a[2] + b[2]) / 2, a[:2], b[:2]) for i, a in enumerate(allh) for b in allh[i + 1:])[:3]
print('  closest hole walls:', [(round(x, 3), p, q) for x, p, q in mind])
e2 = sorted((edge.exterior.distance(Point(a[0], -a[1])) - a[2] / 2, a[:2]) for a in allh)[:3]
print('  closest hole wall to edge:', [(round(x, 3), p) for x, p in e2])
