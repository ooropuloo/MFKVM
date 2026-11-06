# -*- coding: utf-8 -*-
"""MF KVM v2 courtyard review. Reads the board, writes numbers and annotated images. Never writes into kicad/, out/ or fab*."""
import sys, json, os, itertools
sys.path.insert(0, sys.argv[1])
OUT = sys.argv[2]
BASEPDF = sys.argv[3]
import model
from model import rect, PLACE, pad_poly
from shapely.geometry import box, Polygon, LineString
from shapely.ops import nearest_points, unary_union
import fitz
from PIL import Image, ImageDraw, ImageFont

fps, P, tree = model.build()

# Q1 real outline: SOT-23 per JEDEC TO-236 (STD, labelled) because the AOS sheet on LCSC has no outline page.
fq = fps['Q1']
P['Q1'] = model.Part('Q1', 'STD JEDEC TO-236 / SOT-23 (AOS sheet has no outline)', 1.12, rect(fq['x'], fq['y'], 2.92, 1.3), rect(fq['x'], fq['y'], 3.04, 1.4),
                     [box(fq['x'] + s - 0.2, fq['y'] + 0.65, fq['x'] + s + 0.2, fq['y'] + 1.2) for s in (-0.95, 0.95)] + [box(fq['x'] - 0.2, fq['y'] - 1.2, fq['x'] + 0.2, fq['y'] - 0.65)],
                     [box(fq['x'] + s - 0.25, fq['y'] + 0.7, fq['x'] + s + 0.25, fq['y'] + 1.32) for s in (-0.95, 0.95)] + [box(fq['x'] - 0.25, fq['y'] - 1.32, fq['x'] + 0.25, fq['y'] - 0.7)])

ASKED = [('U11', 'J4'), ('C11', 'U5'), ('C19', 'Y1'), ('C40', 'J7'), ('R52', 'R42'), ('R53', 'C41'), ('Y1', 'C17'), ('U10', 'R22'), ('U10', 'R23'), ('U4', 'C10')]
EXTRA = [('U10', 'U11'), ('U12', 'L1'), ('U4', 'Q1'), ('C11', 'U10')]
JLC = {('C11', 'U5'): (0.2, 'chip 0603 / SOT'), ('R52', 'R42'): (0.15, 'chip 0402 / chip 0402'), ('R53', 'C41'): (0.15, 'chip 0402 / chip 0402'),
       ('U10', 'R22'): (0.4, 'chip 0402 / SOP'), ('U10', 'R23'): (0.4, 'chip 0402 / SOP'), ('U4', 'C10'): (0.2, 'chip 0603 / SOT'),
       ('U11', 'J4'): (None, 'connector: no row'), ('C19', 'Y1'): (None, 'oscillator: no row'), ('Y1', 'C17'): (None, 'oscillator: no row'), ('C40', 'J7'): (None, 'connector: no row'),
       ('U10', 'U11'): (0.5, 'SOP / SOP'), ('U12', 'L1'): (None, 'inductor: no row'), ('U4', 'Q1'): (0.4, 'SOT / SOT'), ('C11', 'U10'): (0.4, 'chip 0603 / SOP')}


def pads(ref):
    return [q for q in fps[ref]['pads']]


def padgeo(ref):
    return unary_union([pad_poly(q) for q in pads(ref)])


def land_union(ref):
    return unary_union([P[ref].body, padgeo(ref)]) if not ('dnp' in fps[ref]['attr']) else padgeo(ref)


def crt_box(ref):
    return box(*fps[ref]['crt'])


def closest_pads(a, b):
    best = None
    for qa in pads(a):
        for qb in pads(b):
            d = pad_poly(qa).distance(pad_poly(qb))
            if qa['net'] != qb['net'] and (best is None or d < best[0]):
                best = (d, qa['n'], qa['net'], qb['n'], qb['net'])
    return best


