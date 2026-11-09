# -*- coding: utf-8 -*-
"""usage: measure.py <r5 pcb> <r6 pcb>: the before/after numbers of R6_REPORT.md, measured from the saved board files."""
import collections
import heapq
import math
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import brd

R5, R6 = brd.load(sys.argv[1]), brd.load(sys.argv[2])
OUTLINE = Polygon([(81.5, 80), (118.5, 80), (120, 81.5), (120, 118.5), (118.5, 120), (81.5, 120), (80, 118.5), (80, 81.5)])
H_PP = 0.0994


def gnd_vias(B):
    return [v for v in B['vias'] if v['net'] == 'GND']


def head(t):
    print('\n== ' + t)


# ---------- RF line
head('LNA_OUT line, r6')
B = R6
segs = [s for s in B['segs'] if s['net'] == 'LNA_OUT']
vias = [v for v in B['vias'] if v['net'] == 'LNA_OUT']
for s in segs:
    print(f"  {s['layer']} ({s['a'][0]:.3f},{s['a'][1]:.3f})-({s['b'][0]:.3f},{s['b'][1]:.3f}) w {s['w']} length {math.dist(s['a'], s['b']):.3f}")
for v in vias:
    print(f"  via ({v['x']:.3f},{v['y']:.3f}) {v['size']}/{v['drill']}")
pad = {f"{q['ref']}.{q['num']}": q for q in B['pads']}
u = brd.pad_poly(pad['U1.2'])
j = brd.pad_poly(pad['J8.1'])
free = 0
for s in segs:
    ln = LineString([s['a'], s['b']])
    pd = u if s['layer'] == 'F.Cu' else j
    free += ln.difference(pd).length
print(f'  track outside the two pads: {free:.3f} mm, plus the 1.13 mm barrel (board 1.2 mm less copper)')
lnv = vias[0]
print('  branches: nodes with more than two ends', [k for k, c in collections.Counter([(round(p[0], 3), round(p[1], 3), s['layer']) for s in segs for p in (s['a'], s['b'])]).items() if c > 2] or 'none')
print('  corner: straight in x on both layers, no bends')
d = sorted((math.hypot(v['x'] - lnv['x'], v['y'] - lnv['y']), v['x'], v['y']) for v in gnd_vias(B))[:6]
print('  nearest GND vias to the layer change, centre distance:', [f'{a:.3f} at ({b:.2f},{c:.2f})' for a, b, c in d])
for ly, plane in (('F.Cu', 'In1.Cu'), ('B.Cu', 'In4.Cu')):
    ss = [s for s in segs if s['layer'] == ly]
    z = brd.zone_geom(B, 'GND', plane)
    pour = brd.zone_geom(B, 'GND', ly)
    for s in ss:
        ln = LineString([s['a'], s['b']])
        cor = ln.buffer(s['w'] / 2 + 3 * H_PP, cap_style=2)
        pts = [ln.interpolate(k / 20, normalized=True) for k in range(21)]
        off = sum(not z.contains(p) for p in pts)
        print(f"  {ly}: reference {plane}: samples on the centre line off the plane {off}/21; corridor w/2+3h covered {z.intersection(cor).area / cor.area * 100:.1f}%; same-side pour gap {ln.distance(pour) - s['w'] / 2:.3f}")
    print(f'  {plane} antipad at the via: nearest plane copper to the via centre {Point(lnv["x"], lnv["y"]).distance(z):.3f} (via radius 0.2)')
z3 = brd.zone_geom(B, '3V3', 'In3.Cu')
print(f'  In3 3V3 antipad {Point(lnv["x"], lnv["y"]).distance(z3):.3f}')
line_all = unary_union([LineString([s['a'], s['b']]) for s in segs] + [Point(lnv['x'], lnv['y'])])
for ly in ('F.Cu', 'In2.Cu', 'B.Cu'):
    rows = []
    for n, kind, poly, lab in brd.copper(B, ly, exclude={'LNA_OUT', 'GND'}):
        rows.append((line_all.distance(poly), n, kind, lab))
    rows.sort(key=lambda r: r[0])
    print(f'  nearest non-ground copper on {ly}:', [f'{a:.3f} {n} {k} {l}' for a, n, k, l in rows[:4]])
