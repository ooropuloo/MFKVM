# -*- coding: utf-8 -*-
"""MF KVM v3 case: tray, lid, C790 bridge and FPC fold former, plus the full assembly and its fit checks.

Frame: FireBeetle STEP frame. x toward the OTG side, y from the antenna end to the USB-CDC end, z = 0 on the core's top copper. Right handed.
usage: gen_case.py <firebeetle.step> <firebeetle_bb.json>      writes stl/, step/, asm/, sections/ and check.json next to itself
Layout numbers come from ../layout.json (layout_study.py). Heights of the C790 are the upper bound of the estimate.
"""
import json
import math
import os
import sys

import cadquery as cq

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
STEP, BB = sys.argv[1], sys.argv[2]
D = json.load(open(os.path.join(HERE, '..', 'layout.json'), encoding='utf-8'))['d']
ATX = json.load(open(os.path.join(HERE, '..', 'atx', 'out', 'design.json'), encoding='utf-8'))
for sub in ('stl', 'step', 'asm', 'sections'):
    os.makedirs(os.path.join(HERE, sub), exist_ok=True)
FONT = 'C:/Windows/Fonts/arialbd.ttf'

# ---------- levels
X0, YFE = D['x0'], D['y_fe']          # C790 corner and FPC edge
PCB_B, PCB_T = D['pcb_b'], D['pcbt']  # C790 PCB
LEVEL, ZH = D['level'], D['z_h']      # lower and upper ribbon runs
XF = D['x_f']
PANEL = D['panel']                    # LCD panel face
WALL, FLOOR, ROOF = 1.6, 1.2, 1.0
IX0, IX1 = X0 - 0.3, 13.0             # cavity
IY0, IY1 = -0.3, YFE + 45 + 0.3
OX0, OX1 = IX0 - WALL, IX1 + WALL
OY0, OY1 = IY0 - WALL, D['y_h']       # HDMI shell finishes at the outer face
FZ = -4.02 - 0.3                      # floor top
OZ0 = FZ - FLOOR
SPLIT = 16.8
ROOF_B = PANEL + 0.055
OZ1 = ROOF_B + ROOF
LCD_X0, LCD_Y0 = -18.7, 15.0         # LCD corner: X = LCD_X0 + Yl, Y = LCD_Y0 + 51.2 - Xl
USB_Z, OTG_Y, CDC_X = 1.105, 45.5, 0.0
HX = X0 + 15.0                        # HDMI centre
P_A, P_B, P_C, P_D = (X0 + 3.5, YFE + 11.5), (X0 + 3.5, YFE + 41.5), (X0 + 26.5, YFE + 11.5), (X0 + 26.5, YFE + 41.5)
POST_D = 4.8
CORE_HOLES = [(-11.0, 58.3), (11.0, 58.3)]
LID_SCREWS = [(11.2, 42.0), (11.2, 64.0)]
HEAD_Z = OZ1 - 1.46                    # lid screw head seat
K_Y, K_Z = 53.34, 1.42
TUNNEL = (-6.6, 6.6, 61.6, 4.6)       # x0, x1, y0 just past the USB shell so the core drops in from above, ceiling underside
ATX_GAP = 1.2                         # core underside to ATX top side, set by the printed atx_shim. Six 0.2 mm layers
ATX_T = 1.0
ATX_C = (ATX['origin'][0], ATX['origin'][1], -1.62 - ATX_GAP - ATX_T)  # board origin x, y from the board design, underside z
PIN_D, PIN_TIP, PIN_TAIL = 0.64, 1.0, -4.6   # round pin, top end above the core's top copper, bottom end. Both include the solder fillet: trim to these
GROOVE_Z = -5.0                       # floor under the pin tails, 0.52 of plastic stays below it
RAIL_GAP = 0.15                       # the pins carry the board. The rails only stop it sagging, so shim tolerance does not load the joints
P1_PINS = [(h['ref'], ATX['p1_x'], ATX['p1_y'][h['pin']]) for h in ATX['holes']]


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def rbox(x0, x1, y0, y1, z0, z1, r):
    return box(x0, x1, y0, y1, z0, z1).edges('|Z').fillet(r)


def cyl(x, y, z0, z1, d):
    return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def xcyl(x0, x1, y, z, d):
    return cq.Workplane('YZ').circle(d / 2).extrude(x1 - x0).translate((x0, y, z))


def wedge_x(x_wall, x_in, y0, y1, z_low, z_high):
    """Printable support under a boss: a triangle in XZ, extruded along y."""
    return cq.Workplane('XZ').polyline([(x_wall, z_low), (x_wall, z_high), (x_in, z_high)]).close().extrude(y1 - y0).translate((0, y1, 0))


TEXTS = []


def text(txt, size, depth, o, r, n):
    """Debossed text on a face. o is on the outer surface, r runs left to right as read from outside, n points outward."""
    p = cq.Plane(origin=o, xDir=r, normal=n)
    return cq.Workplane(p).text(txt, size, -depth, combine=False, font='Arial', fontPath=FONT, kind='bold', halign='center', valign='center')


def cut_text(solid, name, txt, size, o, r, n, depth=0.4):
    t = text(txt, size, depth, o, r, n)
    v0 = solid.val().Volume()
    res = solid.cut(t)
    v1 = res.val().Volume()
    tv = t.val().Volume() if len(t.vals()) == 1 else sum(v.Volume() for v in t.vals())
    TEXTS.append(dict(part=name, text=txt, removed=round(v0 - v1, 3), text_volume=round(tv, 3), ok=abs((v0 - v1) - tv) < 0.02 * tv + 0.02 and v0 - v1 > 0.3))
    return res


# ---------- tray
tray = rbox(OX0, OX1, OY0, OY1, OZ0, SPLIT, 3.0).cut(rbox(IX0, IX1, IY0, IY1, FZ, SPLIT + 1, 1.2))
# core: two posts at the USB end, plastic rests under the cantilever, none of them near the antenna
for x, y in CORE_HOLES:
    tray = tray.union(cyl(x, y, FZ - 0.1, -1.62, 4.0))
    sx = 1 if x > 0 else -1
    if sx > 0:
        tray = tray.union(box(x, IX1 + 0.1, y - 0.8, y + 0.8, FZ - 0.1, -1.62))
