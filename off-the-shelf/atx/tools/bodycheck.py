# -*- coding: utf-8 -*-
"""Real part outlines on the ATX board, worst case, for every pair on the same side. KiCad's DRC only sees courtyards, so it cannot prove this by itself.

Outlines are written by hand from the makers' drawings, in each footprint's own frame, and do not come from the generator.
Sources:
  LTV-357T  LITE-ON outline, mini/courtyard_review/sources/liteon_ltv357t_p2.png: 4.40 +-0.2 along the leads, 3.85 +-0.3 along the 2.54 pitch,
            lead span 7.00 +0.2/-0.7, lead width 0.40 +-0.1, pitch 2.54 +-0.25, height 2.00 +-0.2.
  SM06B     JST eSH pages 1 and 3, sources/jst_eSH_p1_land.png and p3_header.png: B 8.0 wide, 4.25 housing, 0.7 tail. Land drawing puts the mouth 0.2 inside the mount pad's far edge.
            JST gives no tolerance on the housing. ASSUMPTION: +-0.1.
  R0402     UNI-ROYAL 0402 as in the v2 review: 1.00 +-0.05 x 0.50 +-0.05.
  PIN       Hand soldered 0.64 pin in a 1.4 pad. ASSUMPTION: fillet reaches 0.8 radius, the same cylinder the case check uses.
ASSUMPTION: each part may sit +-0.1 mm from nominal. Rotation error is not modelled. Two parts can move toward each other, so 0.2 comes off each gap.
Pass: every worst case gap at least MIN_GAP, no part body or lead tip over another part's land, and JLC's spacing page where it has a row.

usage: bodycheck.py <design.json>     exit 0 pass, 1 fail
"""
import json
import math
import re
import sys

from shapely.geometry import Point, box
from shapely.ops import unary_union

PLACE = 0.1
MIN_GAP = 0.10
MIN_OPTO_PITCH = 4.45
# each lib: list of (name, x0, y0, x1, y1) in the footprint frame, at worst case size; 'pin' is a circle
OUTLINES = {
    'OPTO_SO4': [('body', -2.3, -2.075, 2.3, 2.075), ('lead', -3.6, -1.645, 3.6, -0.895), ('lead', -3.6, 0.895, 3.6, 1.645)],
    'JST_SM06B': [('body', -4.1, -1.775, 4.1, 2.675), ('tail', -2.75, -2.475, 2.75, -1.775)],
    'R0402': [('body', -0.55, -0.3, 0.55, 0.3)],
}
PIN_R = 0.8
# JLC SMT spacing page, as tabled in the v2 review (mini/courtyard_review/tools/analyze.py): body-or-land to body-or-land, nominal. Connectors have no row.
JLC_RULE = {('R0402', 'R0402'): 0.15, ('OPTO_SO4', 'R0402'): 0.4, ('OPTO_SO4', 'OPTO_SO4'): 0.5}
NOMINAL = {'OPTO_SO4': (2.2, 1.925), 'R0402': (0.5, 0.25)}
# Land pads in the footprint frame, from the official KiCad footprints the board uses: (x, y, w, h)
PADS = {
    'OPTO_SO4': [(-3.15, -1.27, 2.0, 0.64), (-3.15, 1.27, 2.0, 0.64), (3.15, 1.27, 2.0, 0.64), (3.15, -1.27, 2.0, 0.64)],
    'JST_SM06B': [(-2.5 + i, -2.0, 0.6, 1.55) for i in range(6)] + [(-3.8, 1.875, 1.2, 1.8), (3.8, 1.875, 1.2, 1.8)],
    'R0402': [(-0.48, 0, 0.56, 0.62), (0.48, 0, 0.56, 0.62)],
    'PIN_0.9': [(0, 0, 1.4, 1.4)],
}


def shapes(p):
    """Worst case outlines in board coordinates, same rotation rule as the generator's bake()."""
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    if p['lib'] == 'PIN_0.9':
        return [('pin', Point(p['x'], p['y']).buffer(PIN_R, 32))]
    out = []
    for name, x0, y0, x1, y1 in OUTLINES[p['lib']]:
        xs, ys = [], []
        for bx, by in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            xs.append(p['x'] + bx * c + by * s)
            ys.append(p['y'] - bx * s + by * c)
        out.append((name, box(min(xs), min(ys), max(xs), max(ys))))
    return out


