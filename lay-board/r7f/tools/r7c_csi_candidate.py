# -*- coding: utf-8 -*-
"""r7c CSI: one candidate F.Cu routing for CSI_D1 and CSI_CK with meanders, measured against the real board. Sketch: copper is not changed.

RESULT OF THIS ATTEMPT (2026-11-08): it does NOT meet the rules. D1 fits only 3 legs in its pocket (x 6.35-7.75, y -4.45..-6.45) and
reaches 6.5-6.9 mm against 6.84 minimum; CK touches the D0 stubs and its own legs; P/N differ by 0.4 (D1) and 1.2 mm (CK); the two
pairs come to 0.198 mm (2W is 0.254). The free area is enough (10.8 mm2 against about 6), its shape is not: below D1 the pocket is
blocked by GND via (8.163, -6.663) and VDD_MIPI via (8.55, -6.2), above the escape vias by GND vias (6.8, -2.7), (6.8, -3.35).
A working layout needs those power/ground vias moved too. Kept as the record of the evaluation.

Rules used (the same ones the board would be judged by):
  pair geometry 0.127 / 0.198 (impedance_r7.py, 100 ohm on F over In1); 45 degree corners only (no right angles);
  0.1 mm to any other copper (netclass), 2W = 0.254 mm edge to edge to the other CSI pairs (Espressif p28),
  3W = 0.381 mm edge to edge between legs of the same meander (rule of thumb; Espressif gives none).
Targets: each line's total (existing B.Cu escape + new F.Cu) within 0.762 mm of CSI_D0 (7.60), P/N within 0.15 mm.
usage: r7c_csi_candidate.py <out_dir> <png>
"""
import math
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

