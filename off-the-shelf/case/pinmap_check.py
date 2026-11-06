# -*- coding: utf-8 -*-
"""Pin map of the ATX board against the core, measured on what the factory receives: the drill file and copper Gerbers, against the official FireBeetle STEP.

A wrong pin order can put 3V3 on GND. So every plated hole has to land on the header hole that carries its net, within 0.1 mm, and on no other hole.
The net comes from the pad the factory's Gerber flashes at that hole on both copper layers, not from the generator.
The P1 order is the schematic's (SCH p1) and the drawing's silk, written out by hand here, and the positions are the STEP's holes.

check() runs on any Gerber directory, so test() runs it on the real files and on rewritten copies of those files, each of which has to fail:
a mirror across the board's width, a mirror across the pin row (the holes still fit, the board is on the wrong side), a row reversal, a 180 degree turn and two nets swapped.

usage: pinmap_check.py <firebeetle.step> <gerber dir>     import check, step_holes, test from test_handedness.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'lay-board', 'tools'))
import holecheck  # noqa: E402
import maskcheck  # noqa: E402

TOL = 0.1
# P1 from the top of the schematic's connector, the same order the drawing prints from the USB end. Pin 1 is nearest the USB end.
P1_ORDER = ['RST', '3V3', 'NC', 'GND', 'NC', '28', '29', '30', '8', '7', '48', '49', '50', '52', '4', '5', '37', '38']
# Which header pin each ATX net has to reach. Written by hand, not read from the generator. Firmware must match: atx_pwr 28, atx_rst 29, atx_led 30.
WANT = {'3V3': '3V3', 'GND': 'GND', 'ATX_PWR': '28', 'ATX_RST': '29', 'ATX_LED': '30'}
# Gerber frame is x right, y up, like the case. KiCad wrote it at board + (100, 100) with y negated. No sign change on x or y here: a mirror would need one.
OFFSET = (100.0, -100.0)


def step_holes(step):
    """Named P1 holes from the STEP board solid: 0.9 mm cylinders at x -11.43, sorted from the USB end. Checks the drawing's dimensions as well."""
    core = cq.importers.importStep(step).val()
    board = [s for s in core.Solids() if s.BoundingBox().xlen > 24 and s.BoundingBox().ylen > 55 and s.BoundingBox().zlen < 2]
    assert len(board) == 1, 'board solid not found'
    found = set()
    for f in board[0].Faces():
        if f.geomType() != 'CYLINDER':
            continue
        b = f.BoundingBox()
        if abs(b.xlen - 0.9) < 0.01 and abs(b.ylen - 0.9) < 0.01 and b.xmax < -10:
            found.add((round((b.xmin + b.xmax) / 2, 3), round((b.ymin + b.ymax) / 2, 3)))
    row = sorted(found, key=lambda q: -q[1])
    assert len(row) == len(P1_ORDER), f'{len(row)} holes in the P1 row, schematic has {len(P1_ORDER)}'
    # drawing: 43.18 from first to last, 5.21 to the antenna end, 22.86 between rows, 2.54 pitch
    assert abs(row[0][1] - row[-1][1] - 43.18) < 0.01 and abs(row[-1][1] - 5.21) < 0.01 and abs(row[0][0] * 2 + 22.86) < 0.01, 'P1 row does not match the drawing'
    assert all(abs(row[i][1] - row[i + 1][1] - 2.54) < 0.01 for i in range(17)), 'pitch is not 2.54'
    return [dict(pin=i + 1, name=P1_ORDER[i], x=row[i][0], y=row[i][1]) for i in range(18)]


def check(gerber, holes, origin):
    """Returns (ok, list of messages, table). origin is where the board's (0, 0) sits in the case."""
    msgs, table = [], []
    ly = maskcheck.Layers(gerber)
    top = [o for o in maskcheck.parse(ly.txt['cu', 'T']) if o['pad']]
    bot = [o for o in maskcheck.parse(ly.txt['cu', 'B']) if o['pad']]
    drl = [n for n in os.listdir(gerber) if n.endswith('.drl') and 'PTH' in n and 'NPTH' not in n]
    if len(drl) != 1:
        return False, [f'expected one PTH drill file, got {drl}'], table
    _, _, h = holecheck.parse_drill(open(os.path.join(gerber, drl[0]), encoding='utf-8', errors='replace').read(), drl[0])
    pth = [q for q in h if q['kind'] == 'PTH']
    if len(pth) != len(WANT):
        msgs.append(f'{len(pth)} component holes, want {len(WANT)}')
    to_case = lambda p: (p[0] - OFFSET[0] + origin[0], p[1] - OFFSET[1] + origin[1])

    def at(objs, p):
        return next((o for o in objs if abs(o['at'][0] - p[0]) < 0.02 and abs(o['at'][1] - p[1]) < 0.02), None)
    seen = set()
    for q in pth:
        a, b = at(top, q['a']), at(bot, q['a'])
        if not a or not b or a['net'] != b['net']:
            msgs.append(f"hole {q['a']}: no matching pad on both copper layers")
            continue
        net = a['net']
        x, y = to_case(q['a'])
        near = sorted(holes, key=lambda r: (r['x'] - x) ** 2 + (r['y'] - y) ** 2)[0]
        err = ((near['x'] - x) ** 2 + (near['y'] - y) ** 2) ** 0.5
        want = WANT.get(net)
        table.append(dict(ref=a['pad'][0], net=net, hole_dia=q['dia'], case=(round(x, 3), round(y, 3)), header_pin=near['pin'], header_name=near['name'], error=round(err, 4)))
        if want is None:
            msgs.append(f'{net}: not an expected net')
        elif err > TOL:
            msgs.append(f'{net} at ({x:.2f}, {y:.2f}): nearest header hole is P1-{near["pin"]} {near["name"]}, {err:.3f} mm away')
        elif near['name'] != want:
            msgs.append(f'{net} lands on P1-{near["pin"]} {near["name"]}, it must be {want}')
        else:
            seen.add(net)
    missing = set(WANT) - seen
    if missing:
        msgs.append(f'nets not on their header hole: {sorted(missing)}')
    # Fitting the holes is not enough: the optos and JST are on the top copper and must lie beyond the row toward the -X wall and the USB end.
    jst = [o for o in top if o['pad'][0] == 'J1' and o['pad'][1] in '123456']
    if not jst or not pth:
        msgs.append('JST pads or holes missing')
    else:
        jx = sum(to_case(o['at'])[0] for o in jst) / len(jst)
        jy = sum(to_case(o['at'])[1] for o in jst) / len(jst)
        hx = sum(to_case(q['a'])[0] for q in pth) / len(pth)
        hy_max = max(to_case(q['a'])[1] for q in pth)
        if not jx < hx:
            msgs.append(f'JST at x {jx:.2f} is not on the -X side of the row, x {hx:.2f}')
        if not jy > hy_max:
            msgs.append(f'JST at y {jy:.2f} is not past the row toward the USB end, y {hy_max:.2f}')
        # the parts have to be on the layer that the assembly puts facing the core
        if not re.search(r'%TF\.FileFunction,Copper,L1,Top', ly.txt['cu', 'T']):
            msgs.append('top copper is not layer 1')
    return not msgs, msgs, table


