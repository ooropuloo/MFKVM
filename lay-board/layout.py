# -*- coding: utf-8 -*-
"""One-board P4 KVM mechanical study. Sweeps the case size, checks bodies and cable plugs, writes layout.json.

Coordinates in mm: origin at the PCB centre, y toward the I/O face, z up from the desk.
This is the size sweep only. Part positions here came before routing and are not the board: build_page.py replaces them with the routed
positions, and case/gen_case.py documents the design-to-case mapping. Do not read left and right from this file.
Sources per part are in SOURCE. "official" came from a vendor drawing, "typical" still needs the chosen part's drawing.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WALL, SIDE_GAP = 1.6, 0.4
PCB_T = 1.2
FLOOR, LID = 1.2, 1.2
HDMI_H, USBC_H, MODULE_H = 6.0, 3.2, 3.3
HDMI_PLUG = (19.5, 11.0)
USBC_PLUG = (12.0, 8.0)
HOLE_KEEP = 2.5
LCD_D, LCD_T = 36.0, 1.8
MARGIN_Z = 2.0
TARGET_S, TARGET_H = 44, 20.0  # room left for BGA fan-out, decoupling and a thermal pad

SOURCE = {
    'P4 module': 'official: Waveshare STEP, 25 x 25 x 3.31',
    'USB-C': 'official: same connector envelope as the routed board, 8.94 x 9.06 x 3.2',
    'HDMI': 'typical: Type A SMT, 15 x 12.2 x 6',
    'microSD': 'typical: push-push, 14 x 15 x 1.9',
    'TC358743': 'official: LCSC C3008606, BGA-64 6 x 6 x 1.2',
    'Round LCD': 'typical: 1.28 in GC9A01 bare panel, 36 dia x 1.8',
    'Plugs': 'worst case from Codex R1 envelopes: HDMI 19.5 x 11, USB-C 12 x 8',
}


def layout(s):
    p = s - 2 * (WALL + SIDE_GAP)
    h = p / 2
    z_bot = HDMI_PLUG[1] / 2 + HDMI_H / 2  # the HDMI plug must clear the desk
    z_top = z_bot + PCB_T
    hole = h - HOLE_KEEP + 0.5
    reach = hole - HOLE_KEEP
    face = h + 0.6

    hdmi_x0 = -reach
    hdmi_cx = hdmi_x0 + 7.5
    usb_cx = hdmi_cx + HDMI_PLUG[0] / 2 + 1.0 + USBC_PLUG[0] / 2
    mod_y1 = face - 9.06 - 0.3
    mod_y0 = mod_y1 - 25
    mod_x0 = -reach
    mod_x1 = mod_x0 + 25

    top = {
        'P4 module': (mod_x0, mod_x1, mod_y0, mod_y1, z_top, z_top + MODULE_H),
        'USB-C host': (usb_cx - 4.47, usb_cx + 4.47, face - 9.06, face, z_top, z_top + USBC_H),
        'USB-C power': (h + 0.6 - 9.06, h + 0.6, -7.5, 1.44, z_top, z_top + USBC_H),
        'LCD socket': (-7, 7, -h + 0.2, -h + 3.2, z_top, z_top + 1.0),
    }
    bottom = {
        'HDMI': (hdmi_cx - 7.5, hdmi_cx + 7.5, face - 12.2, face, z_bot - HDMI_H, z_bot),
        'microSD': (-h - 0.3, -h + 13.7, -h + 4.6, -h + 19.6, z_bot - 1.9, z_bot),
        'TC358743': (hdmi_cx + 8.5, hdmi_cx + 14.5, face - 12.5, face - 6.5, z_bot - 1.2, z_bot),
        'Buck 3V3': (h - 8, h - 1.2, face - 17, face - 11.5, z_bot - 2.2, z_bot),
        'LDO 1V8/1V2': (h - 8, h - 1.2, face - 10.5, face - 6, z_bot - 1.2, z_bot),
        'Opto x3': (-h + 15, -h + 30.5, -h + 4.6, -h + 11.1, z_bot - 3.65, z_bot),
        'ATX 6P': (-h + 15, -h + 28.3, -h - 0.3, -h + 1.4, z_bot - 4.15, z_bot),
    }
    holes = [(sx * hole, sy * hole) for sx in (-1, 1) for sy in (-1, 1)]

    z_lcd = z_top + max(MODULE_H, USBC_H) + 0.3
    height_min = z_lcd + LCD_T + 0.3 + LID
    height = round(height_min + MARGIN_Z, 1)
    return dict(s=s, pcb=p, h=h, z_bot=z_bot, z_top=z_top, z_lcd=z_lcd, height_min=height_min, height=height,
                face=face, holes=holes, top=top, bottom=bottom, hdmi_cx=hdmi_cx, usb_cx=usb_cx)


def overlap(a, b):
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3] and a[4] < b[5] and b[4] < a[5]


def rect_hole_gap(b, c):
    dx = max(b[0] - c[0], 0, c[0] - b[1])
    dy = max(b[2] - c[1], 0, c[1] - b[3])
    return (dx * dx + dy * dy) ** 0.5


def check(L):
    errs = []
    for side in ('top', 'bottom'):
        items = list(L[side].items())
        for i, (na, a) in enumerate(items):
            for nb, b in items[i + 1:]:
                if overlap(a, b):
                    errs.append(f'{na} hits {nb}')
            for c in L['holes']:
                if rect_hole_gap(a, c) < HOLE_KEEP - 1e-6:
                    errs.append(f'{na} is {rect_hole_gap(a, c):.2f} mm from hole {c}')
            limit = L['h'] + SIDE_GAP + WALL
            if a[0] < -limit or a[1] > limit or a[2] < -limit or a[3] > limit:
                errs.append(f'{na} outside the case')
    gap = (L['usb_cx'] - USBC_PLUG[0] / 2) - (L['hdmi_cx'] + HDMI_PLUG[0] / 2)
    if gap < 0.5:
        errs.append(f'HDMI and USB plugs only {gap:.2f} mm apart')
    if L['usb_cx'] + USBC_PLUG[0] / 2 > L['s'] / 2 or L['hdmi_cx'] - HDMI_PLUG[0] / 2 < -L['s'] / 2:
        errs.append('plug wider than the I/O face')
    if LCD_D > L['s'] - 2 * WALL:
        errs.append('LCD wider than the case interior')
    if L['z_bot'] - HDMI_H < FLOOR:
        errs.append('HDMI into the case floor')
    return errs


def free_area(L, side):
    used = sum((b[1] - b[0]) * (b[3] - b[2]) for b in L[side].values())
    return L['pcb'] ** 2 - used - 4 * 3.14159 * HOLE_KEEP ** 2


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    best = None
    print('case   pcb    height  volume  free top/bottom  result')
    for s in range(40, 52, 2):
        L = layout(s)
        e = check(L)
        vol = s * s * L['height'] / 1000
        print(f"{s:4d}  {L['pcb']:5.1f}  {L['height']:5.1f}  {vol:6.1f}  {free_area(L, 'top'):6.0f}/{free_area(L, 'bottom'):4.0f}     {'PASS' if not e else 'FAIL'}")
        for x in e:
            print('        ', x)
        if not e and best is None:
            best = L
    if best is None:
        print('RESULT no size passes')
        return 1
    target = layout(TARGET_S)
    assert not check(target)
    target['height'] = TARGET_H
    assert target['height'] >= target['height_min']
    target['source'] = SOURCE
    target['checks'] = {'plug_gap': (target['usb_cx'] - USBC_PLUG[0] / 2) - (target['hdmi_cx'] + HDMI_PLUG[0] / 2)}
    target['lcd'] = {'d': LCD_D, 't': LCD_T}
    target['min'] = {'s': best['s'], 'height_min': best['height_min']}
    json.dump(target, open(os.path.join(out, 'layout.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f"TARGET {TARGET_S} x {TARGET_S} x {TARGET_H}, free top/bottom {free_area(target, 'top'):.0f}/{free_area(target, 'bottom'):.0f} mm2")
    print(f"RESULT smallest passing case {best['s']} x {best['s']} x {best['height']} mm (height includes {MARGIN_Z} mm margin, minimum {best['height_min']:.1f})")
    print('target plug gap', round(target['checks']['plug_gap'], 2), 'z_bot', target['z_bot'], 'z_top', target['z_top'], 'z_lcd', target['z_lcd'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
