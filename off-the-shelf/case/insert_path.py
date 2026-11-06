# -*- coding: utf-8 -*-
"""Can the core, with the ATX board soldered to it, get into the tray? Moves the real shapes along a path and intersects them with the printed tray at every step.

Why it is not a straight drop: core plus ATX is 34.27 mm wide in a 34.85 mm cavity, and the lid screw boss at y 42 overhangs the core's +X edge. So the +X edge goes in first, tilted.
Every part is its bounding box, which is larger than the part. The final flat pose is covered by gen_case.py with the real STEP solids, so the path stops at 1 degree.

usage: insert_path.py <firebeetle bb.json>     writes asm/insert_path.json
"""
import json
import math
import os
import sys

import cadquery as cq

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
tray = cq.importers.importStep(os.path.join(HERE, 'step', 'mf_kvm_tray.step')).val()
chk = json.load(open(os.path.join(HERE, 'check.json'), encoding='utf-8'))
ATX = json.load(open(os.path.join(HERE, '..', 'atx', 'out', 'design.json'), encoding='utf-8'))
bb = json.load(open(sys.argv[1], encoding='utf-8'))
TOL = 0.001


def box(x0, y0, z0, x1, y1, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


cx, cy, z_atx = chk['levels']['ATX_C']
# the PCB has R1.5 corners, a square corner would hit the cavity's own fillet
shapes = {'pcb': cq.Workplane('XY').box(25.4, 60, 1.62, centered=False).edges('|Z').fillet(1.5).translate((-12.685, 0, -1.62)).val()}
for e in bb:
    b = e['bb']
    if e['depth'] == 1 and e['refname'] != 'Board':
        vol = (b[3] - b[0]) * (b[4] - b[1]) * (b[5] - b[2])
        # the tall and the outermost parts are what can touch; small parts in the middle of the board cannot reach anything the larger ones do not
        if vol > 0.5 or abs(b[0]) > 9 or abs(b[3]) > 9:
            shapes[e['refname']] = box(*b)
outline = [(cx + x, cy - y) for x, y in ATX['outline']]
shapes['atx_board'] = cq.Workplane('XY').polyline(outline).close().extrude(1.0).translate((0, 0, z_atx)).val()
for p in ATX['parts']:
    x0, y0, x1, y1 = p['bbox']
    h = dict(OPTO_SO4=2.2, JST_SM06B=2.95, R0402=0.5).get(p['lib'])
    if h:
        shapes['atx_' + p['ref']] = box(cx + x0, cy - y1, z_atx + 1.0, cx + x1, cy - y0, z_atx + 1.0 + h)
for pin in chk['atx']['pins']:
    shapes['pin_' + pin['ref']] = box(pin['x'] - 0.7, pin['y'] - 0.7, -4.6, pin['x'] + 0.7, pin['y'] + 0.7, 1.0)
print('moving shapes', len(shapes))
PIVOT = (12.72, -1.62)  # the core's +X bottom edge. Tilt lifts the -X side.


def pose(s, theta, px, pz):
    r = s.rotate(cq.Vector(PIVOT[0], 0, PIVOT[1]), cq.Vector(PIVOT[0], 1, PIVOT[1]), theta) if theta else s
    return r.translate(cq.Vector(px - PIVOT[0], 0, pz - PIVOT[1]))


# (tilt degrees, pivot x, pivot z): lower it at 45 degrees with the +X edge clear of the boss, then flatten while keeping the board's -X edge just off the -X wall.
# That rule fixes pivot x: 34.27 cos(t) + 2.2 sin(t) - 21.85, the board tip's own reach. The BOOT switch then needs the pocket in the +X wall.
def reach(t):
    a = math.radians(t)
    return 34.27 * math.cos(a) + 2.2 * math.sin(a) - 21.85


WAY = [(45, 5.0, z) for z in (30, 20, 10, 4, 1, -0.5)]
for t in (42, 38, 34, 30, 26, 22, 19, 16, 14, 12, 10, 8, 6, 4, 2, 1):
    WAY.append((t, min(12.72, max(5.0, reach(t) + 0.2)), -1.62 + 1.12 * t / 45))
rows = []
tb = tray.BoundingBox()
for th, px, pz in WAY:
    hits = []
    for k, s in shapes.items():
        m = pose(s, th, px, pz)
        b = m.BoundingBox()
        if b.xmax < tb.xmin or b.xmin > tb.xmax or b.zmin > tb.zmax:
            continue
        v = m.intersect(tray).Volume() if b.zmin < tb.zmax else 0.0
        if v > TOL:
            hits.append((k, round(v, 3)))
    rows.append(dict(tilt=round(th, 2), pivot_x=round(px, 2), pivot_z=round(pz, 2), hits=hits))
    print(rows[-1])
bad = [r for r in rows if r['hits']]
json.dump(dict(rows=rows, bad=len(bad), shapes=len(shapes)), open(os.path.join(HERE, 'asm', 'insert_path.json'), 'w', encoding='utf-8'), indent=0)
print('RESULT', 'CHECK' if bad else 'OK', len(rows), 'poses,', len(bad), 'with a collision')
sys.exit(1 if bad else 0)
