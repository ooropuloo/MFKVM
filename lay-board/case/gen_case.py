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
FIT = 0.15          # per side, lid lip into tray
half = S / 2
HOLES = [(18.0, -18.0), (-18.0, -18.0), (18.0, 18.0), (-18.0, 18.0)]  # symmetric, so the same in both frames
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
        return t.translate((u, -half + depth, z))
    if face == 'B':
        return t.rotate((0, 0, 0), (0, 0, 1), 180).translate((u, half - depth, z))
    if face == 'R':
        return t.rotate((0, 0, 0), (0, 0, 1), 90).translate((half - depth, u, z))
    return t.rotate((0, 0, 0), (0, 0, 1), -90).translate((-half + depth, u, z))


# ---------- tray
outer = rbox(S, S, 0, SPLIT, 3.0)
cavity = rbox(S - 2 * WALL, S - 2 * WALL, FLOOR, SPLIT + 1, 1.6)
tray = outer.cut(cavity)
# posts carry the PCB at Z_BOT; bottom-side parts keep clear of them
for x, y in HOLES:
    tray = tray.union(cyl(x, y, 0, Z_BOT, 4.4))
    # tie the post to the corner so it prints without a free-standing column
    sx, sy = (1 if x > 0 else -1), (1 if y > 0 else -1)
    tray = tray.union(box(min(x, sx * (half - WALL / 2)), max(x, sx * (half - WALL / 2)), y - 1.0, y + 1.0, FLOOR, Z_BOT))
    tray = tray.union(box(x - 1.0, x + 1.0, min(y, sy * (half - WALL / 2)), max(y, sy * (half - WALL / 2)), FLOOR, Z_BOT))
for x, y in HOLES:
    tray = tray.cut(cyl(x, y, -1, Z_BOT + 1, 2.4))
    tray = tray.cut(cyl(x, y, -1, 1.8, 4.2))  # screw head recess
