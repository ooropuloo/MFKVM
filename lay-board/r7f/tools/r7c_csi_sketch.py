# -*- coding: utf-8 -*-
"""r7c CSI inter-pair matching: feasibility sketch only (no copper is changed).

Question: can CSI_D1 and CSI_CK each gain about 3.5 mm on F.Cu under the module, between their existing BGA escape vias and the
module pads, so all three CSI pairs match within 0.762 mm (Espressif ESP32-P4 HW design guidelines p28)?

Method: obstacles = every F.Cu object of another net (pads, tracks, vias) grown by clearance + half track width; free space is what
is left of the area under the module's CSI corner. The script reports the free area and tries serpentine candidates, measuring the
length they add and the minimum spacing, and draws the result.
usage: r7c_csi_sketch.py <out_dir> <png>
"""
import json
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
s = open(f'{OUT}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()
W, GAP = 0.127, 0.198            # TMDS/CSI pair geometry solved in impedance_r7.py (100 ohm on F over In1)
CLR = 0.1                        # netclass clearance
SELF = 3 * W                     # serpentine self spacing, rule of thumb 3W (Espressif gives none for serpentines)
OTHER_PAIR = 2 * W               # Espressif p28: "maintain a minimum spacing of 2W between MIPI trace pairs"
REGION = box(5.9, -7.0, 9.15, -2.3)   # under the module, inside its CSI pads (pads 41-46), F.Cu

segs = [(LineString([(float(m[1]) - 100, float(m[2]) - 100), (float(m[3]) - 100, float(m[4]) - 100)]), float(m[5]), m[6], m[7])
        for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', s)]
vias = [(Point(float(m[1]) - 100, float(m[2]) - 100), float(m[3]), re.search(r'\(net "([^"]+)"\)', s[m.end():m.end() + 600])[1])
        for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)', s)]
# F.Cu pads with their real size, from the footprints
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

MOVE = {'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N'}
obst = []
for g, w, ly, n in segs:
    if ly == 'F.Cu' and n not in MOVE:
        obst.append(g.buffer(w / 2 + (OTHER_PAIR if n.startswith('CSI') else CLR) + W / 2))
for p, d, n in vias:
    if n not in MOVE:
        obst.append(p.buffer(d / 2 + CLR + W / 2))
for b, n in pads:
    if n not in MOVE:
        obst.append(b.buffer(CLR + W / 2))
O = unary_union(obst)
free = REGION.difference(O)
print(f'free F.Cu area for D1 and CK centrelines in the CSI corner: {free.area:.2f} mm2 of {REGION.area:.2f}')

# current F.Cu length of the four nets, and what each needs (D0 total 7.60, B.Cu parts measured on the board)
cur = {n: sum(g.length for g, w, ly, nn in segs if nn == n and ly == 'F.Cu') for n in sorted(MOVE)}
tot = {n: sum(g.length for g, w, ly, nn in segs if nn == n) for n in sorted(MOVE)}
d0 = sum(g.length for g, w, ly, nn in segs if nn == 'CSI_D0_P')
need = {n: d0 - tot[n] for n in MOVE}
for n in sorted(MOVE):
    print(f'  {n}: F.Cu {cur[n]:.2f} mm, total {tot[n]:.2f} mm, needs +{need[n]:.2f} mm to reach D0 ({d0:.2f})')

# Upper bound: a pair serpentine needs, per added mm of length, about (pair pitch + SELF) x 0.5 mm2 of corridor area.
# A coupled pair occupies 2W + GAP = 0.452 mm; adjacent legs of the meander need SELF between them.
pitch = 2 * W + GAP + SELF
area_per_mm = pitch * 0.5 * 2   # each mm of added length is two half-legs of the meander, each pitch wide... per pair
total_need = (need['CSI_D1_P'] + need['CSI_D1_N'] + need['CSI_CK_P'] + need['CSI_CK_N']) / 2   # per pair, averaged over P and N
print(f'meander estimate: about {area_per_mm:.2f} mm2 of free corridor per added mm per pair; two pairs need about {total_need:.1f} mm '
      f'-> {total_need * area_per_mm:.1f} mm2, free {free.area:.1f} mm2 (the free area must also be one connected corridor per pair)')
pieces = list(free.geoms) if hasattr(free, 'geoms') else [free]
print('free pieces (area mm2, bounds):', [(round(g.area, 2), [round(v, 2) for v in g.bounds]) for g in sorted(pieces, key=lambda g: -g.area)[:6]])

fig, ax = plt.subplots(figsize=(9, 8))
for g in (O.geoms if hasattr(O, 'geoms') else [O]):
    if g.intersects(REGION.buffer(1)):
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, color='lightgray', ec='gray', lw=0.3)
for g in pieces:
    xs, ys = g.exterior.xy
    ax.fill(xs, ys, color='palegreen', ec='green', lw=0.6)
for g, w, ly, n in segs:
    if n in MOVE and ly == 'F.Cu':
        x, y = g.xy
        ax.plot(x, y, color='red', lw=1.5)
for p, d, n in vias:
    if n in MOVE:
        ax.add_patch(plt.Circle((p.x, p.y), d / 2, color='red', fill=False))
        ax.text(p.x, p.y + 0.3, n.replace('CSI_', ''), fontsize=7, color='red')
ax.set_xlim(5.5, 10.2)
ax.set_ylim(-1.8, -7.6)
ax.set_aspect('equal')
ax.grid(lw=0.2)
ax.set_title('F.Cu under the module, CSI corner: green = room for a 0.127 mm centreline (D1/CK removed), red = today\'s D1/CK')
plt.tight_layout()
plt.savefig(PNG, dpi=120)
