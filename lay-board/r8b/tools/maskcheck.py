# -*- coding: utf-8 -*-
"""Solder mask manufacturability check, measured on real polygons from the Gerbers.

KiCad's DRC cannot see a sliver between two openings inside one footprint, so this reads what the
factory reads. Refs and nets come from the X2 attributes on the matching copper layer.

Limits are JLCPCB's public capabilities page, read 2026-11-06, 1 oz copper, green mask:
  soldermask bridge 0.10 mm (black or white: 0.13), and at least 0.09 mm from an opening to a neighbouring trace.

usage: maskcheck.py <gerber dir or zip> [--list]     exit 0 pass, 1 fail, 2 could not parse
       maskcheck.py --selftest
"""
import math
import os
import re
import sys
import zipfile

from shapely import STRtree
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

BRIDGE_MIN = 0.10  # green, red, yellow, blue, purple
BRIDGE_MIN_BW = 0.13  # black, white
TRACE_MIN = 0.09
EPS = 2e-4  # arcs are polygons with 32 segments per quarter, about 0.00006 mm error on the pads used here
QS = 32


class GerberError(Exception):
    pass


def _expr(e, var):
    e = re.sub(r'\$(\d+)', lambda m: f'({var.get(int(m[1]), 0.0)!r})', e).replace('x', '*').replace('X', '*')
    if not re.fullmatch(r'[-+*/().\deE ]+', e):
        raise GerberError(f'macro expression {e!r}')
    return float(eval(e, {'__builtins__': {}}, {}))


def _macro_shape(body, params):
    var = {i + 1: p for i, p in enumerate(params)}
    out = Polygon()
    for prim in body:
        prim = prim.strip()
        if not prim or prim.startswith('0'):
            continue
        m = re.match(r'\$(\d+)=(.*)', prim)
        if m:
            var[int(m[1])] = _expr(m[2], var)
            continue
        f = prim.split(',')
        code = int(f[0])
        a = [_expr(x, var) for x in f[1:]]
        rot = 0.0
        if code == 1:
            shape = Point(a[2], a[3]).buffer(a[1] / 2, quad_segs=QS)
            rot = a[4] if len(a) > 4 else 0.0
        elif code == 20:
            (x0, y0, x1, y1), w = a[2:6], a[1]
            n = math.hypot(x1 - x0, y1 - y0) or 1
            ux, uy = -(y1 - y0) / n * w / 2, (x1 - x0) / n * w / 2
            shape = Polygon([(x0 + ux, y0 + uy), (x1 + ux, y1 + uy), (x1 - ux, y1 - uy), (x0 - ux, y0 - uy)])
            rot = a[6]
        elif code == 21:
            w, h, cx, cy = a[1:5]
            shape = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            rot = a[5]
        elif code == 4:
            n = int(a[1])
            shape = Polygon([(a[2 + 2 * i], a[3 + 2 * i]) for i in range(n + 1)])
            rot = a[2 + 2 * (n + 1)]
        elif code == 5:
            n, cx, cy, dia, rot = int(a[1]), a[2], a[3], a[4], a[5]
            shape = Polygon([(cx + dia / 2 * math.cos(2 * math.pi * i / n), cy + dia / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)])
        else:
            raise GerberError(f'macro primitive {code}')
        if rot:
            shape = rotate(shape, rot, origin=(0, 0))
        out = out.union(shape.buffer(0)) if a[0] else out.difference(shape.buffer(0))
    return out


def _std_aperture(kind, p):
    if len(p) > (1 if kind == 'C' else 3 if kind == 'P' else 2):
        raise GerberError(f'aperture {kind} with a hole or rotation {p}')
    if kind == 'C':
        return Point(0, 0).buffer(p[0] / 2, quad_segs=QS)
    if kind == 'R':
        return box(-p[0] / 2, -p[1] / 2, p[0] / 2, p[1] / 2)
    if kind == 'O':
        w, h = p
        r = min(w, h) / 2
        return LineString([(-(w / 2 - r), -(h / 2 - r)), (w / 2 - r, h / 2 - r)]).buffer(r, quad_segs=QS)
    if kind == 'P':
        n = int(p[1])
        rot = math.radians(p[2]) if len(p) > 2 else 0.0
        return Polygon([(p[0] / 2 * math.cos(rot + 2 * math.pi * i / n), p[0] / 2 * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)])
    raise GerberError(f'aperture {kind}')


