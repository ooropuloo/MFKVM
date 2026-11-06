# -*- coding: utf-8 -*-
"""MF KVM v3 ATX board: three LTV-357T optos, resistors, JST SM06B, five plated holes that take straight pins into the core's P1 header. Writes KiCad schematic, board and a Specctra DSN.

usage: gen_atx.py <out_dir> [routed.ses]
Board mm: KiCad frame seen from the top side: x right, y down the screen. The board sits under the core with its top side facing the core's underside, both facing case +Z.
Every position that has to meet the core goes through case_to_board(): board x = case x - CX, board y = CY - case y. That is a flip of y only because KiCad's y points down, the board is not mirrored.
case/pinmap_check.py proves it on the Gerbers and drill file against the STEP. The JST opens at -x (case -X wall). y is negative at the case's HDMI end.
Footprints: official KiCad SO-4_4.4x3.6mm_P2.54mm and JST_SH_SM06B-SRSS-TB_1x06-1MP, as dumped in mini/data/kicad_official.json. Values match mini/gen_mini.py.
"""
import json
import math
import os
import re
import sys
import uuid

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = sys.argv[1]
SES = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT, exist_ok=True)
NAME = 'mf_kvm_atx'
CX, CY = -16.6, 52.75  # board origin in the case frame (FireBeetle STEP frame); case/gen_case.py reads it from design.json
P1_X = -11.43  # P1 header row, STEP and drawing
P1_Y = {'RST': 48.387, '3V3': 45.847, 'NC3': 43.307, 'GND': 40.767, 'NC5': 38.227, 'IO28': 35.687, 'IO29': 33.147, 'IO30': 30.607}  # y from the STEP hole list, pin 1 first


def case_to_board(x, y):
    return x - CX, CY - y


# Outline in board coordinates, walking the edge. Wide part beside the core, narrow tongue under the core's P1 row, notch at the core's mounting post.
OUTLINE = [(-4.95, 12.3), (2.6, 12.3), (2.6, 23.1), (6.1, 23.1), (6.1, 5.75), (5.2, 5.75), (5.2, -3.15), (3.0, -3.15), (3.0, -12.3), (-4.95, -12.3)]
CHAMFER = {0, 2, 3, 4, 7, 8, 9}  # outer corners only
OX, OY = 100.0, 100.0
W_TRACK, CLR = 0.2, 0.15
VIA_D, VIA_DR = 0.6, 0.3


def uid(seed=None):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'v3atx-' + seed)) if seed else str(uuid.uuid4())


def pad(n, x, y, w, h, shape='rect', kind='smd', d1=0.0):
    return dict(n=str(n), x=x, y=y, w=w, h=h, shape=shape, kind=kind, d1=d1)


R0402 = [pad(1, -0.48, 0, 0.56, 0.62), pad(2, 0.48, 0, 0.56, 0.62)]
OPTO = [pad(1, -3.15, -1.27, 2.0, 0.64), pad(2, -3.15, 1.27, 2.0, 0.64), pad(3, 3.15, 1.27, 2.0, 0.64), pad(4, 3.15, -1.27, 2.0, 0.64)]
JST6 = [pad(i + 1, -2.5 + i, -2.0, 0.6, 1.55) for i in range(6)] + [pad('MP1', -3.8, 1.875, 1.2, 1.8), pad('MP2', 3.8, 1.875, 1.2, 1.8)]
PIN = [pad(1, 0, 0, 1.4, 1.4, 'circle', 'thru_hole', 0.9)]  # same 0.9 hole as the core's header, for a 0.64 round pin
parts = []


def part(ref, value, lcsc, lib, pads, x, y, r, nets, body=None):
    parts.append(dict(ref=ref, value=value, lcsc=lcsc, lib=lib, pads=[dict(q) for q in pads], x=x, y=y, r=r, nets=dict(nets), body=body))


def R(ref, value, code, x, y, r, n1, n2):
    part(ref, f'{value} 0402', code, 'R0402', R0402, x, y, r, {'1': n1, '2': n2}, BODY_R)