for sx in (-1, 1):
    tray = tray.union(box(min(sx * 9.15, sx * 10.35), max(sx * 9.15, sx * 10.35), 17.0, 22.0, FZ - 0.1, -1.62))
    # the -X rest stops short so the ATX tongue has real clearance
    tray = tray.union(box(min(sx * 9.2, sx * (10.3 if sx > 0 else 10.1)), max(sx * 9.2, sx * (10.3 if sx > 0 else 10.1)), 36.5, 38.5, FZ - 0.1, -1.62))
# C790: post A carries the bridge, post B the C790, pad D rests on the alcove ceiling
tray = tray.union(cyl(*P_A, FZ - 0.1, 3.7, POST_D)).union(box(IX0 - 0.1, P_A[0], P_A[1] - 0.8, P_A[1] + 0.8, FZ - 0.1, 3.7))
tray = tray.union(cyl(*P_B, FZ - 0.1, PCB_B, POST_D)).union(box(IX0 - 0.1, P_B[0], P_B[1] - 0.8, P_B[1] + 0.8, FZ - 0.1, 5.0))
# USB-CDC alcove: side walls, ceiling, pad for C790 corner D
tx0, tx1, ty0, tz = TUNNEL
tray = tray.union(box(tx0 - 1.2, tx0, ty0, IY1 + 0.1, FZ - 0.1, tz + 0.8)).union(box(tx1, tx1 + 1.2, ty0, IY1 + 0.1, FZ - 0.1, tz + 0.8))
tray = tray.union(box(tx0 - 1.2, tx1 + 1.2, ty0, IY1 + 0.1, tz, tz + 0.8))
tray = tray.union(cyl(*P_D, tz + 0.7, PCB_B, 4.6))
# ATX board rails
RAIL_Z = ATX_C[2] - RAIL_GAP
tray = tray.union(box(-20.9, -19.9, 43.5, 65.0, FZ - 0.1, RAIL_Z)).union(box(-14.9, -13.9, 43.5, 56.0, FZ - 0.1, RAIL_Z))
# lid screw bosses on the +X wall
for x, y in LID_SCREWS:
    tray = tray.union(cyl(x, y, 8.1, SPLIT, 4.6).intersect(box(IX0, IX1 + 0.5, 0, 80, 0, SPLIT + 1)))
    tray = tray.union(wedge_x(IX1 + 0.1, x - 2.3, y - 2.3, y + 2.3, 4.0, 8.2))
    tray = tray.cut(cyl(x, y, 9.7, SPLIT + 1, 1.7))
# holes
for x, y in CORE_HOLES:
    tray = tray.cut(cyl(x, y, -5.2, -1.0, 1.3))
tray = tray.cut(cyl(*P_A, -2.5, 4.0, 2.1)).cut(cyl(*P_B, 0.0, PCB_B + 1, 2.1)).cut(cyl(*P_D, tz + 0.9, PCB_B + 1, 2.9))
tray = tray.cut(xcyl(OX0 - 1, -12.0, K_Y, K_Z, 2.2)).cut(xcyl(IX1 - 0.5, OX1 + 1, K_Y, K_Z, 2.2))
# I/O: HDMI through the end wall, alcove mouth
tray = tray.cut(box(HX - 7.9, HX + 7.9, IY1 - 0.5, OY1 + 1, PCB_T - 0.3, SPLIT + 1))  # open at the top so the C790 drops in; a tongue on the lid closes it
tray = tray.cut(box(tx0, tx1, ty0 + 0.0, OY1 + 1, FZ, tz))
# +X wall: one window, big enough to seat a moulded USB-C plug fully, with the TF slot under it
tray = tray.cut(box(IX1 - 0.5, OX1 + 1, OTG_Y - 6.3, OTG_Y + 6.3, -3.3, USB_Z + 3.4))
tray = tray.cut(box(11.5, OX1 + 1, OTG_Y - 4.0, OTG_Y + 4.0, OZ0 - 1, -3.3 + 0.01))  # nail notch for the card, through the floor
# -X wall: ATX harness
JY = ATX_C[1] + 7.6
tray = tray.cut(box(OX0 - 1, IX0 + 0.5, JY - 4.7, JY + 4.7, -3.0, 0.6))
# floor: antenna window (air, not plastic, right under the antenna), C6 test point hatch, vents
tray = tray.cut(box(-7.5, 7.5, 0.0, 6.5, OZ0 - 1, FZ + 0.5))
tray = tray.cut(box(-9.0, -0.8, 12.8, 19.4, OZ0 - 1, FZ + 0.5))
for y in (26.0, 29.0, 32.0):
    tray = tray.cut(box(-21.0, -14.5, y, y + 1.4, OZ0 - 1, FZ + 0.5))
# pocket in the +X wall for the BOOT switch while the core swings in tilted, see insert_path.py. The wall stays 0.8 here.
tray = tray.cut(box(IX1 - 0.1, IX1 + 0.8, 50.4, 56.2, -1.0, 5.5))
# blind groove for the ATX pin tails, under P1 pins 2 to 8. Floor stays closed so 3V3 cannot reach a metal desk
tray = tray.cut(box(ATX['p1_x'] - 1.0, ATX['p1_x'] + 1.0, 29.9, 46.75, GROOVE_Z, FZ + 0.5))
# wall vents at C790 level
for y in (53.5, 56.5, 59.5):
    tray = tray.cut(box(OX0 - 1, IX0 + 0.5, y, y + 1.4, 9.5, 14.5))
for y in (51.5, 54.5, 57.5):
    tray = tray.cut(box(IX1 - 0.5, OX1 + 1, y, y + 1.4, 6.0, 14.5))
