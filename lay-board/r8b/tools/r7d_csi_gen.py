# -*- coding: utf-8 -*-
"""r7d CSI routing, generated for a TC358743 cluster shifted by DX in x (R7D_DX). Writes the plan json that r7c_csi_plan.py checks
and that gen_mini's r7d stage builds.

Topology (forced by the ball and pad order, see R7D_REPORT.md):
  D0 stays on B.Cu and reaches its pads (41 N, 42 P) from the module's outside edge, as in r6..r7c; it is the longest pair.
  CK and D1 change to F.Cu at their BGA dogbone vias and are lengthened with coupled meanders in the area the shift opened.
  Pair geometry 0.127 / 0.198 (100 ohm, impedance_r7.py); meander legs 0.833 apart (pair 0.452 + 3W); 45 degree corners.
Tuning knobs at the top: leg extents and the extra length trims. Units mm, board design frame (y as in the generator).
usage: r7d_csi_gen.py <DX> <out json> [CK legs top] [CK legs bottom] [D1 leg right] ...
"""
import json
import math
import sys

from shapely.geometry import LineString

DX = float(sys.argv[1])
OUTJ = sys.argv[2]
KW = dict(a.split('=') for a in sys.argv[3:])
W, GAP = 0.127, 0.198
H = (W + GAP) / 2          # centreline to line
C = 0.12                   # 45 degree chamfer on the centreline


def ball(name):
    col = int(name[1]) - 1
    row = 'ABCDEFGH'.index(name[0])
    return (round(5.5 + DX - 2.275 + col * 0.65, 4), round(-4.0 + 2.275 - row * 0.65, 4))


def chamfer(pts, c=C):
    out = [pts[0]]
    for a, b, d in zip(pts, pts[1:], pts[2:]):
        la, lb = math.dist(a, b), math.dist(b, d)
        u = ((b[0] - a[0]) / la, (b[1] - a[1]) / la)
        v = ((d[0] - b[0]) / lb, (d[1] - b[1]) / lb)
        cc = min(c, la / 2.01, lb / 2.01)
        out += [(b[0] - u[0] * cc, b[1] - u[1] * cc), (b[0] + v[0] * cc, b[1] + v[1] * cc)]
    return out + [pts[-1]]


def side(center, s):
    """s=+1 left of travel, -1 right; mitred offset of the chamfered centreline"""
    g = LineString(center).offset_curve(H * s, join_style=2, mitre_limit=4)
    return [(round(x, 4), round(y, 4)) for x, y in g.coords]


def f(k, d):
    return float(KW.get(k, d))


plan = {'tracks': {}, 'vias': []}


def add(net, layer, pts):
    pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-4]
    keep = [pts[0]]   # merge collinear runs, so a straight line is one segment
    for a, b in zip(pts[1:], pts[2:] + [None]):
        if b is not None:
            u = (a[0] - keep[-1][0], a[1] - keep[-1][1])
            v = (b[0] - a[0], b[1] - a[1])
            if abs(u[0] * v[1] - u[1] * v[0]) < 1e-6 and u[0] * v[0] + u[1] * v[1] > 0:
                continue
        keep.append(a)
    pts = keep
    plan['tracks'].setdefault(net, []).append([layer, [list(p) for p in pts]])


# ---------------- D0: the r7c routing, shifted where it is attached to the BGA (balls, escapes); vias and loop stay at the module edge
e8, e7 = ball('E8'), ball('E7')
# D0_P's intra-pair bump, widened to 3W between its legs (r7c had 0.27 mm): legs 0.53 apart centre to centre
_bh = float(KW.get('d0_bump', 1.31))
add('CSI_D0_P', 'B.Cu', [e8, (9.2, e8[1]), (9.32, e8[1] + 0.12), (9.32, e8[1] + _bh - 0.12), (9.44, e8[1] + _bh), (9.73, e8[1] + _bh), (9.85, e8[1] + _bh - 0.12), (9.85, e8[1] + 0.12), (9.97, e8[1]), (10.42, e8[1]), (10.72, -4.025), (10.72, -3.1)])
add('CSI_D0_P', 'F.Cu', [(10.72, -3.1), (9.9, -3.1)])
add('CSI_D0_N', 'B.Cu', [e7, (e7[0] + 0.325, -4.65), (10.9, -4.65), (11.2, -4.35), (11.2, -2.58), (10.72, -2.1)])
add('CSI_D0_N', 'F.Cu', [(10.72, -2.1), (9.9, -2.1)])
plan['vias'] += [['CSI_D0_P', 10.72, -3.1], ['CSI_D0_N', 10.72, -2.1]]