rows = {}
for a, b in ASKED + EXTRA:
    pa, pb = P[a], P[b]
    dnp = [r for r in (a, b) if 'dnp' in fps[r]['attr']]
    ov = crt_box(a).intersection(crt_box(b))
    r = dict(a=a, b=b, side=(fps[a]['layer'], fps[b]['layer']), dnp=dnp,
             crt_overlap=(round(ov.bounds[2] - ov.bounds[0], 3), round(ov.bounds[3] - ov.bounds[1], 3)) if not ov.is_empty and ov.area > 0 else None,
             body_nom=round(pa.body.distance(pb.body), 3),
             body_overlap_area=round(pa.body.intersection(pb.body).area, 3),
             metal_nom=round(pa.metal.distance(pb.metal), 3),
             metal_worst=round(pa.metal_max.distance(pb.metal_max) - 2 * PLACE, 3),
             body_worst=round(pa.body_max.distance(pb.body_max) - 2 * PLACE, 3),
             a_body_to_b_pad=round(pa.body.distance(padgeo(b)), 3),
             b_body_to_a_pad=round(pb.body.distance(padgeo(a)), 3),
             lead_to_b_body=round(unary_union(pa.leads).distance(pb.body), 3) if pa.leads else None,
             lead_to_a_body=round(unary_union(pb.leads).distance(pa.body), 3) if pb.leads else None,
             pad_pad=closest_pads(a, b),
             jlc_gap=round(land_union(a).distance(land_union(b)), 3),
             jlc_rule=JLC[(a, b)],
             heights=(pa.height, pb.height), src=(pa.src, pb.src))
    if dnp:
        r['note'] = f'{dnp[0]} is DNP: no body exists; gaps with its body are shown for the case someone fits it'
    rows[f'{a}/{b}'] = r

# J4 and U11 extras
j = P['J4']
u = P['U11']
pad3 = [q for q in pads('U11') if q['n'] == '3'][0]
j4x = {'housing_rear_y': round(fps['J4']['y'] - 1.675 - 100, 3), 'housing_front_y': round(fps['J4']['y'] + 2.575 - 100, 3),
       'u11_pad3_to_housing': round(pad_poly(pad3).distance(j.body), 3), 'u11_lead3_nom_to_housing': round(u.leads[1].distance(j.body), 3),
       'u11_lead3_max_to_housing_max': round(u.leads_max[1].distance(j.body_max), 3),
       'u11_body_to_housing': round(u.body.distance(j.body), 3), 'u11_body_to_j4_pad7': round(u.body.distance(pad_poly([q for q in pads('J4') if q['n'] == '7'][0])), 3),
       'u11_lead3_to_tail1': round(u.leads[1].distance(j.leads[0]), 3)}
# plug: JST eSH p2 SHR-06V-S 7.0 wide, SHR-06V-S-B 9.0 wide with protrusions; p1 (6.25) mated length from header rear, so 2.0 past the front.
fy = fps['J4']['y'] + 2.575
cx = fps['J4']['x']
plug7 = box(cx - 3.5, fy - 3.0, cx + 3.5, fy + 2.0)
plug9 = box(cx - 4.5, fy - 3.0, cx + 4.5, fy + 2.0)
j4x['plug_rear_y_mated'] = round(fy + 2.0 - 100, 3)
j4x['plug_swath_to_u11_body_y_gap'] = round(u.body.distance(box(cx - 4.5, fy, cx + 4.5, 130)), 3)
bottom_near = []
sw = box(cx - 4.5, fy, cx + 4.5, 130)
for r, p in P.items():
    if fps[r]['layer'] == 'B.Cu' and r != 'J4':
        d = p.metal.distance(sw)
        if d < 1.5:
            bottom_near.append((r, round(d, 3)))
j4x['parts_within_1p5_of_plug_swath'] = bottom_near
rows['_j4'] = j4x

# Courtyard audit for the real bodies
aud = {}
for lib_ref in ['U11', 'U4', 'Q1', 'Y1', 'J4', 'J7', 'L1', 'C10', 'R52', 'C17']:
    fp = fps[lib_ref]
    c = box(*fp['crt'])
    outside = P[lib_ref].metal.difference(c).area
    x0, y0, x1, y1 = P[lib_ref].metal.bounds
    aud[lib_ref] = dict(crt=[round(v - 100, 3) for v in fp['crt']], real=[round(v - 100, 3) for v in (x0, y0, x1, y1)], area_outside_crt=round(outside, 3), area_crt_extra=round(c.difference(P[lib_ref].metal.union(padgeo(lib_ref))).area, 3))
