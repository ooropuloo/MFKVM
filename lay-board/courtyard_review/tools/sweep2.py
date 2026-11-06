# -*- coding: utf-8 -*-
"""Sweep with real outlines where known, and check candidate moves against parts and B.Cu copper. Read only."""
import sys, itertools, json, math
sys.path.insert(0, sys.argv[1])
import model, parse
from model import rect, pad_poly
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union
fps, P, tree = model.build()


def over(r, w, h, src, height=None):
    fp = fps[r]
    P[r] = model.Part(r, src, height, rect(fp['x'], fp['y'], w, h), rect(fp['x'], fp['y'], w + .2, h + .2))


fq = fps['Q1']
P['Q1'] = model.Part('Q1', 'STD JEDEC TO-236', 1.12, rect(fq['x'], fq['y'], 2.92, 1.3), rect(fq['x'], fq['y'], 3.04, 1.4))
over('U7', 6.0, 6.0, 'DS Toshiba TC358743XBG p14', 1.2)
over('U6', 3.0, 3.0, 'STD VSSOP-8 DGK', 1.1)
for r in ('U3', 'U8', 'U9', 'U14'):
    fp = fps[r]
    xs = [q['x'] for q in fp['pads']]
    ys = [q['y'] for q in fp['pads']]
    if max(xs) - min(xs) > max(ys) - min(ys):
        over(r, 2.5, 1.0, 'STD TI DQA0010A', 0.55)
    else:
        over(r, 1.0, 2.5, 'STD TI DQA0010A', 0.55)
print('=== same side, nominal real outlines, body gap < 0.30 (metal includes leads)')
rows = []
for a, b in itertools.combinations(sorted(P), 2):
    if fps[a]['layer'] != fps[b]['layer']:
        continue
    d = P[a].body.distance(P[b].body)
    m = P[a].metal.distance(P[b].metal)
    if d < 0.30 or m < 0.15:
        i = P[a].body.intersection(P[b].body)
        rows.append((round(d, 3), round(m, 3), a, b, round(i.area, 3), [round(v - 100, 3) for v in i.bounds] if i.area > 0 else None, fps[a]['layer'], P[a].src[:14], P[b].src[:14]))
for r in sorted(rows):
    print(r)

# copper on B.Cu
tracks = []
vias = []
for c in tree:
    if isinstance(c, list) and c and c[0] == 'segment' and parse.get(c, 'layer')[1] == 'B.Cu':
        s, e = parse.get(c, 'start'), parse.get(c, 'end')
        tracks.append((LineString([(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))]).buffer(float(parse.get(c, 'width')[1]) / 2), parse.get(c, 'net')[1]))
    if isinstance(c, list) and c and c[0] == 'via':
        a = parse.get(c, 'at')
        vias.append((Point(float(a[1]), float(a[2])).buffer(float(parse.get(c, 'size')[1]) / 2), parse.get(c, 'net')[1]))


def check(moves, trim=None):
    """moves {ref:(dx,dy)} in mm. Returns collisions with unmoved and moved parts, and foreign copper under the new pads."""
    res = {}
    newbody = {}
    newpads = {}
    from shapely.affinity import translate
    for r, p in P.items():
        dx, dy = moves.get(r, (0, 0))
        if fps[r]['layer'] != 'B.Cu':
            continue
        newbody[r] = translate(p.metal, dx, dy)
        pads = []
        for q in fps[r]['pads']:
            g = translate(pad_poly(q), dx, dy)
            if trim and r in trim:
                # land trimmed at the toe to LITE-ON's recommended 3.75 from centre
                cx = fps[r]['x'] + dx
                minx, miny, maxx, maxy = g.bounds
                if minx < cx:
                    g = box(cx - 3.75, miny, maxx, maxy)
                else:
                    g = box(minx, miny, cx + 3.75, maxy)
            pads.append((g, q['net'], q['n']))
        newpads[r] = pads
    for r in moves:
        fails = []
        for o in newbody:
            if o == r or 'dnp' in fps[o]['attr']:
                continue
            d = newbody[r].distance(newbody[o])
            if d < 0.45:
                fails.append((o, 'body/lead', round(d, 3)))
        for g, n, pn in newpads[r]:
            for o in newpads:
                if o == r:
                    continue
                for g2, n2, pn2 in newpads[o]:
                    d = g.distance(g2)
                    if n != n2 and d < 0.25:
                        fails.append((o + '.' + pn2, r + '.' + pn + ' pad', round(d, 3)))
            hits = set()
            for t, tn in tracks + vias:
                if tn != n and g.distance(t) < 0.09:
                    hits.add(tn)
            if hits:
                fails.append(('foreign copper', r + '.' + pn, sorted(hits)))
        res[r] = dict(nets=sorted({q['net'] for q in fps[r]['pads'] if q['net'] and not q['net'].startswith('unconnected')}), fails=fails)
    return res


scen = {
    'Q1 -0.7x': ({'Q1': (-0.7, 0)}, None),
    'Q1 -0.5x': ({'Q1': (-0.5, 0)}, None),
    'U4 +0.5x': ({'U4': (0.5, 0)}, None),
    'U12 -1.75x': ({'U12': (-1.75, 0)}, None),
    'L1 -0.5y U2 -0.5y': ({'L1': (0, -0.5), 'U2': (0, -0.5)}, None),
    'U10 +0.3y U11 +0.85x +1.05y U12 +1.2x +0.2y L1 U2 -0.5y (trim)': ({'U10': (0, .3), 'U11': (.85, 1.05), 'U12': (1.2, .2), 'L1': (0, -.5), 'U2': (0, -.5)}, {'U10', 'U11', 'U12'}),
    'U4 +0.7x': ({'U4': (0.7, 0)}, None),
    'C17 C19 +0.1y': ({'C17': (0, 0.1), 'C19': (0, 0.1)}, None),
    'C10 C11 +0.05y': ({'C10': (0, 0.05), 'C11': (0, 0.05)}, None),
    'trim toes only': ({'U10': (0, 0), 'U11': (0, 0), 'U12': (0, 0)}, {'U10', 'U11', 'U12'}),
}
for k, (m, t) in scen.items():
    print('---', k)
    for r, v in check(m, t).items():
        print('  ', r, v['nets'], v['fails'])
hs = [n for n in {x[1] for x in tracks} if n.startswith(('TMDS', 'CSI', 'HDMI', 'USB'))]
print('hs nets on B.Cu', sorted(hs)[:40])
for r in ('U10', 'U11', 'U12', 'L1', 'U2', 'Q1', 'U4', 'C10', 'C11', 'J4'):
    near = set()
    g = P[r].metal.buffer(1.2)
    for t, n in tracks:
        if g.intersects(t) and n.startswith(('TMDS', 'CSI', 'USB', 'HDMI', 'SD_', 'I2C', 'DDC')):
            near.add(n)
    print(r, 'near signal nets', sorted(near))