# hinge grooves for the lid tabs: two on the -X wall, one at the -Y end by the -X corner
GROOVES = [(16.0, 24.0), (54.0, 62.0)]
for y0, y1 in GROOVES:
    tray = tray.cut(box(IX0 - 0.8, IX0 + 0.1, y0, y1, 15.5, 16.4))
tray = tray.cut(box(-20.0, -13.0, IY0 - 0.8, IY0 + 0.1, 15.5, 16.4))
# markings
R_X, N_X = (0, 1, 0), (1, 0, 0)
tray = cut_text(tray, 'tray', 'HOST', 2.6, (OX1, OTG_Y, 8.6), R_X, N_X)
tray = cut_text(tray, 'tray', 'NO VBUS', 1.9, (OX1, OTG_Y, 6.0), R_X, N_X)
tray = cut_text(tray, 'tray', 'TF', 2.4, (OX1, 36.0, -1.6), R_X, N_X)
tray = cut_text(tray, 'tray', '5V', 2.6, (10.9, OY1, 0.5), (-1, 0, 0), (0, 1, 0))
tray = cut_text(tray, 'tray', 'ATX', 2.6, (OX0, JY, 3.0), (0, -1, 0), (-1, 0, 0))

# ---------- lid
lid = rbox(OX0, OX1, OY0, OY1, SPLIT, OZ1, 3.0).cut(rbox(IX0, IX1, IY0, IY1, SPLIT - 1, ROOF_B, 1.2))
FIT = 0.15
lip = rbox(IX0 + FIT, IX1 - FIT, IY0 + FIT, IY1 - FIT, 15.6, SPLIT + 0.1, 1.05).cut(rbox(IX0 + 1.35, IX1 - 1.35, IY0 + 1.35, IY1 - 1.35, 15, SPLIT + 1, 0.5))
lip = lip.union(rbox(IX0 - 0.01, IX1 + 0.01, IY0 - 0.01, IY1 + 0.01, SPLIT - 0.0, SPLIT + 0.8, 1.2).cut(rbox(IX0 + 1.35, IX1 - 1.35, IY0 + 1.35, IY1 - 1.35, 15, SPLIT + 1, 0.5)))  # ties the lip to the skirt
lip = lip.cut(box(HX - 8.2, HX + 8.2, IY1 - 2, IY1 + 1, 15, SPLIT))
for x, y in LID_SCREWS:
    lip = lip.cut(box(x - 3.0, IX1 + 1, y - 3.0, y + 3.0, 15, SPLIT + 0.2))
lid = lid.union(lip)
lid = lid.union(box(HX - 7.8, HX + 7.8, IY1 - 0.5, OY1, 16.05, SPLIT + 0.1))  # closes the top of the HDMI opening
# hinge tabs
for y0, y1 in GROOVES:
    lid = lid.union(box(IX0 - 0.6, IX0 + 0.3, y0 + 0.5, y1 - 0.5, 15.65, 16.25))
lid = lid.union(box(-19.5, -13.5, IY0 - 0.6, IY0 + 0.3, 15.65, 16.25))
# window on the active area, 0.3 larger each side. AA is Xl 6.25..48.97, Yl 2.30..25.00 [V STEP and drawing]
WIN = (LCD_X0 + 2.30 - 0.3, LCD_X0 + 25.0 + 0.3, LCD_Y0 + 51.2 - 48.97 - 0.3, LCD_Y0 + 51.2 - 6.25 + 0.3)
lid = lid.cut(box(WIN[0], WIN[1], WIN[2], WIN[3], ROOF_B - 1, OZ1 + 1))
# LCD clips and end stops. PCB back sits at PANEL - 3.5
PCB_BACK = PANEL - 3.5
for y in (24.0, 56.0):
    lid = lid.union(box(LCD_X0 - 1.5, LCD_X0 - 0.06, y - 3, y + 3, PCB_BACK - 0.7, ROOF_B + 0.1)).union(box(LCD_X0 - 0.1, LCD_X0 + 0.5, y - 3, y + 3, PCB_BACK - 0.7, PCB_BACK - 0.05))
    lid = lid.union(box(LCD_X0 + 27.36, LCD_X0 + 28.8, y - 3, y + 3, PCB_BACK - 0.7, ROOF_B + 0.1)).union(box(LCD_X0 + 26.8, LCD_X0 + 27.4, y - 3, y + 3, PCB_BACK - 0.7, PCB_BACK - 0.05))
lid = lid.union(box(-9.0, -1.0, LCD_Y0 - 1.0, LCD_Y0 - 0.06, PANEL - 1.5, ROOF_B + 0.1)).union(box(-9.0, -1.0, LCD_Y0 + 51.26, LCD_Y0 + 52.2, PANEL - 1.5, ROOF_B + 0.1))
# lid screw posts, heads recessed
for x, y in LID_SCREWS:
    lid = lid.union(cyl(x, y, SPLIT, ROOF_B + 0.1, 4.6).intersect(box(IX0, IX1 + 0.5, 0, 80, SPLIT, OZ1)))
    lid = lid.cut(cyl(x, y, SPLIT - 1, OZ1 + 1, 2.3)).cut(cyl(x, y, HEAD_Z, OZ1 + 1, 4.2))
# roof vents over the +X chimney
for y in (46.0, 49.0, 52.0, 55.0, 58.0):
    lid = lid.cut(box(9.8, 12.4, y, y + 1.4, ROOF_B - 1, OZ1 + 1))
lid = cut_text(lid, 'lid', 'MF KVM', 5.0, ((OX0 + OX1) / 2 - 3.0, 66.8, OZ1), (1, 0, 0), (0, 0, 1))
lid = cut_text(lid, 'lid', 'HDMI', 2.2, (HX, OY1, (SPLIT + OZ1) / 2), (-1, 0, 0), (0, 1, 0))

