# -*- coding: utf-8 -*-
"""Writes the r4 routing from the r3 routing without running the router again, so every net not named here stays byte-identical.

r4 changed the opto footprint (LTV-357T to EL3H7-G, pads moved) and moved U4 by +0.7 mm in x. This lists, per net, the old
segments and vias to drop and the new ones to add, in design mm (x right, y down as in gen_mini.py). High-speed nets are not named
here; the generator's own prewires for them do not change.

usage: ses_patch_r4.py <r3.ses> <r4.ses>
"""
import math
import re
import sys

UNIT = 10000.0  # SES resolution is um 10, so 1 mm = 10000 units
B, F, I2 = 'B.Cu', 'F.Cu', 'In2.Cu'
W, VIA = 0.127, 'Via400'

# net: dict(drop=[(layer, a, b)], dropv=[pt], add=[(layer, width, [pts...])], addv=[pt])
PATCH = {
    'V2V5': dict(
        drop=[(B, (0.75, 4.06), (0.75, 4.93)), (B, (0.75, 4.93), (1.30, 5.47)), (B, (1.30, 5.47), (2.85, 5.47))],
        add=[(B, 0.2, [(1.45, 4.0625), (1.45, 4.93), (1.99, 5.47), (2.85, 5.47)])]),
    'PWR_C': dict(
        drop=[(B, (0.25, 8.73), (1.42, 8.73)), (B, (1.42, 8.73), (1.42, 9.12)), (B, (1.42, 9.12), (1.18, 9.35)), (B, (1.18, 9.35), (0.25, 9.35)), (I2, (0.25, 9.35), (0.25, 12.51))],
        dropv=[(0.25, 9.35)],
        add=[(B, W, [(0.225, 9.365), (-0.785, 9.365), (-0.95, 9.2)]), (I2, W, [(-0.95, 9.2), (0.25, 10.4), (0.25, 12.51)])],
        addv=[(-0.95, 9.2)]),
    'PWR_E': dict(
        drop=[(B, (0.25, 11.27), (1.40, 11.27)), (B, (1.40, 11.27), (1.40, 11.72)), (B, (-1.61, 13.37), (0.82, 13.37)), (B, (0.82, 13.37), (1.53, 12.67)), (B, (1.53, 12.67), (1.53, 11.85))],
        add=[(B, W, [(0.225, 10.635), (0.85, 10.635), (0.85, 11.17), (1.40, 11.72)]), (B, W, [(-1.61, 13.37), (-1.5454, 13.44), (1.1, 13.44), (1.5274, 13.0126), (1.53, 11.85)])]),
    'ATX_PWR': dict(
        drop=[(B, (-0.77, 10.28), (-0.15, 10.28)), (B, (-0.15, 10.28), (0.36, 10.79)), (B, (0.36, 10.79), (1.51, 10.79))],
        add=[(B, W, [(-0.77, 10.28), (-0.4949, 10.0), (1.2, 10.0), (1.5139, 10.3139), (1.51, 10.79)])]),
    'RST_C': dict(
        drop=[(B, (0.25, 12.33), (-0.92, 12.33)), (B, (-0.92, 12.33), (-0.92, 12.83)), (B, (-0.92, 12.83), (-1.11, 13.02))],
        add=[(B, W, [(0.225, 12.965), (-1.0519, 12.965), (-1.11, 13.02)])]),
    'RST_E': dict(add=[(B, W, [(0.225, 14.235), (0.25, 14.87)])]),
    'RST_LED': dict(
        drop=[(B, (5.23, 12.33), (6.55, 12.33))],
        add=[(B, W, [(6.575, 12.965), (5.869, 12.965), (5.23, 12.33)])]),
    'PWR_LED': dict(
        drop=[(B, (6.55, 8.73), (5.38, 8.73)), (B, (5.38, 8.73), (5.25, 8.87))],
        add=[(B, W, [(6.575, 9.365), (5.75, 9.365), (5.25, 8.87)])]),
    'LED_IN': dict(
        drop=[(B, (13.31, 17.07), (13.95, 16.43))],
        dropv=[(13.31, 17.07)],
        add=[(B, W, [(13.31, 17.07), (13.975, 17.065)])]),
    'LED_K': dict(
        drop=[(B, (12.64, 19.01), (12.74, 19.01)), (B, (12.74, 19.01), (12.78, 18.97)), (B, (13.95, 18.97), (12.78, 18.97))],
        add=[(B, W, [(12.64, 19.01), (13.3221, 18.335), (13.975, 18.335)])]),
    'ATX_LED': dict(
        drop=[(B, (6.88, 18.2), (7.65, 18.97))],
        add=[(B, W, [(6.88, 18.2), (7.015, 18.335), (7.625, 18.335)])]),
    # these two only need their vias off the new pads; their runs are unchanged
    'I2C_SDA': dict(
        drop=[(B, (6.57, 10.65), (6.7, 10.78)), (B, (6.7, 10.78), (9.38, 10.78)), (F, (6.57, 10.65), (8.44, 12.52))],
        dropv=[(6.57, 10.65)],
        add=[(B, W, [(7.63, 10.93), (7.78, 10.78), (9.38, 10.78)]), (F, W, [(7.63, 10.93), (7.63, 11.71), (8.44, 12.52)])],
        addv=[(7.63, 10.93)]),
    'I2C_SCL': dict(
        drop=[(I2, (7.06, 12.82), (7.28, 13.04)), (I2, (7.06, 8.58), (7.06, 12.82)), (F, (7.28, 13.04), (7.28, 13.12))],
        dropv=[(7.28, 13.04)],
        add=[(I2, W, [(7.06, 8.58), (7.0551, 12.2)]), (F, W, [(7.0551, 12.2), (7.28, 12.42), (7.28, 13.12)])],
        addv=[(7.0551, 12.2)]),
}
PLACE = {'U4': (0.5, 5.2)}
TOL = 0.025


