# -*- coding: utf-8 -*-
"""Writes the r6 routing from the r5 routing without running the router again, so every net not named here stays byte-identical.

Same method as ses_patch_r4.py: per net, the old segments and vias to drop and the new ones to add, in design mm (x right, y down
as in gen_mini.py). TMDS and LNA_OUT are prewired in gen_mini.py and do not pass through this file.

usage: ses_patch_r6.py <r5.ses> <r6.ses> [power.json]
"""
import json
import math
import re
import sys

UNIT = 10000.0
B, F, I2 = 'B.Cu', 'F.Cu', 'In2.Cu'
W, VIA, VP = 0.127, 'Via400', 'ViaP600'
W5, W5F = 0.6, 0.5   # 5V outer-layer width, provisional until the current budget is in; F is limited by the J5 pad height
W_VDDC_NEW = 0.15    # the new VDDC run on F and B to C19, C20
W_VDDC_TR, W_VDDC_IN2, W_VDDC_PINCH = 0.3, 0.3, 0.27  # VDDC trunk; the pinch is In2 between the V2V5 via and VDD_MIPI

PATCH = {
    # item 9: 5V leaves J5 on F, drops to B next to each VBUS pad through two vias, and reaches C60 and U2 on B. In2 only feeds U6 and the DDC pull-ups now.
    '5V': dict(
        drop=[(I2, (10.56, 6.95), (13.3225, 9.7125)), (I2, (13.3225, 9.7125), (13.5303, 9.7125)),
              (B, (13.6139, 9.7125), (13.5303, 9.7125)), (B, (13.8776, 9.7136), (13.8765, 9.7125)), (B, (13.8765, 9.7125), (13.6139, 9.7125)),
              (B, (13.6139, 9.7125), (13.6139, 9.4723)), (B, (14.95, 10.0248), (14.1888, 10.0248)), (B, (14.1888, 10.0248), (13.8776, 9.7136)),
              (B, (14.95, 10.987), (14.95, 10.0248)), (B, (13.6139, 9.4723), (13.6139, 9.2769)), (B, (13.6139, 9.2769), (13.05, 8.713)),
              (B, (17.6, 11.55), (15.513, 11.55)), (B, (15.513, 11.55), (14.95, 10.987))],
        dropv=[(13.5303, 9.7125)],
        add=[(F, W5F, [(11.5975, 4.9), (13.75, 4.9), (13.75, 4.35)]),
             (B, W5, [(13.2, 4.9), (13.9, 4.9), (14.75, 5.75), (14.75, 6.85), (15.75, 7.85), (15.75, 11.55), (17.6, 11.55)]),
             (B, W5, [(13.75, 4.35), (13.75, 4.9)]),
             (B, W5, [(14.95, 10.987), (15.75, 10.987)]),
             (B, W5, [(13.05, 8.713), (13.6, 9.263), (13.6, 9.85), (15.75, 9.85)]),
             (B, 0.5, [(13.05, 8.3), (13.95, 8.28)])],
        addv=[(13.2, 4.9, VP), (13.75, 4.9, VP), (13.75, 4.35, VP)]),
    # item 7: the C19, C20 branch from the FB5 side goes away; they sit at the far end now
    'VDDC': dict(
        drop=[(B, (10.4, -5.22), (10.6741, -4.9459)), (B, (10.6741, -4.9459), (11.3209, -4.9459)), (B, (11.3209, -4.9459), (13.7497, -2.5171)), (B, (13.7497, -2.5171), (13.7497, -1.1463)),
              (B, (13.7497, -1.1463), (13.7482, -1.1448)), (B, (13.7482, -1.1448), (13.1573, -1.1448)), (B, (13.1573, -1.1448), (12.2623, -0.2498)),
              (B, (12.2623, -0.2498), (11.4642, 0.5483)), (B, (11.4642, 0.5483), (11.38, 0.5483)), (B, (11.38, 1.2), (11.38, 0.5483)), (B, (11.38, 1.2), (10.8033, 1.2)),
              (B, (10.8033, 1.2), (10.8033, 1.3661)), (B, (10.8033, 1.3661), (10.0196, 2.1498)),
              # item 9: the In2 trunk moves a little so it can take W_VDDC_IN2; the B stretch past FB2 and FB3 centres between them
              (B, (10.0196, 2.1498), (8.3137, 2.1498)), (B, (8.3137, 2.1498), (8.1826, 2.0187)),
              (I2, (4.4548, 1.5161), (4.7038, 1.5161)), (I2, (4.7038, 1.5161), (6.2532, 3.0655)), (I2, (6.2532, 3.0655), (6.2532, 6.1793)), (I2, (6.2532, 6.1793), (6.4348, 6.3609)),
              (I2, (6.4348, 6.3609), (6.8057, 6.3609)), (I2, (6.8057, 6.3609), (8.1826, 4.984)), (I2, (8.1826, 4.984), (8.1826, 2.0187)),
              (I2, (4.388, 0.7258), (4.6567, 0.4571)), (I2, (4.6567, 0.4571), (4.6567, -2.2433)), (I2, (4.6567, -2.2433), (4.2, -2.7)),
              (I2, (4.4548, 1.5161), (4.4548, 0.7926)), (I2, (4.4548, 0.7926), (4.388, 0.7258))],
        add=[(F, W_VDDC_NEW, [(1.25, -5.15), (1.2, -5.1), (-0.2, -5.1), (-0.4, -5.3), (-0.4, -5.34)]),
             (B, W_VDDC_TR, [(8.1826, 2.0187), (9.89, 2.0187), (10.0196, 2.1498)]),
             (I2, W_VDDC_IN2, [(8.1826, 2.0187), (8.1826, 5.2674), (6.95, 6.5), (6.5, 6.5), (6.2, 6.2), (6.2, 4.6), (6.325, 4.475)]),
             (I2, W_VDDC_PINCH, [(6.325, 4.475), (6.325, 3.025)]),
             (I2, W_VDDC_IN2, [(6.325, 3.025), (4.4, 1.1), (4.4, 0.65), (4.6567, 0.35), (4.6567, -2.2433), (4.2, -2.7)]),
             (B, W_VDDC_NEW, [(-0.4, -5.34), (-0.92, -5.45)]),
             (B, 0.2, [(-0.92, -5.45), (-0.95, -5.9), (-0.97, -6.4)])],
        addv=[(-0.4, -5.34)]),
    # F1: the x -5.8 column under R43-R47 becomes the VO4 pull-up rail, SD1_VDD runs beside it at x -6.37 and reaches C40, C41 on In2
    'SD1_VDD': dict(
        drop=[(B, (-5.8, 5.0), (-5.8, 6.1)), (B, (-5.8, 6.1), (-5.8, 7.2)), (B, (-5.8, 7.2), (-5.8, 8.3)), (B, (-5.8, 8.3), (-5.8, 9.4)),
              (B, (-5.8, 5.0), (-6.3317, 5.0)), (B, (-5.8, 9.4), (-6.3317, 9.4)), (B, (-5.8, 9.4), (-5.8, 9.9617)), (B, (-5.8, 9.9617), (-5.82, 9.9817)), (B, (-5.82, 9.9817), (-5.82, 10.9)),
              (B, (-6.3684, 8.9232), (-6.3317, 8.9599)), (B, (-6.3317, 8.9599), (-6.3317, 9.4))],
        add=[(B, 0.3, [(-6.3684, 8.9232), (-6.3684, 5.04), (-6.3317, 5.0)]),
             (I2, 0.2, [(-5.7056, 8.9232), (-5.75, 9.0), (-5.75, 11.15), (-5.2, 11.6)]), (B, 0.3, [(-5.2, 11.6), (-5.5, 11.2)])],
        addv=[(-5.2, 11.6)]),
    'LDO_VO4': dict(
        add=[(F, W, [(-6.35, 3.8454), (-6.35, 4.3)]), (B, W, [(-6.35, 4.3), (-5.95, 4.8)]),
             (B, 0.2, [(-5.8, 5.0), (-5.8, 6.1), (-5.8, 7.2), (-5.8, 8.3), (-5.8, 9.4)])],
        addv=[(-6.35, 4.3)]),
    # test pads moved to make room for J8; these nets only serve the pads and the module pins
    'C6_RXD': dict(
        drop=[(I2, (-12.3863, 18.9598), (-10.4121, 16.9856)), (I2, (-10.4121, 16.9856), (-10.4121, 16.448)),
              (B, (-12.3863, 18.9598), (-12.8082, 18.5379)), (B, (-12.8082, 18.5379), (-14.2621, 18.5379)), (B, (-14.2621, 18.5379), (-15.2, 17.6))],
        dropv=[(-12.3863, 18.9598)],
        add=[(B, W, [(-10.4121, 16.448), (-9.65, 15.7), (-8.8, 15.25)])]),
    'C6_TXD': dict(
        drop=[(B, (-11.9425, 18.5961), (-10.443, 18.5961)), (B, (-10.443, 18.5961), (-9.5, 17.6531)), (B, (-9.5, 17.6531), (-9.5, 16.8293)),
              (B, (-12.6292, 18.1525), (-13.0475, 18.1525)), (B, (-13.0475, 18.1525), (-13.6, 17.6)),
              (B, (-11.9425, 18.5961), (-12.3861, 18.1525)), (B, (-12.3861, 18.1525), (-12.6292, 18.1525))],
        add=[(B, W, [(-9.5, 16.8293), (-8.76, 17.2)])]),
    'C6_IO9': dict(
        drop=[(F, (-11.5586, 16.8454), (-10.771, 16.0578)), (F, (-10.771, 16.0578), (-6.427, 16.0578)),
              (B, (-11.5586, 16.8454), (-12.0, 17.2868)), (B, (-12.0, 17.2868), (-12.0, 17.6))],
        dropv=[(-11.5586, 16.8454)],
        add=[(F, W, [(-7.8, 16.25), (-7.8, 16.0578), (-6.427, 16.0578)]), (B, W, [(-7.8, 16.25), (-7.8, 13.7), (-7.4, 13.2)])],
        addv=[(-7.8, 16.25)]),
}
TOL = 0.025