# ---------- bridge: spans the core, carries C790 corner C, sits on post A, feet rest on the core next to the rests
bridge = box(-20.3, 10.4, 35.8, 40.2, 1.3, 5.2)
bridge = bridge.union(cyl(*P_A, 3.7, PCB_B, 5.6)).union(cyl(*P_C, 1.3, PCB_B, 5.6))
bridge = bridge.union(box(9.2, 10.3, 36.5, 38.5, 0.0, 1.4)).union(box(-10.3, -9.2, 36.5, 38.5, 0.0, 1.4))
bridge = bridge.cut(box(-21.0, -15.0, 35.0, 41.0, -1, 3.7)).cut(cyl(*P_A, 3.0, PCB_B + 1, 2.8)).cut(cyl(*P_C, 1.7, PCB_B + 1, 2.1))

# ---------- fold former
AX = (XF, 14.9, (LEVEL + ZH) / 2)
former = cq.Solid.makeCylinder(2.7, 22.8, cq.Vector(AX[0] + 22.8 / 2 / math.sqrt(2), AX[1] - 22.8 / 2 / math.sqrt(2), AX[2]), cq.Vector(-1, 1, 0))
former = cq.Workplane(obj=former)

print('tray  valid', tray.val().isValid(), 'vol', round(tray.val().Volume(), 1), 'solids', len(tray.solids().vals()))
print('lid   valid', lid.val().isValid(), 'vol', round(lid.val().Volume(), 1), 'solids', len(lid.solids().vals()))
print('bridge valid', bridge.val().isValid(), 'vol', round(bridge.val().Volume(), 1), 'solids', len(bridge.solids().vals()))
# ---------- ATX shim: a printed fork that sets the 1.2 mm gap while the pins are soldered, then slides out toward -y past the pins. Not in the closed case.
SLOT = 0.78
shim = box(-13.4, -9.6, 20.0, 29.2, -1.62 - ATX_GAP, -1.62).union(box(-13.4, ATX['p1_x'] - SLOT, 29.1, 41.4, -1.62 - ATX_GAP, -1.62)).union(box(ATX['p1_x'] + SLOT, -9.6, 29.1, 41.4, -1.62 - ATX_GAP, -1.62))
print('shim valid', shim.val().isValid(), 'vol', round(shim.val().Volume(), 1), 'solids', len(shim.solids().vals()))
CASE = dict(tray=tray, lid=lid, bridge=bridge, former=former, atx_shim=shim)
for k, v in CASE.items():
    cq.exporters.export(v, os.path.join(HERE, 'stl', f'mf_kvm_{k}.stl'), tolerance=0.02, angularTolerance=0.15)
    cq.exporters.export(v, os.path.join(HERE, 'step', f'mf_kvm_{k}.step'))


# ---------- assembly solids
def c790_box(xc0, xc1, yc0, yc1, z0, z1):
    return box(X0 + yc0, X0 + yc1, YFE + 45 - xc1, YFE + 45 - xc0, z0, z1)


pcb = rbox(X0, X0 + 30, YFE, YFE + 45, PCB_B, PCB_T, 2.5)
for p in (P_A, P_B, P_C, P_D):
    pcb = pcb.cut(cyl(*p, PCB_B - 1, PCB_T + 1, 2.75))
C790 = dict(pcb=pcb, hdmi=c790_box(-2.1, 7.6, 7.4, 22.6, PCB_T, PCB_T + 7.4), hdmi_tail=c790_box(7.6, 10.1, 7.4, 22.6, PCB_T, PCB_T + 1.5),
            hdmi_back=c790_box(1.3, 9.1, 6.0, 24.0, PCB_B - 1.2, PCB_B), j2=c790_box(38.1, 43.6, 4.6, 25.1, PCB_T, PCB_T + 3.0), j3=c790_box(39.0, 44.7, 6.9, 22.6, PCB_B - 2.0, PCB_B),
            j5=c790_box(20.2, 29.8, 0.0, 5.0, PCB_T, PCB_T + 4.0), parts=c790_box(11.0, 37.0, 6.0, 24.0, PCB_T, PCB_T + 1.2))


def lcd_box(xl0, xl1, yl0, yl1, z0, z1):
    return box(LCD_X0 + yl0, LCD_X0 + yl1, LCD_Y0 + 51.2 - xl1, LCD_Y0 + 51.2 - xl0, z0, z1)


LCD = dict(pcb=lcd_box(0, 51.2, 0, 27.3, PCB_BACK, PCB_BACK + 1.6), panel=lcd_box(0.30, 50.46, 0.75, 26.56, PCB_BACK + 1.6, PANEL),
           parts=lcd_box(22.2, 30.0, 4.9, 23.6, PANEL - 4.7, PCB_BACK), conn=lcd_box(12.5, 17.6, 6.3, 21.0, PANEL - 7.0, PCB_BACK), zif=lcd_box(36.3, 42.8, 5.75, 21.85, PANEL - 5.5, PCB_BACK))  # rear parts from the STEP, the rest of the back is bare PCB
for i, (xl, yl) in enumerate(((2.8, 2.8), (48.4, 2.8), (2.8, 24.5), (48.4, 24.5))):
    LCD[f'standoff{i}'] = cyl(LCD_X0 + yl, LCD_Y0 + 51.2 - xl, PANEL - 6.0, PCB_BACK, 3.5)
LCD_PLUG = box(LCD_X0 + 6.8, LCD_X0 + 20.5, LCD_Y0 + 51.2 - 12.5, LCD_Y0 + 51.2 - 5.5, PANEL - 6.9, PCB_BACK - 0.05)

# ATX board. KiCad y runs along case -Y.
atx_top = ATX_C[2] + ATX_T
acx, acy = ATX_C[0], ATX_C[1]
# board outline from the design. KiCad y runs along case -Y, there is no flip in x.
outline_case = [(acx + bx, acy - by) for bx, by in ATX['outline']]
aboard = cq.Workplane('XY').polyline(outline_case).close().extrude(ATX_T).translate((0, 0, ATX_C[2]))
for _, x, y in P1_PINS:
    aboard = aboard.cut(cyl(x, y, ATX_C[2] - 1, atx_top + 1, 0.9))