rows['_audit'] = aud
json.dump(rows, open(f'{OUT}/numbers.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

# ---------------- images
SC = 60
doc = fitz.open(BASEPDF)
page = doc[0]
FONT = 'C:/Windows/Fonts/arial.ttf'
FB = 'C:/Windows/Fonts/arialbd.ttf'
MM = 72 / 25.4
COL = ['#d00000', '#0050d0', '#008a2e', '#9a00b0']


def draw_pair(name, refs, gaps, window, title, extras=None, note=None):
    x0, y0, x1, y1 = window
    clip = fitz.Rect(x0 * MM, y0 * MM, x1 * MM, y1 * MM)
    pm = page.get_pixmap(matrix=fitz.Matrix(SC / MM, SC / MM), clip=clip, alpha=False)
    im = Image.frombytes('RGB', (pm.width, pm.height), pm.samples)
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.45).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def T(pt):
        return ((pt[0] - x0) * SC * pm.width / (SC * (x1 - x0)), (pt[1] - y0) * SC * pm.height / (SC * (y1 - y0)))

    def poly(g, outline, fill=None, width=3, dash=False):
        if g.is_empty:
            return
        for gg in (g.geoms if hasattr(g, 'geoms') else [g]):
            pts = [T(c) for c in gg.exterior.coords]
            if fill:
                tmp = Image.new('RGBA', im.size, (0, 0, 0, 0))
                ImageDraw.Draw(tmp).polygon(pts, fill=fill)
                ov.alpha_composite(tmp)
            if dash:
                for i in range(len(pts) - 1):
                    ax, ay = pts[i]
                    bx, by = pts[i + 1]
                    L = max(1, ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5)
                    t = 0
                    while t < L:
                        e = min(t + 9, L)
                        d.line([(ax + (bx - ax) * t / L, ay + (by - ay) * t / L), (ax + (bx - ax) * e / L, ay + (by - ay) * e / L)], fill=outline, width=width)
                        t += 18
            else:
                d.line(pts, fill=outline, width=width)

    def rgba(h, a):
        h = h.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)

    f = ImageFont.truetype(FB, 22)
    fs = ImageFont.truetype(FONT, 18)
    for i, r in enumerate(refs):
        c = COL[i % 4]
        poly(crt_box(r), rgba('#555555', 200), dash=True, width=2)
        for q in pads(r):
            poly(pad_poly(q), rgba(c, 255), width=1, fill=rgba(c, 28))
        if 'dnp' not in fps[r]['attr']:
            poly(P[r].body, rgba(c, 255), fill=rgba(c, 60), width=4)
            for l in P[r].leads:
                poly(l, rgba(c, 255), fill=rgba(c, 150), width=2)
            cc = P[r].body.representative_point() if P[r].body.intersection(box(x0, y0, x1, y1)).is_empty else P[r].body.intersection(box(x0, y0, x1, y1)).representative_point()
            x, y = T((cc.x, cc.y))
            d.text((x - 15, y - 12), r, font=f, fill=rgba(c, 255))
        else:
            x, y = T((fps[r]['x'], fps[r]['y']))
            d.text((x - 40, y - 12), r + ' DNP', font=f, fill=rgba(c, 255))
    for ex in (extras or []):
        poly(ex['g'], rgba(ex.get('c', '#c06000'), 255), fill=rgba(ex.get('c', '#c06000'), ex.get('a', 40)), width=3, dash=ex.get('dash', False))
        if ex.get('t'):
            x, y = T(ex['at'])
            d.text((x, y), ex['t'], font=fs, fill=rgba(ex.get('c', '#c06000'), 255))
    for gi, (ga, gb, lab) in enumerate(gaps):
        pa, pb = nearest_points(ga, gb)
        d.line([T((pa.x, pa.y)), T((pb.x, pb.y))], fill=(255, 0, 180, 255), width=4)
        x, y = T(((pa.x + pb.x) / 2, (pa.y + pb.y) / 2))
        if lab:
            lx, ly = x + 14, y - 34 + 30 * gi
            d.line([(x, y), (lx, ly + 10)], fill=(190, 0, 130, 255), width=1)
            tb = d.textbbox((lx, ly), lab, font=fs)
            d.rectangle(tb, fill=(255, 255, 255, 235))
            d.text((lx, ly), lab, font=fs, fill=(190, 0, 130, 255))
    # scale bar
    bx, by = 14, im.size[1] - 22
    d.line([(bx, by), (bx + SC, by)], fill=(0, 0, 0, 255), width=4)
    d.text((bx + SC + 8, by - 12), '1 mm', font=fs, fill=(0, 0, 0, 255))
    out = Image.alpha_composite(im, ov).convert('RGB')
    H = 74 + (28 if note else 0)
    canvas = Image.new('RGB', (max(out.size[0], 900), out.size[1] + H), 'white')
    dd = ImageDraw.Draw(canvas)
    dd.text((10, 6), title, font=f, fill='black')
    dd.text((10, 38), 'Solid = datasheet body and leads. Thin = copper pads. Dashed grey = generated courtyard. X-ray view from F side, KiCad coordinates.', font=ImageFont.truetype(FONT, 15), fill='#333333')
    if note:
        dd.text((10, 62), note, font=ImageFont.truetype(FONT, 16), fill='#a00000')
    canvas.paste(out, (0, H))
    canvas.save(f'{OUT}/{name}.png')


