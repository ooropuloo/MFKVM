# -*- coding: utf-8 -*-
"""Do the real parts fit? Compares the outline of every placed part with every other part on the same side of the board.

A generated courtyard only knew the pads, so DRC never saw part bodies. This check uses bodies and lead tips from each part's own drawing.
Positions and pads are read back from the saved .kicad_pcb, part numbers and rotations from design.json next to it. The two must agree.

Three gaps per pair, all in mm, on metal and plastic (body plus leads):
  nominal  drawing's typical sizes.
  max      drawing's largest sizes, both parts at once.
  worst    max, less a placement error of +-0.1 mm in x and y on each part. THE 0.1 IS AN ASSUMPTION: JLC publishes no number.
Refuses when a nominal or max gap is 0 or less, or a part's nominal body sits on another part's land.
A worst gap of 0 or less is a warning, not a refusal, because it stacks every tolerance and the assumed placement error together.
Separately listed: the TI DBV0005A drawing's note 4 allows up to 0.25 mm of mold flash per side, outside its body size. That limit is not in max.
Height is not considered: a low part under a tall overhang would be reported as a clash.

usage: bodycheck.py <dir with p4_kvm_mini.kicad_pcb and design.json> [--report file]
exit 0 clean, 1 overlap found, 2 cannot read the board or a part has no outline
"""
import json
import re
import sys

from shapely.geometry import box
from shapely.ops import unary_union

PLACE = 0.10  # ASSUMPTION, per part, per axis
FLASH = 0.25  # TI DBV0005A note 4, per side
NAME = 'p4_kvm_mini'


def row(xs, y0, y1, w):
    return [(x - w / 2, min(y0, y1), x + w / 2, max(y0, y1)) for x in xs]


def spec(src, nom, mx, leads=(), leads_max=(), centre=(0.0, 0.0), flash=False):
    cx, cy = centre
    return dict(src=src, nom=(cx - nom[0] / 2, cy - nom[1] / 2, cx + nom[0] / 2, cy + nom[1] / 2),
                max=(cx - mx[0] / 2, cy - mx[1] / 2, cx + mx[0] / 2, cy + mx[1] / 2), leads=list(leads), leads_max=list(leads_max) or list(leads), flash=flash)


def gull_x(span_nom, span_max, ys, ys_max, w, w_max, edge):
    """Leads leaving in +-x, tips at span/2. edge is the local body edge they start from."""
    a, b = [], []
    for s in (-1, 1):
        for y in ys:
            a.append((min(s * edge, s * span_nom / 2), y - w / 2, max(s * edge, s * span_nom / 2), y + w / 2))
        for y in ys_max:
            b.append((min(s * edge, s * span_max / 2), y - w_max / 2, max(s * edge, s * span_max / 2), y + w_max / 2))
    return a, b


def jst(pins):
    b = pins + 2.0  # JST eSH p3: A = pins - 1, B = pins + 2
    half = (pins - 1) / 2
    xs = [-half + i for i in range(pins)]
    tails = row(xs, -2.375, -1.675, 0.3)
    tails_max = row(xs, -2.475, -1.775, 0.4)
    tabs = [(s * (half + 1.3) - 0.5, 1.075, s * (half + 1.3) + 0.5, 2.675) for s in (-1, 1)]
    tabs_max = [(s * (half + 1.3) - 0.6, 0.975, s * (half + 1.3) + 0.6, 2.775) for s in (-1, 1)]
    return spec(f'JST eSH p1,p3: B {b:g}, depth 4.25, tails 0.7, height 2.9. Housing +-0.1, tail width 0.3 and tab size inside its land are ASSUMED', (b, 4.25), (b + 0.2, 4.45), tails + tabs, tails_max + tabs_max, (0.0, 0.45))


def _sot235(src, nb, mb, sn, sm, wn, wm, flash):
    a = row((-0.95, 0.0, 0.95), nb[1] / 2, sn / 2, wn) + row((-0.95, 0.95), -nb[1] / 2, -sn / 2, wn)
    b = row((-0.95, 0.0, 0.95), mb[1] / 2, sm / 2, wm) + row((-0.95, 0.95), -mb[1] / 2, -sm / 2, wm)
    return spec(src, nb, mb, a, b, flash=flash)