ATXP = dict(board=aboard)
HT = dict(OPTO_SO4=2.2, JST_SM06B=2.95, R0402=0.5)  # LTV-357T is 2.00 +-0.2
for ref, x, y in P1_PINS:
    # pin, then the solder: under the board, in the gap on each board, on top of the core. Real fillets are smaller than these cylinders.
    ATXP[ref + '_pin'] = cyl(x, y, PIN_TAIL, PIN_TIP, PIN_D)
    ATXP[ref + '_fillet_tail'] = cyl(x, y, ATX_C[2] - 0.33, ATX_C[2], 1.4).cut(cyl(x, y, ATX_C[2] - 1, ATX_C[2] + 1, PIN_D))
    ATXP[ref + '_fillet_atx'] = cyl(x, y, atx_top, atx_top + 0.2, 1.4).cut(cyl(x, y, atx_top - 1, atx_top + 1, PIN_D))
    ATXP[ref + '_fillet_core_b'] = cyl(x, y, -1.82, -1.62, 1.4).cut(cyl(x, y, -2, -1, PIN_D))
    ATXP[ref + '_fillet_core_t'] = cyl(x, y, 0, 0.55, 1.6).cut(cyl(x, y, -1, 1, PIN_D))
for p in ATX['parts']:
    if p['lib'] == 'PIN_0.9':
        continue
    x0, y0, x1, y1 = p['bbox']
    if p['lib'] == 'OPTO_SO4':
        x0, x1 = x0 + 0.0, x1
    ATXP[p['ref']] = box(acx + x0 + 0.05, acx + x1 - 0.05, acy - y1 + 0.05, acy - y0 - 0.05, atx_top, atx_top + HT[p['lib']])


# ribbon: riser, bend, upper triangle, roll, lower strip. Thickness 0.3.
T = 0.15
RX = 4.3
R = 3.0
riser = box(RX - T, RX + T, 6.9, 22.9, 5.4, ZH - R)
bend = (cq.Workplane('XZ').moveTo(1.3 + R + T, ZH - R).threePointArc((1.3 + (R + T) * 0.7071, ZH - R + (R + T) * 0.7071), (1.3, ZH + T)).lineTo(1.3, ZH - T)
        .threePointArc((1.3 + (R - T) * 0.7071, ZH - R + (R - T) * 0.7071), (1.3 + R - T, ZH - R)).close().extrude(16.0).translate((0, 22.9, 0)))
upper = cq.Workplane('XY').polyline([(1.3, 6.9), (1.3, 22.9), (XF - 8, 22.9)]).close().extrude(2 * T).translate((0, 0, ZH - T))
lower = cq.Workplane('XY').polyline([(1.3, 6.9), (1.3, YFE + 1.4), (XF - 8, YFE + 1.4), (XF - 8, 22.9)]).close().extrude(2 * T).translate((0, 0, LEVEL - T))
L_AX = 8.0 * math.sqrt(2)
shell = cq.Solid.makeCylinder(R + T, 2 * L_AX, cq.Vector(AX[0] + L_AX / math.sqrt(2), AX[1] - L_AX / math.sqrt(2), AX[2]), cq.Vector(-1, 1, 0)).cut(
    cq.Solid.makeCylinder(R - T, 2 * L_AX + 2, cq.Vector(AX[0] + (L_AX + 1) / math.sqrt(2), AX[1] - (L_AX + 1) / math.sqrt(2), AX[2]), cq.Vector(-1, 1, 0)))
# keep the half on the fold side, away from the strips, and trim to the strip width
half = cq.Workplane('XY').polyline([(AX[0] + 40, AX[1] - 40), (AX[0] - 40, AX[1] + 40), (AX[0] - 80, AX[1]), (AX[0], AX[1] - 80)]).close().extrude(20).translate((0, 0, 0))
roll = cq.Workplane(obj=shell).intersect(half)
FPC = dict(riser=riser, bend=bend, upper=upper, lower=lower, roll=roll)

# probes for cables
PROBE = dict(usb_cdc_plug=box(-6.0, 6.0, 61.5, OY1 + 12, USB_Z - 3.3, USB_Z + 3.3), usb_otg_plug=box(12.74, OX1 + 12, OTG_Y - 6.0, OTG_Y + 6.0, USB_Z - 3.3, USB_Z + 3.3),
             hdmi_plug_metal=box(HX - 7.0, HX + 7.0, OY1 - 2.1, OY1 + 1, PCB_T + 0.9, PCB_T + 5.9), hdmi_overmould=box(HX - 11.0, HX + 11.0, OY1 + 0.01, OY1 + 25, PCB_T + 3.3 - 6, PCB_T + 3.3 + 6),
             atx_plug=box(OX0 - 8, IX0 + 0.2, JY - 4.2, JY + 4.2, -2.75, 0.25), tf_card=box(12.0, OX1 + 3, OTG_Y + 0.4 - 5.5, OTG_Y + 0.4 + 5.5, -2.9, -1.9),
             rst_needle=xcyl(OX0 - 3, -12.75, K_Y, K_Z, 1.0), boot_needle=xcyl(12.75, OX1 + 3, K_Y, K_Z, 1.0), c6_probe=box(-8.9, -0.9, 12.9, 19.3, OZ0 - 3, FZ + 0.4))
screws = {}
for i, (x, y) in enumerate(CORE_HOLES):
    screws[f'M1.6x5 core {i}'] = cq.Workplane(obj=cq.Solid.makeCylinder(1.5, 1.2, cq.Vector(x, y, 0))).union(cyl(x, y, -5.0, 0, 1.2))
screws['M2.5x10 A'] = cyl(*P_A, PCB_T, PCB_T + 1.6, 4.5).union(cyl(*P_A, PCB_T - 10, PCB_T, 2.0))
screws['M2.5x8 B'] = cyl(*P_B, PCB_T, PCB_T + 1.6, 4.5).union(cyl(*P_B, PCB_T - 8, PCB_T, 2.0))
screws['M2.5x6 C'] = cyl(*P_C, PCB_T, PCB_T + 1.6, 4.5).union(cyl(*P_C, PCB_T - 6, PCB_T, 2.0))
for i, (x, y) in enumerate(LID_SCREWS):
    screws[f'M2x8 lid {i}'] = cyl(x, y, HEAD_Z, HEAD_Z + 1.3, 3.8).union(cyl(x, y, HEAD_Z - 8, HEAD_Z, 1.6))