sys.stdout.reconfigure(encoding='utf-8')
OUT, PNG = sys.argv[1], sys.argv[2]
W, GAP, CLR = 0.127, 0.198, 0.1
PITCH = W + GAP
s = open(f'{OUT}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()
segs = [(LineString([(float(m[1]) - 100, float(m[2]) - 100), (float(m[3]) - 100, float(m[4]) - 100)]), float(m[5]), m[6], m[7])
        for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', s)]
vias = [(Point(float(m[1]) - 100, float(m[2]) - 100), float(m[3]), re.search(r'\(net "([^"]+)"\)', s[m.end():m.end() + 600])[1])
        for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)', s)]
pads = []
for fm in re.finditer(r'\(footprint "mini:[^"]*"(.*?)(?=\n\t\(footprint |\n\t\((?:segment|via|zone|gr_))', s, re.S):
    b = fm[1]
    if '(layer "F.Cu")' not in b[:200]:
        continue
    tr = re.search(r'\(translate ([-\d.]+) ([-\d.]+)\)', b)
    rot = re.search(r'\(rotate ([-\d.]+)\)', b)
    ox, oy = float(tr[1]) - 100, float(tr[2]) - 100
    a = math.radians(float(rot[1]) if rot else 0.0)
    for q in re.finditer(r'\(pad "([^"]*)" smd \w+\s+\(at ([-\d.]+) ([-\d.]+)(?: [-\d.]+)?\)\s+\(size ([\d.]+) ([\d.]+)\).*?\(net "([^"]*)"\)', b, re.S):
        x, y, w, h = float(q[2]), float(q[3]), float(q[4]), float(q[5])
        wx, wy = ox + x * math.cos(a) + y * math.sin(a), oy - x * math.sin(a) + y * math.cos(a)
        if abs(math.sin(a)) > 0.5:
            w, h = h, w
        pads.append((box(wx - w / 2, wy - h / 2, wx + w / 2, wy + h / 2), q[6]))
MOVE = ('CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N')
other = [(g.buffer(w / 2), n) for g, w, ly, n in segs if ly == 'F.Cu' and n not in MOVE]
other += [(p.buffer(d / 2), n) for p, d, n in vias if n not in MOVE]
other += [(b, n) for b, n in pads if n not in MOVE]
blen = {n: sum(g.length for g, w, ly, nn in segs if nn == n and ly != 'F.Cu') for n in MOVE}
d0 = (sum(g.length for g, w, ly, nn in segs if nn == 'CSI_D0_P') + sum(g.length for g, w, ly, nn in segs if nn == 'CSI_D0_N')) / 2
VIA = {n: (round(p.x, 3), round(p.y, 3)) for p, d, n in vias if n in MOVE}
PADEND = {'CSI_D1_P': (6.5, -6.8), 'CSI_D1_N': (7.5, -6.8), 'CSI_CK_P': (9.2, -4.1), 'CSI_CK_N': (9.2, -5.1)}


def chamfer(pts, c=0.12):
    """Cut every corner of an axis-aligned polyline at 45 degrees."""
    out = [pts[0]]
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        u = ((b[0] - a[0]) / (math.dist(a, b) or 1), (b[1] - a[1]) / (math.dist(a, b) or 1))
        v = ((d[0] - b[0]) / (math.dist(b, d) or 1), (d[1] - b[1]) / (math.dist(b, d) or 1))
        out += [(b[0] - u[0] * c, b[1] - u[1] * c), (b[0] + v[0] * c, b[1] + v[1] * c)]
    return out + [pts[-1]]


def pair(center, side):
    g = LineString(center).offset_curve(PITCH / 2 * side, join_style=2, mitre_limit=3)
    return list(g.coords)


def mean_y(x_a, x_b, y0, n, step):
    """Centreline meander: horizontal legs alternating x_a -> x_b, descending by 'step' between legs."""
    pts, y = [(x_a, y0)], y0
    for i in range(n):
        x = x_b if i % 2 == 0 else x_a
        pts.append((x, y))
        if i < n - 1:
            y -= step
            pts.append((x, y))
    return pts


STEP = W + GAP + W + 0.381 + 0.0   # pair edge to pair edge 3W between neighbouring legs: pitch of legs = pair width + 3W
STEP = 2 * W + GAP + 0.381
print(f'meander leg pitch {STEP:.3f} mm')
# ---- D1: coupled from y -4.55, legs between x 6.66 and 7.62, P on the left of the first leg (the via side)
d1 = chamfer(mean_y(6.66, 7.55, -4.62, 3, STEP))
# ---- CK: legs between x 8.20 and 8.95 descending from y -3.10
ck = chamfer(mean_y(8.20, 8.92, -3.20, 3, STEP))
cand = {}
for name, cen, ends in (('D1', d1, None), ('CK', ck, None)):
    for side, nn in ((+1, f'CSI_{name}_P'), (-1, f'CSI_{name}_N')):
        line = pair(cen, side)
        cand[nn] = [VIA[nn]] + line + [PADEND[nn]]
res = {}
for nn, pts in cand.items():
    g = LineString(pts)
    tot = blen[nn] + g.length
    near = min((g.distance(o) - W / 2, on) for o, on in other)
    selfmin = min(LineString(pts[i:i + 2]).distance(LineString(pts[j:j + 2])) - W for i in range(len(pts) - 1) for j in range(i + 3, len(pts) - 1))
    res[nn] = (tot, near, selfmin)
    print(f'{nn}: total {tot:.2f} mm (B {blen[nn]:.2f} + F {g.length:.2f}), to D0 {tot - d0:+.2f}; nearest other copper {near[0]:.3f} mm ({near[1]}); own legs {selfmin:.3f} mm')
for p in ('D1', 'CK'):
    print(f'{p}: P - N = {res[f"CSI_{p}_P"][0] - res[f"CSI_{p}_N"][0]:+.3f} mm')
gx = min(LineString(cand[a]).distance(LineString(cand[b])) - W for a in ('CSI_D1_P', 'CSI_D1_N') for b in ('CSI_CK_P', 'CSI_CK_N'))
print(f'D1 to CK edge to edge {gx:.3f} mm (Espressif 2W = 0.254)')

fig, ax = plt.subplots(figsize=(9, 9))
for o, on in other:
    if o.intersects(box(5.5, -7.8, 10.3, -1.8)):
        geoms = o.geoms if hasattr(o, 'geoms') else [o]
        for gg in geoms:
            xs, ys = gg.exterior.xy
            ax.fill(xs, ys, color='lightgray', ec='gray', lw=0.3)
for nn, pts in cand.items():
    xs, ys = zip(*pts)
    ax.plot(xs, ys, lw=W * 72 * 9 / 4.8 / 1.3, color='red' if 'D1' in nn else 'blue', alpha=0.7, solid_capstyle='round')
for g, w, ly, n in segs:
    if n in MOVE and ly == 'F.Cu':
        x, y = g.xy
        ax.plot(x, y, color='k', lw=0.5, ls=':')
ax.set_xlim(5.5, 10.3)
ax.set_ylim(-1.8, -7.8)
ax.set_aspect('equal')
ax.grid(lw=0.2)
ax.set_title('candidate F.Cu meanders: red CSI_D1, blue CSI_CK (dotted: today)')
plt.tight_layout()
plt.savefig(PNG, dpi=120)
