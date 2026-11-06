# -*- coding: utf-8 -*-
"""Hole to copper clearance, measured on the files the factory receives: the Excellon drills and all copper Gerbers.

KiCad's DRC has one limit for every hole. JLCPCB's limits depend on the hole type and the layer, so they are checked here.
Limits are JLCPCB's public capabilities page, https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-11-06:
  Via hole to track 0.2. Inner layer via hole to copper 0.2.                 Here: VIA hole, any layer, other-net copper, 0.20
  NPTH to track 0.2.                                                         Here: NPTH hole, any layer, ANY copper, 0.20
  PTH to track 0.28 minimum, 0.35 recommended.                               Here: PTH hole, outer layers, other-net copper, 0.28
  Inner layer PTH pad hole to copper 0.3.                                    Here: PTH hole, inner layers, other-net copper, 0.30
The page words the outer limits as "to track". Here they cover every other-net copper object, pads and zones as well, which
is stricter, because a drill that wanders can short to a pad as easily as to a track.

Distance is from the hole edge at the diameter in the drill file, to the copper polygon.

Same-net exemption, for plated holes only: copper of the hole's own net is not measured, and neither is the hole's own pad
on an unconnected pin. That covers its annular ring, thermal spokes, zone connections, and same-net tracks and vias.
A plated hole is meant to join that copper, and a wandering drill that reaches it cannot make a short. Copper with no net
name, or marked N/C, is never treated as same net. NPTH holes have no net and get no exemption.
The exempted objects are counted in the report so that the exemption is visible.

The net of a plated hole is read from the pad flashed at its centre on both outer layers. A hole with no pad there, or with
different nets on the two sides, is an error rather than a guess. The hole list and copper layer count must also agree with
the drill file's own header, so a package missing a layer cannot pass by having less copper to measure.

usage: holecheck.py <gerber dir or zip> [--list]     exit 0 pass, 1 fail, 2 could not parse
       holecheck.py --selftest
"""
import os
import re
import shutil
import sys
import tempfile
import zipfile

from shapely import STRtree
from shapely.geometry import LineString, Point

from maskcheck import GerberError, _pos, parse

VIA_MIN = 0.20
NPTH_MIN = 0.20
PTH_OUTER_MIN = 0.28
PTH_INNER_MIN = 0.30
PTH_RECOMMENDED = 0.35  # JLC's recommendation, reported only
EPS = 2e-4  # same tolerance as maskcheck; hole distances are exact to the 1 nm Gerber grid, zone arcs are chords
SEARCH = 0.45  # measure everything this close, so the report can show margin above each limit
NO_NET = ('', 'N/C')


def _read(src):
    if os.path.isdir(src):
        return [(n, open(os.path.join(src, n), encoding='utf-8', errors='replace').read()) for n in sorted(os.listdir(src))]
    z = zipfile.ZipFile(src)
    return [(n, z.read(n).decode('utf-8', 'replace')) for n in sorted(z.namelist())]