OPTO_NAME, OPTO_CODE = 'LTV-357T-C', 'C119091'
# Courtyards hold the real body at worst case size plus 0.1 placement, so DRC sees bodies. Numbers and sources are in tools/bodycheck.py.
BODY_OPTO = (-2.4, -2.175, 2.4, 2.175)
BODY_R = (-0.65, -0.4, 0.65, 0.4)
BODY_JST = (-4.2, -2.575, 4.2, 2.775)
BODY_PIN = (-0.85, -0.85, 0.85, 0.85)
# The RST pin tube crosses above the board at case y 53.3, over the optos.
part('U1', OPTO_NAME, OPTO_CODE, 'OPTO_SO4', OPTO, -0.45, 8.3, 180, {'1': 'PWR_LED', '2': 'GND', '3': 'PWR_E', '4': 'PWR_C'}, BODY_OPTO)
part('U2', OPTO_NAME, OPTO_CODE, 'OPTO_SO4', OPTO, -0.45, 3.7, 180, {'1': 'RST_LED', '2': 'GND', '3': 'RST_E', '4': 'RST_C'}, BODY_OPTO)
part('U3', OPTO_NAME, OPTO_CODE, 'OPTO_SO4', OPTO, -0.45, -0.9, 180, {'1': 'LED_IN', '2': 'LED_K', '3': 'ATX_LED', '4': '3V3'}, BODY_OPTO)
part('J1', 'SM06B-SRSS-TB ATX', 'C160405', 'JST_SM06B', JST6, -1.87, -7.6, -90, {'1': 'PWR_C', '2': 'PWR_E', '3': 'RST_C', '4': 'RST_E', '5': 'LED_K', '6': 'LED_A'}, BODY_JST)
R('R1', '470', 'C25117', 4.5, 9.75, 90, 'ATX_PWR', 'PWR_LED')
R('R2', '470', 'C25117', 4.5, 5.15, 90, 'ATX_RST', 'RST_LED')
R('R3', '270', 'C25099', 4.5, 0.55, 90, 'LED_A', 'LED_IN')
R('R4', '10k', 'C25744', -1.05, 11.2, 0, 'ATX_LED', 'GND')
# NC3, NC5 and RST get no hole on purpose. PWR GPIO28, RST GPIO29, LED GPIO30.
HOLES = (('3V3', '3V3', '3V3'), ('GND', 'GND', 'GND'), ('IO28', 'ATX_PWR', '28'), ('IO29', 'ATX_RST', '29'), ('IO30', 'ATX_LED', '30'))
for i, (pin, net, label) in enumerate(HOLES):
    bx, by = case_to_board(P1_X, P1_Y[pin])
    part(f'H{i + 1}', f'pin to P1 {label}', '', 'PIN_0.9', PIN, bx, by, 0, {'1': net}, BODY_PIN)


def bake(p):
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    res = []
    for q in p['pads']:
        x = q['x'] * c + q['y'] * s
        y = -q['x'] * s + q['y'] * c
        w, h = (q['w'], q['h']) if abs(s) < 0.5 else (q['h'], q['w'])
        res.append(dict(q, wx=p['x'] + x, wy=p['y'] + y, ww=w, wh=h))
    p['abs'] = res


for p in parts:
    bake(p)
    for q in p['pads']:
        if not p['nets'].get(q['n']):
            p['nets'][q['n']] = f"unconnected-({p['ref']}-Pad{q['n']})"
nets = sorted({n for p in parts for n in p['nets'].values()})
netid = {n: i + 1 for i, n in enumerate(nets)}
real_nets = [n for n in nets if not n.startswith('unconnected-')]


def bbox(p):
    xs, ys = [], []
    for q in p['abs']:
        xs += [q['wx'] - q['ww'] / 2, q['wx'] + q['ww'] / 2]
        ys += [q['wy'] - q['wh'] / 2, q['wy'] + q['wh'] / 2]
    if p['body']:
        a = math.radians(p['r'])
        c, s = round(math.cos(a), 6), round(math.sin(a), 6)
        x0, y0, x1, y1 = p['body']
        for bx, by in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            xs.append(p['x'] + bx * c + by * s)
            ys.append(p['y'] - bx * s + by * c)
    return min(xs) - 0.05, min(ys) - 0.05, max(xs) + 0.05, max(ys) + 0.05


sym = {p['ref']: uid('sym-' + p['ref']) for p in parts}


