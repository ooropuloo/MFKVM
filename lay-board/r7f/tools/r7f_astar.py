# -*- coding: utf-8 -*-
"""r7f: routes one open connection on a generated board with a grid A* over F.Cu, In2.Cu and B.Cu (the three signal layers), and
appends it to data/r7f_hand.json, which tools/r7f_stage.py adds after the Freerouting copper. Used where Freerouting left a connection open.

Obstacles: every other net's track, via and pad on the layer, grown by clearance + half the track width (0.11 + 0.0635); for a via
the copper of every signal layer grown by 0.11 + 0.2, other vias' centres within 0.45 mm (hole to hole), board edge 0.35 mm.
Zones (pours) are not obstacles: they are refilled around the new copper. Start: a pad (ref.pad); goal: any other copper of the
same net. The result is judged by KiCad DRC like everything else; this tool proves nothing by itself.
usage: r7f_astar.py <board.kicad_pcb> <net> <ref.pad> <x0,y0,x1,y1 window, design mm> [note]
"""
import heapq
import json
import math
import os
import re
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

sys.path.insert(0, 'D:/git/p4-kvm-box/analysis_r7f/si/scripts')
import brd

pcb, NET, START = sys.argv[1], sys.argv[2], sys.argv[3]
X0, Y0, X1, Y1 = [float(v) + 100 for v in sys.argv[4].split(',')]
NOTE = sys.argv[5] if len(sys.argv) > 5 else ''
B = brd.load(pcb)
txt = open(pcb, encoding='utf-8').read()
ids = dict(re.findall(r'^\s*\(net (\d+) "([^"]*)"\)', txt, re.M))
name = lambda n: ids.get(n, n) if n else n
LY = ['F.Cu', 'In2.Cu', 'B.Cu']
G, W, CL = 0.05, 0.127, 0.11
nx, ny = int((X1 - X0) / G) + 1, int((Y1 - Y0) / G) + 1
xs = X0 + np.arange(nx) * G
ys = Y0 + np.arange(ny) * G
XX, YY = np.meshgrid(xs, ys)
own, other = {}, {}
for ly in LY:
    o, m = [], []
    for net, kind, poly, lab in brd.copper(B, ly):
        (o if name(net) == NET else m).append(poly)
    own[ly] = unary_union(o) if o else None
    other[ly] = unary_union(m)
win = box(X0, Y0, X1, Y1)


def mask(geom, grow):
    g = geom.buffer(grow).intersection(win.buffer(1))
    return shapely.contains_xy(g, XX, YY) if not g.is_empty else np.zeros_like(XX, bool)


edge = Point(0, 0)
outline = box(80, 80, 120, 125)
edge_bad = ~shapely.contains_xy(outline.buffer(-0.35), XX, YY)
free = {ly: ~(mask(other[ly], CL + W / 2) | edge_bad) for ly in LY}
via_bad = edge_bad.copy()
for ly in LY:
    via_bad |= mask(other[ly], CL + 0.2)
for v in B['vias']:
    if name(v['net']) != NET:
        via_bad |= (XX - v['x']) ** 2 + (YY - v['y']) ** 2 < 0.45 ** 2
for q in B['pads']:
    if q['drill']:
        via_bad |= (XX - q['x']) ** 2 + (YY - q['y']) ** 2 < (0.45 + max(q['w'], q['h']) / 2) ** 2
# no via drill inside any SMD pad, of any net (verify: no via in a pasted pad)
for q in B['pads']:
    if not q['drill']:
        via_bad |= mask(brd.pad_poly(q), 0.12)
# the start pad and the goal copper
if START.startswith('xy:'):   # start at a via already placed (all three layers); its own stub and pad within 0.7 mm are not the goal
    _sx, _sy = [float(v) + 100 for v in START[3:].split(',')]
    sp = dict(x=_sx, y=_sy)
    s_ly = None
    s_poly = Point(_sx, _sy).buffer(0.7)
    start = (XX - _sx) ** 2 + (YY - _sy) ** 2 < 0.03 ** 2
else:
    ref, pn = START.split('.')
    sp = next(q for q in B['pads'] if q['ref'] == ref and q['num'] == pn)
    s_ly = 'F.Cu' if sp['side'] == 'F' else 'B.Cu'
    s_poly = brd.pad_poly(sp)
    start = shapely.contains_xy(s_poly, XX, YY)