def W(refs, pad=1.2):
    g = unary_union([crt_box(r) for r in refs] + [P[r].body for r in refs])
    a, b, c, e = g.bounds
    return (a - pad, b - pad, c + pad, e + pad)


def lab(v, what):
    return f'{what} {v:.2f}'


def pad_of(ref, n):
    return pad_poly([q for q in pads(ref) if q['n'] == n][0])


def f2(n):
    return f'{n:.2f}'


# pair images
w = (90.8, 110.2, 107.0, 121.0)
draw_pair('pair_01_U11_J4', ['U11', 'J4'], [(P['U11'].body, P['J4'].body, f"bodies {rows['U11/J4']['body_nom']:.2f}"), (pad_of('U11', '3'), pad_of('J4', '1'), f"pads {rows['U11/J4']['pad_pad'][0]:.2f}"), (P['U11'].leads[1], P['J4'].body, f"lead to housing {j4x['u11_lead3_nom_to_housing']:.2f}")], w, 'J4 / U11, header only', note='Largest courtyard warning: 1.65 x 1.27 mm. The overlap is U11 land toe under J4 rear pads; bodies do not touch.')
draw_pair('pair_01b_J4_plug', ['U11', 'J4'], [(P['U11'].body, box(cx - 4.5, fy, cx + 4.5, 130), f"{j4x['plug_swath_to_u11_body_y_gap']:.2f} to plug")], (88.8, 110.5, 104.0, 124.8), 'J4 with SHR-06V-S-B plug (9.0 wide) mated, and the +y wall',
          extras=[dict(g=box(cx - 4.6, 120.4, cx + 4.6, 122.0), c='#555555', a=35, t='case wall y 20.4..22.0, opening 9.2 wide', at=(cx - 4.6, 122.1)),
                  dict(g=plug9, c='#c06000', a=70, t='plug 9.0 wide (7.0 without protrusions), rear at y 21.475', at=(cx - 4.4, 122.5)),
                  dict(g=box(80, 120, 120, 120.02), c='#000000', a=255, t='board edge y=20', at=(cx + 4.9, 119.5))],
          note='Plug arrives from +y and stops inside the header; it never reaches U11. Case wall opening from check_report.txt.')
