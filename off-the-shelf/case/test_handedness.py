# -*- coding: utf-8 -*-
"""Handedness of every v3 artifact, each tested against an asymmetric feature on the vendor's own drawing or file.

The rule, from DFRobot's top view: with the top side up and the CDC port away from you, the OTG USB-C is on your right.
Every check also runs on a mirrored copy of its data, which must fail. A test that cannot see a mirror proves nothing.

usage: test_handedness.py <firebeetle bb.json> <firebeetle.step> <dfrobot layout.png> <c790 interface jpg> <lcd.stp> [<page_top.json> <page_top.png>]
"""
import json
import os
import sys

import cadquery as cq
import numpy as np
import trimesh
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'lay-board', 'tools'))
import maskcheck  # noqa: E402
import pinmap_check  # noqa: E402

BB, FB_STEP, FIG, C790_FIG, LCD_STP = sys.argv[1:6]
PAGE_J, PAGE_P = (sys.argv[6], sys.argv[7]) if len(sys.argv) > 7 else (None, None)
CHK = json.load(open(os.path.join(HERE, 'check.json'), encoding='utf-8'))
LV = CHK['levels']
fails = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        fails.append(msg)


def both(name, fn, data, mirror):
    """fn must accept the data and refuse its mirror image."""
    real, mir = fn(data), fn(mirror(data))
    check(real and not mir, f'{name} (real {"ok" if real else "WRONG"}, mirrored copy {"wrongly accepted" if mir else "rejected"})')


def right_of(away, up):
    return np.cross(away, up)


# ---------- 1. official figure: what the truth is. DFRobot layout.png, left panel is the top view, CDC at the top of the picture.
fig = np.asarray(Image.open(FIG).convert('RGB')).astype(int)
PX0, PX1, PY60, PPM = 103, 347, 72, 9.6  # board edges in the figure, 244 px = 25.4 mm


def light_share(img, x0, x1, y0, y1):
    r = img[y0:y1, x0:x1]
    light = (r.min(axis=2) > 150) & (r.max(axis=2) - r.min(axis=2) < 30)
    return int(light.sum())


def fig_otg_right(img):
    y0, y1 = int(PY60 + (60 - 50) * PPM), int(PY60 + (60 - 41) * PPM)
    mid = (PX0 + PX1) // 2
    return light_share(img, mid, PX1, y0, y1) > 3 * light_share(img, PX0, mid, y0, y1)


def flip_band(a, x0, x1):
    return np.concatenate([a[:, :x0], a[:, x0:x1][:, ::-1], a[:, x1:]], axis=1)


both('official figure: OTG shell on the right in the top view', fig_otg_right, fig, lambda a: flip_band(a, PX0, PX1))

