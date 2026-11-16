# -*- coding: utf-8 -*-
"""usage: power_paths.py <pcb>: resistance of power paths along the routed copper. rho 1.72e-5 ohm.mm; copper 35 um outer, 15.2 um In2 (solver constant for 0.5 oz).
Via barrel: drill d, plating 18 um assumed (not a JLC number), 1.15 mm long. Resistance network solved by nodal analysis between pad nodes."""
import math
import sys

import numpy as np

import brd

RHO = 1.72e-5
T = {'F.Cu': 0.035, 'B.Cu': 0.035, 'In2.Cu': 0.0152}


def key(p):
    return (round(p[0], 2), round(p[1], 2))


def solve(B, net, a, b):
    """a, b are (x, y, layer). Tracks are split where another track's end or a via lands on them. Returns ohms."""
    segs = [s for s in B['segs'] if s['net'] == net]
    vias = [v for v in B['vias'] if v['net'] == net]
    pts = {}
    for s in segs:
        pts.setdefault(s['layer'], []).extend([s['a'], s['b']])
    for v in vias:
        for ly in T:
            pts.setdefault(ly, []).append((v['x'], v['y']))
    for ly in (a[2], b[2]):
        pts.setdefault(ly, [])
    pts[a[2]].append(a[:2])
    pts[b[2]].append(b[:2])
    nodes = {}

    def nid(p, ly):
        return nodes.setdefault((key(p), ly), len(nodes))

    edges = []
    for s in segs:
        L = math.dist(s['a'], s['b'])
        if L < 1e-9:
            continue
        ux, uy = (s['b'][0] - s['a'][0]) / L, (s['b'][1] - s['a'][1]) / L
        on = []
        for p in pts[s['layer']]:
            t = (p[0] - s['a'][0]) * ux + (p[1] - s['a'][1]) * uy
            d = abs((p[0] - s['a'][0]) * uy - (p[1] - s['a'][1]) * ux)
            if -0.03 <= t <= L + 0.03 and d < max(s['w'] / 2, 0.03):
                on.append((max(0, min(L, t)), p))
        on.sort(key=lambda x: x[0])
        for (t0, p0), (t1, p1) in zip(on, on[1:]):
            n0, n1 = nid(p0, s['layer']), nid(p1, s['layer'])
            if n0 != n1 and t1 > t0:
                edges.append((n0, n1, RHO * (t1 - t0) / (s['w'] * T[s['layer']])))
    for v in vias:
        r0 = v['drill'] / 2 + 0.018
        ri = v['drill'] / 2
        Rb = RHO * 1.15 / (math.pi * (r0 * r0 - ri * ri))
        here = [ly for ly in T if (key((v['x'], v['y'])), ly) in nodes]
        for la, lb in zip(here, here[1:]):
            edges.append((nid((v['x'], v['y']), la), nid((v['x'], v['y']), lb), Rb / 2))
    N = len(nodes)
    G = np.zeros((N, N))
    for i, j, r in edges:
        G[i, i] += 1 / r
        G[j, j] += 1 / r
        G[i, j] -= 1 / r
        G[j, i] -= 1 / r
    G += np.eye(N) * 1e-9
    ia, ib = nodes[(key(a[:2]), a[2])], nodes[(key(b[:2]), b[2])]
    I = np.zeros(N)
    I[ia], I[ib] = 1, -1
    V = np.linalg.solve(G, I)
    return V[ia] - V[ib]


pcb = sys.argv[1]
B = brd.load(pcb)
pad = {f"{q['ref']}.{q['num']}": q for q in B['pads']}


def P(n):
    return (pad[n]['x'], pad[n]['y'], 'F.Cu' if pad[n]['side'] == 'F' else 'B.Cu')


for name, net, a, b in (('J5.A4B9 to U2.4', '5V', 'J5.A4B9', 'U2.4'), ('J5.A4B9 to C60.1', '5V', 'J5.A4B9', 'C60.1'), ('J5.A4B9 to U2.1', '5V', 'J5.A4B9', 'U2.1'),
                        ('C60.1 to U2.4', '5V', 'C60.1', 'U2.4'), ('FB5.2 to U7.C3', 'VDDC', 'FB5.2', 'U7.C3'), ('FB5.2 to U7.F5', 'VDDC', 'FB5.2', 'U7.F5'), ('FB5.2 to U7.G2', 'VDDC', 'FB5.2', 'U7.G2')):
    try:
        print(f'{name:22s} {solve(B, net, P(a), P(b)) * 1000:7.1f} mOhm')
    except Exception as e:
        print(name, 'failed', repr(e)[:100])
