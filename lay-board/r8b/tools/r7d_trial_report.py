# -*- coding: utf-8 -*-
"""r7d trial: numbers for the checkpoint table (sketch board + CSI plan). Nothing is written to the design.

  - reference plane under every new CSI segment: F.Cu over In1 GND, B.Cu over In4 GND. The filled GND polygon of the trial board
    (DRC refill) must cover a strip of W + 2 x 0.2 mm under the segment, less the antipads the plan's new vias will cut (0.4 + 2 x 0.12).
  - nearest GND via to each CSI layer-change via (return path at the transition)
  - decoupling caps: distance from each cap pad to the nearest U7 ball of its net, before (r7c) and after (trial)
  - which nets lost copper at the cluster edge (they need re-routing in a real re-layout)
usage: r7d_trial_report.py <r7c out dir> <trial dir> <plan json>
"""
import json
import math
import re
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

sys.stdout.reconfigure(encoding='utf-8')
R7C, TR, PLAN = sys.argv[1:4]
plan = json.load(open(PLAN))
s = open(f'{TR}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()


def zone_fill(layer, net):
    polys = []
    for zm in re.finditer(r'\(zone\b(.*?)\n\t\)', s, re.S):
        z = zm[1]
        if f'(net_name "{net}")' not in z and f'(net "{net}")' not in z:
            continue
        for fm in re.finditer(r'\(filled_polygon\s+\(layer "([^"]+)"\)\s+\(pts(.*?)\)\s*\)', z, re.S):
            if fm[1] != layer:
                continue
            pts = [(float(a) - 100, float(b) - 100) for a, b in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', fm[2])]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
    return unary_union(polys)


new_vias = [Point(x, y) for n, x, y in plan['vias']]
anti = unary_union([v.buffer(0.2 + 0.12) for v in new_vias])
ref = {'F.Cu': zone_fill('In1.Cu', 'GND'), 'B.Cu': zone_fill('In4.Cu', 'GND')}
print('reference plane check (strip W + 0.4 under each segment, new via antipads removed from the strip as well):')
worst = {}
for net, items in plan['tracks'].items():
    for ly, pts in items:
        g = LineString(pts)
        strip = g.buffer(0.127 / 2 + 0.2, cap_style=2).difference(anti.buffer(0.05))
        miss = strip.difference(ref[ly]).area
        worst[(net, ly)] = max(worst.get((net, ly), 0), miss)
for (net, ly), m in sorted(worst.items()):
    print(f'  {net:9s} {ly}: {m:.4f} mm2 of the strip has no GND below ({"In1" if ly == "F.Cu" else "In4"})')

vias = [(Point(float(m[1]) - 100, float(m[2]) - 100), re.search(r'\(net "([^"]+)"\)', s[m.end():m.end() + 600])[1]) for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)', s)]
gnd = [p for p, n in vias if n == 'GND']
print('GND return via nearest to each CSI layer change:')
for n, x, y in plan['vias']:
    d = min(Point(x, y).distance(g) for g in gnd)
    print(f'  {n:9s} ({x:.2f}, {y:.2f}): {d:.2f} mm')


def decaps(design):
    d = json.load(open(design, encoding='utf-8'))
    P = {p['ref']: p for p in d['parts']}
    pp = d['padpos']
    balls = {}
    for b, n in P['U7']['nets'].items():
        balls.setdefault(n, []).append(pp['U7.' + b])
    out = {}
    for r in ('C13', 'C14', 'C15', 'C16', 'C17', 'C18', 'C19', 'C20', 'C21', 'C22', 'C23', 'C24', 'C25', 'C26', 'C27'):
        p = P[r]
        for k, n in p['nets'].items():
            if n != 'GND' and n in balls:
                out[r] = (n, min(math.dist(pp[f'{r}.{k}'], b) for b in balls[n]))
    return out


a, b = decaps(f'{R7C}/design.json'), decaps(f'{TR}/design.json')
print('decoupling cap pad to nearest U7 ball of its net (mm), r7c -> trial:')
for r in a:
    print(f'  {r:4s} {a[r][0]:9s} {a[r][1]:5.2f} -> {b[r][1]:5.2f}')

# nets that lost copper at the cluster edge: unconnected items in the trial DRC
r = json.load(open(f'{TR}/drc.json', encoding='utf-8'))
nets = sorted({i['description'].split('[')[-1].split(']')[0] for u in r.get('unconnected_items', []) for i in u['items']})
print(f'nets left open by the trial (need re-routing in a real re-layout): {len(nets)}: {nets}')