# ---------- 2. FireBeetle STEP, read through its bounding boxes
bb = {e['refname']: e['bb'] for e in json.load(open(BB, encoding='utf-8')) if e['depth'] == 1}
cen = lambda b: np.array([(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2])


def step_ok(b):
    c = cen(b['Board'])
    away = cen(b['U5']) - c
    up = np.array([0, 0, np.sign(cen(b['U1'])[2] - cen(b['U3'])[2])], float)  # the P4 is on the top side, the C6 on the underside
    r = right_of(away, up)
    return all(np.dot(cen(b[k]) - c, r) * s > 0 for k, s in (('U8', 1), ('K2', 1), ('K1', -1)))


both('STEP: seen from the top with CDC away, OTG and BOOT (K2) right, RST (K1) left, as in the figure', step_ok, bb, lambda b: {k: [-v[3], v[1], v[2], -v[0], v[4], v[5]] for k, v in b.items()})

# ---------- 3. the printed tray, from its STEP: an opening has to be where the part is, and not on the mirror side
tray = cq.importers.importStep(os.path.join(HERE, 'step', 'mf_kvm_tray.step')).val().Solids()[0]
OX0, OX1, OY1 = LV['OX0'], LV['OX1'], LV['OY1']
inside = lambda p: tray.isInside(cq.Vector(*p), 1e-3)
mirror_x = lambda x: OX0 + OX1 - x
wall_p = OX1 - 0.8
wall_m = OX0 + 0.8
OTG = (LV['OTG_Y'], 1.105)
check(not inside((wall_p, *OTG)) and inside((wall_m, *OTG)), f'tray: OTG window in the +X wall at y {OTG[0]}, solid wall at the same place on -X. U8 is at +x in the STEP')
check(not inside((wall_m, LV['JY'], -1.0)) and inside((wall_p, LV['JY'], -1.0)), 'tray: ATX opening in the -X wall only')
check(not inside((OX1 - 0.8, 53.34, 1.42)) and not inside((OX0 + 0.8, 53.34, 1.42)), 'tray: BOOT hole +X, RST hole -X')
check(not inside((LV['HX'], OY1 - 0.9, 12.0)) and inside((-LV['HX'], OY1 - 0.9, 12.0)), f"tray: HDMI opening at x {LV['HX']:.2f}, wall at the mirrored x {-LV['HX']:.2f}")
check(not inside((-5.0, 16.0, -5.0)) and inside((5.0, 16.0, -5.0)), 'tray: C6 test point hatch at -x, where the figure has the pads')
for name in ('tray', 'lid', 'bridge', 'former'):
    m = trimesh.load(os.path.join(HERE, 'stl', f'mf_kvm_{name}.stl'))
    check(m.volume > 0, f'{name} STL has positive signed volume, {m.volume:.0f} mm3, so its faces were not flipped by a mirror')
tray_m = trimesh.load(os.path.join(HERE, 'stl', 'mf_kvm_tray.stl'))
tb = tray.BoundingBox()
check(abs(tray_m.bounds[0][0] - tb.xmin) < 0.05 and abs(tray_m.bounds[1][0] - tb.xmax) < 0.05, 'tray STL and STEP share the same x range; the X range is asymmetric, so a mirrored STL would not match')

# ---------- 4. C790 in the assembly against Geekworm's figure: front face up, HDMI left, FPC right, I2S at the bottom
g = np.asarray(Image.open(C790_FIG).convert('RGB')).astype(int)
scale = g.shape[1] / 1932
B0, B1 = int(125 * scale), int(945 * scale)   # the front view, PCB edges at 165 and 905 of the 1932 px wide figure, so 40 px of margin each side


def fig_hdmi_left(a):
    # only the HDMI shell overhangs the PCB. Past the left edge the figure shows metal, past the right edge it shows white paper.
    y0, y1 = int(345 * scale), int(575 * scale)
    paper = lambda x0, x1: (a[y0:y1, int(x0 * scale):int(x1 * scale)].min(axis=2) > 235).mean()
    return paper(130, 160) < 0.2 and paper(910, 940) > 0.9


both('Geekworm figure: HDMI overhangs the left edge of the front view', fig_hdmi_left, g, lambda a: flip_band(a, B0, B1))
m_c = trimesh.load(os.path.join(HERE, 'asm', 'c790.stl'))
V = np.array(m_c.vertices)


def c790_ok(v):
    pt = LV['PCB_T']
    hd = v[np.abs(v[:, 2] - (pt + 7.4)) < 0.01].mean(axis=0)
    j2 = v[np.abs(v[:, 2] - (pt + 3.0)) < 0.01].mean(axis=0)
    j5 = v[np.abs(v[:, 2] - (pt + 4.0)) < 0.01].mean(axis=0)
    centre = (v[:, 0].min() + v[:, 0].max()) / 2, (v[:, 1].min() + v[:, 1].max()) / 2
    to_fpc = j2[:2] - hd[:2]
    to_i2s = j5[:2] - np.array(centre)
    # figure: right (HDMI to FPC) x down (toward I2S) is into the page, so with z toward the viewer the cross product is negative
    return float(to_fpc[0] * to_i2s[1] - to_fpc[1] * to_i2s[0]) < 0 and pt > v[:, 2].min()


both('assembly C790: same chirality as the figure (HDMI to FPC, then I2S on the right hand side of that)', c790_ok, V, lambda v: v * [-1, 1, 1])
# pin 1 follows the same chirality: the triangle is at the I2S end of J2
XF = -6.7
j5_x = V[np.abs(V[:, 2] - (LV['PCB_T'] + 4.0)) < 0.01][:, 0].mean()
check(j5_x < XF, f'C790 pin 1 (I2S end of J2) is on the -x side, x {j5_x:.1f}, so the roll sends it to J1 pin 1 at high y')

# ---------- 5. LCD against the vendor STEP
lcd = cq.importers.importStep(LCD_STP).val()
s = sorted(lcd.Solids(), key=lambda q: q.BoundingBox().zmin)[0].BoundingBox()  # lowest solid is the connector
m_l = np.array(trimesh.load(os.path.join(HERE, 'asm', 'lcd.stl')).vertices)
X0, Y0, P = LV['LCD_X0'], LV['LCD_Y0'], LV['PANEL']


def lcd_ok(v):
    conn = v[np.abs(v[:, 2] - (P - 7.0)) < 0.02]
    # the placement X = X0 + Yl, Y = Y0 + 51.2 - Xl is a rotation: (-y) x (+x) = +z. So Xl 12.5..17.6 must land at these y, and the panel face stays up.
    ok_y = abs(conn[:, 1].min() - (Y0 + 51.2 - 17.6)) < 0.3 and abs(conn[:, 1].max() - (Y0 + 51.2 - 12.5)) < 0.3
    ok_x = abs(conn[:, 0].min() - (X0 + 6.3)) < 0.3 and abs(conn[:, 0].max() - (X0 + 21.0)) < 0.3
    return ok_x and ok_y and v[:, 2].max() > P - 0.01


check(s.ymin < 7 and s.ymax > 20 and s.xmin > 12 and s.xmax < 18 and s.zmin < -3.5, f'LCD vendor STEP: connector at Xl {s.xmin:.1f}..{s.xmax:.1f}, on the 6.25 mm side of the drawing, behind the panel')
# the LCD is symmetric across its long axis at this level of detail, so only a flip along its length can be seen, and only that flip would matter
both('assembly LCD: connector where a rotation of the vendor STEP puts it', lcd_ok, m_l, lambda v: v * [1, -1, 1] + [0, 2 * Y0 + 51.2, 0])
win = LV['WIN']
check((win[2] + win[3]) / 2 < Y0 + 25.6, 'window offset is toward low y, the Xl = 51.2 end, where the 2.23 mm margin is')

# ---------- 6. ATX board: Gerber is the real top view, y up. It must land in the case without a flip.
ATX = os.path.join(HERE, '..', 'fab_atx_b', 'gerber')
ly = maskcheck.Layers(ATX)
cu = maskcheck.parse(ly.txt['cu', 'T'])
pad = {}
for o in cu:
    if o['pad']:
        pad[(o['pad'][0], o['pad'][1])] = (o['at'][0] - 100, o['at'][1] + 100)
cx, cy, _ = LV['ATX_C']
P_ = {k: (cx + v[0], cy + v[1]) for k, v in pad.items()}   # no sign change on either axis: Gerber is x right, y up, like the case


def atx_ok(p):
    j = np.mean([p[('J1', str(i))] for i in range(1, 7)], axis=0)
    holes = np.mean([p[(f'H{i}', '1')] for i in range(1, 6)], axis=0)
    u1 = np.array(p[('U1', '1')]), np.array(p[('U1', '3')])
    mp = np.array(p[('J1', 'MP1')])
    return abs(j[1] - LV['JY']) < 1.0 and mp[0] < j[0] and mp[0] < cx and holes[1] < j[1] and holes[0] > j[0] and u1[0][0] > u1[1][0]


both('ATX Gerber in the case: JST at the opening y and opening toward -X, pin row toward the core and the antenna end', atx_ok, P_, lambda p: {k: (2 * cx - v[0], v[1]) for k, v in p.items()})
edge = maskcheck.parse(open(os.path.join(ATX, 'mf_kvm_atx-Edge_Cuts.gbr'), encoding='utf-8', errors='replace').read())
pts = np.array([q for o in edge for q in o['geom'].exterior.coords])
pts -= [100, -100]
# notch: top-right of the Gerber view is cut, so at high x the board stops below y +3.15
hi = pts[pts[:, 0] > 4.5]
check(hi[:, 1].max() < 3.6 and hi[:, 1].min() < -22, f'ATX Gerber notch at +x, +y (board stops at y {hi[:, 1].max():.2f} there), which clears the core post at case ({-11.0}, 58.3): post y starts at {58.3 - 2:.1f}, notch at {cy + 3.15:.2f}')
m_a = np.array(trimesh.load(os.path.join(HERE, 'asm', 'atx.stl')).vertices)
z_pad = m_a[np.abs(m_a[:, 2] - (LV['ATX_C'][2] + 1.0 + 2.95)) < 0.01]
check(abs(z_pad[:, 1].mean() - LV['JY']) < 0.6 and z_pad[:, 0].min() < cx - 3, f"assembly ATX model puts the JST at y {z_pad[:, 1].mean():.2f}, Gerber says {np.mean([P_[('J1', str(i))] for i in range(1, 7)], axis=0)[1]:.2f}")
check(abs(max(m_a[m_a[:, 1] > cy + 4][:, 0]) - (cx + 3.0)) < 0.1, 'assembly ATX board has the notch on the same corner as the Gerber')

# ---------- 6b. ATX pin map: real drill file and Gerbers against the STEP's named holes, then rewritten copies that must be refused
ok_map, msgs_map, table_map, rows_map = pinmap_check.test(FB_STEP, ATX, (cx, cy))
for r in table_map:
    print('      ', r['ref'], r['net'], 'hole at', r['case'], 'on P1 pin', r['header_pin'], r['header_name'], 'error', r['error'], 'mm')
check(ok_map and len(table_map) == 5, f'ATX pin map: {len(table_map)} plated holes each on its named header hole within {pinmap_check.TOL} mm, worst {max((r["error"] for r in table_map), default=99):.3f} {msgs_map or ""}')
for r in rows_map:
    check(r['refused'], f"ATX pin map refuses a rewritten copy: {r['name']}. {r['why'][0] if r['why'] else 'NOT REFUSED'}")
holes_step = {h['name']: h for h in pinmap_check.step_holes(FB_STEP) if h['name'] not in ('NC',)}
want_pin = dict(H1='3V3', H2='GND', H3='28', H4='29', H5='30')
for q in CHK['atx']['pins']:
    h = holes_step[want_pin[q['ref']]]
    check(abs(q['x'] - h['x']) < 0.01 and abs(q['y'] - h['y']) < 0.01, f"assembly model pin {q['ref']} at ({q['x']}, {q['y']}), STEP hole {want_pin[q['ref']]} at ({h['x']}, {h['y']})")
m_pin = m_a[(np.abs(m_a[:, 0] - pinmap_check.step_holes(FB_STEP)[1]['x']) < 0.8) & (m_a[:, 2] > 0.6)]
check(abs(m_pin[:, 1].max() - holes_step['3V3']['y']) < 0.4 and abs(m_pin[:, 1].min() - holes_step['30']['y']) < 0.4, f'assembly STL has pins from y {m_pin[:, 1].min():.2f} to {m_pin[:, 1].max():.2f} above the core, and none at P1 pin 1 (RST), y {pinmap_check.step_holes(FB_STEP)[0]["y"]}')

# ---------- 7. the 3D page, read from its own mesh after its own transforms
if PAGE_J:
    j = json.load(open(PAGE_J, encoding='utf-8'))
    check(not j['errors'], f"page: no errors {j['errors'] or ''}")
    check(j['det'] > 0, f"page: root transform determinant {j['det']:.3f} is positive, a rotation and not a mirror")

    def page_ok(q):
        return q['otg_screen'][0] > q['centre'][0] and q['boot_screen'][0] > q['centre'][0] > q['rst_screen'][0] and q['cdc_screen'][1] < q['centre'][1] and q['verts_otg_band_right'] > 50 and q['verts_otg_band_left'] < q['verts_otg_band_right'] / 3

    def mir_j(q):
        f = lambda p: [2 * q['centre'][0] - p[0], p[1]]
        return dict(q, otg_screen=f(q['otg_screen']), boot_screen=f(q['boot_screen']), rst_screen=f(q['rst_screen']), verts_otg_band_right=q['verts_otg_band_left'], verts_otg_band_left=q['verts_otg_band_right'])
    both(f"page: from above with CDC up the screen, OTG right, BOOT right, RST left; mesh vertices right {j['verts_otg_band_right']} left {j['verts_otg_band_left']}", page_ok, j, mir_j)
    img = np.asarray(Image.open(PAGE_P).convert('RGBA')).astype(int)
    h, w = img.shape[:2]
    mm = h / j['mm_per_view_h']
    cxp, cyp = j['centre'][0] * w, j['centre'][1] * h
    y0, y1 = int(cyp - (50 - 30) * mm), int(cyp - (41 - 30) * mm)
    x0, x1 = int(cxp - 12.7 * mm), int(cxp + 12.7 * mm)

    def page_px_ok(a):
        r = a[y0:y1]
        lit = (r[:, :, 3] > 200) & (r[:, :, :3].mean(axis=2) > 120)  # the page lights the black PCB to about 94, the metal is above 160
        m = int(cxp)
        return lit[:, m:x1].sum() > 3 * lit[:, x0:m].sum()
    both('page pixels: bright OTG shell on the right half of the board, same test as the official figure', page_px_ok, img, lambda a: flip_band(a, x0, x1))
    # the two views side by side, for a person
    ofig = Image.open(FIG).convert('RGB').crop((PX0 - 12, 50, PX1 + 12, 655))
    pg = Image.open(PAGE_P).convert('RGBA')
    pgc = pg.crop((int(cxp - 15 * mm), int(cyp - 33 * mm), int(cxp + 15 * mm), int(cyp + 33 * mm)))
    bgd = Image.new('RGBA', pgc.size, (225, 230, 230, 255))
    bgd.alpha_composite(pgc)
    pgc = bgd.convert('RGB').resize((ofig.width, ofig.height))
    both_img = Image.new('RGB', (ofig.width * 2 + 20, ofig.height), 'white')
    both_img.paste(ofig, (0, 0))
    both_img.paste(pgc, (ofig.width + 20, 0))
    both_img.save(os.path.join(HERE, 'handedness', 'official_vs_page.png'))

print('RESULT', 'FAIL' if fails else 'OK', fails if fails else '')
sys.exit(1 if fails else 0)
