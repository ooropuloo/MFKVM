# -*- coding: utf-8 -*-
"""MF KVM r8 case: all aluminium, passive, sealed. Built from the routed board's real positions; check_case.py judges the files.

Two frames, and they differ by a mirror:
  design/KiCad: x right, y DOWN as seen from the top side, z toward the viewer. That is left-handed.
  case (world): origin at the PCB centre, x right, y toward the back wall, z up from the desk, I/O face at y = -S/2. Right-handed.
The only rigid way to put the board in the case with the I/O edge at -y and its top side up is a turn by 180 degrees in the
STEP frame (x, -y_kicad, z), which gives world x = -design x, world y = design y. Every design coordinate passes through
to_world() or world_box() below. A bottom-side part keeps that same mapping: B.Cu does not mirror its design x a second time.

Seen standing outside the I/O face, looking at the case, +x is on the viewer's right:
  host USB-C J3 on the left, HDMI J2 on the right, power USB-C J5 in the left wall (-x), microSD J7 in the right wall (+x).

r8 (40 x 40 board, three mounting holes, no hole in the design (18, 18) corner):
  tray   Al 6061, black anodized all over (inside too: the wall is 0.25 mm from the board edge), 0.75 mm walls, solid floor. Three posts
         carry the PCB; each is tied into its corner (a 0.05 mm slot between post and wall cannot be machined) and ends in a 3.2 mm neck
         that bears on the 2.9 mm GND ring only, so no bare metal comes within 0.3 mm of non-GND copper. A boss under U7 (TC358743,
         bottom side) for a 0.5 mm gap pad.
  lid    Al 6061, black anodized, top 1.0 mm, LCD window 33.4 mm, three integral posts, as r7f otherwise.
  plate  0.8 mm bare Al between the halves, clamped by the post shoulders; the lid rim, plate and tray rim seat metal to metal.
r8b (REVIEW_r8 critical-1, major-1, major-2):
  antenna  external. The back-wall window and its printed insert are gone; the J4 harness opening is cut in the aluminium. A 6.5 mm hole
           in the -x wall takes an SMA bulkhead jack on a U.FL pigtail from J8; a pocket in the 4.2 mm floor behind it clears the 8 mm
           hex and the crimp sleeve. Needs the H 23 floor: a 1.2 mm floor leaves 7.3 mm under the board, less than the hex.
  z        one rigid seat only: lid rim, plate, tray rim. The lid posts stop SLOT_GAP above the PCB and a foam washer fills that gap,
           so board thickness (+-10 %) no longer fights the rim. The board sits on the tray posts under the washers' preload.
  edge     the card opening in the +x wall spans the board's thickness plus 0.35 mm, so the J7 pads (0.2 mm from the edge) and ESP_EN
           (0.24 mm) face no metal. All other non-GND copper is 0.40 mm or more inside the edge (board r8b).
  M2 x 16 screws enter from the bottom, pass the tray post and PCB, and bite into the lid posts (tapped M2 in the aluminium).
  The fourth corner has no screw: the board has no hole there. See LID_HOLD.
usage: gen_case.py <design.json> <out_dir>   (H 23, floor 4.2 only: see antenna above)
"""
import argparse
import json
import os
import sys

import cadquery as cq

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ap = argparse.ArgumentParser()
ap.add_argument('design')
ap.add_argument('out')
ap.add_argument('--H', type=float, default=23.0)
ap.add_argument('--floor', type=float, default=4.2)
A = ap.parse_args()
D = json.load(open(A.design, encoding='utf-8'))
OUT = A.out
os.makedirs(OUT, exist_ok=True)
FONT = 'C:/Windows/Fonts/arialbd.ttf'


def to_world(x, y):
    """Design point to case point. See the module docstring for why x changes sign and y does not."""
    return -x, y


def world_box(bbox):
    """Design (x0, y0, x1, y1) to case (x0, y0, x1, y1), still ordered low to high."""
    ax, ay = to_world(bbox[0], bbox[1])
    bx, by = to_world(bbox[2], bbox[3])
    return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)