_el_a, _el_b = gull_x(7.0, 7.3, (-0.635, 0.635), (-0.635, 0.635), 0.4, 0.5, 2.2)
_lt_a, _lt_b = gull_x(7.0, 7.2, (-1.27, 1.27), (-1.395, 1.395), 0.4, 0.5, 2.2)
_dbv_src = 'TI DBV0005A (TLV733 SBVS235 p36): 2.75-3.05 x 1.45-1.75, span 2.6-3.0, lead 0.3-0.5. Note 4: up to 0.25 flash per side not included'
BY_CODE = {
    'C92243': spec('Everlight EL3H7-G DPC-0000031 rev 7 p7: 4.40+-0.2 x 2.70+-0.2, span 7.00+-0.3, lead 0.40+-0.1, pitch 1.27, H 2.0 max', (4.4, 2.7), (4.8, 3.1), _el_a, _el_b),
    'C119091': spec('LITE-ON LTV-357T rev Aug 2013 p2: 4.40+-0.2 x 3.85+-0.3, span 7.00 +0.2/-0.7, lead 0.40+-0.1, pitch 2.54+-0.25 (r3 and earlier)', (4.4, 3.85), (4.8, 4.45), _lt_a, _lt_b),
    'C882825': _sot235(_dbv_src, (2.9, 1.6), (3.05, 1.75), 2.8, 3.0, 0.4, 0.5, True),
    'C2871228': _sot235(_dbv_src, (2.9, 1.6), (3.05, 1.75), 2.8, 3.0, 0.4, 0.5, True),
    'C78988': _sot235('Silergy SY8089 AN Rev 0.9A p9: 2.80-3.10 x 1.50-1.70, span 2.70-3.00, lead 0.30-0.50', (2.95, 1.6), (3.1, 1.7), 2.85, 3.0, 0.4, 0.5, False),
    'C15127': spec('NOT THE MAKER\'S DRAWING: AOS AO3401A Rev 3.1 has no outline and none was found. Stand-in TI DBZ0003A (JEDEC TO-236): 2.80-3.04 x 1.2-1.4, span 2.10-2.64, lead 0.3-0.5',
                   (2.92, 1.3), (3.04, 1.4), row((-0.95, 0.95), 0.65, 1.185, 0.4) + row((0.0,), -0.65, -1.185, 0.4), row((-0.95, 0.95), 0.7, 1.32, 0.5) + row((0.0,), -0.7, -1.32, 0.5)),
    'C30348': spec('TI DGK0008A (PCA9517 p19): 2.9-3.1 square, span 4.75-5.05, lead 0.25-0.38', (3.0, 3.0), (3.1, 3.1),
                   row((-0.975, -0.325, 0.325, 0.975), 1.5, 2.45, 0.32) + row((-0.975, -0.325, 0.325, 0.975), -1.5, -2.45, 0.32),
                   row((-0.975, -0.325, 0.325, 0.975), 1.55, 2.525, 0.38) + row((-0.975, -0.325, 0.325, 0.975), -1.55, -2.525, 0.38)),
    'C138714': spec('TI DQA0010A (TPD4E05U06 p28): 2.4-2.6 x 0.9-1.1, no leads', (2.5, 1.0), (2.6, 1.1)),
    'C725995': spec('YXC YSO110TR p3: 3.2+-0.1 x 2.5+-0.1, H 1.2 max', (3.2, 2.5), (3.3, 2.6)),
    'C83423': spec('Sunlord SWPA series catalogue, SWPA4020S row: 4.0+-0.2 square, H 2.0 max', (4.0, 4.0), (4.4, 4.4)),
    'C160405': jst(6),
    'C160407': jst(8),
    'C585350': spec('Molex SD-104031-001 rev B2 sheet 1: 11.95+-0.15 x 11.40+-0.15, H 1.42+-0.15', (11.95, 11.4), (12.1, 11.55), centre=(0.02, 0.0)),
    'C3008606': spec('TC358743XBG, P-VFBGA64-0606: 6.0 square. Tolerance +-0.1 ASSUMED', (6.0, 6.0), (6.2, 6.2)),
    'C720616': spec('XUNPU HDMI-001S drawing: width 14.95. Depth from the existing footprint model, not re-measured. +-0.1 ASSUMED', (15.0, 12.82), (15.2, 13.02), centre=(0.0, 1.71)),
    'C41427493': spec('HX TYPE-C 16P L8.35: JLC lists no drawing. Outline from the footprint model, UNVERIFIED. +-0.1 ASSUMED', (8.94, 10.0), (9.14, 10.2), centre=(0.0, 1.45)),
    'C98485': spec('Sunlord GZ series: 2.0+-0.2 x 1.25+-0.2 (EIA 0805, LCSC scan not read at table level)', (2.0, 1.25), (2.4, 1.65)),
    'C45783': spec('Samsung CL series p6, 0805: 2.00+-0.20 x 1.25+-0.20 at most', (2.0, 1.25), (2.4, 1.65)),
    'C19330': spec('Murata BLM18AG JENF243A p4: 1.6+-0.15 x 0.8+-0.15', (1.6, 0.8), (1.9, 1.1)),
}
BY_LIB = {
    'R': spec('UNI-ROYAL 0402 p4: 1.0+-0.10 x 0.5+-0.05', (1.0, 0.5), (1.2, 0.6)),
    'C0402': spec('Samsung CL05 p6 / FH 0402B: 1.0+-0.05 x 0.5+-0.05', (1.0, 0.5), (1.1, 0.6)),
    'C0603': spec('Samsung CL10 p6: 1.6+-0.1 x 0.8+-0.1', (1.6, 0.8), (1.8, 1.0)),
}
MODULE = spec('Waveshare wiki ESP32-P4-Module, Dimensions drawing: 25.00 x 25.00, H 3.30 + 0.80. Tolerance not published, +-0.15 ASSUMED', (25.0, 25.0), (25.3, 25.3))