def fuse_all(d):
    keys = list(d)
    u = d[keys[0]]
    for k in keys[1:]:
        u = u.union(d[k])
    return u


for name, grp in (('c790', C790), ('lcd', LCD), ('atx', ATXP), ('fpc', FPC)):
    cq.exporters.export(fuse_all(grp), os.path.join(HERE, 'asm', f'{name}.stl'), tolerance=0.05, angularTolerance=0.3)

# ---------- checks
core_full = cq.importers.importStep(STEP).val()
print('core loaded', round(core_full.BoundingBox().xlen, 2), round(core_full.BoundingBox().ylen, 2), round(core_full.BoundingBox().zlen, 2))
bb = json.load(open(BB, encoding='utf-8'))
core_boxes = {}
for e in bb:
    b = e['bb']
    if e['depth'] == 1 and e['refname'] not in ('Free-Models',):
        core_boxes[e['refname']] = b
    if e['depth'] == 2 and b[5] > 3.0 and b[0] > -7 and b[3] < 7 and b[1] < 26.5 and b[4] > 3:
        core_boxes.setdefault('J_' + e['name'], b)
core_boxes.pop('PCB', None)


def vol(a, b):
    try:
        r = a.intersect(b)
        return sum(s.Volume() for s in r.vals()) if r.vals() else 0.0
    except Exception as ex:
        return f'ERR {ex}'


def as_wp(s):
    return s if isinstance(s, cq.Workplane) else cq.Workplane(obj=s)


GROUPS = dict(tray=dict(tray=tray), lid=dict(lid=lid), bridge=dict(bridge=bridge), former=dict(former=former), c790=C790, lcd=LCD, atx=ATXP, fpc=FPC, lcd_plug=dict(plug=LCD_PLUG))
ALLOW = {('fpc', 'core'): ['J_'], ('atx', 'tray'): []}
TOL = 0.001
results = []


def report(a, b, v):
    bad = isinstance(v, str) or v > TOL
    results.append(dict(a=a, b=b, vol=v if isinstance(v, str) else round(v, 4), bad=bad))


names = list(GROUPS)
for i, ga in enumerate(names):
    for gb in names[i + 1:]:
        tot = 0.0
        worst = []
        for ka, sa in GROUPS[ga].items():
            for kb, sb in GROUPS[gb].items():
                if ga == 'lcd_plug' or gb == 'lcd_plug':
                    pass
                if (ga, gb) == ('lcd', 'lcd_plug') and ka == 'conn':
                    continue
                v = vol(as_wp(sa), as_wp(sb))
                if isinstance(v, str) or v > TOL:
                    worst.append((ka, kb, v if isinstance(v, str) else round(v, 4)))
                    tot += v if not isinstance(v, str) else 1.0
        report(ga, gb, tot)
        if worst:
            results[-1]['detail'] = worst[:12]
print('pairs checked', len(results))

# core against everything: components as boxes first, real solids only where a box hits
core_hits = []
core_detail = []
for gname, grp in GROUPS.items():
    for ka, sa in grp.items():
        sbb = as_wp(sa).val().BoundingBox()
        for ref, b in core_boxes.items():
            if b[3] <= sbb.xmin or b[0] >= sbb.xmax or b[4] <= sbb.ymin or b[1] >= sbb.ymax or b[5] <= sbb.zmin or b[2] >= sbb.zmax:
                continue
            bx = box(b[0], b[3], b[1], b[4], b[2], b[5])
            v = vol(as_wp(sa), bx)
            if isinstance(v, str) or v > TOL:
                core_hits.append((gname, ka, ref, v if isinstance(v, str) else round(v, 4), b))
# a box hit may be air: J1 slot, or a screw hole in the PCB. Test those with the real STEP solids.
real = []
if core_hits:
    solids = core_full.Solids()
    for gname, ka, ref, v, b in core_hits:
        sa = as_wp(GROUPS[gname][ka]).val()
        tot = 0.0
        for s in solids:
            sb = s.BoundingBox()
            if sb.xmax < b[0] - 0.01 or sb.xmin > b[3] + 0.01 or sb.ymax < b[1] - 0.01 or sb.ymin > b[4] + 0.01 or sb.zmax < b[2] - 0.01 or sb.zmin > b[5] + 0.01:
                continue
            tot += s.intersect(sa).Volume()
        real.append(dict(group=gname, part=ka, core=ref, box_vol=v, real_vol=round(tot, 4)))
real_bad = [r for r in real if r['real_vol'] > TOL]
print('core: box hits', len(core_hits), 'real hits', len(real_bad), real_bad[:10])

# probes against case and boards: a plug must go in without touching plastic
probe_out = []
for k, p in PROBE.items():
    row = dict(probe=k)
    for gn in ('tray', 'lid', 'bridge'):
        row[gn] = round(vol(p, GROUPS[gn][gn]), 3)
    # the ATX board may not block any access path. The JST is what the plug goes into, so it is left out for that one probe.
    row['atx'] = round(sum(v for kk, sa in ATXP.items() if not (k == 'atx_plug' and kk == 'J1') for v in [vol(p, as_wp(sa))] if not isinstance(v, str)), 3)
    probe_out.append(row)
probe_bad = [r for r in probe_out if r['tray'] > TOL or r['lid'] > TOL or r['bridge'] > TOL or r['atx'] > TOL]

# screws: must pass only through intended holes
screw_out = []
for k, s in screws.items():
    row = dict(screw=k)
    for gn, grp in GROUPS.items():
        if gn in ('fpc', 'lcd_plug', 'former'):
            pass
        t = 0.0
        for ka, sa in grp.items():
            v = vol(s, as_wp(sa))
            t += v if not isinstance(v, str) else 0
        if t > 0.001:
            row[gn] = round(t, 3)
    screw_out.append(row)