def parse_drill(text, name=''):
    """Returns (plated, total copper layers, holes). Each hole is dict(kind, dia, a, b): b differs from a for a slot."""
    if '; FORMAT={-:-/ absolute / metric / decimal}' not in text or 'METRIC' not in text:
        raise GerberError(f'{name}: drill file is not absolute metric decimal')
    ff = re.search(r'TF\.FileFunction,(Plated|NonPlated),1,(\d+),(PTH|NPTH)', text)
    if not ff:
        raise GerberError(f'{name}: drill file has no plated or non-plated function')
    plated = ff[1] == 'Plated'
    tools, func, cur, holes = {}, None, None, []
    header = True
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'; #@! TA\.AperFunction,(\w+),(\w+),(\w+)', line)
        if m:
            func = m[3]
            continue
        if line.startswith(';') or line in ('M48', 'G90', 'G05', 'M30') or line.startswith('FMAT') or line == 'METRIC':
            continue
        if line == '%':
            header = False
            continue
        m = re.fullmatch(r'T(\d+)C([\d.]+)', line)
        if m and header:
            tools[int(m[1])] = (float(m[2]), func)
            continue
        m = re.fullmatch(r'T(\d+)', line)
        if m:
            if int(m[1]) not in tools:
                raise GerberError(f'{name}: undefined tool {line}')
            cur = int(m[1])
            continue
        n = r'(-?\d+(?:\.\d+)?)'
        m = re.fullmatch(rf'X{n}Y{n}(?:G85X{n}Y{n})?', line)
        if not m or cur is None:
            raise GerberError(f'{name}: unknown drill line {line!r}')
        a = (float(m[1]), float(m[2]))
        b = (float(m[3]), float(m[4])) if m[3] else a
        dia, f = tools[cur]
        if not plated:
            kind = 'NPTH'
        elif f == 'ViaDrill':
            kind = 'VIA'
        elif f == 'ComponentDrill':
            kind = 'PTH'
        else:
            raise GerberError(f'{name}: plated tool T{cur} has unknown function {f!r}')
        holes.append(dict(kind=kind, dia=dia, a=a, b=b))
    return plated, int(ff[2]), holes


def _check_regions(text, objs, label):
    """Zone regions can be cut into one outline. Shapely's repair must keep the area the Gerber's own outline encloses."""
    regions = [o for o in objs if o['kind'] == 'region']
    k = 0
    for body in re.findall(r'G36\*(.*?)G37\*', text, re.S):
        for contour in re.split(r'(?=X-?\d+Y-?\d+D02\*)', body):
            p = [(int(x), int(y)) for x, y in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]\*', contour)]
            if len(p) < 3:
                continue
            area = abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2 / 1e12
            if k >= len(regions):
                raise GerberError(f'{label}: more region outlines than parsed polygons')
            got = regions[k]['geom'].area
            if abs(got - area) > max(1e-4, area * 1e-4):
                raise GerberError(f'{label}: region near {_pos(regions[k]["at"])} parsed as {got:.5f} mm2, its outline encloses {area:.5f} mm2')
            k += 1
    if k != len(regions):
        raise GerberError(f'{label}: {len(regions)} polygons but {k} region outlines')
    return k


def load(src):
    """Copper layers, by TF.FileFunction, and holes, with the checks that make a missing input an error."""
    copper, holes, counts, files = {}, [], set(), set()
    for n, t in _read(src):
        if n.endswith('.drl'):
            plated, total, h = parse_drill(t, n)
            files.add('PTH' if plated else 'NPTH')
            counts.add(total)
            holes += h
        elif n.endswith('.gbr'):
            m = re.search(r'%TF\.FileFunction,Copper,L(\d+),(Top|Inr|Bot)\*%', t)
            if m:
                if int(m[1]) in copper:
                    raise GerberError(f'two files claim copper layer L{m[1]}')
                copper[int(m[1])] = dict(name=n, side=m[2], objs=parse(t))
                copper[int(m[1])]['regions'] = _check_regions(t, copper[int(m[1])]['objs'], n)
    if files != {'PTH', 'NPTH'}:
        raise GerberError(f'both PTH and NPTH drill files are required, found {sorted(files)}')
    if len(counts) != 1:
        raise GerberError(f'drill files disagree on the layer count {counts}')
    total = counts.pop()
    if sorted(copper) != list(range(1, total + 1)):
        raise GerberError(f'drill files say {total} copper layers, found L{sorted(copper)}')
    if copper[1]['side'] != 'Top' or copper[total]['side'] != 'Bot' or any(copper[i]['side'] != 'Inr' for i in range(2, total)):
        raise GerberError('copper layer sides are not Top, inner, Bot')
    empty = [i for i in copper if not copper[i]['objs']]
    if empty:
        raise GerberError(f'copper layers {empty} are empty')
    return copper, holes, total