draw_pair('pair_02_C11_U5', ['C11', 'U5'], [(P['C11'].body, unary_union(P['U5'].leads), f"lead to cap {rows['C11/U5']['lead_to_a_body']:.2f}"), (pad_of('C11', '2'), pad_of('U5', '2'), '')], W(['C11', 'U5']), 'C11 / U5')
draw_pair('pair_03_C19_Y1', ['C19', 'Y1'], [(P['C19'].body, P['Y1'].body, f"bodies {rows['C19/Y1']['body_nom']:.2f}"), (padgeo('C19'), pad_of('Y1', '1'), f"pads {rows['C19/Y1']['pad_pad'][0]:.2f}")], W(['C19', 'Y1']), 'C19 / Y1')
draw_pair('pair_04_C40_J7', ['C40', 'J7'], [(P['C40'].body, P['J7'].body, f"bodies {rows['C40/J7']['body_nom']:.2f}"), (padgeo('C40'), P['J7'].body, f"pad to shell {rows['C40/J7']['b_body_to_a_pad']:.2f}")], (88.5, 106.5, 95.8, 112.8), 'C40 / J7 rear corner', note='Courtyard corner (92.35, 110.54) is an empty bbox corner: nothing of J7 is there.')
draw_pair('pair_04b_J7_card', ['C40', 'J7'], [], (74.5, 95.5, 96.5, 113.0), 'J7 with card inserted', extras=[dict(g=box(78.0, 80, 79.6, 120), c='#555555', a=35, t='wall', at=(78.05, 111.9)), dict(g=box(80, 80, 80.02, 120), c='#000000', a=255), dict(g=box(fps['J7']['x'] - 5.7 - 4.0, fps['J7']['y'] - 5.555, fps['J7']['x'] - 5.7 + 11.0, fps['J7']['y'] + 5.445), c='#c06000', a=55, t='microSD 11 x 15, 4.0 out of the shell', at=(76.6, 96.3))], note='Push-pull, no eject travel. Card stops inside the shell, so C40 is not in its path. It stands 1.5 mm proud of the wall.')
draw_pair('pair_05_R52_R42', ['R52', 'R42'], [(padgeo('R52'), padgeo('R42'), f"pads {rows['R52/R42']['pad_pad'][0]:.2f}")], W(['R52', 'R42']), 'R52 / R42 (R42 is DNP)')
draw_pair('pair_06_R53_C41', ['R53', 'C41'], [(P['R53'].body, P['C41'].body, f"bodies {rows['R53/C41']['body_nom']:.2f}"), (padgeo('R53'), padgeo('C41'), f"pads {rows['R53/C41']['pad_pad'][0]:.2f}")], W(['R53', 'C41']), 'R53 / C41')
draw_pair('pair_07_Y1_C17', ['Y1', 'C17'], [(P['Y1'].body, P['C17'].body, f"bodies {rows['Y1/C17']['body_nom']:.2f}"), (pad_of('Y1', '2'), pad_of('C17', '1'), f"pads {rows['Y1/C17']['pad_pad'][0]:.2f}")], W(['Y1', 'C17']), 'Y1 / C17')
draw_pair('pair_08_U10_R22', ['U10', 'R22'], [(unary_union(P['U10'].leads), P['R22'].body, f"lead to R22 {rows['U10/R22']['lead_to_b_body']:.2f}"), (pad_of('U10', '1'), padgeo('R22'), f"pads {rows['U10/R22']['pad_pad'][0]:.2f}")], W(['U10', 'R22']), 'U10 / R22')
draw_pair('pair_09_U10_R23', ['U10', 'R23'], [(unary_union(P['U10'].leads), P['R23'].body, f"lead to R23 {rows['U10/R23']['lead_to_b_body']:.2f}"), (pad_of('U10', '2'), padgeo('R23'), f"pads {rows['U10/R23']['pad_pad'][0]:.2f}")], W(['U10', 'R23']), 'U10 / R23')
draw_pair('pair_10_U4_C10', ['U4', 'C10'], [(unary_union(P['U4'].leads), P['C10'].body, f"lead to cap {rows['U4/C10']['lead_to_a_body'] if False else rows['U4/C10']['lead_to_b_body']:.2f}"), (pad_of('U4', '3'), pad_of('C10', '2'), f"pads {rows['U4/C10']['pad_pad'][0]:.2f}")], W(['U4', 'C10']), 'U4 / C10')
# extras
ovl = P['U10'].body.intersection(P['U11'].body)
draw_pair('extra_A_U10_U11', ['U10', 'U11'], [], (98.5, 106.5, 108.5, 117.0), 'NEW: U10 / U11 bodies overlap, DRC is silent', extras=[dict(g=ovl, c='#ff0000', a=170, t='overlap 0.25 nominal (0.55 max)', at=(ovl.bounds[0], ovl.bounds[1] - 0.45))], note='Courtyards hold pads only (y +-1.69), body is 3.85 along the pitch (y +-1.925) and the parts sit 3.6 apart.')
ovl = P['U12'].body.intersection(P['L1'].body)
draw_pair('extra_B_U12_L1', ['U12', 'L1'], [], (105.5, 110.5, 117.0, 121.0), 'NEW: U12 / L1 bodies overlap, DRC is silent', extras=[dict(g=ovl, c='#ff0000', a=170, t='overlap', at=(ovl.bounds[0] - 1.5, ovl.bounds[1] - 0.5))])
ovl = P['U4'].body.intersection(P['Q1'].body)
draw_pair('extra_C_U4_Q1', ['U4', 'Q1'], [], (94.8, 102.5, 102.5, 108.5), 'NEW: U4 / Q1 bodies overlap, DRC is silent', extras=[dict(g=ovl, c='#ff0000', a=170, t='overlap', at=(ovl.bounds[0] - 0.2, ovl.bounds[1] - 0.45))], note='gen.log lists it as courtyard touch 0.00 x 2.67. Courtyards use pads only (x +-1.35), real bodies are 2.9 long.')
draw_pair('extra_D_C11_U10', ['C11', 'U10'], [(P['C11'].body, P['U10'].body, f"{rows['C11/U10']['body_nom']:.3f} nominal")], (100.5, 105.5, 107.0, 112.5), 'NEW: C11 / U10 touch within tolerance')
# fix preview: same centres, Everlight 4.40 x 2.70 body, 1.27 pitch, 7.00 span, land 1.5 x 0.6 at 3.175 from centre
def ssop(ref):
    f0 = fps[ref]
    x, y = f0['x'], f0['y']
    lands = [rect(x + sx * 3.175, y + sy * 0.635, 1.5, 0.6) for sx in (-1, 1) for sy in (-1, 1)]
    leads = [box(min(x + sx * 2.2, x + sx * 3.5), y + sy * 0.635 - 0.2, max(x + sx * 2.2, x + sx * 3.5), y + sy * 0.635 + 0.2) for sx in (-1, 1) for sy in (-1, 1)]
    return rect(x, y, 4.4, 2.7), leads, lands