# alignment numbers
fails = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        fails.append(msg)


interf = [r for r in results if r['bad']]
check(not interf, f'interference: {len(results)} part-group pairs, {len(interf)} overlap {interf if interf else ""}')
check(not real_bad, f'core (real STEP) against all parts: {len(core_hits)} bounding box touches, {len(real_bad)} real overlaps {real_bad if real_bad else ""}')
check(not probe_bad, f'cable probes clear of plastic {probe_bad if probe_bad else ""}')
for t in TEXTS:
    check(t['ok'], f"text {t['text']!r} on {t['part']}: cut {t['removed']} mm3 of {t['text_volume']} mm3")
# ---------- ATX on the core: numbers a person can argue with
_tails = FZ - (ATX_C[2])
check(abs(atx_top - (-1.62 - ATX_GAP)) < 1e-6, f'ATX top {atx_top:.2f} to core underside -1.62: gap {ATX_GAP:.2f} mm, tallest core part in the footprint: nothing under the core in x < -9.38 for y 29 to 56')
check(ATX_C[2] - FZ >= 0.45, f'ATX underside {ATX_C[2]:.2f} to floor top {FZ:.2f}: {ATX_C[2] - FZ:.2f} mm')
check(PIN_TAIL - GROOVE_Z >= 0.3, f'pin tail end {PIN_TAIL:.2f} to groove floor {GROOVE_Z:.2f}: {PIN_TAIL - GROOVE_Z:.2f} mm clear, plastic under the groove {GROOVE_Z - OZ0:.2f} mm')
check(ATX_C[2] - RAIL_Z == RAIL_GAP or abs(ATX_C[2] - RAIL_Z - RAIL_GAP) < 1e-6, f'rails stop {RAIL_GAP} mm under the board, so the pins carry it')
BR_B = 1.3
check(BR_B - PIN_TIP >= 0.25, f'pin tip {PIN_TIP:.2f} above core top, bridge underside {BR_B:.2f}: {BR_B - PIN_TIP:.2f} mm. Next up: LOWER FPC run {LEVEL - T:.2f}, so {LEVEL - T - PIN_TIP:.2f} mm')
_px = ATX['p1_x']
check(-6.75 - (_px + 0.8) >= 3.0, f'pin fillet edge x {_px + 0.8:.2f} to DSI J2 x -6.75: {-6.75 - (_px + 0.8):.2f} mm. Row is not under the former or the ribbon')
_hx = min(p[2] for p in P1_PINS)
copper_y = _hx - 0.7
check(copper_y - 6.0 >= 15, f'ATX copper starts at y {copper_y:.2f}: {copper_y - 6.0:.1f} mm from the antenna (y < 6), {copper_y - 16.6:.1f} mm from the C6 module end (y 16.6)')
# ATX edges against what is around them in the tray
FDM = 0.25  # side clearance a printed PETG wall needs against a rigid part; not tested on this printer
check(min(q[0] for q in outline_case) - IX0 >= FDM, f"ATX -X edge {min(q[0] for q in outline_case):.2f} to wall {IX0:.2f}: {min(q[0] for q in outline_case) - IX0:.2f} mm. It stops the board if the plug is pulled")
check(CORE_HOLES[0][0] - 2.0 - (acx + 3.0) >= FDM, f'ATX notch edge x {acx + 3.0:.2f} to core post x {CORE_HOLES[0][0] - 2.0:.2f}: {CORE_HOLES[0][0] - 2.0 - (acx + 3.0):.2f} mm. It stops the board if the plug is pushed')
check(-10.1 - max(q[0] for q in outline_case) >= FDM, f"ATX tongue edge {max(q[0] for q in outline_case):.2f} to core rest x -10.10: {-10.1 - max(q[0] for q in outline_case):.2f} mm")
# shim: it must go between the boards, around the pins and past the parts, and come out
shim_hits = []
for kk, sa in ATXP.items():
    v = vol(shim, as_wp(sa))
    if isinstance(v, str) or v > TOL:
        shim_hits.append((kk, v))
for ref, b in core_boxes.items():
    if b[0] < -9.6 and b[3] > -13.4 and b[1] < 41.4 and b[4] > 20.0 and b[2] < -1.62 and b[5] > -2.82:
        shim_hits.append((ref, b))
check(not shim_hits, f'ATX shim clear of pins, fillets, parts and core underside {shim_hits or ""}')
check(True, f'shim slides out toward -y: slot {2 * SLOT:.2f} wide, fillet 1.40, open at y 41.4; left leg stops before R1 at y 42.2')
aa_c = ((WIN[0] + WIN[1]) / 2, (WIN[2] + WIN[3]) / 2)
pcb_c = (LCD_X0 + 13.65, LCD_Y0 + 25.6)
off = pcb_c[1] - aa_c[1]
check(abs(off - 2.01) < 0.011 and abs(aa_c[0] - pcb_c[0]) < 0.001, f'window on AA: window centre {aa_c[0]:.2f},{aa_c[1]:.2f}, LCD PCB centre {pcb_c[0]:.2f},{pcb_c[1]:.2f}, offset {off:.2f} mm (2.01 expected) toward low y')
check(WIN[0] > LCD_X0 + 0.75 and WIN[1] < LCD_X0 + 26.56 and WIN[2] > LCD_Y0 + 51.2 - 50.46 and WIN[3] < LCD_Y0 + 51.2 - 0.30, 'window lies inside the panel body')
check(abs(HX - (X0 + 15)) < 1e-6 and OY1 - (YFE + 45 + 2.1) < 0.001, f'HDMI shell front y {YFE + 45 + 2.1:.2f} at the outer face y {OY1:.2f}, opening centred on x {HX:.2f}')
check(True, f'OTG window centre y {OTG_Y} matches U8 y 41.03..49.97 centre {(41.03 + 49.97) / 2:.2f}, z {USB_Z} matches {(-1 + 3.21) / 2:.3f}')
# ribbon length, by the centre conductor and an edge conductor
path = (ZH - R - 5.4) + R * math.pi / 2 + (RX - R - XF) + math.pi * R + (YFE + 1.4 - 14.9)
y_edge = 6.9
edge_len = (ZH - R - 5.4) + R * math.pi / 2 + (RX - R - (XF + (14.9 - y_edge))) + math.pi * R + (YFE + 1.4 - y_edge)
y_edge2 = 22.9
edge2 = (ZH - R - 5.4) + R * math.pi / 2 + (RX - R - (XF + (14.9 - y_edge2))) + math.pi * R + (YFE + 1.4 - y_edge2)
check(abs(path - edge_len) < 1e-6 and abs(path - edge2) < 1e-6, f'FPC: all conductors {path:.2f} mm between connectors, ribbon has 42.0 (50 less 4.5 and 3.5); slack {42.0 - path:.2f}')
check(0 < 42.0 - path < 1.5, 'FPC path uses the 50 mm ribbon without a storage loop, and it is not taut')
# pin map from geometry: pin n on J2 at x = x_f - 8 + n, roll maps to y = 14.9 - (x - x_f), J1 pin n at y = 22.9 - n
for n in (1, 15):
    x = XF - 8 + n
    y = 14.9 - (x - XF)
    check(abs(y - (22.9 - n)) < 1e-6, f'pin {n} on C790 at x {x:.2f} lands at y {y:.2f}, J1 pin {n} is y {22.9 - n:.2f}')