def _flash_at(objs, tree, pt):
    return [objs[i] for i in tree.query(pt, predicate='intersects') if objs[i]['kind'] == 'flash']


def _label(o):
    if o['pad']:
        return f"{o['pad'][0]}.{o['pad'][1]}"
    what = {'ViaPad': 'via', 'Conductor': 'track', 'Zone': 'zone'}.get(o['func'], o['func'] or o['kind'])
    return f"{what}{_pos(o['at'])}"


def check(src):
    copper, holes, total = load(src)
    trees = {i: STRtree([o['geom'] for o in c['objs']]) for i, c in copper.items()}
    for h in holes:
        h['line'] = LineString([h['a'], h['b']]) if h['a'] != h['b'] else Point(h['a'])
        mid = Point((h['a'][0] + h['b'][0]) / 2, (h['a'][1] + h['b'][1]) / 2)
        h['pad'] = h['net'] = None
        h['label'] = f"{h['kind']}{_pos(h['a'])}"
        if h['kind'] == 'NPTH':
            continue
        top = _flash_at(copper[1]['objs'], trees[1], mid)
        bot = _flash_at(copper[total]['objs'], trees[total], mid)
        if not top or not bot:
            raise GerberError(f"plated hole {h['label']} has no pad flashed on {'the top' if not top else 'the bottom'}")
        nets = {o['net'] or '' for o in top + bot}
        if len(nets) != 1:
            raise GerberError(f"plated hole {h['label']} sits on pads of different nets {sorted(nets)}")
        h['net'] = nets.pop()
        padded = [o for o in top + bot if o['pad']]
        if padded:
            h['pad'] = padded[0]['pad']
            h['label'] = f"{h['pad'][0]}.{h['pad'][1]}"
        elif h['kind'] == 'VIA':
            h['label'] = f"via{_pos(h['a'])}"

    rows, exempt = [], {}
    for h in holes:
        r = h['dia'] / 2
        for i, c in copper.items():
            inner = c['side'] == 'Inr'
            limit = {'VIA': VIA_MIN, 'NPTH': NPTH_MIN, 'PTH': PTH_INNER_MIN if inner else PTH_OUTER_MIN}[h['kind']]
            for k in trees[i].query(h['line'], predicate='dwithin', distance=r + SEARCH).tolist():
                o = c['objs'][k]
                if h['kind'] != 'NPTH':
                    same = (h['net'] not in NO_NET and o['net'] == h['net']) or (h['pad'] and o['pad'] == h['pad'])
                    if same:
                        key = (h['kind'], o['func'] or o['kind'])
                        exempt[key] = exempt.get(key, 0) + 1
                        continue
                gap = o['geom'].distance(h['line']) - r
                rows.append(dict(kind=h['kind'], hole=h['label'], dia=h['dia'], hnet=h['net'], layer=f"L{i}", inner=inner, gap=round(gap, 4), limit=limit,
                                 other=_label(o), onet=o['net'], at=_pos(h['a'])))
    rows.sort(key=lambda x: x['gap'])
    res = dict(rows=rows, exempt=exempt, layers=total, regions=sum(c['regions'] for c in copper.values()), holes={k: sum(h['kind'] == k for h in holes) for k in ('VIA', 'PTH', 'NPTH')})
    res['fails'] = [x for x in rows if x['gap'] < x['limit'] - EPS]
    res['ok'] = not res['fails']
    res['min'] = {}
    for x in rows:
        k = (x['kind'], 'inner' if x['inner'] else 'outer')
        if k not in res['min'] or x['gap'] < res['min'][k]['gap']:
            res['min'][k] = x
    return res