# I/O face: HDMI and host USB-C, with shallow pockets so overmoulded plugs seat fully
tray = tray.cut(box(HDMI_X - 8.1, HDMI_X + 8.1, -half - 1, -half + WALL + 1, HDMI_Z - 3.4, HDMI_Z + 3.4))
tray = tray.cut(box(HDMI_X - 10.3, HDMI_X + 10.3, -half - 1, -half + 0.8, -1, HDMI_Z + 5.9))
tray = tray.cut(cq.Workplane('XZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((USB_X, -half + WALL + 1, USB_Z)))
tray = tray.cut(box(USB_X - 6.3, USB_X + 6.3, -half - 1, -half + 0.8, USB_Z - 4.2, SPLIT + 1))
# -x wall: power USB-C J5
tray = tray.cut(cq.Workplane('YZ').slot2D(9.9, 4.1).extrude(WALL + 2).translate((-half - 1, J5_Y, USB_Z)))
tray = tray.cut(box(-half - 1, -half + 0.8, J5_Y - 6.3, J5_Y + 6.3, USB_Z - 4.2, SPLIT + 1))
# +x wall: microSD J7, with a finger scoop to grip the card
tray = tray.cut(box(half - WALL - 1, half + 1, J7_Y - 6.3, J7_Y + 6.3, Z_BOT - 2.2, Z_BOT - 0.05))
tray = tray.cut(box(half - 0.8, half + 1, J7_Y - 8.5, J7_Y + 8.5, Z_BOT - 4.0, Z_BOT + 1.0))
# back wall: ATX harness J4
tray = tray.cut(box(J4_X - 4.6, J4_X + 4.6, half - WALL - 1, half + 1, Z_BOT - 4.6, Z_BOT - 0.05))
# vents under the PCB. The bridge U7 and the regulators U2, L1 sit toward the -x wall and the back, so the slots go there.
# They stop at the wall's inner face so they do not nibble a post, and at z 6.0 so 1.1 mm of wall stays under the J5 pocket.
VENT_Z = (2.2, 6.0)
for i in range(9):      # -x wall, from beside U7 to beside L1
    y = -10.0 + i * 3.0
    tray = tray.cut(box(-half - 1, -half + WALL + 0.2, y, y + 1.4, *VENT_Z))
for i in range(4):      # back wall, behind U2, L1 and U12
    x = -16.4 + i * 3.0
    tray = tray.cut(box(x, x + 1.4, half - WALL - 0.2, half + 1, *VENT_Z))
tray = tray.cut(text_on('ATX', 2.0, 0.35, 'B', J4_X, 10.5))
tray = tray.cut(text_on('TF', 2.0, 0.35, 'R', J7_Y, 11.0))

# ---------- lid
lid = rbox(S, S, SPLIT, H, 3.0).cut(rbox(S - 2 * WALL, S - 2 * WALL, SPLIT - 1, H - TOP, 1.6))
lip = rbox(S - 2 * WALL - 2 * FIT, S - 2 * WALL - 2 * FIT, SPLIT - 1.2, SPLIT + 0.2, 1.5).cut(rbox(S - 2 * WALL - 2.4, S - 2 * WALL - 2.4, SPLIT - 2, SPLIT + 1, 1.0))
lid = lid.union(lip)
# keep the lip off the connector openings below the split
lid = lid.cut(box(USB_X - 6.3, USB_X + 6.3, -half - 1, -half + WALL + 1.3, SPLIT - 2, SPLIT))
lid = lid.cut(box(-half - 1, -half + WALL + 1.3, J5_Y - 6.3, J5_Y + 6.3, SPLIT - 2, SPLIT))
# overmoulded USB-C plugs are taller than the tray: the pocket carries on up the lid skirt
lid = lid.cut(box(USB_X - 6.3, USB_X + 6.3, -half - 1, -half + 0.8, SPLIT - 2, USB_Z + 4.2))
lid = lid.cut(box(-half - 1, -half + 0.8, J5_Y - 6.3, J5_Y + 6.3, SPLIT - 2, USB_Z + 4.2))
# round LCD: window through the top, seat for the module under it
lid = lid.cut(cyl(0, 0, H - TOP - 1, H + 1, LCD_D - 5.6))
ring = cyl(0, 0, H - TOP - 1.2, H - TOP, LCD_D + 3.0).cut(cyl(0, 0, H - TOP - 2, H, LCD_D + 0.5))
lid = lid.union(ring.intersect(rbox(S - 2 * WALL + 0.02, S - 2 * WALL + 0.02, 0, H, 1.6)))
# posts from the lid down to the PCB, screws bite into the 1.6 mm pilot.
# J6 opens toward the -x wall right next to the (-18, +18) screw, so its plug and wires need that corner. There the post starts
# above the J6 relief: a full-height post would leave under 0.1 mm of plastic outside the thread, and the wires would hit it.
J6_POST_Z = Z_TOP + 4.6
jx0, jy0, jx1, jy1 = world_box(parts['J6']['bbox'])
J6_CORNER = min(HOLES, key=lambda h: (h[0] - (jx0 + jx1) / 2) ** 2 + (h[1] - (jy0 + jy1) / 2) ** 2)
for x, y in HOLES:
    z0 = J6_POST_Z if (x, y) == J6_CORNER else Z_TOP
    post = cyl(x, y, z0, H - TOP, 3.8)
    post = post.intersect(box(-half + WALL - 0.01, half - WALL + 0.01, -half + WALL - 0.01, half - WALL + 0.01, 0, H))
    lid = lid.union(post)
    lid = lid.cut(cyl(x, y, z0 - 1, H - TOP - 0.6, 1.6))
lid = lid.cut(box(jx0 - 0.3, jx1 + 0.3, jy0 - 0.3, jy1 + 0.3, Z_TOP - 1, Z_TOP + 4.6))
lid = lid.cut(cyl(0, 0, Z_TOP - 1, H - TOP, LCD_D + 0.5).intersect(box(-half, half, -half, half, H - TOP - LCD_T - 0.4, H - TOP)))
# markings on the lid skirt; the HDMI pocket stays in the tray, so its labels sit above it
lid = lid.cut(text_on('MF KVM', 3.0, 0.4, 'F', HDMI_X - 1.0, 17.0))
lid = lid.cut(text_on('HOST', 1.9, 0.35, 'F', USB_X, 17.2))
lid = lid.cut(text_on('5V', 2.0, 0.35, 'L', J5_Y, 17.2))
lid = lid.cut(text_on('HDMI', 1.9, 0.35, 'F', HDMI_X - 1.0, 14.8))

print('tray valid', tray.val().isValid(), 'vol', round(tray.val().Volume(), 1), 'solids', len(tray.solids().vals()))
print('lid  valid', lid.val().isValid(), 'vol', round(lid.val().Volume(), 1), 'solids', len(lid.solids().vals()))
print('world: J2 HDMI x', round(HDMI_X, 2), ' J3 USB x', round(USB_X, 2), ' J5 y', round(J5_Y, 2), ' J7 y', round(J7_Y, 2), ' J4 x', round(J4_X, 2), ' J6 corner', J6_CORNER)
cq.exporters.export(tray, f'{OUT}/mf_kvm_tray.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(lid, f'{OUT}/mf_kvm_lid.stl', tolerance=0.02, angularTolerance=0.15)
cq.exporters.export(tray, f'{OUT}/mf_kvm_tray.step')
cq.exporters.export(lid, f'{OUT}/mf_kvm_lid.step')
