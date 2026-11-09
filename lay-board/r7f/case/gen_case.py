# -*- coding: utf-8 -*-
"""MF KVM case: tray and lid built from the routed board's real positions. Writes STL and STEP; check_case.py judges them.

Two frames, and they differ by a mirror:
  design/KiCad: x right, y DOWN as seen from the top side, z toward the viewer. That is left-handed.
  case (world): origin at the PCB centre, x right, y toward the back wall, z up from the desk, I/O face at y = -22. Right-handed.
The only rigid way to put the board in the case with the I/O edge at -y and its top side up is a turn by 180 degrees in the
STEP frame (x, -y_kicad, z), which gives world x = -design x, world y = design y. Every design coordinate passes through
to_world() or world_box() below. A bottom-side part keeps that same mapping: B.Cu does not mirror its design x a second time.

Seen standing outside the I/O face, looking at the case, +x is on the viewer's right:
  host USB-C J3 on the left, HDMI J2 on the right, power USB-C J5 in the left wall (-x), microSD J7 in the right wall (+x).

Four M2 x 16 screws enter from the bottom, pass the tray post and PCB, and bite into the lid posts.

r7f (analysis_r7d/thermal/THERMAL_REPORT.md 6.5, configuration f1, approved 2026-11-09):
  lid    Al 6061, black anodized (emissivity about 0.85), top 1.0 mm, wall 1.6 mm, LCD window 33.4 mm, four integral posts.
         The lid now starts at SPLIT + PLATE_T; its old plastic lip is gone (the plate lies across the split).
         12 vent slots 1.2 x 5 mm in the top, in the strip behind the LCD seat (the seat is 42 mm across a 44 mm case, so there is
         no room beside it at the side walls).
  plate  0.8 mm Al between the halves at z SPLIT .. SPLIT + 0.8, outline = the case outline, cut out around J6 (+0.5 mm) and the
         posts; the post passes a 4.2 mm hole and a 5.5 mm shoulder on the post presses the plate, metal on metal (ground and heat).
  pads   dispensed low-modulus gap filler (about 3 W/mK) between the module shield and the plate, only over the P4 (12 x 12 mm) and
         the C6 (7 x 7 mm) areas; written as mf_kvm_gapfill.step for the drawing, not a printed part.
  tray   stays plastic but heat resistant: ASA, ABS, PC or PA12 (HDT above 90 C), not PLA.
  ground lid posts bear on the plated GND rings of H1-H4 (the J6-corner post stops above J6 and does not); the plate is grounded
         through the four post shoulders. Anodize insulates: the post end faces, shoulders, lid rim and pilot bores are masked
         (case_spec.json 'masked'), the plate is bare, and 'lid / plate to GND < 1 ohm' is an assembly acceptance test.
usage: gen_case.py <design.json> <out_dir>
"""
import json
import os
import sys

import cadquery as cq

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
D = json.load(open(sys.argv[1], encoding='utf-8'))
OUT = sys.argv[2]
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


S, H = 44.0, 20.0
WALL, FLOOR, TOP = 1.6, 1.2, 1.0
Z_BOT, Z_TOP = 8.5, 9.7
SPLIT = 13.8
PLATE_T = 0.8                 # r7f Al spreader plate, z SPLIT .. SPLIT + PLATE_T
LID_Z0 = SPLIT + PLATE_T
# REVIEW_r7f major-2: anodize is an insulator, so the faces that carry ground must be masked from it (bare Al, or a conductive
# chromate conversion coat) and the plate stays bare; the ground is accepted only by a resistance measurement after assembly.
MATERIALS = {'lid': 'Al 6061-T6, black anodized (emissivity ~0.85) except the masked contact faces (bare Al or conductive chromate conversion)',
             'plate': 'Al 5052 or 6061, 0.8 mm, bare (no anodize, no paint); no thermal paste on any contact face (posts, shoulders, rim)',
             'tray': 'ASA (or ABS / PC / PA12; heat deflection above 90 C; not PLA)', 'gapfill': 'dispensed gap filler, low modulus, about 3 W/mK'}
MASKED = {'post_end': 'lid post end faces that bear on the PCB GND rings (H1-H4; the J6-corner post end face too, it bears on the plate area only via its shoulder)',
          'post_shoulder': 'post shoulders (5.5 mm) that clamp the plate',
          'lid_rim': 'lid rim face (z 14.6) that sits on the plate',
          'post_bore': 'M2 pilot bores (thread contact to the screw)'}