def summary(res):
    parts = []
    for k, lim in ((('VIA', 'outer'), VIA_MIN), (('VIA', 'inner'), VIA_MIN), (('NPTH', 'outer'), NPTH_MIN), (('NPTH', 'inner'), NPTH_MIN), (('PTH', 'outer'), PTH_OUTER_MIN), (('PTH', 'inner'), PTH_INNER_MIN)):
        m = res['min'].get(k)
        parts.append(f"{k[0]} {k[1]} min {m['gap'] if m else 'none near'} (limit {lim})")
    return f"{len(res['fails'])} under limit; " + ', '.join(parts) + f"; holes {res['holes']} on {res['layers']} copper layers"


def report(res, out=sys.stdout, rows=False):
    print(summary(res), file=out)
    print('limits: JLCPCB capabilities page, 2026-11-06. Same-net copper on plated holes is exempt, NPTH has no exemption.', file=out)
    print(f"same-net objects exempted, by hole type and object: {dict(sorted(res['exempt'].items()))}", file=out)
    print(f"zone regions whose parsed area was checked against the outline: {res['regions']}", file=out)
    pth = [x for x in res['rows'] if x['kind'] == 'PTH']
    print(f"PTH holes, closest other-net copper within {SEARCH} mm of the hole edge: {len(pth)} objects ({sum(x['gap'] < PTH_RECOMMENDED for x in pth)} under the {PTH_RECOMMENDED} JLC recommends)", file=out)
    for x in pth[:12]:
        print(f"  {x['gap']:.4f} limit {x['limit']} {x['hole']} [{x['hnet']}] {x['layer']} to {x['other']} [{x['onet']}]", file=out)
    npth = [x for x in res['rows'] if x['kind'] == 'NPTH']
    print(f"NPTH hole wall to any copper, reported margin above the {NPTH_MIN} limit. {res['holes']['NPTH']} holes:", file=out)
    closest = {}
    for x in npth:
        if x['at'] not in closest or x['gap'] < closest[x['at']]['gap']:
            closest[x['at']] = x
    for at, x in sorted(closest.items()):
        print(f"  {at} {x['gap']:.4f}, margin {x['gap'] - NPTH_MIN:.4f}, {x['layer']} to {x['other']} [{x['onet']}]", file=out)
    if not npth:
        print(f"  no copper within {SEARCH} mm", file=out)
    print(f"under limit: {len(res['fails'])}", file=out)
    for x in res['fails']:
        print(f"  {x['gap']:.4f} limit {x['limit']} {x['kind']} {x['hole']} [{x['hnet']}] {x['layer']} to {x['other']} [{x['onet']}]", file=out)
    if rows:
        for x in res['rows']:
            print(f"  {x['gap']:.4f} limit {x['limit']} {x['kind']} {x['hole']} [{x['hnet']}] {x['layer']} to {x['other']} [{x['onet']}]", file=out)
    print('RESULT ' + ('PASS' if res['ok'] else 'FAIL'), file=out)


