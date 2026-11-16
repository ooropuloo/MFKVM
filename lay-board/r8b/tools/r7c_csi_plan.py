# -*- coding: utf-8 -*-
"""r7c CSI re-plan: check a proposed routing of all three CSI pairs (data/r7c_csi.json) against the routed board, before it is built.

The proposal replaces every CSI segment and via on the board. Checked, against every other object on F.Cu and B.Cu of the current
board (tracks, vias, all pads including BGA balls and module pads; inner layers only see the new vias):
  clearance 0.1 mm to other nets; 2W = 0.254 mm edge to edge between different CSI pairs (Espressif p28);
  3W = 0.381 mm between non-adjacent segments of the same line (meander legs);
  via: hole to hole >= 0.2 mm, pad to pad >= 0.1 mm, holes not in a pad;
  corners: every bend 45 degrees or less (no right angles);
  length = sum of segments per net; within a pair <= 0.15 mm; across pairs <= 0.762 mm (Espressif 30 mil).
usage: r7c_csi_plan.py <out_dir> <plan.json> [png]
"""
import json
import math
import re
import sys

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

sys.stdout.reconfigure(encoding='utf-8')
OUT, PLAN = sys.argv[1], sys.argv[2]
PNG = sys.argv[3] if len(sys.argv) > 3 else None
W, CLR, PAIRSEP, SELF = 0.127, 0.1, 0.254, 0.381
VIA_D, VIA_H = 0.4, 0.2
s = open(f'{OUT}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()
CSI = {'CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N'}
segs = [(LineString([(float(m[1]) - 100, float(m[2]) - 100), (float(m[3]) - 100, float(m[4]) - 100)]), float(m[5]), m[6], m[7])
        for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', s)]
vias = [(Point(float(m[1]) - 100, float(m[2]) - 100), float(m[3]), re.search(r'\(net "([^"]+)"\)', s[m.end():m.end() + 600])[1])
        for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)', s)]
pads = []   # (shape, net, layers)
for fm in re.finditer(r'\(footprint "mini:[^"]*"(.*?)(?=\n\t\(footprint |\n\t\((?:segment|via|zone|gr_))', s, re.S):
    b = fm[1]
    side = 'F' if '(layer "F.Cu")' in b[:200] else 'B'
    tr = re.search(r'\(translate ([-\d.]+) ([-\d.]+)\)', b)
    rot = re.search(r'\(rotate ([-\d.]+)\)', b)
    ox, oy = float(tr[1]) - 100, float(tr[2]) - 100
    a = math.radians(float(rot[1]) if rot else 0.0)
    for q in re.finditer(r'\(pad "([^"]*)" (smd|thru_hole) (\w+)\s+\(at ([-\d.]+) ([-\d.]+)(?: [-\d.]+)?\)\s+\(size ([\d.]+) ([\d.]+)\)(.*?)\(net "([^"]*)"\)', b, re.S):
        x, y, w, h = float(q[4]), float(q[5]), float(q[6]), float(q[7])
        wx, wy = ox + x * math.cos(a) + y * math.sin(a), oy - x * math.sin(a) + y * math.cos(a)
        if abs(math.sin(a)) > 0.5:
            w, h = h, w
        shp = Point(wx, wy).buffer(w / 2) if q[3] == 'circle' else box(wx - w / 2, wy - h / 2, wx + w / 2, wy + h / 2)
        pads.append((shp, q[9], {'F', 'B'} if q[2] == 'thru_hole' else {side}))

plan = json.load(open(PLAN, encoding='utf-8'))
# inside the BGA breakout the ball pitch (0.65) leaves no room for 2W between pairs; the Espressif pair spacing is applied outside it
EXEMPT = box(*plan['exempt_box']) if 'exempt_box' in plan else None
inside = lambda g: EXEMPT is not None and EXEMPT.contains(g)
new = []    # (LineString, net, layer)
for net, items in plan['tracks'].items():
    for ly, pts in items:
        for a, b in zip(pts, pts[1:]):
            new.append((LineString([a, b]), net, ly))
newv = [(Point(x, y), net) for net, x, y in plan['vias']]

problems = []
# 1. clearance to other nets
for g, net, ly in new:
    L = ly[0]
    for o, w, oly, on in segs:
        if oly == ly and on not in CSI and on != net:
            d = g.distance(o) - W / 2 - w / 2
            if d < CLR - 1e-6:
                problems.append(f'{net} {ly} {list(g.coords)} to track {on}: {d:.3f}')
    for p, d_, on in vias:
        if on not in CSI and on != net:
            d = g.distance(p) - W / 2 - d_ / 2
            if d < CLR - 1e-6:
                problems.append(f'{net} {ly} {list(g.coords)} to via {on} ({p.x:.3f},{p.y:.3f}): {d:.3f}')
    for shp, on, lys in pads:
        if L in lys and on != net:
            d = g.distance(shp) - W / 2
            if d < CLR - 1e-6:
                problems.append(f'{net} {ly} {list(g.coords)} to pad {on} {[round(v, 2) for v in shp.bounds]}: {d:.3f}')
for p, net in newv:
    for o, w, oly, on in segs:
        if on not in CSI and on != net and oly in ('F.Cu', 'B.Cu', 'In2.Cu'):
            d = p.distance(o) - VIA_D / 2 - w / 2
            if d < CLR - 1e-6:
                problems.append(f'via {net} ({p.x},{p.y}) to {oly} track {on}: {d:.3f}')
    for q, d_, on in vias:
        if on in CSI:
            continue
        d = p.distance(q)
        if d - VIA_H < 0.2 - 1e-6 or (on != net and d - VIA_D / 2 - d_ / 2 < CLR - 1e-6):
            problems.append(f'via {net} ({p.x},{p.y}) to via {on} ({q.x:.3f},{q.y:.3f}): centres {d:.3f}')
    for shp, on, lys in pads:
        if on != net and p.distance(shp) - VIA_D / 2 < CLR - 1e-6:
            problems.append(f'via {net} ({p.x},{p.y}) to pad {on} {[round(v, 2) for v in shp.bounds]}: {p.distance(shp) - VIA_D / 2:.3f}')
        if shp.contains(p):
            problems.append(f'via {net} ({p.x},{p.y}) inside pad {on}')
# new vias among themselves and new tracks of other nets
for i, (p, n1) in enumerate(newv):
    for q, n2 in newv[i + 1:]:
        if p.distance(q) - VIA_H < 0.2 - 1e-6 or p.distance(q) - VIA_D < CLR - 1e-6:
            problems.append(f'vias {n1} {n2} too close: {p.distance(q):.3f}')
    for g, net, ly in new:
        if net != n1 and g.distance(p) - VIA_D / 2 - W / 2 < CLR - 1e-6:
            problems.append(f'via {n1} ({p.x},{p.y}) to new {net} {ly}: {g.distance(p) - VIA_D / 2 - W / 2:.3f}')
# 2. between new tracks
for i, (g1, n1, l1) in enumerate(new):
    for g2, n2, l2 in new[i + 1:]:
        if l1 != l2 or n1 == n2:
            continue
        need = CLR if n1[:6] == n2[:6] or inside(g1) or inside(g2) else PAIRSEP
        d = g1.distance(g2) - W
        if d < need - 1e-6:
            problems.append(f'{n1} vs {n2} on {l1}: {d:.3f} < {need}')
# 3. self spacing (non-adjacent segments of one line on one layer)
for net, items in plan['tracks'].items():
    for ly, pts in items:
        sg = [LineString([a, b]) for a, b in zip(pts, pts[1:])]
        for i in range(len(sg)):
            for j in range(i + 2, len(sg)):
                d = sg[i].distance(sg[j]) - W
                # 3W self spacing between long parallel runs (meander legs); short chamfers and teeth only need the normal clearance
                ua = (sg[i].coords[1][0] - sg[i].coords[0][0], sg[i].coords[1][1] - sg[i].coords[0][1])
                ub = (sg[j].coords[1][0] - sg[j].coords[0][0], sg[j].coords[1][1] - sg[j].coords[0][1])
                par = sg[i].length > 0.3 and sg[j].length > 0.3 and abs(ua[0] * ub[1] - ua[1] * ub[0]) < 0.17 * sg[i].length * sg[j].length
                need = (plan.get('self_sep', {}).get(net, SELF)) if par else CLR   # per-net exception, stated in the plan
                if d < need - 1e-6 and not (j == i + 2 and sg[i + 1].length < 0.6):
                    problems.append(f'{net} {ly} own segments {i},{j}: {d:.3f} < {need}')
        # 4. corners
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            u = (b[0] - a[0], b[1] - a[1])
            v = (c[0] - b[0], c[1] - b[1])
            nu, nv = math.hypot(*u), math.hypot(*v)
            ang = math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / (nu * nv))))) if nu and nv else 0
            if ang > 45.5:
                problems.append(f'{net} {ly} bend {ang:.0f} deg at {b}')