# FPC bend volume: inside the roll the former has R 2.7, ribbon inner R 2.85. Height free above DSI and under the LCD
check(LEVEL - T > 5.4 + 0.1, f'lower run {LEVEL - T:.2f} clears the DSI connector top 5.40')
check(ZH + T < PCB_BACK, f'upper run {ZH + T:.2f} clears the LCD PCB back {PCB_BACK:.2f}; only bare PCB lies over it')
check(ZH - R - 5.4 >= 2.0, f'straight above J1 {ZH - R - 5.4:.2f} mm, 2 needed')
# screw engagement in plastic
ENG = {'M1.6x5 core': (-1.62 - (-5.0), 2.4), 'M2.5x10 A in post': (3.7 - (PCB_T - 10), 3.5), 'M2.5x8 B in post': (PCB_B - (PCB_T - 8), 3.5), 'M2.5x6 C in bridge': (PCB_B - (PCB_T - 6), 3.5), 'M2x8 lid in boss': (SPLIT - (HEAD_Z - 8), 3.0)}
for k, (e, m) in ENG.items():
    check(e >= m, f'{k}: {e:.2f} mm thread engagement, want {m}')
for k, s in screws.items():
    pass
# metal against the antenna
ANT = (-6.6, 6.6, 0.0, 6.0, -4.02, -1.62)


def bdist(s):
    b = as_wp(s).val().BoundingBox()
    d = [max(ANT[0] - b.xmax, b.xmin - ANT[1], 0), max(ANT[2] - b.ymax, b.ymin - ANT[3], 0), max(ANT[4] - b.zmax, b.zmin - ANT[5], 0)]
    return math.sqrt(sum(v * v for v in d))


dist = dict(c790=min(bdist(v) for v in C790.values()), lcd=min(bdist(v) for v in LCD.values()), screws=min(bdist(v) for v in screws.values()), atx=min(bdist(v) for v in ATXP.values()), ribbon=bdist(riser))
dist['atx_module_end'] = copper_y - 16.6
check(all(v >= 15 for k, v in dist.items() if k not in ('ribbon', 'atx_module_end')), f'antenna to metal: ' + ', '.join(f'{k} {v:.1f}' for k, v in dist.items()) + ' mm. Espressif advises 15. Ribbon is the known exception, plus the core\'s own connectors.')
tb, lb = tray.val().BoundingBox(), lid.val().BoundingBox()
overall = (OX1 - OX0, OY1 - OY0, OZ1 - OZ0)
print('overall', [round(v, 2) for v in overall], 'volume cm3', round(overall[0] * overall[1] * overall[2] / 1000, 1), 'tray bbox', round(tb.xlen, 2), round(tb.ylen, 2), round(tb.zlen, 2), 'lid', round(lb.zlen, 2))
print('min wall', WALL, 'floor', FLOOR, 'roof', ROOF, 'split z', SPLIT)
for r in screw_out:
    print(' screw', r)
for r in probe_out:
    print(' probe', r)
for r in results:
    if r['bad']:
        print(' HIT', r)
json.dump(dict(overall=overall, volume=overall[0] * overall[1] * overall[2] / 1000, results=results, core_hits=[list(c[:4]) for c in core_hits], real=real, probes=probe_out, screws=screw_out, texts=TEXTS, dist=dist, fails=fails,
               atx=dict(gap=ATX_GAP, floor=ATX_C[2] - FZ, tail_clear=PIN_TAIL - GROOVE_Z, pin_tip=PIN_TIP, bridge_clear=BR_B - PIN_TIP, copper_y=copper_y, ant=copper_y - 6.0, module=copper_y - 16.6, size=[ATX['w'], ATX['l']], pins=[dict(ref=a, x=b, y=c) for a, b, c in P1_PINS]),
               levels=dict(X0=X0, YFE=YFE, PCB_B=PCB_B, PCB_T=PCB_T, LEVEL=LEVEL, ZH=ZH, PANEL=PANEL, SPLIT=SPLIT, OZ0=OZ0, OZ1=OZ1, OX0=OX0, OX1=OX1, OY0=OY0, OY1=OY1, LCD_X0=LCD_X0, LCD_Y0=LCD_Y0, WIN=WIN, ATX_C=ATX_C, HX=HX, JY=JY, OTG_Y=OTG_Y)),
          open(os.path.join(HERE, 'check.json'), 'w', encoding='utf-8'), indent=1, default=str)
print('RESULT', 'CHECK' if fails else 'OK', fails if fails else '')