for grp, nets in (('SW', {'SW'}), ('TMDS', {'D2_P', 'D2_N', 'D1_P', 'D1_N', 'D0_P', 'D0_N', 'CK_P', 'CK_N'}), ('CSI', {'CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N'}), ('USB HS', {'USB_DP', 'USB_DN'}), ('USB2', {'USB2_DP', 'USB2_DN'}), ('L1', None)):
    if nets:
        best = min(line_all.distance(p) for ly in ('F.Cu', 'In2.Cu', 'B.Cu') for n, k, p, l in brd.copper(B, ly, nets=nets))
        print(f'  to {grp}: {best:.2f} mm')
print('  J8 centre, board mm', B['fps']['J8']['x'], B['fps']['J8']['y'], 'pads', [(q['num'], round(q['x'], 3), round(q['y'], 3), q['w'], q['h'], q['net']) for q in B['fps']['J8']['pads']])

# ---------- edge stitching
head('Edge stitching (GND vias within 1.5 mm of the edge, gaps along the outline)')


def perim(p):
    return OUTLINE.exterior.project(Point(p))


for name, B in (('r5', R5), ('r6', R6)):
    near = [(v['x'], v['y']) for v in gnd_vias(B) if OUTLINE.exterior.distance(Point(v['x'], v['y'])) <= 1.5]
    pth = [(q['x'], q['y']) for q in B['pads'] if q['net'] == 'GND' and q['kind'] == 'thru_hole' and OUTLINE.exterior.distance(Point(q['x'], q['y'])) <= 1.5]
    pos = sorted(perim(p) for p in near)
    L = OUTLINE.exterior.length
    gaps = [(pos[(k + 1) % len(pos)] - pos[k]) % L for k in range(len(pos))]
    big = sorted(((g, OUTLINE.exterior.interpolate(pos[k]).coords[0]) for k, g in enumerate(gaps)), reverse=True)[:5]
    print(f'  {name}: {len(near)} vias, {len(pth)} GND PTH also in that band; largest gaps', [f'{g:.1f} from ({c[0]:.1f},{c[1]:.1f})' for g, c in big])
new = [(v['x'], v['y']) for v in gnd_vias(R6)]
old = {(round(v['x'], 2), round(v['y'], 2)) for v in gnd_vias(R5)}
added = [p for p in new if (round(p[0], 2), round(p[1], 2)) not in old]
gone = [p for p in old if p not in {(round(a, 2), round(b, 2)) for a, b in new}]
print(f'  GND vias r5 {len(gnd_vias(R5))}, r6 {len(new)}, added {len(added)}, removed or moved {gone}')

# ---------- return vias
head('Return vias: high-speed via to nearest GND via, centre distance, mm')
for net in ('CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N', 'USB_DP', 'USB_DN', 'USB2_DP', 'USB2_DN'):
    for v in R6['vias']:
        if v['net'] == net:
            a = min(math.hypot(g['x'] - v['x'], g['y'] - v['y']) for g in gnd_vias(R5))
            b = min(math.hypot(g['x'] - v['x'], g['y'] - v['y']) for g in gnd_vias(R6))
            print(f"  {net:9s} ({v['x']:.2f},{v['y']:.2f})  r5 {a:.2f}  r6 {b:.2f}")


