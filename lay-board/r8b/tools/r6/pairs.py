# -*- coding: utf-8 -*-
"""usage: pairs.py <pcb> [<pcb2>]: pad-edge to pad-edge path length of each differential line along its routed tree, skew and corner angles.
Length follows the review's s2_pairs.py: longest pad-to-pad path through the net's own segments and vias, minus the part inside the end pads. Delay 5.72 ps/mm (review's solved value)."""
import collections
import math
import sys

import brd
from shapely.geometry import LineString, Point

PAIRS = [('D2', 'D2_P', 'D2_N', 606), ('D1', 'D1_P', 'D1_N', 606), ('D0', 'D0_P', 'D0_N', 606), ('CK', 'CK_P', 'CK_N', 606), ('CSI_D0', 'CSI_D0_P', 'CSI_D0_N', 1029), ('CSI_D1', 'CSI_D1_P', 'CSI_D1_N', 1029), ('CSI_CK', 'CSI_CK_P', 'CSI_CK_N', 1029)]


def key(p):
    return (round(p[0], 3), round(p[1], 3))


def net_graph(B, net):
    g = collections.defaultdict(list)
    segs = [s for s in B['segs'] if s['net'] == net]
    for s in segs:
        L = math.dist(s['a'], s['b'])
        g[(key(s['a']), s['layer'])].append(((key(s['b']), s['layer']), L))
        g[(key(s['b']), s['layer'])].append(((key(s['a']), s['layer']), L))
    for v in [v for v in B['vias'] if v['net'] == net]:
        nodes = [n for n in list(g) if math.dist(n[0], (v['x'], v['y'])) < 0.02]
        for a in nodes:
            for b in nodes:
                if a != b:
                    g[a].append((b, 0.0))
    # T junctions inside a segment are not nodes here; the hand routed nets have none
    return g


def path_len(B, net):
    """Longest shortest-path between nodes that lie in a pad of that net, less the run inside the pads."""
    g = net_graph(B, net)
    pads = [q for q in B['pads'] if q['net'] == net]
    term = {}
    for n in g:
        for q in pads:
            if n[1] in brd.pad_layers(q) and brd.pad_poly(q).buffer(0.001).contains(Point(n[0])):
                term[n] = q
    best = (0, None)
    for a in term:
        dist = {a: 0.0}
        todo = [a]
        while todo:
            u = min(todo, key=lambda x: dist[x])
            todo.remove(u)
            for v, w in g[u]:
                d = dist[u] + w
                if v not in dist or d < dist[v] - 1e-9:
                    dist[v] = d
                    todo.append(v)
        for b, d in dist.items():
            if b in term and term[b]['ref'] + term[b]['num'] != term[a]['ref'] + term[a]['num'] and d > best[0]:
                best = (d, (a, b))
    return best[0], len([s for s in B['segs'] if s['net'] == net])


def corners(B, net):
    """Deflection angle at every 2-segment node on one layer: 0 straight, 90 a right angle."""
    ang = []
    at = collections.defaultdict(list)
    for s in B['segs']:
        if s['net'] == net:
            at[(key(s['a']), s['layer'])].append((key(s['a']), key(s['b'])))
            at[(key(s['b']), s['layer'])].append((key(s['b']), key(s['a'])))
    for (p, ly), v in at.items():
        if len(v) == 2:
            a, b = v[0][1], v[1][1]
            u1 = (p[0] - a[0], p[1] - a[1])
            u2 = (b[0] - p[0], b[1] - p[1])
            n = math.hypot(*u1) * math.hypot(*u2)
            if n > 0:
                ang.append((round(math.degrees(math.acos(max(-1, min(1, (u1[0] * u2[0] + u1[1] * u2[1]) / n)))), 1), p))
    return ang


for pcb in sys.argv[1:]:
    B = brd.load(pcb)
    print(pcb)
    print(f'{"pair":8s}{"P mm":>9s}{"N mm":>9s}{"skew mm":>9s}{"ps":>7s}{"%UI":>7s}{"vias P/N":>9s}  90deg  acute  widths')
    for name, p, n, ui in PAIRS:
        lp, _ = path_len(B, p)
        ln, _ = path_len(B, n)
        vp = sum(v['net'] == p for v in B['vias'])
        vn = sum(v['net'] == n for v in B['vias'])
        a = corners(B, p) + corners(B, n)
        c90 = sum(abs(x[0] - 90) < 2 for x in a)
        acute = sum(x[0] > 92 for x in a)
        ws = sorted({s['w'] for s in B['segs'] if s['net'] in (p, n)})
        sk = abs(lp - ln)
        print(f'{name:8s}{lp:9.3f}{ln:9.3f}{sk:9.3f}{sk * 5.72:7.1f}{sk * 5.72 / ui * 100:7.2f}{vp:6d}/{vn:<3d}{c90:6d}{acute:7d}  {ws}')
    # same list of 90 degree corners for the record
    for nm in ('CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N', 'USB_DP', 'USB_DN', 'USB2_DP', 'USB2_DN'):
        c = [x for x in corners(B, nm) if abs(x[0] - 90) < 2]
        if c:
            print('  90 deg', nm, c)