S, H, WALL, FLOOR = 42.0, A.H, 0.75, A.floor
TOP, EDGE_GAP = 1.0, 0.25
R_OUT, R_IN = 0.8, 0.5        # R_IN clears the board's 1.5 mm corner chamfer by 0.21 mm; R_OUT leaves the outer faces flat to |u| 20.2
# the r7f stack above the floor's inner face, unchanged: HDMI is 6.0 mm under the board
Z_BOT = FLOOR + 7.3
Z_TOP = Z_BOT + 1.2
SPLIT = Z_TOP + 4.1
PLATE_T = 0.8
LID_Z0 = SPLIT + PLATE_T
assert abs(H - (LID_Z0 + 5.4)) < 1e-9, f'H {H} and FLOOR {FLOOR} do not fit the stack: H must be FLOOR + 18.8'
half = S / 2
CAV = half - WALL
_B = D['board']
assert abs(_B['x0'] + _B['x1']) < 1e-6 and abs(_B['y0'] + _B['y1']) < 1e-6, 'the case is built for a board centred on the design origin'
assert abs((_B['x1'] - _B['x0']) + 2 * (EDGE_GAP + WALL) - S) < 1e-6 and abs((_B['y1'] - _B['y0']) + 2 * (EDGE_GAP + WALL) - S) < 1e-6, 'board + gaps + walls must make S'
Y0, Y1 = -half, half
HOLES = [to_world(x, y) for x, y in _B['holes']]
LCD_D, LCD_T = 39.0, 3.6
parts = {p['ref']: p for p in D['parts']}

POST_D, SHOULDER_D, PLATE_HOLE_D = 3.8, 5.5, 4.2
# r8b: the lid posts end SLOT_GAP above the PCB; a foam washer of free height WASHER['t'] works in that gap
SLOT_GAP = 0.9
WASHER = dict(od=3.6, id=2.2, t=1.5)
MATERIALS = {'tray': 'Al 6061-T6, CNC, black anodized all over, inside faces included (emissivity ~0.85; insulation toward the board edge) except the masked contact faces (bare Al or conductive chromate conversion)',
             'lid': 'Al 6061-T6, CNC, black anodized (emissivity ~0.85) except the masked contact faces (bare Al or conductive chromate conversion)',
             'plate': 'Al 5052 or 6061, 0.8 mm, bare (no anodize, no paint); no thermal paste on any contact face (posts, shoulders, rims)',
             'gapfill': 'dispensed gap filler, low modulus, about 3 W/mK',
             'boss_pad': 'gap pad 5.6 x 5.6 x 0.5 mm, soft (Shore 00 below 40), about 3 W/mK, between the U7 package and the tray boss',
             'washer': 'closed-cell silicone or urethane (PORON type) foam washer, OD %g x ID %g x %g mm free, one on each screw between the PCB top and the lid post end; not conductive' % (WASHER['od'], WASHER['id'], WASHER['t']),
             'pigtail': 'U.FL (I-PEX MHF1) plug to SMA bulkhead jack, 1.13 mm cable, 100 mm; 1/4-36 UNS thread, 8 mm rear hex, nut and lock washer outside; external 2.4 GHz antenna, SMA plug'}
MASKED = {'post_shoulder': 'lid post shoulders (5.5 mm) that clamp the plate',
          'lid_rim': 'lid rim face that sits on the plate',
          'post_bore': 'lid M2 tapped bores (thread contact to the screw)',
          'tray_post_end': 'tray post necked end faces that bear on the PCB bottom GND rings',
          'tray_rim': 'tray rim face under the plate'}
ACCEPT = ['lid to board GND (J5 USB-C shell) < 1 ohm, measured after assembly with a 4-wire or low-range ohmmeter',
          'plate to board GND < 1 ohm, measured the same way',
          'tray to board GND < 1 ohm, measured the same way']
LID_HOLD = ('three M2 screws only. The board has no hole in the fourth corner (design (18, 18)), so nothing can pass it to a screw; '
            'that corner holds C72/C73 underneath and the J6 plug and wires on top. The lid is a rigid aluminium cup and its fourth corner '
            'rests on the plate and the tray rim, so it cannot be pushed in; three clamped corners fix its plane. A lip into the tray is not '
            'possible because the plate lies across the split.')