# ---------- path lengths
def graph(B, net):
    segs = [s for s in B['segs'] if s['net'] == net]
    vias = [v for v in B['vias'] if v['net'] == net]
    pads = [q for q in B['pads'] if q['net'] == net]
    pts = collections.defaultdict(set)
    for s in segs:
        pts[s['layer']].update([tuple(s['a']), tuple(s['b'])])
    for v in vias:
        for ly in ('F.Cu', 'In2.Cu', 'B.Cu'):
            pts[ly].add((v['x'], v['y']))
    for q in pads:
        for ly in brd.pad_layers(q):
            pts[ly].add((q['x'], q['y']))
    g = collections.defaultdict(list)
    for s in segs:
        L = math.dist(s['a'], s['b'])
        if L < 1e-9:
            continue
        ux, uy = (s['b'][0] - s['a'][0]) / L, (s['b'][1] - s['a'][1]) / L
        on = []
        for p in pts[s['layer']]:
            t = (p[0] - s['a'][0]) * ux + (p[1] - s['a'][1]) * uy
            dd = abs((p[0] - s['a'][0]) * uy - (p[1] - s['a'][1]) * ux)
            if -0.03 <= t <= L + 0.03 and dd < s['w'] / 2 + 0.02:
                on.append((t, p))
        on.sort()
        for (t0, p0), (t1, p1) in zip(on, on[1:]):
            g[(p0, s['layer'])].append(((p1, s['layer']), max(t1 - t0, 0), 0))
            g[(p1, s['layer'])].append(((p0, s['layer']), max(t1 - t0, 0), 0))
    for v in vias:
        p = (v['x'], v['y'])
        nodes = [(p, ly) for ly in ('F.Cu', 'In2.Cu', 'B.Cu') if (p, ly) in g]
        for a in nodes:
            for b in nodes:
                if a != b:
                    g[a].append((b, 0.0, 1))
    # a pad joins every track end inside it
    for q in pads:
        poly = brd.pad_poly(q).buffer(0.02)
        for ly in brd.pad_layers(q):
            ins = [n for n in list(g) if n[1] == ly and poly.contains(Point(n[0]))]
            for a in ins:
                for b in ins:
                    if a != b:
                        g[a].append((b, 0.0, 0))
    return g, pads


def shortest(B, net, a, b):
    g, pads = graph(B, net)
    pa = next(q for q in pads if f"{q['ref']}.{q['num']}" == a)
    pb = next(q for q in pads if f"{q['ref']}.{q['num']}" == b)
    sa = [n for n in g if n[1] in brd.pad_layers(pa) and brd.pad_poly(pa).buffer(0.02).contains(Point(n[0]))]
    sb = {n for n in g if n[1] in brd.pad_layers(pb) and brd.pad_poly(pb).buffer(0.02).contains(Point(n[0]))}
    h = [(0.0, 0, i, n) for i, n in enumerate(sa)]
    seen = {}
    c = len(h)
    while h:
        d, nv, _, u = heapq.heappop(h)
        if u in seen:
            continue
        seen[u] = (d, nv)
        if u in sb:
            return d, nv
        for w, L, vv in g[u]:
            if w not in seen:
                c += 1
                heapq.heappush(h, (d + L, nv + vv, c, w))
    return None, None


head('VDDC decoupling: capacitor pad to ball, routed path mm / vias')
for cap in ('C19.1', 'C20.1', 'C21.1'):
    for ball in ('C3', 'F5', 'G2'):
        a = shortest(R5, 'VDDC', cap, f'U7.{ball}')
        b = shortest(R6, 'VDDC', cap, f'U7.{ball}')
        print(f'  {cap} to {ball}: r5 {a[0]:.1f}/{a[1]}  r6 {b[0]:.1f}/{b[1]}')
head('Buck input')
for name, a, b in (('C60.1 to U2.4', 'C60.1', 'U2.4'), ('C60.1 to U2.1', 'C60.1', 'U2.1')):
    x = shortest(R5, '5V', a, b)
    y = shortest(R6, '5V', a, b)
    print(f'  {name}: r5 {x[0]:.2f}/{x[1]} via, r6 {y[0]:.2f}/{y[1]} via')