def pads(p):
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    out = []
    for x, y, w, h in PADS[p['lib']]:
        cx, cy = p['x'] + x * c + y * s, p['y'] - x * s + y * c
        ww, hh = (w, h) if abs(s) < 0.5 else (h, w)
        out.append(box(cx - ww / 2, cy - hh / 2, cx + ww / 2, cy + hh / 2))
    return out


def land_union(p):
    """Nominal body plus lands, what JLC's page measures."""
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    hx, hy = NOMINAL[p['lib']]
    hx, hy = (hx, hy) if abs(s) < 0.5 else (hy, hx)
    return unary_union(pads(p) + [box(p['x'] - hx, p['y'] - hy, p['x'] + hx, p['y'] + hy)])


def board_positions(pcb):
    """(ref: x, y) of every footprint in a saved .kicad_pcb, with the 100, 100 origin taken off."""
    res = {}
    t = open(pcb, encoding='utf-8').read()
    for blk in re.split(r'\(footprint "atx:', t)[1:]:
        m = re.search(r'\((?:translate|at) ([-\d.]+) ([-\d.]+)', blk)  # this KiCad build saves (transform (translate x y))
        ref = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', blk)[1]
        res[ref] = (float(m[1]) - 100.0, float(m[2]) - 100.0)
    return res


def check(design):
    d = json.load(open(design, encoding='utf-8'))
    parts = d['parts']
    rows, bad, jlc = [], [], []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            best = None
            for na, ga in shapes(a):
                for nb, gb in shapes(b):
                    if ga.intersects(gb):
                        q = ga.intersection(gb).bounds
                        g = -min(q[2] - q[0], q[3] - q[1]) - 2 * PLACE
                    else:
                        g = ga.distance(gb) - 2 * PLACE
                    if best is None or g < best[0]:
                        best = (round(g, 3), na, nb)
            rows.append(dict(a=a['ref'], b=b['ref'], gap=best[0], what=f'{best[1]} / {best[2]}'))
            if best[0] < MIN_GAP:
                bad.append(rows[-1])
            rule = JLC_RULE.get(tuple(sorted((a['lib'], b['lib']))))
            if rule is not None:
                g = round(land_union(a).distance(land_union(b)), 3)
                jlc.append(dict(a=a['ref'], b=b['ref'], gap=g, rule=rule))
                if g < rule:
                    bad.append(dict(a=a['ref'], b=b['ref'], gap=g, what=f'JLC spacing wants {rule}'))
            # a body or lead of one part over a land of the other, after both have moved toward each other
            for u, v in ((a, b), (b, a)):
                for nu, gu in shapes(u):
                    for gv in pads(v):
                        g = gu.distance(gv) - 2 * PLACE
                        if g < 0:
                            bad.append(dict(a=u['ref'], b=v['ref'], gap=round(g, 3), what=f'{nu} over a land'))
    opto = sorted((p['y'], p['ref']) for p in parts if p['lib'] == 'OPTO_SO4')
    pitch = [round(y1 - y0, 3) for (y0, _), (y1, _) in zip(opto, opto[1:])]
    if any(v < MIN_OPTO_PITCH for v in pitch):
        bad.append(dict(a='opto', b='pitch', gap=min(pitch), what=f'under {MIN_OPTO_PITCH}'))
    rows.sort(key=lambda r: r['gap'])
    jlc.sort(key=lambda r: r['gap'] - r['rule'])
    return dict(ok=not bad, bad=bad, rows=rows, pitch=pitch, jlc=jlc)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    r = check(sys.argv[1])
    print('opto pitch', r['pitch'], 'want at least', MIN_OPTO_PITCH)
    for q in r['rows'][:12]:
        print(f"  {q['a']:>3} {q['b']:<3} worst case gap {q['gap']:7.3f}  {q['what']}")
    print('JLC spacing, closest to its rule:', r['jlc'][:3])
    for q in r['bad']:
        print('BAD', q)
    print('RESULT', 'PASS' if r['ok'] else 'FAIL')
    sys.exit(0 if r['ok'] else 1)