SHIELD_Z = Z_TOP + 3.31      # module top (Waveshare ESP32-P4-Module height 3.31 mm, as check_case HEIGHT)
PAD_P4 = (-3.0, 5.4, 12.0)   # design x, y, side: over the module centre (thermal model pad 'p4' area)
PAD_C6 = (-10.0, 12.4, 7.0)
TRAY_POST_D, BORE_D, HEAD_D, HEAD_Z = 4.0, 2.4, 4.2, 1.8
NECK_D, TRAY_NECK_H, LID_NECK_H = 3.2, 0.5, 1.3   # neck: GND ring 2.9 plus 0.15; the lid post stays 3.2 mm up to 1.3 mm above the PCB, past the 1.0 mm C1 beside the design (-18, 18) post
assert SLOT_GAP < LID_NECK_H
PILOT_D = 1.6
U7_PKG_H, BOSS, BOSS_GAP = 1.2, 5.6, 0.5


def at(ref):
    return to_world(parts[ref]['x'], parts[ref]['y'])


HDMI_X = at('J2')[0]
USB_X = at('J3')[0]
J5_Y = at('J5')[1]
J7_Y = at('J7')[1]
J4_X = at('J4')[0]
U7_X, U7_Y = at('U7')
HDMI_Z = Z_BOT - 3.0
# HDMI opening in the shape of the receptacle (2026-11-16). It was a 16.2 x 6.8 rectangle; the outline stays inside that rectangle, with the
# two corners on the board side cut off. J2 is on the bottom side, so its shell hangs below the board with its narrow edge up against the
# board (XunPu HDMI-001S drawing: shell 14.95 x 5.96, the two cut corners are on the PCB side). The drawing does not dimension the cut;
# it scales to about 2.2 mm. 1.8 mm here leaves the wall clear of a shell whose cut is as small as 1.6 mm (check_case.py).
HDMI_OPEN = dict(x=HDMI_X, z=HDMI_Z, w=16.2, h=6.8, chamfer=1.8, narrow_edge='board side (+z)')
_w, _h, _c = HDMI_OPEN['w'] / 2, HDMI_OPEN['h'] / 2, HDMI_OPEN['chamfer']
HDMI_OPEN_PTS = [(-_w, -_h), (_w, -_h), (_w, _h - _c), (_w - _c, _h), (-_w + _c, _h), (-_w, _h - _c)]   # (x, z) about (HDMI_X, HDMI_Z)
USB_Z = Z_TOP + 1.6
assert parts['J5']['x'] > 0 and at('J5')[0] < 0, 'J5 must land on the -x wall'
assert parts['J7']['x'] < 0 and at('J7')[0] > 0, 'J7 must land on the +x wall'
BACK_POST = max(HOLES, key=lambda h: h[1] + abs(h[0]))
J4_OPEN = dict(x0=J4_X - 4.6, x1=J4_X + 4.6, z0=Z_BOT - 4.6, z1=Z_BOT - 0.05)
assert J4_OPEN['x1'] < BACK_POST[0] - TRAY_POST_D / 2 - 0.5, 'J4 opening runs into the back post'
SD_RELIEF = 1.2 + 0.35       # the card opening's top edge above the board's bottom face: 0.35 mm past the top face, so neither the J7 pads (B.Cu) nor ESP_EN (F.Cu, 0.24 mm from the edge) face metal
# r8b external antenna: SMA bulkhead jack in the -x wall (seen from the I/O face: the left side), under the board, clear of the J5 plug
assert abs(FLOOR - 4.2) < 1e-9, 'the SMA pocket needs the 4.2 mm floor (H 23)'
ANT = dict(wall='-x', y=-10.0, z=6.0, hole=6.5, hex_af=8.0, hex_t=2.5, sleeve_d=5.0, sleeve_l=10.0)
POCKET = dict(x0=-CAV, x1=-CAV + 13.0, y0=ANT['y'] - 4.9, y1=ANT['y'] + 4.9, z0=1.0)
HEX_AC = ANT['hex_af'] / 0.8660254
assert ANT['z'] - HEX_AC / 2 > POCKET['z0'] + 0.3 and ANT['z'] + HEX_AC / 2 < Z_BOT - 0.3, 'SMA hex (any rotation) must clear the pocket floor and the board'
assert all(not (POCKET['y0'] - (HEAD_D + 1.2) / 2 - 0.3 < h[1] < POCKET['y1'] + (HEAD_D + 1.2) / 2 + 0.3) for h in HOLES if h[0] < 0), 'SMA pocket too close to a screw head recess'
assert at('J5')[1] - 6.0 > ANT['y'] + 5.0, 'a 10 mm antenna base must stay clear of the J5 plug overmould'


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def rbox(w, d, z0, z1, r):
    return cq.Workplane('XY').rect(w, d).extrude(z1 - z0).edges('|Z').fillet(r).translate((0, 0, z0))