goal = {}
for ly in LY:
    g = []
    for net, kind, poly, lab in brd.copper(B, ly, nets=None):
        if name(net) == NET and not (kind == 'pad' and lab == START) and not poly.within(s_poly.buffer(0.05)):
            g.append(poly)
    goal[ly] = shapely.contains_xy(unary_union(g), XX, YY) if g else np.zeros_like(XX, bool)
    if ly == s_ly or s_ly is None:
        goal[ly] &= ~mask(s_poly, 0.3 if s_ly else 0.0)
# own pads are fine to cross only at the start and goal; never cross a pad of the net elsewhere (would short nothing, but keep it clean)
VIA_COST = 3.0
dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
L = {ly: i for i, ly in enumerate(LY)}
openq = []
best = {}
for _ly in ([s_ly] if s_ly else LY):
    iy, ix = np.nonzero(start & free[_ly])
    for a, b in zip(iy, ix):
        heapq.heappush(openq, (0.0, 0.0, (L[_ly], a, b), None))
came = {}
found = None
while openq:
    f, g, node, prev = heapq.heappop(openq)
    if node in came:
        continue
    came[node] = prev
    li, a, b = node
    if goal[LY[li]][a, b] and g > 0.2:
        found = node
        break
    for da, db in dirs:
        a2, b2 = a + da, b + db
        if 0 <= a2 < ny and 0 <= b2 < nx and free[LY[li]][a2, b2] and (li, a2, b2) not in came:
            c = g + G * math.hypot(da, db)
            heapq.heappush(openq, (c, c, (li, a2, b2), node))
    if not via_bad[a, b]:
        for l2 in range(3):
            if l2 != li and free[LY[l2]][a, b] and (l2, a, b) not in came:
                heapq.heappush(openq, (g + VIA_COST, g + VIA_COST, (l2, a, b), node))
if not found and os.environ.get('ASTAR_DBG'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 4, figsize=(24, 8))
    reach = np.zeros((3, ny, nx), bool)
    for (li, a_, b_) in came:
        reach[li, a_, b_] = True
    for ax, (t, m) in zip(axs, [('F free', free['F.Cu']), ('In2 free', free['In2.Cu']), ('B free', free['B.Cu']), ('via ok', ~via_bad)]):
        img = np.dstack([m * 0.8, m * 0.8, m * 0.8])
        img[..., 0] = np.maximum(img[..., 0], reach.any(0))
        ax.imshow(img, origin='upper', extent=(X0 - 100, X1 - 100, Y1 - 100, Y0 - 100))
        ax.set_title(t)
    fig.savefig(os.environ['ASTAR_DBG'], dpi=90)
assert found, f'no path for {NET} from {START}'
path = []
n = found
while n is not None:
    path.append(n)
    n = came[n]
path = path[::-1]
# compress into straight runs per layer, vias where the layer changes
segs, vias, run = [], [], [path[0]]
pt = lambda n_: (round(X0 + n_[2] * G - 100, 4), round(Y0 + n_[1] * G - 100, 4))
for p_, q_ in zip(path, path[1:]):
    if q_[0] != p_[0]:
        if len(run) > 1:
            segs.append((LY[run[0][0]], pt(run[0]), pt(run[-1])))
        vias.append(pt(q_))
        run = [q_]
        continue
    if len(run) >= 2:
        d1 = (run[-1][1] - run[-2][1], run[-1][2] - run[-2][2])
        d2 = (q_[1] - p_[1], q_[2] - p_[2])
        if d1 != d2:
            segs.append((LY[run[0][0]], pt(run[0]), pt(run[-1])))
            run = [run[-1]]
    run.append(q_)
if len(run) > 1:
    segs.append((LY[run[0][0]], pt(run[0]), pt(run[-1])))
# the first point is inside the start pad; pull it to the pad centre so the track lands on the pad
segs[0] = (segs[0][0], (round(sp['x'] - 100, 4), round(sp['y'] - 100, 4)) if (segs[0][0] == s_ly or s_ly is None) else segs[0][1], segs[0][2])
length = sum(math.dist(a, b) for _, a, b in segs)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'r7f_hand.json')
cur = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else []
cur = [h for h in cur if not (h['net'] == NET and h['note'] == (NOTE or f'from {START}'))]
cur.append(dict(net=NET, w=W, segs=[[l, list(a), list(b)] for l, a, b in segs], vias=[list(v) for v in vias], len=length, note=NOTE or f'from {START}'))
json.dump(cur, open(out, 'w', encoding='utf-8'), indent=1)
print(f'{NET}: {len(segs)} segments, {len(vias)} vias, {length:.2f} mm', segs, vias)