# ---------------- CK: dogbone vias, then a coupled meander east, N on the right of travel all the way (ends at pad 44, below 43)
c8, c7 = ball('C8'), ball('C7')
nv, pv = (round(7.45 + DX, 4), -2.7), (round(8.1 + DX, 4), -2.7)
add('CSI_CK_N', 'B.Cu', [c7, nv])
# CK_P's intra-pair bump under the BGA (r6..r7c), shifted: CK_N reaches pad 44, a millimetre past CK_P's pad 43
add('CSI_CK_P', 'B.Cu', [c8, (c8[0] + 0.375, -3.4), (c8[0] + 0.625, -3.4), (c8[0] + 0.825, -3.2), (c8[0] + 0.825, -2.9), (c8[0] + 0.625, -2.7), pv])
plan['vias'] += [['CSI_CK_N', nv[0], nv[1]], ['CSI_CK_P', pv[0], pv[1]]]
# CK centreline waypoints (x,y;...), axis aligned; starts heading east between the two lines, ends heading -y at the descent column
W_CK = KW.get('ck_w', '5.93,-2.8875;6.6,-2.8875;6.6,-1.5;7.433,-1.5;7.433,-3.25;8.266,-3.25;8.266,-3.6')
cen = chamfer([tuple(map(float, q.split(','))) for q in W_CK.split(';')])
P = side(cen, +1)
N = side(cen, -1)
add('CSI_CK_P', 'F.Cu', [pv] + P + [(P[-1][0], -3.98), (P[-1][0] + 0.12, -4.1), (9.3, -4.1)])
add('CSI_CK_N', 'F.Cu', [nv, (nv[0] + 0.25, -2.95), (nv[0] + 0.35, -3.05)] + N + [(N[-1][0], -4.98), (N[-1][0] + 0.12, -5.1), (9.3, -5.1)])

# ---------------- D1: dogbone vias, coupled meander of horizontal legs going down, N on the left of travel (ends east, at pad 45)
d8, d7 = ball('D8'), ball('D7')
dnv, dpv = (round(7.45 + DX, 4), -3.35), (round(6.8 + DX, 4), -4.0)
add('CSI_D1_N', 'B.Cu', [d7, dnv])
add('CSI_D1_P', 'B.Cu', [d8, (round(7.45 + DX, 4), -4.0), dpv])
plan['vias'] += [['CSI_D1_N', dnv[0], dnv[1]], ['CSI_D1_P', dpv[0], dpv[1]]]
# D1 centreline waypoints; starts heading east (N on the left = north), ends heading -y above pads 46 (P, x 6.5) and 45 (N, x 7.5)
W_D1 = KW.get('d1_w', '5.05,-4.2;5.55,-4.2;5.55,-5.7;6.33,-5.7;6.33,-4.2;7.0,-4.2;7.0,-6.2')
cen = chamfer([tuple(map(float, q.split(','))) for q in W_D1.split(';')])
Nl = side(cen, +1)
Pl = side(cen, -1)
# D1_N tooth: P's BGA escape is 0.65 mm longer than N's (dogbone positions are fixed by the ball grid), so N gets a tooth on the outside
# of the last leg, where N is the east line. Height and position are knobs.
_ta, _ty = float(KW.get('d1_tooth', 0.0)), float(KW.get('d1_tooth_y', -4.7))
_nl = list(Nl)
if _ta > 0:
    _x = _nl[-1][0]
    _c, _g = float(KW.get('d1_tooth_c', 0.05)), float(KW.get('d1_tooth_g', 0.45))   # out a, along g, back a, 45 degree corners: adds 2a - 2.343c
    _t = [(_x, _ty), (_x + _c, _ty - _c), (_x + _ta - _c, _ty - _c), (_x + _ta, _ty - 2 * _c), (_x + _ta, _ty - 2 * _c - _g),
          (_x + _ta - _c, _ty - 3 * _c - _g), (_x + _c, _ty - 3 * _c - _g), (_x, _ty - 4 * _c - _g)]
    _nl = _nl[:-1] + _t + [_nl[-1]]
_nl = [q for q in _nl if not (abs(q[1] - Nl[0][1]) < 1e-6 and q[0] <= dnv[0] + 0.12 + 1e-6)]   # the fan-in replaces N's first stub
add('CSI_D1_N', 'F.Cu', [dnv, (dnv[0], Nl[0][1] + 0.12), (dnv[0] + 0.12, Nl[0][1])] + _nl + [(Nl[-1][0], -6.45), (7.5, -6.8)])
_pe = Pl[-1]
add('CSI_D1_P', 'F.Cu', [dpv, (dpv[0], Pl[0][1] + 0.12), (dpv[0] + 0.12, Pl[0][1])] + Pl + [(_pe[0], -6.75 + (_pe[0] - 6.5)), (6.5, -6.75), (6.5, -6.8)])

u7 = (5.5 + DX - 3.0, -7.0, 5.5 + DX + 3.0, -1.0)   # U7 body, 6 x 6
plan['exempt_box'] = [u7[0] - 0.05, u7[1] - 0.05, u7[2] + 0.05, u7[3] + 0.05]
# D1_N's single length tooth keeps 2W (0.254) to its own line instead of 3W: a 3W tooth would add 0.9 mm where 0.6 is needed.
# Espressif gives no serpentine rule; the meander legs of every pair keep 3W.
plan['self_sep'] = {'CSI_D1_N': 0.254}
json.dump(plan, open(OUTJ, 'w'), indent=0)
print('plan written', OUTJ)
