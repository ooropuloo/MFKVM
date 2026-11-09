# -*- coding: utf-8 -*-
"""Read-only board access for the r6 measurements: parses a saved .kicad_pcb into tracks, vias, pads and zone fills, per net and layer.

The parser follows the independent review's pcbparse.py (KiCad 10 files: footprint transform block, nets by name).
Coordinates are board mm as in the file (design + 100).
"""
import math
import re
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid
from shapely import affinity


def tokenize(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            i += 1
        elif c in '()':
            yield c
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while s[j] != '"':
                if s[j] == chr(92):
                    j += 1
                buf.append(s[j])
                j += 1
            yield ('s', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()"':
                j += 1
            yield s[i:j]
            i = j


def parse(s):
    stack = [[]]
    for t in tokenize(s):
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        elif isinstance(t, tuple):
            stack[-1].append(t[1])
        else:
            stack[-1].append(t)
    return stack[0][0]


def find(n, key):
    for c in n:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def findall(n, key):
    return [c for c in n if isinstance(c, list) and c and c[0] == key]


def rot(x, y, deg):
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def load(path):
    root = parse(open(path, encoding='utf-8').read())
    B = dict(segs=[], vias=[], zones=[], fps={}, pads=[], edges=[])
    for c in root[1:]:
        if not isinstance(c, list):
            continue
        k = c[0]
        if k == 'segment':
            s, e = find(c, 'start'), find(c, 'end')
            B['segs'].append(dict(a=(float(s[1]), float(s[2])), b=(float(e[1]), float(e[2])), w=float(find(c, 'width')[1]), layer=find(c, 'layer')[1], net=find(c, 'net')[1]))
        elif k == 'via':
            at = find(c, 'at')
            B['vias'].append(dict(x=float(at[1]), y=float(at[2]), size=float(find(c, 'size')[1]), drill=float(find(c, 'drill')[1]), net=find(c, 'net')[1]))
        elif k == 'zone':
            n = find(c, 'net')
            nm = find(c, 'net_name')
            z = dict(net=(n[1] if n else ''), layer=(find(c, 'layer') or ['', ''])[1], filled=[], keepout=find(c, 'keepout') is not None, name=nm[1] if nm else '')
            for fp in findall(c, 'filled_polygon'):
                pts = [(float(p[1]), float(p[2])) for p in find(fp, 'pts')[1:] if p[0] == 'xy']
                z['filled'].append(dict(layer=find(fp, 'layer')[1], pts=pts))
            B['zones'].append(z)
        elif k == 'footprint':
            tr = find(c, 'transform')
            if tr:
                tx, ty, r = float(find(tr, 'translate')[1]), float(find(tr, 'translate')[2]), float(find(tr, 'rotate')[1])
            else:
                at = find(c, 'at')
                tx, ty, r = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
            layer = find(c, 'layer')[1]
            ref = next(p[2] for p in findall(c, 'property') if p[1] == 'Reference')
            fp = dict(ref=ref, x=tx, y=ty, rot=r, layer=layer, pads=[])
            for p in findall(c, 'pad'):
                at = find(p, 'at')
                dx, dy = rot(float(at[1]), float(at[2]), r)
                sz = find(p, 'size')
                net = find(p, 'net')
                drill = find(p, 'drill')
                d = dict(ref=ref, num=p[1], kind=p[2], shape=p[3], x=tx + dx, y=ty + dy, w=float(sz[1]), h=float(sz[2]), layers=find(p, 'layers')[1:], net=net[1] if net else None, drill=drill[1:] if drill else None, rot=(float(at[3]) if len(at) > 3 else 0.0) + r, side=layer[0])
                fp['pads'].append(d)
                B['pads'].append(d)
            B['fps'][ref] = fp
    return B


def pad_layers(q):
    out = []
    for ly in q['layers']:
        if ly == '*.Cu':
            out += ['F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu']
        elif ly.endswith('.Cu'):
            out.append(ly)
    return out


def pad_poly(q):
    if q['shape'] == 'circle':
        return Point(q['x'], q['y']).buffer(q['w'] / 2, 24)
    if q['shape'] == 'oval':
        m = min(q['w'], q['h'])
        ax, ay = (q['w'] - m) / 2, (q['h'] - m) / 2
        g = LineString([(-ax, -ay), (ax, ay)]).buffer(m / 2, 24) if (ax or ay) else Point(0, 0).buffer(m / 2, 24)
    else:
        g = box(-q['w'] / 2, -q['h'] / 2, q['w'] / 2, q['h'] / 2)
    if round(q['rot']) % 180 == 90 and q['w'] != q['h']:
        g = affinity.rotate(g, 90, origin=(0, 0))
    return affinity.translate(g, q['x'], q['y'])


def seg_poly(s):
    return LineString([s['a'], s['b']]).buffer(s['w'] / 2, 12)


def via_poly(v):
    return Point(v['x'], v['y']).buffer(v['size'] / 2, 24)


def zone_geom(B, net, layer):
    gs = []
    for z in B['zones']:
        if z['net'] != net:
            continue
        for f in z['filled']:
            if f['layer'] == layer:
                p = Polygon(f['pts'])
                if not p.is_valid:
                    p = make_valid(p)
                gs.append(p)
    return unary_union(gs) if gs else Polygon()


def copper(B, layer, nets=None, exclude=None):
    """Tracks, vias and pads on a layer, optionally for or excluding a net set, as a list of (net, kind, polygon, label)."""
    out = []
    for s in B['segs']:
        if s['layer'] == layer and (nets is None or s['net'] in nets) and (exclude is None or s['net'] not in exclude):
            out.append((s['net'], 'track', seg_poly(s), f"({s['a'][0]:.2f},{s['a'][1]:.2f})-({s['b'][0]:.2f},{s['b'][1]:.2f}) w{s['w']:.3f}"))
    for v in B['vias']:
        if (nets is None or v['net'] in nets) and (exclude is None or v['net'] not in exclude):
            out.append((v['net'], 'via', via_poly(v), f"({v['x']:.2f},{v['y']:.2f})"))
    for q in B['pads']:
        if layer in pad_layers(q) and q['net'] and (nets is None or q['net'] in nets) and (exclude is None or q['net'] not in exclude):
            out.append((q['net'], 'pad', pad_poly(q), f"{q['ref']}.{q['num']}"))
    return out