def fp(p):
    x0, y0, x1, y1 = bbox(p)
    pads = []
    for q in p['abs']:
        n = p['nets'].get(q['n'], '')
        net = f'(net {netid[n]} "{n}") ' if n else ''
        if q['kind'] == 'thru_hole':
            pads.append(f'(pad "{q["n"]}" thru_hole circle (at {q["wx"] - p["x"]:.4f} {q["wy"] - p["y"]:.4f}) (size {q["ww"]:g} {q["wh"]:g}) (drill {q["d1"]}) (layers "*.Cu" "*.Mask") {net}(uuid "{uid()}"))')
        else:
            pads.append(f'(pad "{q["n"]}" smd rect (at {q["wx"] - p["x"]:.4f} {q["wy"] - p["y"]:.4f}) (size {q["ww"]:g} {q["wh"]:g}) (layers "F.Cu" "F.Paste" "F.Mask") {net}(uuid "{uid()}"))')
    thru = p['lib'] == 'PIN_0.9'
    extra = ' exclude_from_bom exclude_from_pos_files' if thru else ''
    return f'''(footprint "atx:{p['lib']}" (layer "F.Cu") (uuid "{uid()}") (at {p['x'] + OX:.4f} {p['y'] + OY:.4f})
    (property "Reference" "{p['ref']}" (at {x0 - p['x']:.3f} {y0 - p['y'] - 0.3:.3f}) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (property "Value" "{p['value']}" (at 0 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (property "LCSC" "{p['lcsc']}" (at 0 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (path "/{sym[p['ref']]}") (sheetname "/") (sheetfile "{NAME}.kicad_sch")
    (attr {'through_hole' if thru else 'smd'}{extra})
    (fp_rect (start {x0 - p['x']:.3f} {y0 - p['y']:.3f}) (end {x1 - p['x']:.3f} {y1 - p['y']:.3f}) (stroke (width 0.05) (type default)) (fill no) (layer "F.CrtYd") (uuid "{uid()}"))
    {' '.join(pads)}
  )'''