def near(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) < TOL


def mm(u):
    return (u[0] / UNIT, -u[1] / UNIT)


def un(p):
    return (round(p[0] * UNIT), round(-p[1] * UNIT))


def rewrite(net, block, P):
    segs, vias = [], []
    for m in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', block):
        v = [int(t) for t in m.group(3).split()]
        pts = [(v[k], v[k + 1]) for k in range(0, len(v), 2)]
        for a, b in zip(pts, pts[1:]):
            segs.append([m.group(1), int(m.group(2)), a, b])
    for m in re.finditer(r'\(via\s+"?([^"\s)]+)"?\s+(-?\d+)\s+(-?\d+)', block):
        vias.append((m.group(1), int(m.group(2)), int(m.group(3))))
    for ly, a, b in P.get('drop', []):
        hit = [g for g in segs if g[0] == ly and ((near(mm(g[2]), a) and near(mm(g[3]), b)) or (near(mm(g[2]), b) and near(mm(g[3]), a)))]
        assert len(hit) == 1, (net, 'drop', ly, a, b, len(hit))
        segs.remove(hit[0])
    for p in P.get('dropv', []):
        hit = [v for v in vias if near(mm(v[1:]), p)]
        assert len(hit) == 1, (net, 'dropv', p)
        vias.remove(hit[0])
    ends = [mm(e) for g in segs for e in g[2:4]]

    def snap(p):
        for e in ends:
            if near(e, p):
                return un(e)
        return un(p)

    for ly, w, pts in P.get('add', []):
        q = [snap(p) for p in pts]
        for a, b in zip(q, q[1:]):
            if a != b:
                segs.append([ly, round(w * UNIT), a, b])
    for rec in P.get('addv', []):
        u = un(rec[:2])
        vias.append((rec[2] if len(rec) > 2 else VIA, u[0], u[1]))
    for rec in P.get('widen', []):  # (layer, a, b, new width): keeps the geometry, changes only the width
        hit = [g for g in segs if g[0] == rec[0] and ((near(mm(g[2]), rec[1]) and near(mm(g[3]), rec[2])) or (near(mm(g[2]), rec[2]) and near(mm(g[3]), rec[1])))]
        assert len(hit) == 1, (net, 'widen', rec)
        hit[0][1] = round(rec[3] * UNIT)
    txt = [f'(net "{net}"']
    for ly, w, a, b in segs:
        txt.append(f'        (wire\n          (path {ly} {w}\n            {a[0]} {a[1]}\n            {b[0]} {b[1]}\n          )\n        )')
    for name, x, y in vias:
        txt.append(f'        (via {name} {x} {y})')
    return '\n'.join(txt) + '\n      )\n      '


def main(src, dst, widen=None):
    if widen:
        for net, rows in json.load(open(widen, encoding='utf-8')).items():
            PATCH.setdefault(net, {}).setdefault('widen', []).extend(rows)
    s = open(src, encoding='utf-8').read()
    i = s.find('network_out')
    starts = [(m.start() + i, m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', s[i:])]
    out, last, seen = [], 0, set()
    for j, (a, net) in enumerate(starts):
        if net not in PATCH:
            continue
        end = starts[j + 1][0] if j + 1 < len(starts) else s.rfind('\n      )\n    )\n  )\n)')
        out.append(s[last:a])
        out.append(rewrite(net, s[a:end], PATCH[net]))
        last = end
        seen.add(net)
    assert seen == set(PATCH), set(PATCH) - seen
    out.append(s[last:])
    open(dst, 'w', encoding='utf-8', newline='\n').write(''.join(out))
    print('patched nets', sorted(seen))


if __name__ == '__main__':
    main(*sys.argv[1:])