def cyl(x, y, z0, z1, d):
    return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def text_on(txt, size, depth, face, u, z):
    """Debossed text. face: F front (y-), B back (y+), R right (x+), L left (x-). u is the world coordinate along the wall."""
    t = cq.Workplane('XY').text(txt, size, depth + 0.5, font='Arial', fontPath=FONT, kind='bold', halign='center', valign='center')
    t = t.rotate((0, 0, 0), (1, 0, 0), 90)  # upright, the solid runs toward -y, which is outward on the front face
    if face == 'F':
        return t.translate((u, Y0 + depth, z))
    if face == 'B':
        return t.rotate((0, 0, 0), (0, 0, 1), 180).translate((u, Y1 - depth, z))
    if face == 'R':
        return t.rotate((0, 0, 0), (0, 0, 1), 90).translate((half - depth, u, z))
    return t.rotate((0, 0, 0), (0, 0, 1), -90).translate((-half + depth, u, z))


LABEL_D = 0.3
Z_LAB_TRAY, Z_LAB_LID = Z_BOT + 2.8, Z_BOT + 8.8

# ---------- tray
tray = rbox(S, S, 0, SPLIT, R_OUT).cut(rbox(2 * CAV, 2 * CAV, FLOOR, SPLIT + 1, R_IN))
for x, y in HOLES:
    sx, sy = (1 if x > 0 else -1), (1 if y > 0 else -1)
    wx, wy, r = sx * (half - WALL / 2), sy * (half - WALL / 2), TRAY_POST_D / 2
    zt = Z_BOT - TRAY_NECK_H
    post = cyl(x, y, FLOOR - 0.01, zt, TRAY_POST_D)
    post = post.union(box(min(x, wx), max(x, wx), y - r, y + r, FLOOR - 0.01, zt))
    post = post.union(box(x - r, x + r, min(y, wy), max(y, wy), FLOOR - 0.01, zt))
    post = post.union(box(min(x, wx), max(x, wx), min(y, wy), max(y, wy), FLOOR - 0.01, zt))
    post = post.union(cyl(x, y, zt - 0.01, Z_BOT, NECK_D))
    if FLOOR < HEAD_Z + 0.6:   # thin floor: keep 0.6 mm of metal over the head recess
        post = post.union(cyl(x, y, 0, HEAD_Z + 0.6, HEAD_D + 1.2))
    tray = tray.union(post)
for x, y in HOLES:
    tray = tray.cut(cyl(x, y, -1, Z_BOT + 1, BORE_D))
    tray = tray.cut(cyl(x, y, -1, HEAD_Z, HEAD_D))