def offset_poly(pts, d):
    """Moves each edge inward by d and intersects neighbours. The outline is simple and these moves are small."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)) / 2
    sign = 1 if area > 0 else -1
    res = []
    for i in range(n):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        cx, cy = pts[(i + 1) % n]
        u = (bx - ax, by - ay)
        v = (cx - bx, cy - by)
        lu, lv = math.hypot(*u), math.hypot(*v)
        nu = (-u[1] / lu * sign * d, u[0] / lu * sign * d)
        nv = (-v[1] / lv * sign * d, v[0] / lv * sign * d)
        # intersection of (a + nu) + t u and (b + nv) + s v
        den = u[0] * v[1] - u[1] * v[0]
        t = ((bx + nv[0] - ax - nu[0]) * v[1] - (by + nv[1] - ay - nu[1]) * v[0]) / den
        res.append((ax + nu[0] + t * u[0], ay + nu[1] + t * u[1]))
    return res


def chamfered(pts, r):
    res = []
    n = len(pts)
    for i in range(n):
        if i not in CHAMFER:
            res.append(pts[i])
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        la, lc = math.hypot(a[0] - b[0], a[1] - b[1]), math.hypot(c[0] - b[0], c[1] - b[1])
        res.append((b[0] + (a[0] - b[0]) / la * r, b[1] + (a[1] - b[1]) / la * r))
        res.append((b[0] + (c[0] - b[0]) / lc * r, b[1] + (c[1] - b[1]) / lc * r))
    return res


outline = chamfered(OUTLINE, 0.2)
HX0, HX1 = min(q[0] for q in OUTLINE), max(q[0] for q in OUTLINE)
HY0, HY1 = min(q[1] for q in OUTLINE), max(q[1] for q in OUTLINE)
W, L = HX1 - HX0, HY1 - HY0
edges = [f'(gr_line (start {a[0] + OX:.3f} {a[1] + OY:.3f}) (end {b[0] + OX:.3f} {b[1] + OY:.3f}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "{uid()}"))' for a, b in zip(outline, outline[1:] + outline[:1])]

tracks = []
nvia = 0
if SES:
    s = open(SES, encoding='utf-8').read()
    res = float(re.search(r'\(resolution um (\d+)\)', s).group(1))
    k = 1 / res / 1000.0
    i = s.find('network_out')
    netpos = [(m.start(), m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', s[i:])]
    for j, (a, n) in enumerate(netpos):
        block = s[i + a:i + (netpos[j + 1][0] if j + 1 < len(netpos) else len(s) - i)]
        if n not in netid:
            raise SystemExit(f'unknown net in SES: {n}')
        for wm in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', block):
            v = [int(t) for t in wm.group(3).split()]
            pts = [(v[t] * k, -v[t + 1] * k) for t in range(0, len(v), 2)]
            for a0, b0 in zip(pts, pts[1:]):
                tracks.append(f'(segment (start {a0[0] + OX:.4f} {a0[1] + OY:.4f}) (end {b0[0] + OX:.4f} {b0[1] + OY:.4f}) (width {W_TRACK}) (layer "{wm.group(1)}") (net {netid[n]}) (uuid "{uid()}"))')
        for vm in re.finditer(r'\(via\s+"?([^"\s]+)"?\s+(-?\d+)\s+(-?\d+)', block):
            x, y = int(vm.group(2)) * k, -int(vm.group(3)) * k
            tracks.append(f'(via (at {x + OX:.4f} {y + OY:.4f}) (size {VIA_D}) (drill {VIA_DR}) (layers "F.Cu" "B.Cu") (net {netid[n]}) (uuid "{uid()}"))')
            nvia += 1

head = f'''(kicad_pcb (version 20241229) (generator "v3atx") (generator_version "9.0")
  (general (thickness 1.0) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal)
    (9 "F.Adhes" user "F.Adhesive") (11 "B.Adhes" user "B.Adhesive") (13 "F.Paste" user) (15 "B.Paste" user)
    (5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen") (1 "F.Mask" user) (3 "B.Mask" user)
    (17 "Dwgs.User" user "User.Drawings") (19 "Cmts.User" user "User.Comments") (21 "Eco1.User" user "User.Eco1") (23 "Eco2.User" user "User.Eco2")
    (25 "Edge.Cuts" user) (27 "Margin" user) (31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard") (35 "F.Fab" user) (33 "B.Fab" user))
  (setup (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))
  (net 0 "")
''' + ''.join(f'  (net {netid[n]} "{n}")\n' for n in nets)


def silk(t, x, y, h, w, layer='B.SilkS', angle=0):
    mir = ' (justify mirror)' if layer.startswith('B') else ''
    return f'(gr_text "{t}" (at {x + OX:.2f} {y + OY:.2f} {angle}) (layer "{layer}") (uuid "{uid()}") (effects (font (size {h} {h}) (thickness {w})){mir}))'


silks = [silk('MF KVM ATX', -1.0, -4.6, 0.8, 0.12), silk('REV B', -1.0, -6.0, 0.7, 0.12), silk('AWAY FROM CORE', -0.8, 1.0, 0.6, 0.1)]
for q in parts:
    if q['lib'] == 'PIN_0.9':
        silks.append(silk(q['value'].split()[-1], 3.35, q['y'], 0.6, 0.1))
body = [fp(p) for p in parts] + edges + tracks + silks
open(f'{OUT}/{NAME}.kicad_pcb', 'w', encoding='utf-8', newline='\n').write(head + '  ' + '\n  '.join(body) + '\n)\n')

# ---------- schematic: one symbol per part, every pin carries its net as a global label
root = uid('root')
sy, inst, labels = [], [], []
cx, cy = 30.48, 30.48
for p in parts:
    pins = list(dict.fromkeys(q['n'] for q in p['pads']))
    h = max(len(pins) * 2.54 + 2.54, 7.62)
    if cy + h > 180:
        cy, cx = 30.48, cx + 66.04
    sid = 'S_' + p['ref']
    pin_def = [f'(pin passive line (at -7.62 {-i * 2.54:g} 0) (length 2.54) (name "{n}" (effects (font (size 1 1)))) (number "{n}" (effects (font (size 1 1)))))' for i, n in enumerate(pins)]
    sy.append(f'''(symbol "{sid}" (pin_names (offset 0.5)) (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "{p['ref'][0]}" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "{sid}" (at 0 5 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "{sid}_0_1" (rectangle (start -5.08 1.27) (end 7.62 {-(len(pins) - 1) * 2.54 - 1.27:g}) (stroke (width 0.2) (type default)) (fill (type background))))
      (symbol "{sid}_1_1" {' '.join(pin_def)})
    )''')
    x, y = cx, cy
    uu = ' '.join(f'(pin "{n}" (uuid "{uid()}"))' for n in pins)
    inst.append(f'''(symbol (lib_id "atx:{sid}") (at {x:g} {y:g} 0) (unit 1) (exclude_from_sim no) (in_bom {'no' if p['lib'] == 'PIN_0.9' else 'yes'}) (on_board yes) (dnp no) (uuid "{sym[p['ref']]}")
    (property "Reference" "{p['ref']}" (at {x + 1:g} {y - 3:g} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{p['value']}" (at {x + 10:g} {y:g} 0) (effects (font (size 1 1)) (justify left)))
    (property "Footprint" "atx:{p['lib']}" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "LCSC" "{p['lcsc']}" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    {uu}
    (instances (project "{NAME}" (path "/{root}" (reference "{p['ref']}") (unit 1))))
  )''')
    for i, n in enumerate(pins):
        px, py = x - 7.62, y + i * 2.54
        net = p['nets'][n]
        if net.startswith('unconnected-'):
            labels.append(f'(no_connect (at {px:g} {py:g}) (uuid "{uid()}"))')
        else:
            labels.append(f'(global_label "{net}" (shape passive) (at {px:g} {py:g} 180) (fields_autoplaced yes) (effects (font (size 1 1)) (justify right)) (uuid "{uid()}"))')
    cy = round((cy + h + 7.62) / 2.54) * 2.54
sch = f'''(kicad_sch (version 20250114) (generator "v3atx") (generator_version "9.0") (uuid "{root}") (paper "A3")
  (title_block (title "MF KVM v3 ATX") (rev "B") (comment 1 "LTV-357T x3, PWR and RST switch outputs, LED sense. H1-H5 are straight pins into FireBeetle P1"))
  (lib_symbols {' '.join(x.replace('(symbol "S_', '(symbol "atx:S_', 1) for x in sy)})
  {' '.join(inst)}
  {' '.join(labels)}
  (sheet_instances (path "/" (page "1")))
)
'''
open(f'{OUT}/{NAME}.kicad_sch', 'w', encoding='utf-8', newline='\n').write(sch)
open(f'{OUT}/atx.kicad_sym', 'w', encoding='utf-8', newline='\n').write('(kicad_symbol_lib (version 20241209) (generator "v3atx") (generator_version "9.0")\n' + '\n'.join(sy) + '\n)\n')
open(f'{OUT}/sym-lib-table', 'w', newline='\n').write('(sym_lib_table (version 7) (lib (name "atx") (type "KiCad") (uri "${KIPRJMOD}/atx.kicad_sym") (options "") (descr "")))\n')
open(f'{OUT}/fp-lib-table', 'w', newline='\n').write('(fp_lib_table (version 7) (lib (name "atx") (type "KiCad") (uri "${KIPRJMOD}/atx.pretty") (options "") (descr "")))\n')
os.makedirs(f'{OUT}/atx.pretty', exist_ok=True)
seen = set()
for p in parts:
    if p['lib'] in seen:
        continue
    seen.add(p['lib'])
    t = fp(dict(p, nets={}))
    t = re.sub(r'\(at [-\d.]+ [-\d.]+\)\n', '\n', t, count=1)
    t = re.sub(r'\(path "[^"]*"\) \(sheetname "/"\) \(sheetfile "[^"]*"\)\n', '', t)
    t = t.replace(f'"atx:{p["lib"]}"', f'"{p["lib"]}" (version 20241229) (generator "v3atx") (generator_version "9.0")', 1)
    t = re.sub(r'\(property "Reference" "[^"]*"', '(property "Reference" "REF**"', t, count=1)
    open(f'{OUT}/atx.pretty/{p["lib"]}.kicad_mod', 'w', encoding='utf-8', newline='\n').write(t + '\n')
# JLC 2 layer capability, not the 6 layer limits mini uses
rules = dict(min_clearance=0.127, min_track_width=0.127, min_via_diameter=0.45, min_via_annular_width=0.13, min_through_hole_diameter=0.2, min_hole_to_hole=0.5, min_hole_clearance=0.25, min_copper_edge_clearance=0.2, min_silk_clearance=0, min_text_height=0.5, min_text_thickness=0.08, solder_mask_clearance=0, min_connection=0.127)
pro = {'board': {'design_settings': {'rules': rules, 'defaults': {}, 'rule_severities': {'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore', 'silk_over_copper': 'ignore', 'silk_overlap': 'ignore', 'silk_edge_clearance': 'ignore', 'courtyards_overlap': 'error', 'solder_mask_bridge': 'error', 'text_height': 'ignore', 'text_thickness': 'ignore'}}},
       'net_settings': {'classes': [{'name': 'Default', 'clearance': CLR, 'track_width': W_TRACK, 'via_diameter': VIA_D, 'via_drill': VIA_DR, 'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.2, 'diff_pair_gap': 0.2, 'wire_width': 6, 'bus_width': 12, 'line_style': 0, 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'pcb_color': 'rgba(0, 0, 0, 0.000)', 'priority': 2147483647}], 'meta': {'version': 4}},
       'meta': {'filename': f'{NAME}.kicad_pro', 'version': 3}}
json.dump(pro, open(f'{OUT}/{NAME}.kicad_pro', 'w'), indent=1)
json.dump({'parts': [{k: p[k] for k in ('ref', 'value', 'lcsc', 'lib', 'x', 'y', 'r', 'nets')} | {'bbox': bbox(p), 'side': 'F', 'dnp': False, 'consign': False} for p in parts], 'nets': real_nets, 'w': W, 'l': L, 'outline': outline, 'origin': [CX, CY], 'p1_x': P1_X, 'p1_y': P1_Y, 'holes': [dict(ref=f'H{i + 1}', pin=h[0], net=h[1]) for i, h in enumerate(HOLES)]}, open(f'{OUT}/design.json', 'w', encoding='utf-8'), indent=0)


# ---------- Specctra DSN for Freerouting
def um(v):
    return round(v * 1000)


stacks, images, places = {}, [], []
for p in parts:
    pins = []
    for q in p['abs']:
        dx, dy = q['wx'] - p['x'], -(q['wy'] - p['y'])
        thru = q['kind'] == 'thru_hole'
        key = ('T' if thru else 'S') + ('C' if q['shape'] == 'circle' else 'R') + f"{um(q['ww'])}x{um(q['wh'])}"
        stacks[key] = (thru, q['shape'] == 'circle', q['ww'], q['wh'])
        pins.append(f'(pin {key} "{q["n"]}" {um(dx)} {um(dy)})')
    images.append(f'(image IM_{p["ref"]} {" ".join(pins)})')
    places.append(f'(component IM_{p["ref"]} (place {p["ref"]} {um(p["x"])} {um(-p["y"])} front 0))')


def stack_shape(key, v):
    thru, circ, w, h = v
    ws, hs = um(w), um(h)
    if thru:
        return f'(padstack {key} (shape (circle F.Cu {ws})) (shape (circle B.Cu {ws})) (attach off))'
    return f'(padstack {key} (shape (rect F.Cu {-ws // 2} {-hs // 2} {ws // 2} {hs // 2})) (attach off))'


pad_txt = ' '.join(stack_shape(k, v) for k, v in stacks.items())
via_txt = f'(padstack Via600 (shape (circle F.Cu {um(VIA_D)})) (shape (circle B.Cu {um(VIA_D)})) (attach off))'
netlist = []
for n in real_nets:
    pins = ' '.join(f'{p["ref"]}-"{q}"' for p in parts for q, m in p['nets'].items() if m == n)
    netlist.append(f'(net {n} (pins {pins}))')
I = 0.3  # the router has no edge rule, so it gets a boundary inset by more than the 0.2 edge clearance
inset = offset_poly(outline, I)
outline_pts = ' '.join(f'{um(x)} {um(-y)}' for x, y in inset + inset[:1])
dsn = f'''(pcb {NAME}.dsn
  (parser (string_quote ") (space_in_quoted_tokens on) (host_cad "KiCad") (host_version "9"))
  (resolution um 10)
  (unit um)
  (structure
    (layer F.Cu (type signal) (property (index 0)))
    (layer B.Cu (type signal) (property (index 1)))
    (boundary (path pcb 0 {outline_pts}))
    (via Via600)
    (rule (width {um(W_TRACK)}) (clearance {um(CLR)}) (clearance {um(CLR)} (type wire_pin)) (clearance {um(CLR)} (type smd_via_same_net)))
  )
  (placement {' '.join(places)})
  (library {' '.join(images)} {pad_txt} {via_txt})
  (network {' '.join(netlist)} (class SIG {" ".join(real_nets)} (circuit (use_via Via600)) (rule (width {um(W_TRACK)}) (clearance {um(CLR)}))))
  (wiring)
)
'''
open(f'{OUT}/{NAME}.dsn', 'w', encoding='utf-8', newline='\n').write(dsn)
print('parts', len(parts), 'nets', len(real_nets), 'tracks', len(tracks), 'vias', nvia)

bad = []
for i, a in enumerate(parts):
    A = bbox(a)
    if a['lib'] != 'PIN_0.9' and (A[0] < HX0 - 0.01 or A[2] > HX1 + 0.01 or A[1] < HY0 or A[3] > HY1):
        bad.append((a['ref'], 'outside', [round(v, 2) for v in A]))
    for b in parts[i + 1:]:
        B = bbox(b)
        if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
            bad.append((a['ref'], b['ref'], round(min(A[2], B[2]) - max(A[0], B[0]), 2), round(min(A[3], B[3]) - max(A[1], B[1]), 2)))
print('placement problems', len(bad))
for b in bad:
    print(' ', b)