def outline(p):
    if p['consign']:
        return MODULE
    if p['lcsc'] in BY_CODE:
        return BY_CODE[p['lcsc']]
    if p['lib'] == 'R0402':
        return BY_LIB['R'] if p['ref'].startswith('R') else BY_LIB['C0402']
    if p['lib'] == 'C0603':
        return BY_LIB['C0603']
    return None


def place(p, r):
    """Same pose as gen_mini.bake(): rotate, then a bottom-side part is mirrored in x."""
    import math
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    xs, ys = [], []
    for x, y in ((r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])):
        wx = x * c + y * s
        wy = -x * s + y * c
        if p['side'] == 'B':
            wx = -wx
        xs.append(p['x'] + wx)
        ys.append(p['y'] + wy)
    return box(min(xs), min(ys), max(xs), max(ys))


def read_pcb(path):
    s = open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'\(footprint "mini:[^"]*"(.*?)(?=\n\s*\(footprint "|\n\s*\(gr_line|\Z)', s, re.S):
        b = m.group(1)
        r = re.search(r'\(property "Reference" "([^"]+)"', b)
        # KiCad's saved format is (transform (translate x y) ...); the generator's own output is (at x y)
        at = re.search(r'\(translate ([-\d.]+) ([-\d.]+)\)', b) or re.search(r'\(at ([-\d.]+) ([-\d.]+)', b)
        if not r or not at:
            continue
        x, y = float(at[1]) - 100, float(at[2]) - 100
        pads = []
        for q in re.finditer(r'\(pad "[^"]*"\s+\w+\s+\w+\s+\(at ([-\d.]+) ([-\d.]+)[^)]*\)\s+\(size ([\d.]+) ([\d.]+)\)', b):
            cx, cy, w, h = x + float(q[1]), y + float(q[2]), float(q[3]), float(q[4])
            pads.append(box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
        out[r[1]] = dict(x=x, y=y, pads=pads)
    return out


def worst_gap(a, b):
    """Gap left once the two outlines move toward each other by 2 x PLACE in x and in y. Negative: they can touch, by about that much."""
    d = a.distance(b)
    grown = a.buffer(2 * PLACE, join_style=2)
    return grown.distance(b) if grown.distance(b) > 0 else d - 2 * PLACE


def check(folder):
    d = json.load(open(f'{folder}/design.json', encoding='utf-8'))
    pcb = read_pcb(f'{folder}/{NAME}.kicad_pcb')
    problems = []
    parts = []
    for p in d['parts']:
        if p['lib'] == 'TP_1.0':
            continue
        o = outline(p)
        if o is None:
            problems.append(f"{p['ref']}: no outline for {p['lcsc']} {p['lib']}")
            continue
        got = pcb.get(p['ref'])
        if not got or abs(got['x'] - p['x']) > 0.001 or abs(got['y'] - p['y']) > 0.001:
            problems.append(f"{p['ref']}: design.json and the board disagree on position")
            continue
        nom = [place(p, o['nom'])] + [place(p, r) for r in o['leads']]
        mx = [place(p, o['max'])] + [place(p, r) for r in o['leads_max']]
        flash = None
        if o['flash']:
            r = o['max']
            flash = unary_union(mx + [place(p, (r[0] - FLASH, r[1] - FLASH, r[2] + FLASH, r[3] + FLASH))])
        parts.append(dict(ref=p['ref'], side=p['side'], dnp=p['dnp'], src=o['src'], lcsc=p['lcsc'], lib=p['lib'], body=nom[0], nom=unary_union(nom), max=unary_union(mx), flash=flash if flash is not None else unary_union(mx), has_flash=flash is not None, pads=unary_union(got['pads'])))
    rows = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if a['side'] != b['side']:
                continue
            g_nom = a['nom'].distance(b['nom'])
            g_max = a['max'].distance(b['max'])
            rows.append(dict(a=a['ref'], b=b['ref'], side=a['side'], fitted=not (a['dnp'] or b['dnp']), nom=g_nom, nom_area=a['nom'].intersection(b['nom']).area, max=g_max, max_area=a['max'].intersection(b['max']).area,
                             worst=worst_gap(a['max'], b['max']), flash=(worst_gap(a['flash'], b['flash']) if a['has_flash'] or b['has_flash'] else None),
                             body_pad=min(a['body'].distance(b['pads']), b['body'].distance(a['pads']))))
    rows.sort(key=lambda r: (r['worst'], r['nom']))
    fails = [r for r in rows if r['fitted'] and (r['nom'] <= 0 or r['max'] <= 0 or r['body_pad'] <= 0)]
    warns = [r for r in rows if r['fitted'] and r not in fails and (r['worst'] <= 0 or (r['flash'] is not None and r['flash'] <= 0))]
    return dict(ok=not fails and not problems, fails=fails, warns=warns, rows=rows, problems=problems, parts=parts)


def summary(res):
    close = min((r['nom'] for r in res['rows'] if r['fitted']), default=None)
    return f"{len(res['parts'])} parts, {len(res['rows'])} same-side pairs, {len(res['fails'])} overlaps, {len(res['warns'])} worst-case warnings, smallest nominal gap {close:.3f} mm" + (' PROBLEMS ' + '; '.join(res['problems']) if res['problems'] else '')


def line(r):
    fl = f"{r['flash']:7.3f}" if r['flash'] is not None else '      -'
    return f"{r['a'] + '/' + r['b']:12s} {r['side']}  nom {r['nom']:6.3f} (area {r['nom_area']:5.2f})  max {r['max']:6.3f}  worst {r['worst']:6.3f}  flash {fl}  body-to-land {r['body_pad']:6.3f}{'' if r['fitted'] else '  not fitted'}"


def report(res, f=sys.stdout):
    print('Real outline check. mm. See tools/bodycheck.py for what each gap means.', file=f)
    print('ASSUMPTION: worst = max less +-0.1 mm placement on each part, in x and y. JLC publishes no number.', file=f)
    print('flash = worst, with TI DBV0005A note 4 at its 0.25 mm per side limit. Reported, not used to refuse.', file=f)
    print('Height is not considered.\n', file=f)
    print('RESULT', 'PASS' if res['ok'] else 'FAIL', summary(res), file=f)
    for x in res['problems']:
        print('PROBLEM', x, file=f)
    print('\nOverlaps (refused):', file=f)
    for r in res['fails']:
        print('  ' + line(r), file=f)
    if not res['fails']:
        print('  none', file=f)
    print('\nWorst-case warnings (nominal and max both clear):', file=f)
    for r in res['warns']:
        print('  ' + line(r), file=f)
    if not res['warns']:
        print('  none', file=f)
    print('\nClosest 40 pairs:', file=f)
    for r in res['rows'][:40]:
        print('  ' + line(r), file=f)
    print('\nSources, one line per outline used:', file=f)
    seen = {}
    for p in res['parts']:
        seen.setdefault(p['src'], []).append(p['ref'])
    for src, refs in seen.items():
        print(f"  {','.join(refs)}: {src}", file=f)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    res = check(sys.argv[1])
    report(res)
    if '--report' in sys.argv:
        with open(sys.argv[sys.argv.index('--report') + 1], 'w', encoding='utf-8') as fh:
            report(res, fh)
    sys.exit(2 if res['problems'] else (0 if res['ok'] else 1))