ACCEPT = ['lid to board GND (J5 USB-C shell) < 1 ohm, measured after assembly with a 4-wire or low-range ohmmeter',
          'plate to board GND < 1 ohm, measured the same way']
SHIELD_Z = Z_TOP + 3.31      # module top (Waveshare ESP32-P4-Module height 3.31 mm, as check_case HEIGHT)
PAD_P4 = (-3.0, 5.4, 12.0)   # design x, y, side: over the module centre (thermal model pad 'p4' area)
PAD_C6 = (-10.0, 12.4, 7.0)
FIT = 0.15          # per side, lid lip into tray
half = S / 2
# r7c: the board outline and holes come from design.json (gen_mini 'board'); the walls keep 2 mm outside every board edge.
# The board is symmetric in x, so the x walls stay at +-22; in y the front wall stays at -22 and the back wall follows the board.
_B = D.get('board') or {'x0': -20.0, 'x1': 20.0, 'y0': -20.0, 'y1': 20.0, 'holes': [(18.0, -18.0), (-18.0, -18.0), (18.0, 18.0), (-18.0, 18.0)]}
assert abs(_B['x0'] + _B['x1']) < 1e-6 and abs(_B['x1'] - _B['x0'] + 4.0 - S) < 1e-6, 'case width is built for a 40 mm board, symmetric in x'
Y0, Y1 = _B['y0'] - 2.0, _B['y1'] + 2.0
SY, CY = Y1 - Y0, (Y0 + Y1) / 2
HOLES = [(-x, y) for x, y in _B['holes']]   # design to world: x changes sign
LCD_D, LCD_T = 39.0, 3.6
parts = {p['ref']: p for p in D['parts']}


def at(ref):
    return to_world(parts[ref]['x'], parts[ref]['y'])


HDMI_X = at('J2')[0]
USB_X = at('J3')[0]
J5_Y = at('J5')[1]
J7_Y = at('J7')[1]
J4_X = at('J4')[0]
HDMI_Z = Z_BOT - 3.0
USB_Z = Z_TOP + 1.6
# the design +x board edge is the case's -x wall, and the design -x edge the +x wall
assert parts['J5']['x'] > 0 and to_world(parts['J5']['x'], 0)[0] < 0, 'J5 must land on the -x wall'
assert parts['J7']['x'] < 0 and to_world(parts['J7']['x'], 0)[0] > 0, 'J7 must land on the +x wall'


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


# ---------- tray
outer = rbox(S, SY, 0, SPLIT, 3.0).translate((0, CY, 0))
cavity = rbox(S - 2 * WALL, SY - 2 * WALL, FLOOR, SPLIT + 1, 1.6).translate((0, CY, 0))
tray = outer.cut(cavity)
# posts carry the PCB at Z_BOT; bottom-side parts keep clear of them
for x, y in HOLES:
    tray = tray.union(cyl(x, y, 0, Z_BOT, 4.4))
    # tie the post to the corner so it prints without a free-standing column
    sx, sy = (1 if x > 0 else -1), (1 if y > 0 else -1)
    tray = tray.union(box(min(x, sx * (half - WALL / 2)), max(x, sx * (half - WALL / 2)), y - 1.0, y + 1.0, FLOOR, Z_BOT))
    _yw = (Y1 - WALL / 2) if sy > 0 else (Y0 + WALL / 2)
    tray = tray.union(box(x - 1.0, x + 1.0, min(y, _yw), max(y, _yw), FLOOR, Z_BOT))
for x, y in HOLES:
    tray = tray.cut(cyl(x, y, -1, Z_BOT + 1, 2.4))
    tray = tray.cut(cyl(x, y, -1, 1.8, 4.2))  # screw head recess