y = shortest(R6, '5V', 'C64.1', 'U2.4')
print(f'  C64.1 to U2.4 r6 {y[0]:.2f} (centre to centre through the strap), pad gap', round(brd.pad_poly(pad['C64.1']).distance(brd.pad_poly(pad['U2.4'])), 3))
print('  C64.2 to J5.1 pad gap', round(brd.pad_poly(pad['C64.2']).distance(brd.pad_poly(pad['J5.1'])), 3), ' C64 to FB_3V3 track, min', round(min(brd.pad_poly(pad[k]).distance(p) for k in ('C64.1', 'C64.2') for n, kk, p, l in brd.copper(R6, 'B.Cu', nets={'FB_3V3'})), 3))
print('  R51.2 GND via distance to J5.1 pad', round(Point(111.25, 107.7).distance(brd.pad_poly(pad['J5.1'])), 3))

# ---------- 5V on In2
head('5V copper')
for name, B in (('r5', R5), ('r6', R6)):
    t = collections.Counter()
    for s in B['segs']:
        if s['net'] == '5V':
            t[(s['layer'], s['w'])] += math.dist(s['a'], s['b'])
    print(' ', name, {k: round(v, 2) for k, v in sorted(t.items())}, 'vias', [(round(v['x'], 2), round(v['y'], 2), v['size']) for v in B['vias'] if v['net'] == '5V'])
head('VDDC copper')
for name, B in (('r5', R5), ('r6', R6)):
    t = collections.Counter()
    for s in B['segs']:
        if s['net'] == 'VDDC':
            t[(s['layer'], round(s['w'], 3))] += math.dist(s['a'], s['b'])
    print(' ', name, {k: round(v, 2) for k, v in sorted(t.items())})

# ---------- TMDS gap profile, width, reference
head('TMDS: pair gap, reference plane, r6')
for name, B in (('r5', R5), ('r6', R6)):
    z = brd.zone_geom(B, 'GND', 'In4.Cu')
    for pr in ('D2', 'D1', 'D0', 'CK'):
        p = [s for s in B['segs'] if s['net'] == pr + '_P']
        n = [s for s in B['segs'] if s['net'] == pr + '_N']
        lp = unary_union([LineString([s['a'], s['b']]) for s in p])
        ln = unary_union([LineString([s['a'], s['b']]) for s in n])
        gaps = []
        off = 0
        tot = 0
        step = 0.02
        for s in p + n:
            L = math.dist(s['a'], s['b'])
            other = ln if s in p else lp
            for k in range(int(L / step) + 1):
                t = k * step / max(L, 1e-9)
                q = Point(s['a'][0] + (s['b'][0] - s['a'][0]) * t, s['a'][1] + (s['b'][1] - s['a'][1]) * t)
                gaps.append(q.distance(other) - 0.127)
                tot += 1
                off += not z.contains(q)
        gaps.sort()
        others = unary_union([brd.seg_poly(s) for s in B['segs'] if s['layer'] == 'B.Cu' and s['net'] not in (pr + '_P', pr + '_N') and s['net'].rstrip('PN').rstrip('_') in ('D2', 'D1', 'D0', 'CK')])
        adj = unary_union([brd.seg_poly(s) for s in p + n]).distance(others)
        print(f'  {name} {pr}: gap min {gaps[0]:.3f} median {gaps[len(gaps) // 2]:.3f} p95 {gaps[int(len(gaps) * .95)]:.3f} max {gaps[-1]:.3f}; to another lane min {adj:.3f}; samples off In4 {off}/{tot}; widths {sorted({s["w"] for s in p + n})}')
head('CSI reference, r6')
for net in ('CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N'):
    out = []
    for ly, pl in (('F.Cu', 'In1.Cu'), ('B.Cu', 'In4.Cu')):
        z = brd.zone_geom(R6, 'GND', pl)
        ss = [s for s in R6['segs'] if s['net'] == net and s['layer'] == ly]
        tot = off = 0
        for s in ss:
            ln = LineString([s['a'], s['b']])
            for k in range(0, int(ln.length / 0.02) + 1):
                tot += 1
                off += not z.contains(ln.interpolate(k * 0.02))
        out.append(f'{ly} {off * 0.02:.2f} mm of {tot * 0.02:.2f} off {pl}')
    print(f'  {net}: ' + '; '.join(out))