tray = tray.union(box(U7_X - BOSS / 2, U7_X + BOSS / 2, U7_Y - BOSS / 2, U7_Y + BOSS / 2, FLOOR - 0.01, Z_BOT - U7_PKG_H - BOSS_GAP))
tray = tray.cut(cq.Workplane('XZ').polyline(HDMI_OPEN_PTS).close().extrude(WALL + 2).translate((HDMI_X, Y0 + WALL + 1, HDMI_Z)))
tray = tray.cut(cq.Workplane('XZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((USB_X, Y0 + WALL + 1, USB_Z)))
tray = tray.cut(cq.Workplane('YZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((-half - 1, J5_Y, USB_Z)))
tray = tray.cut(box(half - WALL - 0.01, half + 1, J7_Y - 6.3, J7_Y + 6.3, Z_BOT - 2.2, Z_BOT + SD_RELIEF))
tray = tray.cut(box(J4_OPEN['x0'], J4_OPEN['x1'], Y1 - WALL - 0.01, Y1 + 1, J4_OPEN['z0'], J4_OPEN['z1']))
tray = tray.cut(box(POCKET['x0'], POCKET['x1'], POCKET['y0'], POCKET['y1'], POCKET['z0'], FLOOR + 0.01))
tray = tray.cut(cq.Workplane('YZ').circle(ANT['hole'] / 2).extrude(WALL + 2).translate((-half - 1, ANT['y'], ANT['z'])))
tray = tray.cut(text_on('ANT', 2.0, LABEL_D, 'L', ANT['y'], Z_LAB_TRAY))
tray = tray.cut(text_on('ATX', 2.0, LABEL_D, 'B', J4_X, Z_LAB_TRAY))
tray = tray.cut(text_on('TF', 2.0, LABEL_D, 'R', J7_Y, Z_LAB_TRAY))
tray = tray.cut(text_on('HDMI', 1.9, LABEL_D, 'F', HDMI_X - 1.0, Z_LAB_TRAY))

# ---------- lid
lid = rbox(S, S, LID_Z0, H, R_OUT).cut(rbox(2 * CAV, 2 * CAV, LID_Z0 - 1, H - TOP, R_IN))
lid = lid.cut(cyl(0, 0, H - TOP - 1, H + 1, LCD_D - 5.6))
ring = cyl(0, 0, H - TOP - 1.2, H - TOP, LCD_D + 3.0).cut(cyl(0, 0, H - TOP - 2, H, LCD_D + 0.5))
lid = lid.union(ring.intersect(rbox(2 * CAV + 0.02, 2 * CAV + 0.02, 0, H, R_IN)))
for x, y in HOLES:
    post = cyl(x, y, Z_TOP + LID_NECK_H, H - TOP, POST_D).union(cyl(x, y, Z_TOP + SLOT_GAP, Z_TOP + LID_NECK_H + 0.01, NECK_D))
    post = post.union(cyl(x, y, LID_Z0, H - TOP, SHOULDER_D))   # clamps the plate: ground and heat path
    lid = lid.union(post.intersect(box(-CAV - 0.01, CAV + 0.01, -CAV - 0.01, CAV + 0.01, 0, H)))
    lid = lid.cut(cyl(x, y, Z_TOP - 1, H - TOP - 0.6, PILOT_D))
lid = lid.cut(cyl(0, 0, Z_TOP - 1, H - TOP, LCD_D + 0.5).intersect(box(-half, half, Y0, Y1, H - TOP - LCD_T - 0.4, H - TOP)))
lid = lid.cut(text_on('MF KVM', 3.0, LABEL_D, 'F', HDMI_X - 1.0, Z_LAB_LID))
lid = lid.cut(text_on('HOST', 1.9, LABEL_D, 'F', USB_X, Z_LAB_LID))
lid = lid.cut(text_on('5V', 2.0, LABEL_D, 'L', J5_Y, Z_LAB_LID))

# ---------- plate: case outline, J6 cut-out (+0.5 mm), post holes
jx0, jy0, jx1, jy1 = world_box(parts['J6']['bbox'])
plate = rbox(S, S, SPLIT, LID_Z0, R_OUT)
plate = plate.cut(box(jx0 - 0.5, jx1 + 0.5, jy0 - 0.5, jy1 + 0.5, SPLIT - 1, LID_Z0 + 1))
for x, y in HOLES:
    plate = plate.cut(cyl(x, y, SPLIT - 1, LID_Z0 + 1, PLATE_HOLE_D))
gap = None
for dx, dy, side in (PAD_P4, PAD_C6):
    wx, wy = to_world(dx, dy)
    g = box(wx - side / 2, wx + side / 2, wy - side / 2, wy + side / 2, SHIELD_Z, SPLIT)
    gap = g if gap is None else gap.union(g)

SPEC = dict(materials=MATERIALS, masked=MASKED, acceptance=ACCEPT, lid_hold=LID_HOLD,
            envelope=[S, S, H], wall=WALL, floor=FLOOR, corner_r=[R_OUT, R_IN], stack=dict(z_bot=Z_BOT, z_top=Z_TOP, split=SPLIT, lid_z0=LID_Z0),
            plate_t=PLATE_T, split=SPLIT, lid_z0=LID_Z0, pads={'P4': PAD_P4, 'C6': PAD_C6}, shield_z=SHIELD_Z,
            post_d=POST_D, shoulder_d=SHOULDER_D, plate_hole_d=PLATE_HOLE_D, tray_post_d=TRAY_POST_D, neck=dict(d=NECK_D, tray_h=TRAY_NECK_H, lid_h=LID_NECK_H),
            screws='3 x M2 x 16 from the bottom, head seat z %.1f, tapped M2 in the lid posts' % HEAD_Z,
            boss=dict(ref='U7', centre=[U7_X, U7_Y], size=BOSS, top_z=Z_BOT - U7_PKG_H - BOSS_GAP, gap=BOSS_GAP, package_h=U7_PKG_H),
            j4_opening=J4_OPEN, hdmi_opening=HDMI_OPEN, antenna=ANT, sma_pocket=POCKET, sd_relief=SD_RELIEF,
            compliant=dict(slot_gap=SLOT_GAP, washer=WASHER, note='the only rigid seat is lid rim / plate / tray rim; the lid posts do not touch the PCB'),
            panel='no V-cut on any edge; routed outline with mouse-bite tabs set inside the outline or filed flush after break-out: nothing may stand proud of the 40.00 mm outline',
            assembly=['SMA jack through the -x wall hole from inside, lock washer and nut outside, before the PCB goes in', 'U.FL plug onto J8 (board underside), cable laid on the floor clear of the U7 boss',
                      'PCB onto the three tray posts', 'one foam washer over each screw hole on the PCB top', 'gap filler on the module shield, plate, lid; three M2 x 16 from below'])
for stale in ('mf_kvm_antenna_insert.step', 'mf_kvm_antenna_insert.stl'):
    if os.path.exists(f'{OUT}/{stale}'):
        os.remove(f'{OUT}/{stale}')
for name, solid in (('tray', tray), ('lid', lid), ('plate', plate)):
    v = solid.val()
    print(f'{name:15s} valid {v.isValid()} solids {len(solid.solids().vals())} vol {v.Volume():.1f} bbox {v.BoundingBox().xmin:.2f}..{v.BoundingBox().xmax:.2f} {v.BoundingBox().ymin:.2f}..{v.BoundingBox().ymax:.2f} {v.BoundingBox().zmin:.2f}..{v.BoundingBox().zmax:.2f}')
    cq.exporters.export(solid, f'{OUT}/mf_kvm_{name}.stl', tolerance=0.02, angularTolerance=0.15)
    cq.exporters.export(solid, f'{OUT}/mf_kvm_{name}.step')
cq.exporters.export(gap, f'{OUT}/mf_kvm_gapfill.step')
json.dump(SPEC, open(f'{OUT}/case_spec.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(f'case outside {S:g} x {S:g} x {H:g} mm, wall {WALL}, floor {FLOOR}; z bot {Z_BOT:.2f} top {Z_TOP:.2f} split {SPLIT:.2f} lid {LID_Z0:.2f}; holes {HOLES}')
print('world: J2 HDMI x', round(HDMI_X, 2), ' J3 USB x', round(USB_X, 2), ' J5 y', round(J5_Y, 2), ' J7 y', round(J7_Y, 2), ' J4 x', round(J4_X, 2), ' U7', (U7_X, U7_Y))
print('J4 opening', J4_OPEN, 'antenna', ANT, 'pocket', POCKET)