preview = {}
for r in ('U10', 'U11', 'U12'):
    b, l, a = ssop(r)
    preview[r] = dict(body=b, leads=l, lands=a, metal=unary_union([b] + l), union=unary_union([b] + a))
res = {}
for r, v in preview.items():
    res[r] = []
    for o, p in P.items():
        if o == r or fps[o]['layer'] != 'B.Cu' or 'dnp' in fps[o]['attr']:
            continue
        if o in preview:
            d = v['metal'].distance(preview[o]['metal'])
            dl = v['union'].distance(preview[o]['union'])
        else:
            d = v['metal'].distance(p.metal)
            dl = v['union'].distance(land_union(o))
        if dl < 0.7:
            res[r].append((o, round(d, 3), round(dl, 3)))
rows['_ssop_preview'] = res
print('PREVIEW', res)
json.dump(rows, open(f'{OUT}/numbers.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
oldp = {r: P[r] for r in preview}
for r, v in preview.items():
    P[r] = model.Part(r, 'EL3H7L-G drawing', 2.0, v['body'], v['body'], v['leads'], v['leads'])
    fps[r] = dict(fps[r], pads=[dict(q, x=a.centroid.x, y=a.centroid.y, w=1.5, h=0.6) for q, a in zip(fps[r]['pads'], v['lands'])])
draw_pair('fix_A_ssop_preview', ['U10', 'U11', 'U12', 'J4', 'L1', 'C11', 'R22', 'R23'], [], (90.0, 106.0, 118.0, 121.0), 'Fix A preview: 2.7 mm wide SSOP-4 at the same centres. Nothing moved. Copper not re-routed in this picture.', note='Pads drawn are the proposed lands. Traces under them are the current ones and would need short re-routes.')
for r, p0 in oldp.items():
    P[r] = p0
fps2, _, _ = model.build()
for r in oldp:
    fps[r] = fps2[r]
# overview
refs_over = ['U4', 'U5', 'C10', 'C11', 'U10', 'U11', 'U12', 'J4', 'Q1', 'R52', 'R53', 'R42', 'C41', 'C40', 'R22', 'R23', 'L1', 'U2']
draw_pair('overview_J4_opto_area', refs_over, [], (90.0, 102.0, 118.0, 121.0), 'Bottom side, J4 / opto / regulator area, datasheet outlines')
print(json.dumps(rows, indent=0, ensure_ascii=False))