# I/O face: HDMI and host USB-C, with shallow pockets so overmoulded plugs seat fully
tray = tray.cut(box(HDMI_X - 8.1, HDMI_X + 8.1, Y0 - 1, Y0 + WALL + 1, HDMI_Z - 3.4, HDMI_Z + 3.4))
tray = tray.cut(box(HDMI_X - 10.3, HDMI_X + 10.3, Y0 - 1, Y0 + 0.8, -1, HDMI_Z + 5.9))
tray = tray.cut(cq.Workplane('XZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((USB_X, Y0 + WALL + 1, USB_Z)))
tray = tray.cut(box(USB_X - 6.3, USB_X + 6.3, Y0 - 1, Y0 + 0.8, USB_Z - 4.2, SPLIT + 1))
# -x wall: power USB-C J5
tray = tray.cut(cq.Workplane('YZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((-half - 1, J5_Y, USB_Z)))
tray = tray.cut(box(-half - 1, -half + 0.8, J5_Y - 6.3, J5_Y + 6.3, USB_Z - 4.2, SPLIT + 1))
# +x wall: microSD J7, with a finger scoop to grip the card
tray = tray.cut(box(half - WALL - 1, half + 1, J7_Y - 6.3, J7_Y + 6.3, Z_BOT - 2.2, Z_BOT - 0.05))
tray = tray.cut(box(half - 0.8, half + 1, J7_Y - 8.5, J7_Y + 8.5, Z_BOT - 4.0, Z_BOT + 1.0))
# back wall: ATX harness J4
tray = tray.cut(box(J4_X - 4.6, J4_X + 4.6, Y1 - WALL - 1, Y1 + 1, Z_BOT - 4.6, Z_BOT - 0.05))
# vents under the PCB. The bridge U7 and the regulators U2, L1 sit toward the -x wall and the back, so the slots go there.
# They stop at the wall's inner face so they do not nibble a post, and at z 6.0 so 1.1 mm of wall stays under the J5 pocket.
VENT_Z = (2.2, 6.0)
for i in range(9):      # -x wall, from beside U7 to beside L1
    y = -10.0 + i * 3.0
    tray = tray.cut(box(-half - 1, -half + WALL + 0.2, y, y + 1.4, *VENT_Z))
for i in range(4):      # back wall, behind U2, L1 and U12
    x = -16.4 + i * 3.0
    tray = tray.cut(box(x, x + 1.4, Y1 - WALL - 0.2, Y1 + 1, *VENT_Z))
tray = tray.cut(text_on('ATX', 2.0, 0.35, 'B', J4_X, 10.5))
tray = tray.cut(text_on('TF', 2.0, 0.35, 'R', J7_Y, 11.0))

# ---------- lid (r7f: Al, starts above the plate, no lip)
lid = rbox(S, SY, LID_Z0, H, 3.0).cut(rbox(S - 2 * WALL, SY - 2 * WALL, LID_Z0 - 1, H - TOP, 1.6)).translate((0, CY, 0))
# overmoulded USB-C plugs are taller than the tray: the pocket carries on up the lid skirt
lid = lid.cut(box(USB_X - 6.3, USB_X + 6.3, Y0 - 1, Y0 + 0.8, SPLIT - 2, USB_Z + 4.2))
lid = lid.cut(box(-half - 1, -half + 0.8, J5_Y - 6.3, J5_Y + 6.3, SPLIT - 2, USB_Z + 4.2))
# round LCD: window through the top, seat for the module under it
lid = lid.cut(cyl(0, 0, H - TOP - 1, H + 1, LCD_D - 5.6))
ring = cyl(0, 0, H - TOP - 1.2, H - TOP, LCD_D + 3.0).cut(cyl(0, 0, H - TOP - 2, H, LCD_D + 0.5))
lid = lid.union(ring.intersect(rbox(S - 2 * WALL + 0.02, SY - 2 * WALL + 0.02, 0, H, 1.6).translate((0, CY, 0))))
# posts from the lid down to the PCB, screws bite into the 1.6 mm pilot.
# J6 opens toward the -x wall right next to the (-18, +18) screw, so its plug and wires need that corner. There the post starts
# above the J6 relief: a full-height post would leave under 0.1 mm of plastic outside the thread, and the wires would hit it.
J6_POST_Z = Z_TOP + 4.6
jx0, jy0, jx1, jy1 = world_box(parts['J6']['bbox'])
J6_CORNER = min(HOLES, key=lambda h: (h[0] - (jx0 + jx1) / 2) ** 2 + (h[1] - (jy0 + jy1) / 2) ** 2)
POST_D, SHOULDER_D, PLATE_HOLE_D = 3.8, 5.5, 4.2
for x, y in HOLES:
    z0 = J6_POST_Z if (x, y) == J6_CORNER else Z_TOP
    post = cyl(x, y, z0, H - TOP, POST_D)
    # r7f: shoulder from the plate top up; it clamps the plate (ground and heat path). The J6 corner post starts above the plate.
    post = post.union(cyl(x, y, max(LID_Z0, z0), H - TOP, SHOULDER_D))
    post = post.intersect(box(-half + WALL - 0.01, half - WALL + 0.01, Y0 + WALL - 0.01, Y1 - WALL + 0.01, 0, H))
    lid = lid.union(post)
    lid = lid.cut(cyl(x, y, z0 - 1, H - TOP - 0.6, 1.6))
lid = lid.cut(box(jx0 - 0.3, jx1 + 0.3, jy0 - 0.3, jy1 + 0.3, Z_TOP - 1, Z_TOP + 4.6))
lid = lid.cut(cyl(0, 0, Z_TOP - 1, H - TOP, LCD_D + 0.5).intersect(box(-half, half, Y0, Y1, H - TOP - LCD_T - 0.4, H - TOP)))
# r7f vents: 12 slots 1.2 x 5 mm (72 mm2) through the top, in the strip behind the LCD seat: 4 along x in the middle (world y 22, 24)
# and 8 along y further out (x +-8.8 .. +-14.5, y 20.1..25.1), clear of the seat ring (42 mm) and of the back post shoulders
VENTS = [(x, y, 5.0, 1.2) for y in (22.0, 24.0) for x in (-2.75, 2.75)] + [(x, 22.6, 1.2, 5.0) for x in (-14.5, -12.6, -10.7, -8.8, 8.8, 10.7, 12.6, 14.5)]
for x, y, w, d in VENTS:
    lid = lid.cut(box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, H - TOP - 0.5, H + 1))
# markings on the lid skirt; the HDMI pocket stays in the tray, so its labels sit above it
lid = lid.cut(text_on('MF KVM', 3.0, 0.4, 'F', HDMI_X - 1.0, 17.0))
lid = lid.cut(text_on('HOST', 1.9, 0.35, 'F', USB_X, 17.2))
lid = lid.cut(text_on('5V', 2.0, 0.35, 'L', J5_Y, 17.2))
lid = lid.cut(text_on('HDMI', 1.9, 0.35, 'F', HDMI_X - 1.0, 14.8))

# ---------- r7f fan duct (user decision on REVIEW_r7f major-4: external 5 V fan, own USB supply, not powered by the board).
# Through-flow: air enters the existing tray vents (9 in the -x wall, 4 in the back wall), passes the board-edge gap, leaves through
# the 12 lid slots into this duct and out through a 30 x 30 mm 5 V fan (suction) lying on the duct's top. The duct is a separate printed
# part (heat-resistant plastic, as the tray) held to the lid top with VHB tape; it covers the slot strip, stays clear of the LCD window,
# and its floor runs under the overhanging part of the fan so the fan can only draw through the slots.
FAN = 30.0                   # 30 x 30 mm axial fan, 24 mm screw pitch (common 3010 size; model ASSUMED, not chosen)
FAN_PITCH, FAN_SCREW = 24.0, 3.2
DUCT_H, DUCT_WALL = 5.0, 1.2
DUCT_Y0 = (LCD_D - 5.6) / 2 + 0.5     # front edge 0.5 mm behind the LCD window (r 16.7)
FAN_CY = DUCT_Y0 + FAN / 2            # fan centre (world y); the fan and duct overhang the back wall by about 20 mm
DUCT = dict(x0=-16.5, x1=16.5, y0=DUCT_Y0, y1=DUCT_Y0 + FAN, z0=H, z1=H + DUCT_H)   # 33 mm wide: covers every lid slot (x +-15.1)
duct = box(DUCT['x0'], DUCT['x1'], DUCT['y0'], DUCT['y1'], DUCT['z0'], DUCT['z1'])
duct = duct.cut(box(DUCT['x0'] + DUCT_WALL, DUCT['x1'] - DUCT_WALL, DUCT['y0'] + DUCT_WALL, DUCT['y1'] - DUCT_WALL, DUCT['z0'] - 1, DUCT['z1'] - DUCT_WALL))
# floor: open only over the lid's slot strip (inside the case outline), closed where the duct hangs past the back wall
duct = duct.union(box(DUCT['x0'], DUCT['x1'], Y1, DUCT['y1'], DUCT['z0'], DUCT['z0'] + DUCT_WALL))
duct = duct.cut(cyl(0, FAN_CY, DUCT['z1'] - DUCT_WALL - 1, DUCT['z1'] + 1, FAN - 2.0))     # fan opening
for sx in (-1, 1):
    for sy in (-1, 1):
        duct = duct.cut(cyl(sx * FAN_PITCH / 2, FAN_CY + sy * FAN_PITCH / 2, DUCT['z1'] - DUCT_WALL - 1, DUCT['z1'] + 1, FAN_SCREW - 0.6))   # self-tapping M3 into the plastic
print('duct valid', duct.val().isValid(), 'vol', round(duct.val().Volume(), 1), 'fan centre y', round(FAN_CY, 2), 'duct y', round(DUCT['y0'], 2), '..', round(DUCT['y1'], 2))
cq.exporters.export(duct, f'{OUT}/mf_kvm_fanduct.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(duct, f'{OUT}/mf_kvm_fanduct.step')

# ---------- r7f plate: case outline, J6 cut-out (+0.5 mm), post holes, the same overmould pockets as the walls
plate = rbox(S, SY, SPLIT, LID_Z0, 3.0).translate((0, CY, 0))
plate = plate.cut(box(jx0 - 0.5, jx1 + 0.5, jy0 - 0.5, jy1 + 0.5, SPLIT - 1, LID_Z0 + 1))
for x, y in HOLES:
    plate = plate.cut(cyl(x, y, SPLIT - 1, LID_Z0 + 1, PLATE_HOLE_D))
plate = plate.cut(box(USB_X - 6.3, USB_X + 6.3, Y0 - 1, Y0 + 0.8, SPLIT - 1, LID_Z0 + 1))
plate = plate.cut(box(-half - 1, -half + 0.8, J5_Y - 6.3, J5_Y + 6.3, SPLIT - 1, LID_Z0 + 1))
# gap filler regions (world), from the shield top to the plate
gap = None
for dx, dy, side in (PAD_P4, PAD_C6):
    wx, wy = to_world(dx, dy)
    g = box(wx - side / 2, wx + side / 2, wy - side / 2, wy + side / 2, SHIELD_Z, SPLIT)
    gap = g if gap is None else gap.union(g)
print('plate valid', plate.val().isValid(), 'vol', round(plate.val().Volume(), 1), '; gap filler vol', round(gap.val().Volume(), 1), 'mm3')
print('materials', MATERIALS)
import json as _json
FANSPEC = dict(fan=f'{FAN:g} x {FAN:g} mm 5 V axial fan, suction, on the duct top; powered from its own USB-A/USB-C 5 V supply, NOT from the board (board 5V budget unchanged)',
               flow_lps_assumed=0.15, duct=DUCT, inlets='tray vents: 9 in the -x wall, 4 in the back wall (unchanged)', outlets='12 lid slots under the duct',
               mount='duct on the lid top with VHB tape; fan screwed to the duct (4 x M3 self-tapping, 24 mm pitch)', material='duct printed in ASA / ABS / PC / PA12, as the tray')
_json.dump(dict(materials=MATERIALS, masked=MASKED, acceptance=ACCEPT, fan=FANSPEC, plate_t=PLATE_T, split=SPLIT, lid_z0=LID_Z0, vents=VENTS, pads={'P4': PAD_P4, 'C6': PAD_C6},
                shield_z=SHIELD_Z, post_d=POST_D, shoulder_d=SHOULDER_D, plate_hole_d=PLATE_HOLE_D), open(f'{OUT}/case_spec.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
cq.exporters.export(plate, f'{OUT}/mf_kvm_plate.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(plate, f'{OUT}/mf_kvm_plate.step')
cq.exporters.export(gap, f'{OUT}/mf_kvm_gapfill.step')
print('tray valid', tray.val().isValid(), 'vol', round(tray.val().Volume(), 1), 'solids', len(tray.solids().vals()))
print('lid  valid', lid.val().isValid(), 'vol', round(lid.val().Volume(), 1), 'solids', len(lid.solids().vals()))
print(f'case outside {S:g} x {SY:g} x {H:g} mm, y {Y0:g}..{Y1:g}; holes {HOLES}')
print('world: J2 HDMI x', round(HDMI_X, 2), ' J3 USB x', round(USB_X, 2), ' J5 y', round(J5_Y, 2), ' J7 y', round(J7_Y, 2), ' J4 x', round(J4_X, 2), ' J6 corner', J6_CORNER)
cq.exporters.export(tray, f'{OUT}/mf_kvm_tray.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(lid, f'{OUT}/mf_kvm_lid.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(tray, f'{OUT}/mf_kvm_tray.step')
cq.exporters.export(lid, f'{OUT}/mf_kvm_lid.step')