def selftest():
    """Known geometry on a small synthetic package. Every limit is tested on both sides, and missing inputs must stop it."""
    head = '%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nG01*\n'
    ap = '%TA.AperFunction,ViaPad*%\n%ADD10C,0.400000*%\n%TD*%\n%TA.AperFunction,ComponentPad*%\n%ADD11C,1.000000*%\n%TD*%\n%TA.AperFunction,Conductor*%\n%ADD12C,0.100000*%\n%TD*%\n'

    def um(v):
        return str(round(v * 1e6))

    def flash(d, x, y, net, pad=None):
        p = f'%TO.P,{pad[0]},{pad[1]}*%\n' if pad else ''
        return f'{p}%TO.N,{net}*%\nD{d}*\nX{um(x)}Y{um(y)}D03*\n%TD*%\n'

    def track(x, y0, y1, net):
        # a vertical 0.1 wide track whose left edge is x
        return f'%TO.N,{net}*%\nD12*\nX{um(x + 0.05)}Y{um(y0)}D02*\nX{um(x + 0.05)}Y{um(y1)}D01*\n%TD*%\n'

    def layer(n, side, body):
        return f'%TF.FileFunction,Copper,L{n},{side}*%\n{head}{ap}{body}M02*\n'

    def drill(func, n, lines, tools):
        h = f'M48\n; FORMAT={{-:-/ absolute / metric / decimal}}\n; #@! TF.FileFunction,{func},1,{n},{"PTH" if func == "Plated" else "NPTH"}\nFMAT,2\nMETRIC\n'
        for t, (dia, f) in tools.items():
            h += f'; #@! TA.AperFunction,{func},{"PTH" if func == "Plated" else "NPTH"},{f}\nT{t}C{dia:.3f}\n'
        return h + '%\nG90\nG05\n' + lines + 'M30\n'

    tmp = tempfile.mkdtemp(prefix='holecheck_')

    def build(outer='', inner='', pth='', npth='T1\nX9.0Y9.0\n', layers=(1, 2, 3, 4), pads=True):
        d = tempfile.mkdtemp(dir=tmp)
        n = 4
        own = (flash(10, 0, 0, 'A') + flash(11, 5, 0, 'B', ('J1', '1'))) if pads else ''
        for i, side in ((1, 'Top'), (2, 'Inr'), (3, 'Inr'), (4, 'Bot')):
            if i in layers:
                body = own + (inner if side == 'Inr' else outer)
                open(f'{d}/L{i}.gbr', 'w').write(layer(i, side, body or ''))
        open(f'{d}/p-PTH.drl', 'w').write(drill('Plated', n, 'T1\nX0.0Y0.0\nT2\nX5.0Y0.0\n' + pth, {1: (0.2, 'ViaDrill'), 2: (0.6, 'ComponentDrill')}))
        open(f'{d}/p-NPTH.drl', 'w').write(drill('NonPlated', n, npth, {1: (2.0, 'ComponentDrill')}))
        return d

    def expect(d, ok, gap=None):
        r = check(d)
        assert r['ok'] == ok, (r['ok'], ok, summary(r), r['fails'][:3])
        if gap is not None:
            got = r['fails'][0]['gap'] if not ok else min(x['gap'] for x in r['rows'] if x['gap'] < 0.40)
            assert abs(got - gap) < 1e-3, (got, gap)
        return r

    try:
        # via hole radius 0.1 at x=0
        expect(build(outer=track(0.31, -1, 1, 'X')), True, 0.21)  # via outer, 0.21
        expect(build(outer=track(0.29, -1, 1, 'X')), False, 0.19)  # via outer, 0.19
        expect(build(inner=track(0.31, -1, 1, 'X')), True, 0.21)  # via inner
        expect(build(inner=track(0.29, -1, 1, 'X')), False, 0.19)
        # PTH hole radius 0.3 at x=5, so hole edge 5.3; the pad itself is own copper
        expect(build(outer=track(5.58 + 0.01, -1, 1, 'X')), True, 0.29)  # outer 0.29 passes
        expect(build(outer=track(5.57, -1, 1, 'X')), False, 0.27)  # outer 0.27 fails
        expect(build(inner=track(5.61, -1, 1, 'X')), True, 0.31)  # inner 0.31 passes
        expect(build(inner=track(5.59, -1, 1, 'X')), False, 0.29)  # inner 0.29 fails, the same gap passes on an outer layer
        expect(build(outer=track(5.59, -1, 1, 'X')), True, 0.29)
        # same net: exempt on plated holes, including inside the limit
        r = expect(build(outer=track(0.2, -1, 1, 'A'), inner=track(5.4, -1, 1, 'B')), True)
        assert r['exempt'].get(('VIA', 'Conductor')) and r['exempt'].get(('PTH', 'Conductor'))
        # a track with no net is never same net as anything
        expect(build(outer=track(0.2, -1, 1, 'N/C')), False)
        # NPTH hole radius 1 at (9,9): any net, no exemption, on any layer, tracks and a pad
        expect(build(outer=track(10.19 - 0.0, 8, 10, 'A')), False, 0.19)
        expect(build(inner=track(10.19, 8, 10, 'B')), False, 0.19)
        expect(build(inner=track(10.21, 8, 10, 'B')), True, 0.21)
        expect(build(outer=flash(10, 9, 10.39, 'Q')), False, 0.19)
        # NPTH in a zone with a keyhole knockout, the way KiCad plots it: a 6 mm square with a 2.4 mm square hole, gap 0.2 less 0.01
        def zone(half, net='GND', cut=0.0):
            cx, cy = 9.0, 9.0
            pts = [(cx - 3, cy - 3), (cx + 3, cy - 3), (cx + 3, cy), (cx + half, cy), (cx + half, cy - half), (cx - half, cy - half), (cx - half, cy + half), (cx + half, cy + half), (cx + half, cy), (cx + 3, cy), (cx + 3, cy + 3), (cx - 3, cy + 3)]
            s = f'%TO.N,{net}*%\nG36*\nX{um(pts[0][0])}Y{um(pts[0][1])}D02*\n'
            for p in pts[1:] + pts[:1]:
                s += f'X{um(p[0])}Y{um(p[1])}D01*\n'
            return s + 'G37*\n%TD*%\n'
        r = expect(build(inner=zone(1.19)), False, 0.19)
        assert r['regions'] == 2 and abs(r['fails'][0]['gap'] - 0.19) < 1e-3, r['regions']  # the knockout survived the keyhole repair
        expect(build(inner=zone(1.21)), True, 0.21)
        # a slot is measured along its whole length: 0.6 wide, ends at y=-0.5 and +0.5 at x=5, track above the top end
        slot = 'X5.0Y-0.5G85X5.0Y0.5\n'
        d = build(pth=slot, outer=f'%TO.N,X*%\nD12*\nX{um(4)}Y{um(1.05)}D02*\nX{um(6)}Y{um(1.05)}D01*\n%TD*%\n')
        r = check(d)
        assert not r['ok'] and abs(r['fails'][0]['gap'] - 0.2) < 1e-3, r['fails'][:2]  # edge at 0.8, track bottom at 1.0
        # things that must stop it, not pass quietly
        for bad, why in ((lambda: build(layers=(1, 2, 4)), 'missing inner layer'), (lambda: build(pads=False), 'plated hole without a pad'), (lambda: build(pth='X1Y2Q3\n'), 'unknown drill line')):
            try:
                check(bad())
            except GerberError:
                continue
            raise AssertionError(f'{why} was accepted')
        d = build()
        os.remove(f'{d}/p-NPTH.drl')
        try:
            check(d)
        except GerberError:
            pass
        else:
            raise AssertionError('missing NPTH drill file was accepted')
        # different nets on the two sides of one hole
        d = build()
        t = open(f'{d}/L4.gbr').read().replace('%TO.N,A*%', '%TO.N,Z*%')
        open(f'{d}/L4.gbr', 'w').write(t)
        try:
            check(d)
        except GerberError:
            pass
        else:
            raise AssertionError('a hole between two nets was accepted')
        # a keyhole the parser spoils must stop it: a bow tie encloses less than its repair keeps
        objs = [dict(kind='region', geom=Point(0, 0).buffer(1), at=(0, 0))]
        try:
            _check_regions('G36*\nX0Y0D02*\nX1000000Y0D01*\nX1000000Y1000000D01*\nX0Y0D01*\nG37*\n', objs, 'selftest')
        except GerberError:
            pass
        else:
            raise AssertionError('a region whose area changed was accepted')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('selftest ok')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.argv[1] == '--selftest':
        selftest()
        sys.exit(0)
    try:
        r = check(sys.argv[1])
    except GerberError as e:
        print('COULD NOT PARSE', e)
        sys.exit(2)
    report(r, rows='--list' in sys.argv)
    sys.exit(0 if r['ok'] else 1)