def _rewrite(src, dst, fx, fy, swap=None):
    """Writes a copy of the Gerber directory with every coordinate moved by fx, fy, or two net names exchanged. This is the file a bad generator would have written."""
    os.makedirs(dst, exist_ok=True)
    for n in os.listdir(src):
        t = open(os.path.join(src, n), encoding='utf-8', errors='replace', newline='').read()
        if n.endswith('.gbr'):
            k = 1e6 if '%FSLAX46Y46*%' in t else 1e5

            def g(m):
                x, y = int(m[1]) / k, int(m[2]) / k
                return f'X{round(fx(x) * k)}Y{round(fy(y) * k)}'
            t = re.sub(r'(?<![A-Z])X(-?\d+)Y(-?\d+)', g, t)  # not the %FSLAX46Y46% format statement
            if swap:
                a, b = swap
                t = t.replace(f'TO.N,{a}*', 'TO.N,@@*').replace(f'TO.N,{b}*', f'TO.N,{a}*').replace('TO.N,@@*', f'TO.N,{b}*')
        elif n.endswith('.drl'):
            def d(m):
                return f'X{fx(float(m[1])):.3f}Y{fy(float(m[2])):.3f}'
            t = re.sub(r'X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)', d, t)
        open(os.path.join(dst, n), 'w', encoding='utf-8', errors='replace', newline='').write(t)


def test(step, gerber, origin):
    """Returns (real_ok, real table, rows). Each row is a rewritten copy and whether the check refused it."""
    holes = step_holes(step)
    ok, msgs, table = check(gerber, holes, origin)
    # Gerber coordinates of the things a mirror is taken about
    row_gx = holes[0]['x'] - origin[0] + OFFSET[0]
    ys = [holes[i]['y'] for i in (1, 3, 5, 6, 7)]
    row_gy = (max(ys) + min(ys)) / 2 - origin[1] + OFFSET[1]
    bc = OFFSET[0]
    cases = {
        'mirror across the board width (about its origin)': (lambda x: 2 * bc - x, lambda y: y, None),
        'mirror across the pin row: holes still fit, board on the wrong side': (lambda x: 2 * row_gx - x, lambda y: y, None),
        'row reversal, 3V3 end swapped with GPIO30 end': (lambda x: x, lambda y: 2 * row_gy - y, None),
        '180 degree turn about the middle of the row': (lambda x: 2 * row_gx - x, lambda y: 2 * row_gy - y, None),
        '3V3 and GND nets swapped': (lambda x: x, lambda y: y, ('3V3', 'GND')),
        'row shifted by one pitch': (lambda x: x, lambda y: y + 2.54, None),
    }
    rows = []
    tmp = tempfile.mkdtemp(prefix='pinmap')
    try:
        for i, (name, (fx, fy, swap)) in enumerate(cases.items()):
            d = os.path.join(tmp, str(i))
            _rewrite(gerber, d, fx, fy, swap)
            bad_ok, bad_msgs, _ = check(d, holes, origin)
            rows.append(dict(name=name, refused=not bad_ok, why=bad_msgs[:2]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok, msgs, table, rows


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    origin = json.load(open(os.path.join(HERE, '..', 'atx', 'out', 'design.json'), encoding='utf-8'))['origin']
    ok, msgs, table, rows = test(sys.argv[1], sys.argv[2], origin)
    for r in table:
        print(r)
    print('REAL', 'PASS' if ok else 'FAIL', msgs)
    for r in rows:
        print('COPY', 'refused' if r['refused'] else 'WRONGLY ACCEPTED', '|', r['name'], '|', r['why'])
    sys.exit(0 if ok and all(r['refused'] for r in rows) else 1)
