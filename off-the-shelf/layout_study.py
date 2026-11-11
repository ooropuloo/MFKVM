# -*- coding: utf-8 -*-
"""MF KVM v3 layout study. Every number in layout_study.md comes from this script.

Frame: FireBeetle STEP frame. x toward the OTG side, y from the antenna end (0) to the USB-CDC end (60), z = 0 on the core's top copper.
usage: layout_study.py            writes layout_study.md and layout.json next to itself
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- inputs. E = evidence: V primary source, I inferred, G engineering guess
WALL, FLOOR, ROOF = 1.6, 1.2, 1.0      # G print-friendly
GAP = 0.3                              # G air gap, part to case
CORE = dict(w=25.4, l=60.0, top=5.40, bot=-4.02, pcb=-1.62, usb_y=61.47, usb_top=3.21, tall_top=3.35)  # V STEP
J1 = dict(x=4.30, y_mid=14.9, ins=4.5)  # V STEP: slot at x 4.13..4.45 below the slider, ribbon seats at z 0.9, so 4.5 inside
RIBBON = dict(len=50.0, w=16.0, r=3.0, ins_c790=3.5)  # V len (Wurth 686715050001). G width, R, J2 insertion
L_EFF = RIBBON['len'] - J1['ins'] - RIBBON['ins_c790']
S_MIN = 2.0                            # G straight above the upright connector before any bend
ENTRY_STRAIGHT = 4.5                   # G C790 research asks about 5 mm straight. In the roll only one ribbon edge is this short, the centre has 12.5. 4.5 leaves 0.26 mm of slack instead of a taut ribbon
ANT = (-6.6, 6.6, 0.0, 6.0, -4.02, -1.62)  # V module outline, I antenna is y 0..6
C790 = dict(l=45.0, w=30.0, pcb=1.6, hdmi_out=2.1, back=2.0, top=7.4, j2_mid=14.85, entry=1.4, ribbon_up=1.2, j5_top=4.0, hdmi_tail=10.1, hdmi_body=7.6)
# V outline. G heights, upper bound of the 9-11 mm total: back 2 + pcb 1.6 + top 7.4 = 11.0
LCD = dict(l=51.2, w=27.3, panel_to_back=3.5, ic=1.2, conn=3.5)  # V STEP. Rear parts only at Xl 12.5..17.6 (conn), 22..30 (IC), 36..43 (ZIF); elsewhere bare PCB, so tall things are parked under bare PCB
PLUG_TOP = 1.105 + 3.3                 # G overmoulded USB-C plug, 6.6 tall, centred on the receptacle
SHELF = 0.8                            # G plastic between the plug and the C790 solder tails
TAIL = 1.2                             # G HDMI tails below the C790 PCB
R = RIBBON['r']


def boxdist(a, b):
    d = [max(a[i * 2] - b[i * 2 + 1], b[i * 2] - a[i * 2 + 1], 0.0) for i in range(3)]
    return math.sqrt(sum(v * v for v in d))


def transport(start_t, start_n, ops):
    """Carries the ribbon frame from C790 to J1. r = t x n points at conductor 1. n is the face away from the C790 contacts."""
    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def rot(v, ax, ang):
        c, s = round(math.cos(ang), 9), round(math.sin(ang), 9)
        d = sum(p * q for p, q in zip(ax, v))
        x = cross(ax, v)
        return tuple(v[i] * c + x[i] * s + ax[i] * d * (1 - c) for i in range(3))
    t, n = start_t, start_n
    for ax, ang in ops:
        k = math.sqrt(sum(p * p for p in ax))
        ax = tuple(p / k for p in ax)
        t, n = rot(t, ax, ang), rot(n, ax, ang)
    r = cross(t, n)
    return [round(v, 6) + 0.0 for v in t], [round(v, 6) + 0.0 for v in n], [round(v, 6) + 0.0 for v in r]


def mapping(start_t, start_n, ops):
    t, n, r = transport(start_t, start_n, ops)
    assert t == [0.0, 0.0, -1.0], t
    # J1 facts: pin 1 at high y (DFRobot pinout figure, white dot), spring contact on the -x side of the slot (STEP section)
    pin1_ok = r[1] > 0
    # opposite-contact ribbon: J1 contact face is +n. J1 needs the contact to face -x
    opp_ok = n[0] < 0
    return pin1_ok, ('opposite' if opp_ok else 'same-side')


def study():
    out = []
    H90 = math.pi / 2
    PI = math.pi

    # ---------- A: stacked crosswise, C790 face down, past the -x edge, LCD beside it
    level = 10.4
    z_t = level + 2 * R
    # hump: riser, arc to -x, arc down, arc to -x, straight into J2
    xe = (z_t - R - CORE['top']) + 3 * R * H90 + (z_t - level - 2 * R) + J1['x'] - 2 * R - L_EFF
    edge = xe + C790['entry']
    x0 = edge - C790['l'] - C790['hdmi_out']
    top = level + C790['ribbon_up'] + C790['pcb'] + C790['back']
    h_in = max(top, z_t + 0.3) + GAP - (CORE['bot'] - GAP)
    wx = CORE['w'] / 2 + GAP - x0 + GAP
    wy = CORE['usb_y'] + GAP * 2
    pm = mapping((1, 0, 0), (0, 0, -1), [((0, 1, 0), H90)])
    pm0 = mapping((1, 0, 0), (0, 0, 1), [((0, 1, 0), H90)])
    c = (edge - 45, edge, 0, 30, level + 1.2, level + 2.8)
    l = (x0, x0 + 51.2, 31.0, 58.3, level + 1.0, level + 6)
    out.append(dict(key='A', name='Stacked crosswise, C790 face down past the core, LCD beside it', x=wx + 2 * WALL, y=wy + 2 * WALL, z=h_in + FLOOR + ROOF, foot='rectangle', pin=pm, c790=c, lcd=l,
                    rib=(edge, 4.45, 6.9, 22.9, CORE['top'], z_t), note=f'The 50 mm ribbon has to go somewhere, which pushes the C790 edge out to x {edge:.1f}. Face-up here gives pin 1 to pin 15 ({"ok" if pm0[0] else "3V3 onto GND"}), so it has to be face down.'))

    # ---------- B: flat, C790 face up off the +x edge, ribbon hump, LCD on top of C790
    pcb_b = CORE['bot'] - GAP + 0.1 + C790['back']
    pcbt = pcb_b + C790['pcb']
    level = pcbt + C790['ribbon_up']
    hdmi = pcbt + C790['top']
    panel = hdmi + 0.15 + LCD['panel_to_back']
    top = panel
    z_t = top - 0.3
    path0 = (z_t - R - CORE['top']) + 3 * R * H90 + (z_t - level - 2 * R) + ENTRY_STRAIGHT
    # horizontal run = xe - J1.x - 2R - entry straight, so the rest of the free path sets where the ribbon meets J2
    xe = L_EFF - path0 + J1['x'] + 2 * R + ENTRY_STRAIGHT
    edge = xe - C790['entry']
    x1 = edge + C790['l'] + C790['hdmi_out']
    wx = x1 + CORE['w'] / 2 + 2 * GAP
    wy = CORE['usb_y'] + 2 * GAP
    z = top - (CORE['bot'] - GAP) + FLOOR + ROOF
    pm = mapping((-1, 0, 0), (0, 0, 1), [((0, -1, 0), H90)])
    area_l = (wx + 2 * WALL) * (30.6 + 2 * WALL) + (CORE['w'] + 2 * GAP + 2 * WALL) * (wy - 30.6)
    c = (edge, edge + 45, 0, 30, pcb_b, pcbt)
    l = (edge, edge + 51.2, 1.3, 28.6, panel - 3.5, panel)
    out.append(dict(key='B', name='Flat L: C790 face up off the +x edge, LCD on C790, ribbon hump', x=wx + 2 * WALL, y=wy + 2 * WALL, z=z, foot='L', vol_real=area_l * z / 1000, pin=pm, c790=c, lcd=l,
                    rib=(4.15, edge, 6.9, 22.9, CORE['top'], z_t), note=f'No roll, no tunnel, height {z:.1f}. Bounding box is huge, real volume is the L ({area_l * z / 1000:.0f} cm3). OTG and TF sit in the notch of the L.'))

    # ---------- common to the inline layouts: the ribbon rises, runs -x, rolls 45 deg over a R3 former, then runs +y into J2
    x_f = J1['x'] - R - RIBBON['w'] / 2
    y_e = J1['y_mid'] + RIBBON['w'] / 2 + ENTRY_STRAIGHT
    y_fe = y_e - C790['entry']
    x0 = x_f - C790['j2_mid']
    x1 = x0 + C790['w']
    y_h = y_fe + C790['l'] + C790['hdmi_out']
    wx = (CORE['w'] / 2 + GAP) - min(x0 - GAP, -CORE['w'] / 2 - GAP)
    # the HDMI shell finishes at the outer face, so y runs from the antenna-end wall to y_h
    ops_roll = [((1, -1, 0), PI), ((0, 1, 0), H90)]

    # ---------- C: inline, roll goes up. C790 sits high, USB plug passes beneath with room to spare
    z_h = CORE['top'] + S_MIN + R
    level = z_h + 2 * R
    pcbt = level - C790['ribbon_up']
    hdmi = pcbt + C790['top']
    j5 = pcbt + C790['j5_top']
    panel = max(j5, level + 0.15) + 0.15 + LCD['panel_to_back']
    h_in = panel - (CORE['bot'] - GAP)
    p = (z_h - R - CORE['top']) + R * H90 + (J1['x'] - R - x_f) + PI * R + (y_e - J1['y_mid'])
    c = (x0, x1, y_fe, y_fe + 45, pcbt - 1.6, pcbt)
    y_lcd = 15.0
    l = (x0, x0 + 27.3, y_lcd, y_lcd + 51.2, panel - 3.5, panel)
    pm = mapping((0, -1, 0), (0, 0, 1), ops_roll)
    out.append(dict(key='C', name='Inline, roll upward: C790 high over the core, LCD on top', x=wx + 2 * WALL, y=y_h + GAP + WALL, z=h_in + FLOOR + ROOF, foot='rectangle', pin=pm, c790=c, lcd=l, path=p,
                    rib=(x_f - 8, 4.45, 6.9, 22.9, CORE['top'], level + 0.15), note='Simplest structure over the USB plug, but it pays the 6 mm roll on top of everything.'))

    # ---------- D: inline, roll goes down so the lower run is J2 level, as low as the USB plug tunnel allows
    pcb_b = PLUG_TOP + 0.2 + SHELF + TAIL + 0.1
    pcbt = pcb_b + C790['pcb']
    level = pcbt + C790['ribbon_up']
    z_h = level + 2 * R
    assert level - 0.15 > CORE['top'] + 0.1
    s = z_h - R - CORE['top']
    assert s >= S_MIN
    p = s + R * H90 + (J1['x'] - R - x_f) + PI * R + (y_e - J1['y_mid'])
    hdmi = pcbt + C790['top']
    panel = max(z_h + 0.15, hdmi) + 0.15 + LCD['panel_to_back'] + 0.8  # the extra 0.8 lifts the LCD's M2 standoffs over the ribbon's bend and roll, found by the case's interference check
    h_in = panel - (CORE['bot'] - GAP)
    c = (x0, x1, y_fe, y_fe + 45, pcb_b, pcbt)
    l = (-18.7, -18.7 + 27.3, y_lcd, y_lcd + 51.2, panel - 3.5, panel)
    # a 180 deg wrap gives the same frame up or down, only the side the former sits on differs
    pm = mapping((0, -1, 0), (0, 0, 1), ops_roll)
    out.append(dict(key='D', name='Inline, roll downward: C790 just above the USB plug tunnel, LCD on top', x=wx + 2 * WALL, y=y_h + GAP + WALL, z=h_in + FLOOR + ROOF, foot='rectangle, with a plug alcove under the HDMI end', pin=pm, c790=c, lcd=l, path=p,
                    rib=(x_f - 8, 4.45, 6.9, 22.9, CORE['top'], z_h + 0.15), note='Picked. See below.', d=dict(x_f=x_f, y_e=y_e, y_fe=y_fe, x0=x0, x1=x1, y_h=y_h, pcb_b=pcb_b, pcbt=pcbt, level=level, z_h=z_h, s=s, hdmi=hdmi, panel=panel, path=p)))

    # ---------- E: C790 under the core, ribbon wraps the +x edge
    pcbt = CORE['bot'] - GAP - 3.0
    pcb_b = pcbt - 1.6
    level = pcbt + 1.2
    z_h = CORE['top'] + S_MIN + R + 3.0
    r2 = (z_h - level) / 2
    p = (z_h - R - CORE['top']) + R * H90 + PI * r2
    xe = J1['x'] + R + 8 - (L_EFF - p - 8)
    bot = pcb_b - C790['back']
    panel = CORE['usb_top'] + 0.3 + 7.0
    z = panel - bot + FLOOR + ROOF
    x_right = J1['x'] + R + 8 + r2
    edge = xe + 1.4
    x_left = edge - 47.1
    pm = mapping((1, 0, 0), (0, 0, 1), [((0, -1, 0), 3 * H90)])
    c = (edge - 45, edge, 0, 30, pcb_b, pcbt)
    l = (-30.0, 21.2, 31.0, 58.3, panel - 3.5, panel)
    out.append(dict(key='E', name='C790 under the core, ribbon wrapped round the +x edge', x=x_right - x_left + 2 * GAP + 2 * WALL, y=CORE['usb_y'] + 2 * GAP + 2 * WALL, z=z, foot='rectangle', pin=pm, c790=c, lcd=l, path=p,
                    rib=(4.15, x_right, 6.9, 22.9, level, z_h), note='Rejected twice: the C790 ground plane sits under the antenna, and pin 1 lands on pin 15.', reject=True))
    return out


rows = study()
for r in rows:
    r['vol'] = r['x'] * r['y'] * r['z'] / 1000
    a = ANT
    r['d_c790'] = boxdist(a, r['c790'])
    r['d_lcd'] = boxdist(a, r['lcd'])
    r['d_rib'] = boxdist(a, r['rib'])

d = next(r for r in rows if r['key'] == 'D')['d']
json.dump(dict(rows=[r for r in rows], d=d, L_EFF=L_EFF), open(os.path.join(HERE, 'layout.json'), 'w'), indent=1, default=str)

md = []
md.append('# MF KVM v3 layout study\n')
md.append('All numbers come from `layout_study.py`. Heights use the upper bound of the C790 estimate (total 11 mm). Walls 1.6, floor 1.2, roof 1.0, air gap 0.3. Nothing has been measured on real parts.\n')
md.append('## Why 65 x 35 x 24 was wrong\n')
md.append('It assumed the C790 could lie along the core. It cannot without a fold, because a ribbon only bends about an axis across its width, so the two connector long axes stay parallel unless the ribbon is folded on a diagonal. J1 runs along the core\'s 60 mm side and J2 runs along the C790\'s 30 mm side, so the C790\'s 45 mm side lies across the core. On top of that the 50 mm ribbon has %.1f mm of free path to use up (50 minus 4.5 inside J1 and 3.5 inside J2 [G]). There is no shorter catalogue part in the research.\n' % L_EFF)
md.append('## Results\n')
md.append('| | Layout | Outer X x Y x Z mm | Box cm3 | Real cm3 | Pin 1 | Ribbon type | Antenna to C790 / LCD / ribbon mm | Ribbon path vs %.1f |' % L_EFF)
md.append('|---|---|---|---|---|---|---|---|---|')
for r in rows:
    pin = 'ok' if r['pin'][0] else 'WRONG'
    path = f"{r['path']:.1f}" if 'path' in r else 'sized to fit'
    real = f"{r['vol_real']:.0f}" if 'vol_real' in r else f"{r['vol']:.0f}"
    md.append(f"| {r['key']} | {r['name']} | {r['x']:.1f} x {r['y']:.1f} x {r['z']:.1f} | {r['vol']:.0f} | {real} | {pin} | {r['pin'][1]} | {r['d_c790']:.1f} / {r['d_lcd']:.1f} / {r['d_rib']:.1f} | {path} |")
md.append('')
for r in rows:
    md.append(f"- **{r['key']}:** {r['note']}")
md.append('')
D = next(r for r in rows if r['key'] == 'D')
B = next(r for r in rows if r['key'] == 'B')
md.append('## Pick: D\n')
md.append(f"**{D['x']:.1f} x {D['y']:.1f} x {D['z']:.1f} mm, {D['vol']:.0f} cm3.** The case in `case/gen_case.py` is built to these numbers.\n")
md.append('- **Smallest box that keeps the antenna clear.** C starts the same way and is taller. A and B also clear the antenna but need a far bigger box. E has the C790 under the antenna.')
md.append('- **Antenna.** C790 starts at y %.1f. C790, LCD, ATX board and screws are all past Espressif\'s 15 mm. The ribbon comes within %.1f mm, and the core\'s own connectors are closer still, where DFRobot put them. Stacking the C790 directly over y 0..30 would be smaller but needs a shorter ribbon than the catalogue has, and puts its ground plane over the antenna.' % (d['y_fe'], D['d_rib']))
md.append('- **Ribbon.** The free path gets used by the roll, %.1f mm routed against %.1f mm available, with no slack loop to store.' % (d['path'], L_EFF))
md.append('- **Cost: a 45 degree roll in a MIPI ribbon.** A fold keeps every conductor the same length, so it adds no skew in theory, but no one has tested this exact ribbon and radius at 972 Mbit/s. A printed former sets R. Check the picture first thing when the parts arrive.')
md.append('- **Cost: the 5 V plug sits in a %.1f mm deep alcove** under the HDMI end, because the C790 overhangs the core\'s USB end. An overmoulded plug must be 13 mm wide and 6.6 mm tall or less.\n' % (d['y_h'] - CORE['usb_y']))
md.append('## Runner up: B\n')
md.append(f"Flat L, bounding box {B['x']:.0f} x {B['y']:.0f} x {B['z']:.0f}, real volume {B['vol_real']:.0f} cm3, height only {B['z']:.1f}. It has no roll and no alcove, the OTG and TF ports stand in open air, and the antenna is clearest of all. It loses because the footprint is {B['x']:.0f} x {B['y']:.0f} mm and it is a strange shape to pack. **If the roll fails on the bench, or a flat box suits you better than a small one, B is the fallback.** It uses the same ribbon, the same pin map and the same ATX board.\n")
md.append('## Later improvement\n')
md.append('A custom L-shaped flex PCB (not a catalogue FFC) removes the fold and about 6 mm of height, about 60 cm3 [G]. It needs 100 ohm impedance control on flex and an extra order, so it is not part of this design.\n')
md.append('## Ribbon pin map, derived\n')
md.append('The frame is carried from C790 to J1 in code, `transport()`. Conductor 1 lies on t x n, where t is the direction of travel and n is the face away from the C790 contacts.\n')
md.append('| Fact | Value | Evidence |')
md.append('|---|---|---|')
md.append('| C790 J2 pin 1 | low Y_c, contacts toward the PCB | [P] triangle in the photo, [V] G6 for contact direction |')
md.append('| J1 pin 1 | high y (toward the P4), white dot | [V] DFRobot pinout figure |')
md.append('| J1 contact | spring contact on the -x side of the slot, slider on the +x side | [V] section of the official STEP at y 11.9, `case/j1_section.png` (made from the vendor model, not in the repo; see THIRD_PARTY.md). A vendor model, not the part in hand [U] |')
md.append('')
md.append('For D, C790 face up with its FPC edge toward -y: t = -y, n = +z, so conductor 1 is on -x. The roll takes it to t = +x, n = -z, conductor 1 on +y. The final bend gives t = -z, n = -x, conductor 1 on +y.')
md.append('')
md.append('- **Pin 1 lands on pin 1**, independent of ribbon type.')
md.append('- **Opposite-contact ribbon** (Wurth 686715050001): the J1 contact face is +n = -x, which is the side the spring is on. That agrees with the DFRobot wording (contacts toward the contacts, blue backing toward the black slider).')
md.append('- **If the real J1 has its contact on +x**, the same layout needs a same-side ribbon (Wurth 686615050001). The layout does not change, only the part number. Buy one of each. Look before plugging in.')
md.append('- **Checked by conductor position too:** on the roll line y - 14.9 = -(x - x_f), pin 1 at x_f - 7 maps to y = 21.9, which is J1 pin 1.')
md.append('- **What the geometry rejects:** C790 face up off the -x edge gives pin 1 to pin 15 (3V3 to GND). The +x roll variant does too.')
open(os.path.join(HERE, 'layout_study.md'), 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')
for r in rows:
    print(r['key'], f"{r['x']:.1f} x {r['y']:.1f} x {r['z']:.1f}", f"box {r['vol']:.0f}", 'real', round(r.get('vol_real', r['vol'])), 'pin', r['pin'], f"ant c790 {r['d_c790']:.1f} lcd {r['d_lcd']:.1f} rib {r['d_rib']:.1f}", 'path', round(r.get('path', 0), 1))
print(d)