def near(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) < TOL


def mm(u):
    return (u[0] / UNIT, -u[1] / UNIT)


def un(p):
    return (round(p[0] * UNIT), round(-p[1] * UNIT))


def rewrite(net, block):
    P = PATCH[net]
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
    # new copper snaps onto surviving copper ends, so nothing opens by a rounding error
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
    for p in P.get('addv', []):
        u = un(p)
        vias.append((VIA, u[0], u[1]))
    txt = [f'(net "{net}"']
    for ly, w, a, b in segs:
        txt.append(f'        (wire\n          (path {ly} {w}\n            {a[0]} {a[1]}\n            {b[0]} {b[1]}\n          )\n        )')
    for name, x, y in vias:
        txt.append(f'        (via {name} {x} {y})')
    return '\n'.join(txt) + '\n      )\n      '


def main(src, dst):
    s = open(src, encoding='utf-8').read()
    for ref, (x, y) in PLACE.items():
        s, n = re.subn(rf'\(place {ref} -?\d+ -?\d+ ', f'(place {ref} {round(x * UNIT)} {round(-y * UNIT)} ', s)
        assert n == 1, ref
    i = s.find('network_out')
    starts = [(m.start() + i, m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', s[i:])]
    out, last, seen = [], 0, set()
    for j, (a, net) in enumerate(starts):
        if net not in PATCH:
            continue
        end = starts[j + 1][0] if j + 1 < len(starts) else s.rfind('\n      )\n    )\n  )\n)')
        out.append(s[last:a])
        out.append(rewrite(net, s[a:end]))
        last = end
        seen.add(net)
    assert seen == set(PATCH), set(PATCH) - seen
    out.append(s[last:])
    open(dst, 'w', encoding='utf-8', newline='\n').write(''.join(out))
    print('patched nets', sorted(seen))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