# 5. lengths
L = {n: sum(g.length for g, nn, ly in new if nn == n) for n in CSI}
for n in sorted(L):
    print(f'  {n}: {L[n]:.3f} mm')
pairs = {p: (L[f'CSI_{p}_P'], L[f'CSI_{p}_N']) for p in ('D0', 'D1', 'CK')}
for p, (a, b) in pairs.items():
    print(f'{p}: P-N {a - b:+.3f} mm', '' if abs(a - b) <= 0.15 else ' OVER 0.15')
    if abs(a - b) > 0.15:
        problems.append(f'{p} intra {a - b:+.3f}')
mean = {p: (a + b) / 2 for p, (a, b) in pairs.items()}
spread = max(mean.values()) - min(mean.values())
print('pair means', {p: round(m, 3) for p, m in mean.items()}, f'spread {spread:.3f} mm (limit 0.762)')
if spread > 0.762:
    problems.append(f'inter-pair spread {spread:.3f}')
print(f'{len(problems)} problems')
for x in problems[:40]:
    print('  ', x)
if PNG:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(16, 8))
    for ax, ly in zip(axs, ('F.Cu', 'B.Cu')):
        for o, w, oly, on in segs:
            if oly == ly and on not in CSI:
                x, y = o.buffer(w / 2).exterior.xy
                ax.fill(x, y, color='lightgray')
        for p, d_, on in vias:
            if on not in CSI:
                ax.add_patch(plt.Circle((p.x, p.y), d_ / 2, color='gray'))
        for shp, on, lys in pads:
            if ly[0] in lys and shp.intersects(box(5.5, -7.8, 11.5, -1.5)):
                x, y = shp.exterior.xy
                ax.fill(x, y, color='khaki', ec='olive', lw=0.3)
        col = {'D0': 'red', 'D1': 'green', 'CK': 'blue'}
        for g, net, l in new:
            if l == ly:
                x, y = g.xy
                ax.plot(x, y, color=col[net[4:6]], lw=1.6, alpha=0.8, ls='-' if net.endswith('P') else '--')
        for p, net in newv:
            ax.add_patch(plt.Circle((p.x, p.y), VIA_D / 2, color=col[net[4:6]], fill=False, lw=1.2))
        ax.set_xlim(5.8, 11.5)
        ax.set_ylim(-1.5, -7.6)
        ax.set_aspect('equal')
        ax.grid(lw=0.2)
        ax.set_title(f'{ly}: red D0, green D1, blue CK (solid P, dashed N)')
    plt.tight_layout()
    plt.savefig(PNG, dpi=110)
sys.exit(1 if problems else 0)