def parse(text):
    """Returns objects: dict(geom, kind flash|draw|region, pad, net, func, at). Anything not understood raises."""
    if '%MOMM*%' not in text:
        raise GerberError('units are not mm')
    m = re.search(r'%FSLAX\d(\d)Y\d(\d)\*%', text)
    if not m:
        raise GerberError('no format statement')
    scale = 10 ** int(m[1])
    macros, ap, apfunc = {}, {}, {}
    pad = net = cur = None
    pendfunc = None
    x = y = 0.0
    mode = 'G01'
    region = None
    objs = []

    def add(geom, kind, at):
        objs.append(dict(geom=geom.buffer(0), kind=kind, pad=pad, net=net, func=apfunc.get(cur) if kind != 'region' else 'Zone', at=at))

    def close_contour():
        nonlocal region
        if region and len(region) >= 4:
            add(Polygon(region), 'region', region[0])
        region = []

    for tok in re.finditer(r'%([^%]*)%|([^%*\s][^%*]*)\*', text):
        ext, word = tok[1], tok[2]
        if ext is not None:
            ext = ext.strip()
            if ext.startswith('AM'):
                head, *rest = re.split(r'\*\s*', ext)
                macros[head[2:]] = [r.replace('\n', '') for r in rest if r.strip()]
            elif ext.startswith('ADD'):
                a = re.match(r'ADD(\d+)([A-Za-z_][^,*]*),?([^*]*)\*', ext)
                d, name, raw = int(a[1]), a[2], a[3]
                p = [float(v) for v in raw.split('X') if v]
                ap[d] = _macro_shape(macros[name], p) if name in macros else _std_aperture(name, p)
                apfunc[d] = pendfunc
            elif ext.startswith('TA.AperFunction,'):
                pendfunc = ext[16:].rstrip('*').split(',')[0]
            elif ext.startswith('TO.P,'):
                f = ext[5:].rstrip('*').split(',')
                pad = (f[0], f[1] if len(f) > 1 else '')
            elif ext.startswith('TO.N,'):
                net = ext[5:].rstrip('*')
            elif ext.startswith('TD'):
                what = ext[2:].rstrip('*')
                if what in ('', '.P'):
                    pad = None
                if what in ('', '.N'):
                    net = None
                if what in ('', '.AperFunction'):
                    pendfunc = None
            elif ext.startswith('LPC'):
                raise GerberError('clear polarity is not handled')
            elif ext.startswith(('LM', 'LR', 'LS', 'SR')) and ext.rstrip('*') not in ('LMN', 'LR0', 'LS1', 'SR'):
                raise GerberError(f'unhandled transform {ext}')
            continue
        w = word.strip()
        if w.startswith('G04') or w == 'M02':
            continue
        if w == 'G36':
            region = []
            continue
        if w == 'G37':
            close_contour()
            region = None
            continue
        if w in ('G01', 'G02', 'G03', 'G75', 'G74'):
            if w == 'G74':
                raise GerberError('single quadrant arcs')
            if w != 'G75':
                mode = w
            continue
        m = re.fullmatch(r'(?:G54)?D(\d+)', w)
        if m and int(m[1]) >= 10:
            cur = int(m[1])
            if cur not in ap:
                raise GerberError(f'undefined aperture D{cur}')
            continue
        m = re.fullmatch(r'(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0([123])', w)
        if not m:
            raise GerberError(f'unknown word {w!r}')
        if m[1]:
            mode = m[1]
        nx = int(m[2]) / scale if m[2] else x
        ny = int(m[3]) / scale if m[3] else y
        i = int(m[4]) / scale if m[4] else 0.0
        j = int(m[5]) / scale if m[5] else 0.0
        op = m[6]
        pts = [(x, y), (nx, ny)]
        if op == '1' and mode != 'G01':
            cx, cy = x + i, y + j
            r = math.hypot(x - cx, y - cy)
            a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
            if mode == 'G03' and a1 <= a0:
                a1 += 2 * math.pi
            if mode == 'G02' and a1 >= a0:
                a1 -= 2 * math.pi
            n = max(8, int(abs(a1 - a0) / (math.pi / 2 / QS)))
            pts = [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
        if region is not None:
            if op == '2':
                close_contour()
                region = [(nx, ny)]
            elif op == '1':
                if not region:
                    region = [(x, y)]
                region += pts[1:]
            else:
                raise GerberError('flash inside a region')
        elif op == '3':
            add(translate(ap[cur], nx, ny), 'flash', (nx, ny))
        elif op == '1':
            shape = ap[cur]
            if abs(shape.area - math.pi * (shape.bounds[2] / 1) ** 2) > 0.02 * shape.area:
                raise GerberError(f'draw with a non round aperture D{cur}')
            add(LineString(pts).buffer(shape.bounds[2], quad_segs=QS), 'draw', (nx, ny))
        x, y = nx, ny
    return objs


class Layers:
    """Reads layers from a Gerber directory or zip by their TF.FileFunction, not by file name."""

    def __init__(self, src):
        self.txt = {}
        if os.path.isdir(src):
            items = [(n, open(os.path.join(src, n), encoding='utf-8', errors='replace').read()) for n in sorted(os.listdir(src)) if n.endswith('.gbr')]
        else:
            z = zipfile.ZipFile(src)
            items = [(n, z.read(n).decode('utf-8', 'replace')) for n in sorted(z.namelist()) if n.endswith('.gbr')]
        for n, t in items:
            m = re.search(r'%TF\.FileFunction,([^*]+)\*%', t)
            if not m:
                continue
            f = m[1].split(',')
            if f[0] == 'Soldermask':
                self.txt['mask', f[1][0]] = t
            elif f[0] == 'Copper' and f[-1] in ('Top', 'Bot'):
                self.txt['cu', f[-1][0]] = t
        for k in (('mask', 'T'), ('mask', 'B'), ('cu', 'T'), ('cu', 'B')):
            if k not in self.txt:
                raise GerberError(f'layer {k} is missing from {src}')


def _pos(p):
    return f'({p[0] - 100:.2f},{-p[1] - 100:.2f})'


def _label(o):
    if o['pad']:
        return f"{o['pad'][0]}.{o['pad'][1]}"
    return f"NPTH{_pos(o['at'])}"


def check(src):
    """Returns (report dict). report['bridges'] is every pair of openings under 0.30 mm."""
    ly = Layers(src)
    res = dict(bridges=[], merged=[], trace=[], counts={}, min_bridge=None, min_trace=None, tracenear=[])
    for side, name in (('T', 'F'), ('B', 'B')):
        mask = parse(ly.txt['mask', side])
        cu = parse(ly.txt['cu', side])
        if not mask or not cu:
            raise GerberError(f'{name}: empty layer')
        # name each opening from the copper pad underneath it
        pads = [c for c in cu if c['pad']]
        tree = STRtree([c['geom'] for c in pads])
        unnamed = 0
        for o in mask:
            hits = [pads[i] for i in tree.query(o['geom'], predicate='intersects')]
            hits = sorted(hits, key=lambda c: -c['geom'].intersection(o['geom']).area)
            if hits:
                o['pad'], o['net'] = hits[0]['pad'], hits[0]['net']
            else:
                unnamed += 1
        res['counts'][name] = dict(openings=len(mask), copper=len(cu), not_on_a_pad=unnamed)
        # pair distances
        geoms = [o['geom'] for o in mask]
        tree = STRtree(geoms)
        a, b = tree.query(geoms, predicate='dwithin', distance=0.30)
        for i, j in zip(a.tolist(), b.tolist()):
            if i >= j:
                continue
            g = geoms[i].distance(geoms[j])
            la, lb = _label(mask[i]), _label(mask[j])
            same_pad = mask[i]['pad'] and mask[i]['pad'] == mask[j]['pad']
            if g <= 0:
                if not same_pad:
                    res['merged'].append(dict(side=name, a=la, b=lb, neta=mask[i]['net'], netb=mask[j]['net'], at=_pos(mask[i]['at'])))
                continue
            res['bridges'].append(dict(side=name, gap=round(g, 4), a=la, b=lb, neta=mask[i]['net'], netb=mask[j]['net'], at=_pos(mask[i]['at'])))
        # opening to conductors of another net
        cond = [c for c in cu if not c['pad']]
        tree = STRtree([c['geom'] for c in cond])
        for o in mask:
            for k in tree.query(o['geom'], predicate='dwithin', distance=0.20).tolist():
                c = cond[k]
                if o['net'] and c['net'] == o['net']:
                    continue
                g = o['geom'].distance(c['geom'])
                res['tracenear'].append(dict(side=name, gap=round(g, 4), a=_label(o), net=c['net'], kind=c['func'] or c['kind'], at=_pos(o['at'])))
    res['bridges'].sort(key=lambda r: r['gap'])
    res['tracenear'].sort(key=lambda r: r['gap'])
    res['min_bridge'] = res['bridges'][0]['gap'] if res['bridges'] else None
    res['min_trace'] = res['tracenear'][0]['gap'] if res['tracenear'] else None
    res['under_010'] = [r for r in res['bridges'] if r['gap'] < BRIDGE_MIN - EPS]
    res['under_013'] = [r for r in res['bridges'] if r['gap'] < BRIDGE_MIN_BW - EPS]
    res['trace'] = [r for r in res['tracenear'] if r['gap'] < TRACE_MIN - EPS]
    res['merged_diff'] = [r for r in res['merged'] if r['neta'] != r['netb']]
    res['ok'] = not res['under_010'] and not res['trace'] and not res['merged_diff']
    return res


def summary(res):
    return (f"mask bridge minimum {res['min_bridge']} mm, {len(res['under_010'])} under {BRIDGE_MIN}, "
            f"{len(res['under_013'])} under {BRIDGE_MIN_BW} (black/white only); "
            f"opening to other-net conductor minimum {res['min_trace']} mm, {len(res['trace'])} under {TRACE_MIN}; "
            f"{len(res['merged_diff'])} openings merged across nets; openings {res['counts']}")


def report(res, out=sys.stdout):
    print(summary(res), file=out)
    for title, rows in (('bridges under 0.10', res['under_010']), ('bridges 0.10 to 0.13', [r for r in res['under_013'] if r not in res['under_010']])):
        print(f'{title}: {len(rows)}', file=out)
        for r in rows:
            print(f"  {r['side']} {r['gap']:.3f} {r['a']} [{r['neta']}] | {r['b']} [{r['netb']}] near {r['at']}", file=out)
    print(f"openings merged across nets: {len(res['merged_diff'])}", file=out)
    for r in res['merged_diff']:
        print(f"  {r['side']} {r['a']} [{r['neta']}] | {r['b']} [{r['netb']}] near {r['at']}", file=out)
    print(f"opening to conductor under {TRACE_MIN}: {len(res['trace'])}", file=out)
    for r in res['trace']:
        print(f"  {r['side']} {r['gap']:.3f} {r['a']} to {r['kind']} [{r['net']}] near {r['at']}", file=out)
    print('RESULT ' + ('PASS' if res['ok'] else 'FAIL'), file=out)


def selftest():
    """Known geometry, including a rotated pad that a bounding box would misjudge."""
    head = '%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nG01*\n'
    am = '%AMRoundRect*\n0 c*\n4,1,4,$2,$3,$4,$5,$6,$7,$8,$9,$2,$3,0*\n1,1,$1+$1,$2,$3*\n1,1,$1+$1,$4,$5*\n1,1,$1+$1,$6,$7*\n1,1,$1+$1,$8,$9*\n20,1,$1+$1,$2,$3,$4,$5,0*\n20,1,$1+$1,$4,$5,$6,$7,0*\n20,1,$1+$1,$6,$7,$8,$9,0*\n20,1,$1+$1,$8,$9,$2,$3,0*%\n'
    # two 0.3 x 1.0 rectangles, centres 0.4 apart: gap 0.1
    o = parse(head + '%ADD10R,0.300000X1.000000*%\nD10*\nX0Y0D03*\nX400000Y0D03*\nM02*\n')
    assert abs(o[0]['geom'].distance(o[1]['geom']) - 0.1) < 1e-6
    # a square rotated 45 degrees through RoundRect corners: half diagonal 0.5 + radius 0.05
    o = parse(head + am + '%ADD11RoundRect,0.050000X0X-0.500000X0.500000X0X0X0.500000X-0.500000X0X0*%\nD11*\nX0Y0D03*\nM02*\n')
    g = o[0]['geom']
    assert abs(g.bounds[2] - 0.55) < 1e-3 and g.contains(Point(0.45, 0)) and not g.contains(Point(0.4, 0.4))
    # the same diamond beside a flat bar, against distances computed directly
    o2 = parse(head + '%ADD10R,1.000000X0.200000*%\n' + am + '%ADD11RoundRect,0.000000X0X-0.500000X0.500000X0X0X0.500000X-0.500000X0X0*%\nD11*\nX0Y0D03*\nD10*\nX1000000Y1000000D03*\nM02*\n')
    d = o2[0]['geom'].distance(o2[1]['geom'])
    edge = Polygon([(0, -0.5), (0.5, 0), (0, 0.5), (-0.5, 0)]).distance(box(0.5, 0.9, 1.5, 1.1))
    assert abs(d - edge) < 1e-6 and d > 0.5, d
    # circle drawn along a line, oval, and a region with an arc
    o = parse(head + '%ADD12C,0.200000*%\n%ADD13O,1.000000X0.400000*%\nD12*\nX0Y0D02*\nX1000000Y0D01*\nD13*\nX0Y2000000D03*\nG36*\nX5000000Y0D02*\nG75*\nG03*\nX5000000Y0I1000000J0D01*\nG37*\nM02*\n')
    assert abs(o[0]['geom'].area - (0.2 + math.pi * 0.01)) < 1e-3
    assert abs(o[1]['geom'].area - (0.6 * 0.4 + math.pi * 0.04)) < 1e-3
    assert abs(o[2]['geom'].area - math.pi) < 1e-2, o[2]['geom'].area
    # things it does not understand must stop it, not pass silently
    for bad in ('%LPC*%\n', 'G91*\n', '%ADD14R,1X1X0.5*%\n'):
        try:
            parse(head + bad + 'M02*\n')
        except GerberError:
            continue
        raise AssertionError(f'{bad!r} was accepted')
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
    report(r)
    sys.exit(0 if r['ok'] else 1)
