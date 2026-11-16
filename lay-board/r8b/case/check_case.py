# -*- coding: utf-8 -*-
"""Judges the case files against the real board, not against the numbers that built the case.

Board facts come from kicad-cli exports of the routed .kicad_pcb, redone on every run:
  STEP: right-handed by the STEP standard, so it fixes handedness. Gives outline, screw holes, shell slots, pads and z.
  Gerber X2: every flash names its ref and pin, every object its net. Pad flashes are checked against the STEP first; the
  copper (pads, tracks, regions) with its nets is what the metal-clearance checks measure against.
Board to case is a rotation by 180 degrees about z and a lift. check_case asserts determinant +1 and does not import gen_case.
Openings and labels come from slicing the STL meshes. Bodies are tested against the STEP solids of the same case.
design.json supplies only component envelopes and body heights, and each ref's position there is checked against the real pads.

r8: tray, lid and plate are aluminium, so every case solid is metal. No metal may come within 0.3 mm (true 3-D
distance) of non-GND copper on either face or of a part body; connector shells on GND (J2 J3 J5 J7 J8) may touch.
r8b (REVIEW_r8 critical-1, major-1, major-2): the checks no longer stop at nominal sizes.
  edge   the board is pushed against each wall by the whole lateral tolerance (TOL) and the 0.3 mm rule is applied again; inner-layer
         non-GND copper must be COPPER_EDGE_MIN inside the real outline.
  z      the lid posts must not touch the PCB; the gap they leave, over board-thickness and machining tolerance, must stay inside the
         foam washer's working range. The only rigid seat is lid rim / plate / tray rim.
  radio  external antenna: an SMA bulkhead hole in the -x wall, a floor pocket that clears the jack's hex and crimp sleeve, no window.

usage: check_case.py <case_dir> [--design design.json] [--pcb x.kicad_pcb] [--report file] [--append] [--title text] [--H 23] [--floor 4.2]
exit 0 when everything passes, 1 otherwise.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import cadquery as cq
import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box as sbox
from shapely.ops import polygonize, unary_union
from shapely.prepared import prep

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('case_dir')
ap.add_argument('--design', default=os.path.join(HERE, '..', 'out', 'design.json'))
ap.add_argument('--pcb', default=os.path.join(HERE, '..', 'out', 'p4_kvm_mini.kicad_pcb'))
ap.add_argument('--report')
ap.add_argument('--append', action='store_true')
ap.add_argument('--title', default='')
ap.add_argument('--H', type=float, default=23.0)
ap.add_argument('--floor', type=float, default=4.2)
A = ap.parse_args()

KICAD = os.environ.get('KICAD_CLI', 'kicad-cli')
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=os.path.join(os.environ.get('KICAD_TOOL_HOME', os.path.expanduser('~/.kicad-tool-home')), 'doc'), KICAD_CONFIG_HOME=os.path.join(os.environ.get('KICAD_TOOL_HOME', os.path.expanduser('~/.kicad-tool-home')), 'cfg'), KICAD_CACHE_HOME=os.path.join(os.environ.get('KICAD_TOOL_HOME', os.path.expanduser('~/.kicad-tool-home')), 'cache'))

# The mechanical stack and hardware. These are requirements on the case, written here on purpose rather than read from gen_case.
S, WALL, EDGE_GAP, H, FLOOR, TOP = 42.0, 0.75, 0.25, A.H, A.floor, 1.0
half = S / 2
_B = json.load(open(A.design, encoding='utf-8'))['board']
Y0, Y1 = _B['y0'] - EDGE_GAP - WALL, _B['y1'] + EDGE_GAP + WALL
Z_BOT = FLOOR + 7.3          # HDMI J2 is 6.0 mm under the board
Z_TOP = Z_BOT + 1.2
SPLIT = Z_TOP + 4.1
PLATE_Z = (SPLIT, SPLIT + 0.8)
LID_Z0 = PLATE_Z[1]
assert abs(H - (LID_Z0 + 5.4)) < 1e-9, 'H must be FLOOR + 18.8 (the r7f stack above the floor)'
HOLES_N = 3
LCD_D, LCD_T = 39.0, 3.6
SCREW_HEAD_D, SCREW_L, SCREW_MAJOR, SCREW_SEAT = 3.8, 16.0, 2.0, 1.8
USB_SHELL, HDMI_SHELL = (8.94, 3.2), (15.0, 6.0)
# The HDMI shell's mating face is not a rectangle: the two corners on the PCB side are cut off (XunPu HDMI-001S drawing, shell 14.95 x 5.96).
# The drawing gives no dimension for the cut; it scales to about 2.2 mm. ASSUMED 1.6 mm as the smallest it could be, so a wall that clears
# this shape clears the real shell. Measure the part before the case is machined.
HDMI_SHELL_CUT = 1.6
HDMI_OPEN_TAPER = 2.0        # the opening's edge on the board side is at least this much shorter than its edge on the floor side
PLUG = {'J3': (12.0, 8.0), 'J5': (12.0, 8.0), 'J2': (19.5, 11.0)}  # worst case overmoulds, from layout.py's sources
PLUG_REACH = 1.2             # the overmould may come this close to the board edge (r7f: 0.8 mm pocket in a wall 2.0 mm past the edge)
METAL_CLEAR = 0.3            # bare or anodized metal to non-GND copper or to a part body, true 3-D distance
SHELL_GND = {'J2', 'J3', 'J5', 'J7', 'J8'}   # metal connector shells on GND: may touch the case
BOSS_SIDE, BOSS_GAP, BOSS_TOL = 5.6, 0.5, 0.05
# r8b requirements (not read from gen_case)
ANT = dict(y=-10.0, z=6.0, thread=6.35, hole=(6.4, 6.7), hex_af=8.0, hex_t=2.5, sleeve_d=5.0, sleeve_l=10.0, base_d=10.0)   # SMA bulkhead jack on a 1.13 mm pigtail: 1/4-36 UNS, 8 mm rear hex (Siretta, Linx drawings); sleeve and antenna base are ASSUMED typical sizes
TOL = dict(outline=0.2, hole_play=0.1, machining=0.05, board_t=0.10)   # JLCPCB capabilities page: outline +-0.2 mm (routed), thickness +-10 %; M2 in a 2.2 mm hole; machining ASSUMED +-0.05
SHIFT = TOL['outline'] + TOL['hole_play'] + TOL['machining']
COPPER_EDGE_MIN = 0.40       # non-GND copper to the board outline, unless it faces a wall opening (J7 pads)
SLOT_GAP = 0.9               # lid post end above the PCB top
WASHER = dict(od=3.6, id=2.2, t=1.5)
WASHER_WORK = (0.20, 0.60)   # foam compression range the washer is used in; ASSUMED from typical urethane/silicone foam data, no part number chosen
HEIGHT = {'ESP32-P4-Module': 3.31, 'USB-C_HX_16P': 3.2, 'JST_SM08B': 4.25, 'JST_SM06B': 4.25, 'HDMI-001S': 6.0, 'microSD_Molex_104031-0811': 1.42, 'BGA-64_6x6': 1.2,
          'SOT-23-5': 1.45, 'SOT-23': 1.2, 'MSOP-8': 1.1, 'OSC3225': 1.2, 'SSOP-4_1.27': 2.0, 'IND4020': 2.0, 'C0805': 1.4, 'C0603': 1.0, 'R0402': 0.6, 'USON-10': 0.6, 'TP_1.0': 0.1, 'U.FL-R-SMT-1': 2.5, 'WSON-8_2x2_EP': 0.8, 'X1SON-2_0.6x1': 0.45, 'R0201': 0.3}  # r7f: TI DSG0008A 0.8 max, DPY0002A 0.45 max. U.FL: mated plug, Hirose catalogue p4, 2.5 max with U.FL-LP-040/066; the receptacle alone is 1.25

results, lines = [], []


def say(text=''):
    print(text)
    lines.append(str(text))


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    say(f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  [{detail}]' if detail else ''))


# ---------- real board
_tmp = tempfile.TemporaryDirectory(prefix='chkcase_', ignore_cleanup_errors=True)  # removed at exit
tmp = _tmp.name
step = os.path.join(tmp, 'board.step')
for cmd in ([KICAD, 'pcb', 'export', 'step', '--force', '--no-components', '--include-pads', '-o', step, A.pcb],
            [KICAD, 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu', '-o', tmp + os.sep, A.pcb]):
    r = subprocess.run(cmd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
    assert r.returncode == 0, r.stdout + r.stderr
sha = hashlib.sha256(open(A.pcb, 'rb').read()).hexdigest()[:16]

board_step = cq.importers.importStep(step)
solids = board_step.solids().vals()
body = max(solids, key=lambda v: v.Volume())
bb = body.BoundingBox()
CX, CY = (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2
# r7c: turn about the design origin, not the outline centre (they differ once the board is not symmetric). STEP x = design x,
# STEP y = -design y, so the design origin sits at (CX - design centre x, CY + design centre y) in STEP coordinates.
CX -= (_B['x0'] + _B['x1']) / 2
CY += (_B['y0'] + _B['y1']) / 2
zs = [v.BoundingBox() for v in solids]
Z0 = min(b.zmin for b in zs)
# STEP (x, y, z) to case: a turn by 180 degrees about the board centre, then a lift so the board's underside is at Z_BOT
R = np.array([[-1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]])
assert abs(np.linalg.det(R) - 1.0) < 1e-12, 'board to case must be a proper rotation'
assert np.allclose(R @ R.T, np.eye(3)), 'board to case must be orthonormal'
T = -R @ np.array([CX, CY, 0.0]) + np.array([0, 0, Z_BOT - Z0])


def to_case(p):
    return R @ np.asarray(p, float) + T


def to_case2(g):
    """A shapely geometry in the STEP/Gerber frame, moved into the case frame (same move as to_case)."""
    return affinity.affine_transform(g, [R[0, 0], R[0, 1], R[1, 0], R[1, 1], T[0], T[1]])


pcb_case = body.rotate(cq.Vector(CX, CY, 0), cq.Vector(CX, CY, 1), 180).translate(cq.Vector(-CX, -CY, T[2]))
probe = np.array([CX + 7.0, CY - 3.0, 0.5])
assert np.allclose(to_case(probe), [-7.0, 3.0, 0.5 + T[2]]), 'to_case must be the same move as the solid'
pb = pcb_case.BoundingBox()


def parse_gerber(path):
    """Pad flashes with ref and pin, and every copper object (flash, draw, region) with its net, in the Gerber frame."""
    fs, aper, cur, pos, attr, net = 1e6, {}, None, (0.0, 0.0), None, None
    flashes, copper, region, pts = [], [], False, []
    for raw in open(path, encoding='utf-8', errors='replace'):
        s = raw.strip()
        m = re.match(r'%FSLAX(\d)(\d)Y', s)
        if m:
            fs = 10 ** int(m.group(2))
        m = re.match(r'%ADD(\d+)([A-Za-z_]\w*),?([\d.]*)(?:X([\d.]+))?', s)
        if m:
            assert m[2] in ('C', 'R', 'O'), f'aperture type {m[2]} not handled'
            aper[int(m[1])] = (m[2], float(m[3]), float(m[4] or m[3]))
            continue
        assert not s.startswith(('%AM', '%LPC', '%SR')) and not re.match(r'G0[23]\*', s), f'Gerber construct not handled: {s}'
        m = re.match(r'%TO\.P,([^,*]+),([^,*]+)', s)
        if m:
            attr = (m.group(1), m.group(2))
        m = re.match(r'%TO\.N,([^*]*)\*%', s)
        if m:
            net = m[1]
        if s.startswith('%TD'):
            attr = net = None
            continue
        if s == 'G36*':
            region, pts = True, []
            continue
        if s == 'G37*':
            if len(pts) > 2:
                copper.append((net, Polygon(pts).buffer(0)))
            region = False
            continue
        m = re.match(r'^D(\d+)\*$', s)
        if m and int(m[1]) >= 10:
            cur = int(m[1])
            continue
        m = re.match(r'(?:X(-?\d+))?(?:Y(-?\d+))?D0([123])\*', s)
        if not m or not (m[1] or m[2]):
            continue
        p = (int(m[1]) / fs if m[1] else pos[0], int(m[2]) / fs if m[2] else pos[1])
        d = int(m[3])
        if region:
            if d == 2 and len(pts) > 2:
                copper.append((net, Polygon(pts).buffer(0)))
            pts = [p] if d == 2 else pts + [p]
        elif d == 1:
            t, w, _ = aper[cur]
            assert t == 'C', 'a track drawn with a non-round aperture'
            copper.append((net, LineString([pos, p]).buffer(w / 2, 16)))
        elif d == 3:
            t, w, h = aper[cur]
            if t == 'C':
                g = Point(p).buffer(w / 2, 16)
            elif t == 'R':
                g = sbox(p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2)
            else:
                rr = min(w, h) / 2
                g = LineString([(p[0] - (w / 2 - rr), p[1] - (h / 2 - rr)), (p[0] + (w / 2 - rr), p[1] + (h / 2 - rr))]).buffer(rr, 16)
            copper.append((net, g))
            if attr:
                flashes.append((attr[0], attr[1], p[0], p[1]))
        pos = p
    return flashes, copper


def find(ext):
    return next(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(ext))


def find_layer(tag):
    hit = [os.path.join(tmp, f) for f in os.listdir(tmp) if tag in f and not f.endswith('.gbrjob')]
    assert len(hit) == 1, (tag, hit)
    return hit[0]


gb = {'F': parse_gerber(find('F_Cu.gtl')), 'B': parse_gerber(find('B_Cu.gbl'))}
flash = {k: v[0] for k, v in gb.items()}
assert flash['F'] and flash['B'], 'Gerber X2 pad attributes missing'
# Gerber frame must equal the STEP frame: every flash on F sits inside a pad solid on the top face, likewise B on the bottom
top_pads = [v.BoundingBox() for v in solids if v.BoundingBox().zmin > 0.5]
bot_pads = [v.BoundingBox() for v in solids if v.BoundingBox().zmax < 0.5]
thru = [v.BoundingBox() for v in solids if v.BoundingBox().zmin < -0.01 and v.BoundingBox().zmax > 1.0]


def inside(gx, gy, boxes, tol=0.06):
    return any(b.xmin - tol <= gx <= b.xmax + tol and b.ymin - tol <= gy <= b.ymax + tol for b in boxes)


miss = {k: [f for f in flash[k] if not inside(f[2], f[3], (top_pads if k == 'F' else bot_pads) + thru)] for k in flash}
say(f'board {os.path.basename(A.pcb)} sha256 {sha}, solids {len(solids)}, outline {bb.xlen:.2f} x {bb.ylen:.2f}, thru-plated {len(thru)}')
check('Gerber pad positions agree with STEP pad solids', not miss['F'] and not miss['B'], f"misses F {len(miss['F'])} B {len(miss['B'])}, of {len(flash['F'])} + {len(flash['B'])}")
check('board top is +z in the STEP', min(b.zmin for b in top_pads) > max(b.zmax for b in bot_pads))
COPPER = {k: [(n, to_case2(g)) for n, g in v[1]] for k, v in gb.items()}
NONGND = {k: unary_union([g for n, g in v if n != 'GND']) for k, v in COPPER.items()}
ALLCU = {k: unary_union([g for _, g in v]) for k, v in COPPER.items()}

INNER = {k: [(n, to_case2(g)) for n, g in parse_gerber(find_layer(k + '_Cu'))[1]] for k in ('In1', 'In2', 'In3', 'In4')}
# the real outline, from the bottom face of the STEP body (the corners are chamfered: the bounding box is not the edge there)
_bot = max((f_ for f_ in body.Faces() if abs(f_.Center().z - bb.zmin) < 1e-6), key=lambda f_: f_.Area())
_ow = _bot.outerWire()
assert all(e.geomType() == 'LINE' for e in _ow.Edges()), 'outline with arcs: sample it instead of reading vertices'
_pts, _edges = [], list(_ow.Edges())
_cur = _edges.pop(0)
_pts = [(_cur.startPoint().x, _cur.startPoint().y), (_cur.endPoint().x, _cur.endPoint().y)]
while _edges:
    nxt = next(e for e in _edges if min(math.hypot(e.startPoint().x - _pts[-1][0], e.startPoint().y - _pts[-1][1]), math.hypot(e.endPoint().x - _pts[-1][0], e.endPoint().y - _pts[-1][1])) < 1e-6)
    _edges.remove(nxt)
    a_, b_ = (nxt.startPoint().x, nxt.startPoint().y), (nxt.endPoint().x, nxt.endPoint().y)
    _pts.append(b_ if math.hypot(a_[0] - _pts[-1][0], a_[1] - _pts[-1][1]) < 1e-6 else a_)
OUTLINE = to_case2(Polygon(_pts).buffer(0))
assert abs(OUTLINE.area - _bot.Area()) < 0.2 * OUTLINE.area and OUTLINE.area > 1500, OUTLINE.area

pads = {}
for side, fl in flash.items():
    for ref, pin, gx, gy in fl:
        pads.setdefault(ref, []).append((pin, side, *to_case((gx, gy, 0))[:2]))
_cu = {k: prep(ALLCU[k].buffer(1e-3)) for k in ALLCU}
lost = [(ref, p[0], p[1]) for ref, lst in pads.items() for p in lst if not _cu[p[1]].contains(Point(p[2], p[3]))]
check('parsed copper holds every pad flash on its layer', not lost, f"{len(COPPER['F'])} F + {len(COPPER['B'])} B copper objects, non-GND area F {NONGND['F'].area:.0f} B {NONGND['B'].area:.0f} mm2" + (f', lost {lost[:4]}' if lost else ''))


def pin_xy(ref, want):
    q = [(p[2], p[3]) for p in pads[ref] if p[0] in want]
    assert q, (ref, want)
    return np.mean(q, axis=0)


def slots_of(ref):
    """Plated slots of a connector, from the STEP through-solids, matched to the ref by its Gerber pads."""
    out = []
    for b in thru:
        c = to_case(((b.xmin + b.xmax) / 2, (b.ymin + b.ymax) / 2, 0))[:2]
        if any(math.hypot(c[0] - p[2], c[1] - p[3]) < 0.1 for p in pads[ref]):
            out.append(c)
    return out


def mid(pts):
    a = np.array(pts)
    return (a.min(axis=0) + a.max(axis=0)) / 2


CONN = {}
for ref, n in (('J2', 4), ('J3', 4), ('J5', 4)):
    sl = slots_of(ref)
    assert len(sl) == n, (ref, len(sl))
    CONN[ref] = mid(sl)
CONN['J7'] = (pin_xy('J7', {'SH1'}) + pin_xy('J7', {'SH4'})) / 2  # the card's centreline: the official footprint's card outline is centred on these two
CONN['J4'] = mid([(p[2], p[3]) for p in pads['J4'] if p[0] in {'1', '2', '3', '4', '5', '6'}])
CONN['J6'] = mid([(p[2], p[3]) for p in pads['J6'] if p[0] in {str(i) for i in range(1, 9)}])
CONN['ANT'] = np.array([-half, ANT['y']])   # r8b: not a board part; the SMA jack sits in the -x wall
WALLS = {'-y': lambda c: c[1] - Y0, '+y': lambda c: Y1 - c[1], '-x': lambda c: c[0] + half, '+x': lambda c: half - c[0]}
EDGE = {'-y': pb.ymin, '+y': pb.ymax, '-x': pb.xmin, '+x': pb.xmax}
OUTER = {'-y': Y0, '+y': Y1, '-x': -half, '+x': half}


def nearest_wall(c):
    return min(WALLS, key=lambda w: WALLS[w](c))


holes_real = []
for e in body.Edges():
    if e.geomType() == 'CIRCLE' and e.radius() > 0.9 and abs(e.startPoint().z - bb.zmin) < 0.01:
        c = e.Center()
        cx, cy = to_case((c.x, c.y, 0))[:2]
        holes_real.append((round(float(cx), 3), round(float(cy), 3), round(2 * e.radius(), 3)))
check('three screw holes found in the board', len(holes_real) == HOLES_N, str(holes_real))
say(f"real connector centres in the case frame: {', '.join(f'{k} ({v[0]:.2f}, {v[1]:.2f}) nearest wall {nearest_wall(v)}' for k, v in CONN.items())}")
say('standing outside the I/O face (-y) +x is on your right: J3 ' + ('LEFT' if CONN['J3'][0] < 0 else 'RIGHT') + ', J2 ' + ('LEFT' if CONN['J2'][0] < 0 else 'RIGHT'))
check('real J3 is left of real J2, seen from outside the I/O face', CONN['J3'][0] < CONN['J2'][0])
SIDE = {'J3': 'F', 'J5': 'F', 'J6': 'F', 'J2': 'B', 'J7': 'B', 'J4': 'B', 'J8': 'B'}
wrong = [r for r, sd in SIDE.items() if not any(q[1] == sd for q in pads[r])]
check('connector sides as the z windows below assume', not wrong, str(wrong) if wrong else 'J3 J5 J6 top, J2 J7 J4 J8 bottom')
nogs = [r for r in SHELL_GND if not any(n == 'GND' and g.distance(Point(pin_xy(r, {q[0] for q in pads[r]}))) < 8 for k in ('F', 'B') for n, g in COPPER[k])]
check('the connectors allowed to touch metal have shell pads on GND', not nogs, ' '.join(sorted(SHELL_GND)) + (f'; no GND pad: {nogs}' if nogs else ''))


# ---------- case files
def load_stl(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:400]:
        v = np.array(re.findall(rb'vertex\s+(\S+)\s+(\S+)\s+(\S+)', data), dtype=float)
        return v.reshape(-1, 3, 3)
    n = int.from_bytes(data[80:84], 'little')
    a = np.frombuffer(data, dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n, offset=84)
    return a['v'].astype(float)


def mesh_volume(t):
    return abs(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()) / 6


PARTS = ('tray', 'lid', 'plate')
have = {k: all(os.path.exists(os.path.join(A.case_dir, f'mf_kvm_{k}.{e}')) for e in ('step', 'stl')) for k in PARTS}
have['gapfill'] = os.path.exists(os.path.join(A.case_dir, 'mf_kvm_gapfill.step'))
check('tray, lid, plate, gap filler and case_spec files exist', all(have[k] for k in ('tray', 'lid', 'plate', 'gapfill')) and os.path.exists(os.path.join(A.case_dir, 'case_spec.json')), str({k: v for k, v in have.items() if not v}))
mesh = {k: load_stl(os.path.join(A.case_dir, f'mf_kvm_{k}.stl')) for k in PARTS if have[k]}
sol = {k: cq.importers.importStep(os.path.join(A.case_dir, f'mf_kvm_{k}.step')).val() for k in PARTS if have[k]}
tray_m, lid_m, plate_m = mesh['tray'], mesh['lid'], mesh['plate']
tray_s, lid_s, plate_s = sol['tray'], sol['lid'], sol['plate']
METAL = ('tray', 'lid', 'plate')
spec = json.load(open(os.path.join(A.case_dir, 'case_spec.json'), encoding='utf-8'))
for k in mesh:
    dv = abs(mesh_volume(mesh[k]) - sol[k].Volume()) / sol[k].Volume()
    check(f'{k} STL and STEP are the same part', dv < 0.01, f'volume differs {dv * 100:.2f}%')
stray = sorted(f for f in os.listdir(A.case_dir) if f.endswith(('.step', '.stl')) and f.rsplit('.', 1)[0] not in [f'mf_kvm_{k}' for k in PARTS + ('gapfill',)])
check('no fan duct, vent, antenna insert or other stray part in the case files or case_spec', not stray and not ({'fan', 'vents', 'window', 'fpc_land'} & set(spec)), f'stray {stray}, spec keys {sorted(spec)}' if stray or {'fan', 'vents'} & set(spec) else 'tray, lid, plate, gap filler')

# ---------- envelope and walls
boxes = [sol[k].BoundingBox() for k in sol]
ex = (min(b.xmin for b in boxes), max(b.xmax for b in boxes), min(b.ymin for b in boxes), max(b.ymax for b in boxes), min(b.zmin for b in boxes), max(b.zmax for b in boxes))
mb = np.concatenate([m.reshape(-1, 3) for m in mesh.values()])
mx = (mb[:, 0].min(), mb[:, 0].max(), mb[:, 1].min(), mb[:, 1].max(), mb[:, 2].min(), mb[:, 2].max())
check(f'outside envelope is exactly {S:g} x {S:g} x {H:g} mm', abs(ex[1] - ex[0] - S) < 0.01 and abs(ex[3] - ex[2] - S) < 0.01 and abs(ex[4]) < 0.01 and abs(ex[5] - H) < 0.01
      and abs(ex[0] + half) < 0.01 and abs(ex[2] - Y0) < 0.01,
      f'STEP x {ex[0]:.3f}..{ex[1]:.3f} y {ex[2]:.3f}..{ex[3]:.3f} z {ex[4]:.3f}..{ex[5]:.3f}; STL x {mx[0]:.3f}..{mx[1]:.3f} y {mx[2]:.3f}..{mx[3]:.3f} z {mx[4]:.3f}..{mx[5]:.3f}')


def slice_mesh(tris, axis, value):
    """Section of a triangle mesh by the plane coord[axis] = value, as shapely geometry in the other two axes (order kept)."""
    keep = [i for i in range(3) if i != axis]
    d = tris[:, :, axis] - value
    mask = (d.min(axis=1) < 0) & (d.max(axis=1) > 0)
    segs = []
    for t, dd in zip(tris[mask], d[mask]):
        pts = []
        for i in range(3):
            a, b, da, db = t[i], t[(i + 1) % 3], dd[i], dd[(i + 1) % 3]
            if (da < 0) != (db < 0):
                p = a + (b - a) * (da / (da - db))
                pts.append((round(p[keep[0]], 4), round(p[keep[1]], 4)))
        if len(pts) == 2 and pts[0] != pts[1]:
            segs.append(LineString(pts))
    if not segs:
        return Polygon()
    # polygonize returns a ring with a hole and the hole's filling as separate faces; even-odd on their outlines separates solid from void
    faces = sorted((Polygon(f.exterior) for f in polygonize(unary_union(segs))), key=lambda g: -g.area)
    out = Polygon()
    for f in faces:
        out = out.symmetric_difference(f)
    return out


def geoms(g):
    return [x for x in (g.geoms if hasattr(g, 'geoms') else [g]) if not x.is_empty]


def thickness(sec, wall, u=0.0):
    """Material along the inward normal from the outer face at u, first piece only (mm)."""
    o = OUTER[wall]
    s = 1 if wall in ('-y', '-x') else -1
    a, b = o - s * 1.0, o + s * 6.0
    line = LineString([(u, a), (u, b)]) if wall in ('-y', '+y') else LineString([(a, u), (b, u)])
    segs = sorted(geoms(line.intersection(sec)), key=lambda g: Point(line.coords[0]).distance(g))
    return segs[0].length if segs else 0.0


z_tw, z_lw = FLOOR + 0.2, LID_Z0 + 0.5    # below every wall opening; below every lid label
sec_t, sec_l = slice_mesh(tray_m, 2, z_tw), slice_mesh(lid_m, 2, z_lw)
wt = {(k, w): thickness(sc, w) for k, sc in (('tray', sec_t), ('lid', sec_l)) for w in OUTER}
check(f'tray and lid walls are {WALL} mm on all four sides', all(abs(v - WALL) < 0.01 for v in wt.values()), ', '.join(f'{k} {w} {v:.3f}' for (k, w), v in wt.items()))


def wall_section(wall, depth, parts=PARTS):
    """Solid material at a given depth inside a wall, all case parts together, as (u, z): u is x on y walls, y on x walls."""
    axis = 1 if wall in ('-y', '+y') else 0
    v = OUTER[wall] + (depth if wall in ('-y', '-x') else -depth)
    return unary_union([slice_mesh(mesh[k], axis, v + 1e-5) for k in parts if k in mesh])


def wall_u(c, wall):
    return c[0] if wall in ('-y', '+y') else c[1]


THROAT = WALL - 0.3  # mid wall
sections = {w: wall_section(w, THROAT) for w in WALLS}


def stadium(u, z, w, h):
    return LineString([(u - (w - h) / 2, z), (u + (w - h) / 2, z)]).buffer(h / 2)


def hdmi_shell(u):
    """Mating face of the bottom-side HDMI shell: 15 x 6 under the board, the two corners against the board cut off."""
    w, h, c = HDMI_SHELL[0] / 2, HDMI_SHELL[1], HDMI_SHELL_CUT
    return Polygon([(u - w, Z_BOT - h), (u + w, Z_BOT - h), (u + w, Z_BOT - c), (u + w - c, Z_BOT), (u - w + c, Z_BOT), (u - w, Z_BOT - c)])


usb_z = Z_TOP + USB_SHELL[1] / 2
need = {
    'J2': ('-y', hdmi_shell(CONN['J2'][0]), f'HDMI shell 15 x 6 with {HDMI_SHELL_CUT} mm cut corners'),
    'J3': ('-y', stadium(CONN['J3'][0], usb_z, *USB_SHELL), 'USB-C shell 8.94 x 3.2'),
    'J5': ('-x', stadium(CONN['J5'][1], usb_z, *USB_SHELL), 'USB-C shell 8.94 x 3.2'),
    'J7': ('+x', sbox(CONN['J7'][1] - 5.5, Z_BOT - 1.42, CONN['J7'][1] + 5.5, Z_BOT - 0.4), 'card 11 wide at the shell'),
    'J4': ('+y', sbox(CONN['J4'][0] - 4.0, Z_BOT - 3.5, CONN['J4'][0] + 4.0, Z_BOT - 0.4), 'SHR-06V plug 8 wide'),
    'ANT': ('-x', Point(ANT['y'], ANT['z']).buffer(ANT['thread'] / 2, 32), 'SMA 1/4-36 thread'),
}
WALL_RECT = sbox(-half + 0.25, 0.05, half - 0.25, H - 0.05)   # inside the corner radius at mid-wall depth


def voids(sec):
    return [g for g in geoms(WALL_RECT.difference(sec)) if g.area > 0.05]


def hole_near(sec, shape):
    """The void piece of the wall that contains the shape's centre."""
    c = shape.centroid
    best = [g for g in voids(sec) if g.contains(c)]
    return best[0] if best else None


for ref, (wall, shape, what) in need.items():
    check(f'{ref} on the {wall} wall is the wall nearest its real position', nearest_wall(CONN[ref]) == wall, f'nearest {nearest_wall(CONN[ref])}')
    hit = shape.intersection(sections[wall]).area
    check(f'{ref} opening in {wall} wall clears the {what}', hit < 0.05, f'{hit:.2f} mm2 of wall in the way at u {wall_u(CONN[ref], wall):.2f}')
    h = hole_near(sections[wall], shape)
    if h is None:
        check(f'{ref} opening centred on the connector', False, 'no opening at the connector centre')
    else:
        x0, z0, x1, z1 = h.bounds
        off = (x0 + x1) / 2 - wall_u(CONN[ref], wall)
        check(f'{ref} opening centred on the connector', abs(off) < 0.5, f'offset {off:+.2f}, opening u {x0:.2f}..{x1:.2f} z {z0:.2f}..{z1:.2f}')
    if ref in PLUG:
        # r8: the overmould may reach PLUG_REACH past the board edge. Where the wall's outer face is closer than that, the wall face is the stop.
        w, ht = PLUG[ref]
        z = Z_BOT - HDMI_SHELL[1] / 2 if ref == 'J2' else usb_z
        u = wall_u(CONN[ref], wall)
        plug = sbox(u - w / 2, max(0.02, z - ht / 2), u + w / 2, z + ht / 2)
        past = abs(OUTER[wall] - EDGE[wall])
        if past <= PLUG_REACH:
            check(f'{ref} plug overmould {w} x {ht} reaches within {PLUG_REACH} mm of the board edge', True, f'outer face is {past:.2f} mm past the board edge, no pocket needed')
        else:
            hit = plug.intersection(wall_section(wall, past - PLUG_REACH)).area
            check(f'{ref} plug overmould {w} x {ht} reaches within {PLUG_REACH} mm of the board edge', hit < 0.05, f'{hit:.2f} mm2 in the way {past - PLUG_REACH:.2f} mm inside the outer face')
gap = abs(CONN['J2'][0] - CONN['J3'][0]) - (PLUG['J2'][0] + PLUG['J3'][0]) / 2
check('HDMI and host USB plugs fit side by side', gap > 0.3, f'{gap:.2f} mm between overmoulds')
# HDMI opening follows the receptacle's shape: narrow edge against the board, and metal stays METAL_CLEAR off the shell all round
_h = hole_near(sections['-y'], need['J2'][1])
if _h is None:
    check('HDMI opening has the receptacle shape, narrow edge on the board side', False, 'no opening at the connector centre')
else:
    _x0, _z0, _x1, _z1 = _h.bounds
    _wide = lambda z: sum(g.length for g in geoms(LineString([(_x0 - 1, z), (_x1 + 1, z)]).intersection(_h)) if g.geom_type == 'LineString')
    _board, _floor = _wide(_z1 - 0.3), _wide(_z0 + 0.3)
    check('HDMI opening has the receptacle shape, narrow edge on the board side', _floor - _board >= HDMI_OPEN_TAPER,
          f'{_board:.2f} mm wide 0.3 below its board-side edge, {_floor:.2f} mm wide 0.3 above its floor-side edge, need {HDMI_OPEN_TAPER} less on the board side')
    _near = need['J2'][1].buffer(METAL_CLEAR).intersection(sections['-y']).area
    check(f'HDMI opening keeps {METAL_CLEAR} mm round the shell (cut corners taken as {HDMI_SHELL_CUT} mm)', _near < 0.05, f'{_near:.2f} mm2 of wall within {METAL_CLEAR} mm of the shell')

# sealed: every void through a wall is one of the named openings
for wall in WALLS:
    named = [r for r, (w, _, _) in need.items() if w == wall]
    vs = voids(sections[wall])
    odd = [tuple(round(c, 1) for c in g.bounds) for g in vs if not any(g.contains(need[r][1].centroid) for r in named)]
    check(f'{wall} wall is sealed: its only openings are {", ".join(named)}', not odd and len(vs) == len(named), f'{len(vs)} opening(s); unnamed at {odd}' if odd or len(vs) != len(named) else f'{len(vs)} opening(s)')


# ---------- labels: a cut shows as a void at label depth that is not a void deeper in the wall
def label_islands(wall):
    shallow = wall_section(wall, 0.15)
    deep = wall_section(wall, 0.6)  # below the 0.3 mm text, inside the 0.75 mm wall
    extra = deep.difference(shallow).buffer(0.1)
    return [g for g in geoms(extra) if g.area > 0.1]


LABEL = {'HDMI': ('-y', 'J2', 4.0, 8.5), 'MF KVM': ('-y', 'J2', 11.0, 17.5), 'HOST': ('-y', 'J3', 4.0, 8.0), '5V': ('-x', 'J5', 1.8, 4.5), 'TF': ('+x', 'J7', 1.5, 4.0), 'ATX': ('+y', 'J4', 3.5, 6.5), 'ANT': ('-x', 'ANT', 3.5, 6.5)}
ZLAB = {'HDMI': Z_BOT + 2.8, 'MF KVM': Z_BOT + 8.8, 'HOST': Z_BOT + 8.8, '5V': Z_BOT + 8.8, 'TF': Z_BOT + 2.8, 'ATX': Z_BOT + 2.8, 'ANT': Z_BOT + 2.8}
isl = {w: label_islands(w) for w in WALLS}
for name, (wall, ref, wmin, wmax) in LABEL.items():
    u = wall_u(CONN[ref], wall)
    group = [g for g in isl[wall] if abs(g.centroid.y - ZLAB[name]) < 1.25 and abs(g.centroid.x - u) < wmax / 2 + 1.5]   # r8b: was 9 for every label; ANT sits 7.6 mm from the J5 slot's end
    if group:
        x0 = min(g.bounds[0] for g in group)
        x1 = max(g.bounds[2] for g in group)
        ok = wmin <= x1 - x0 <= wmax and abs((x0 + x1) / 2 - u) < 2.5
        check(f'label {name} is cut in the {wall} wall beside {ref}', ok, f'text u {x0:.1f}..{x1:.1f} z {min(g.bounds[1] for g in group):.1f}..{max(g.bounds[3] for g in group):.1f}, connector u {u:.2f}')
    else:
        check(f'label {name} is cut in the {wall} wall beside {ref}', False, 'no cut there')

# ---------- lid top and floor sealed
top_sec = slice_mesh(lid_m, 2, H - TOP / 2)
top_holes = [Polygon(r) for g in geoms(top_sec) for r in g.interiors]
win_a = math.pi * ((LCD_D - 5.6) / 2) ** 2
check('lid top is sealed: the LCD window is its only opening', len(top_holes) == 1 and abs(top_holes[0].area - win_a) < 0.01 * win_a and top_holes[0].centroid.distance(Point(0, 0)) < 0.05,
      f'{len(top_holes)} opening(s), areas {[round(h_.area, 1) for h_ in top_holes]}, window {win_a:.1f} mm2')
for zf in (0.5, 0.9):   # r8b: 0.9 is just under the SMA pocket's floor (1.0); the old FLOOR / 2 cut would run through the pocket
    fl_sec = slice_mesh(tray_m, 2, zf)
    fl_holes = [Polygon(r) for g in geoms(fl_sec) for r in g.interiors]
    check(f'floor is sealed at z {zf}: its only openings are the three screw recesses', len(fl_holes) == HOLES_N and all(min(math.hypot(h_.centroid.x - x, h_.centroid.y - y) for x, y, _ in holes_real) < 0.1 for h_ in fl_holes),
          f'{len(fl_holes)} opening(s)')

# ---------- screws and posts
tip = SCREW_SEAT + SCREW_L


def holes_at(tris, z):
    sec = slice_mesh(tris, 2, z)
    return [Polygon(r) for g in geoms(sec) for r in g.interiors], sec


def bore_at(tris, x, y, z):
    """Diameter of the round void around (x, y) at height z, or None when that spot is solid or not enclosed."""
    holes, sec = holes_at(tris, z)
    for h in holes:
        if h.contains(Point(x, y)) and h.area < 40:
            return 2 * math.sqrt(h.area / math.pi), math.hypot(h.centroid.x - x, h.centroid.y - y), sec
    return None, None, sec


def wall_outside(sec, x, y, bore):
    """Thinnest metal around a bore: distance to the nearest edge of the section other than the bore itself."""
    c, best = Point(x, y), 9.0
    for g in geoms(sec):
        best = min(best, c.distance(g.exterior))
        for r in g.interiors:
            if not Polygon(r).contains(c):
                best = min(best, c.distance(r))
    return best - bore / 2


RING_OD = 2.9                          # plated GND ring of the mounting holes (checked against the board below)
seat_ring = lambda x, y: Point(x, y).buffer(RING_OD / 2).difference(Point(x, y).buffer(SCREW_MAJOR / 2 + 0.2))
t_below, t_above = slice_mesh(tray_m, 2, Z_BOT - 0.03), slice_mesh(tray_m, 2, Z_BOT + 0.03)
l_above, l_below = slice_mesh(lid_m, 2, Z_TOP + 0.03), slice_mesh(lid_m, 2, Z_TOP - 0.03)
l_end_in, l_end_out = slice_mesh(lid_m, 2, Z_TOP + SLOT_GAP + 0.03), slice_mesh(lid_m, 2, Z_TOP + SLOT_GAP - 0.03)   # r8b: the lid post ends here
for x, y, d in holes_real:
    tag = f'({x:.0f}, {y:.0f})'
    v, off, _ = bore_at(tray_m, x, y, FLOOR + 2.8)
    check(f'tray clearance bore at {tag} lines up', v is not None and off < 0.1 and v >= SCREW_MAJOR + 0.2, f'd {v and round(v, 2)}, offset {off and round(off, 2)}')
    v, off, _ = bore_at(tray_m, x, y, 1.0)
    check(f'tray head recess at {tag} takes the M2 head', v is not None and off < 0.1 and v >= SCREW_HEAD_D, f'd {v and round(v, 2)}')
    # r8: the seat is the copper GND ring outside the screw clearance (r7f: 80 % of a 1.1..2.2 mm annulus, written for a 4.4 mm plastic post)
    seat = seat_ring(x, y)
    check(f'tray post at {tag} seats the PCB at z {Z_BOT:.1f} on its GND ring', seat.intersection(t_below).area > 0.95 * seat.area and seat.intersection(t_above).area < 0.01, f'{seat.intersection(t_below).area:.2f} of {seat.area:.2f} mm2')
    ztest = Z_TOP + 6.3
    v, off, sec = bore_at(lid_m, x, y, ztest)
    t = wall_outside(sec, x, y, v) if v else 0
    check(f'lid pilot at {tag} lines up at z {ztest:.1f}', v is not None and off < 0.1 and 1.4 <= v <= 1.8 and t >= 0.8, f'd {v and round(v, 2)}, wall {t:.2f}')
    for zz in (Z_TOP + SLOT_GAP + 0.2, Z_TOP + 2.0):
        v, off, sec = bore_at(lid_m, x, y, zz)
        t = wall_outside(sec, x, y, v) if v else 0
        check(f'lid post at {tag} is whole at z {zz:.1f}', v is not None and off < 0.1 and t >= 0.75, f'd {v and round(v, 2)}, wall {t:.2f}')
    w_seat = Point(x, y).buffer(3.2 / 2).difference(Point(x, y).buffer(WASHER['id'] / 2))   # the post end the washer bears on
    near = Point(x, y).buffer(3.0)
    check(f'lid post at {tag} ends {SLOT_GAP} mm above the PCB and gives the washer a seat', w_seat.intersection(l_end_in).area > 0.95 * w_seat.area and near.intersection(l_end_out).area < 0.01,
          f'{w_seat.intersection(l_end_in).area:.2f} of {w_seat.area:.2f} mm2 at z {Z_TOP + SLOT_GAP + 0.03:.2f}, {near.intersection(l_end_out).area:.2f} mm2 below it')
top_of_pilot = H - TOP - 0.6
check('M2 x 16 tip stops inside the pilot', tip < top_of_pilot, f'seat z {SCREW_SEAT}, tip z {tip}, pilot top z {top_of_pilot:.1f}')
check('thread engagement in every lid post is at least 1.5 x d', tip - Z_TOP >= 1.5 * SCREW_MAJOR, f'{tip - Z_TOP:.1f} mm from the PCB top to the tip')
# the board outline, a little inside, catches every case contact with the PCB faces
board2 = sbox(pb.xmin, pb.ymin, pb.xmax, pb.ymax).buffer(-0.1)
pieces = geoms(t_below.intersection(board2))
far = [tuple(round(c, 1) for c in g.centroid.coords[0]) for g in pieces if min(math.hypot(g.centroid.x - x, g.centroid.y - y) for x, y, _ in holes_real) > 0.5]
check('the tray touches the PCB only at the three screw holes', len(pieces) == HOLES_N and not far, f'{len(pieces)} contact patch(es)' + (f', away from a hole at {far}' if far else ''))
pieces = geoms(l_above.intersection(board2))
check('the lid does not touch the PCB anywhere (one rigid seat: the rim)', not pieces, f'{len(pieces)} contact patch(es) at ' + str([tuple(round(c, 1) for c in g.centroid.coords[0]) for g in pieces][:4]) if pieces else 'none')


# ---------- bodies against the solids
def bx(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def vol(a, b):
    try:
        return a.intersect(b).Volume()
    except Exception:
        return 0.0


USB_ALONG = {'J3': 'y', 'J5': 'x'}
D = json.load(open(A.design, encoding='utf-8'))
fails, moved, BODY, ENV2 = [], [], {}, {}
for p in D['parts']:
    x0d, y0d, x1d, y1d = p['bbox']
    if p['ref'] == 'U1':
        x0d, y0d, x1d, y1d = p['x'] - 12.6, p['y'] - 12.6, p['x'] + 12.6, p['y'] + 12.6
    if p['ref'] == 'J2':
        x0d, y0d, x1d, y1d = p['x'] - 7.6, -20.7, p['x'] + 7.6, -8.0
    # design to case for the envelope only. It must hold every real pad of the ref, or the envelope is checked in the wrong place.
    x0, x1, y0, y1 = -x1d, -x0d, y0d, y1d
    ENV2[p['ref']] = sbox(x0, y0, x1, y1)
    if p['ref'] in pads:
        out = [q[0] for q in pads[p['ref']] if not (x0 - 0.6 <= q[2] <= x1 + 0.6 and y0 - 0.6 <= q[3] <= y1 + 0.6)]
        if out:
            moved.append((p['ref'], out[:3]))
    h = HEIGHT[p['lib']]
    z0, z1 = (Z_TOP, Z_TOP + h) if p['side'] == 'F' else (Z_BOT - h, Z_BOT)
    if p['ref'] in USB_ALONG:   # r8: the USB-C shell is a stadium tube along its mating axis (r7f: a box, with 0.25 mm3 allowed for its corners)
        prof = cq.Workplane('XZ' if USB_ALONG[p['ref']] == 'y' else 'YZ').slot2D(USB_SHELL[0], USB_SHELL[1])
        if USB_ALONG[p['ref']] == 'y':
            b = prof.extrude(y1 - y0 - 0.2).translate((CONN[p['ref']][0], y1 - 0.1, usb_z)).val()
        else:
            b = prof.extrude(x1 - x0 - 0.2).translate((x0 + 0.1, CONN[p['ref']][1], usb_z)).val()
        assert abs(b.BoundingBox().zmax - Z_TOP - USB_SHELL[1]) < 1e-6
    elif p['ref'] == 'J2':      # the HDMI shell is a tube of its mating-face outline along y: the two corners against the board are cut (HDMI_SHELL_CUT)
        w, c = (x1 - x0) / 2 - 0.1, HDMI_SHELL_CUT
        prof = cq.Workplane('XZ').polyline([(-w, z0), (w, z0), (w, z1 - c), (w - c, z1), (-w + c, z1), (-w, z1 - c)]).close()
        b = prof.extrude(y1 - y0 - 0.2).translate(((x0 + x1) / 2, y1 - 0.1, 0)).val()
        assert abs(b.BoundingBox().zmax - Z_BOT) < 1e-6 and abs(b.BoundingBox().ymin - (y0 + 0.1)) < 1e-6
    else:
        b = bx(x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, z0, z1)
    BODY[p['ref']] = b
    vt, vl = vol(tray_s, b), vol(lid_s, b)
    if vt > 0.01 or vl > 0.01:
        fails.append((p['ref'], round(vt, 2), round(vl, 2)))
check('every part envelope holds its real pads after the design-to-case map', not moved, str(moved[:5]) if moved else f"{len(D['parts'])} parts")
check('no part body touches the tray or lid', not fails, str(fails[:12]) if fails else 'none')

# ---------- r8: metal clearance. Distances are true 3-D: OCC for part bodies; for copper, sections every 0.025 mm through
# the 0.3 mm shell on both sides of each copper face, each held to the horizontal distance the sphere leaves at that height.
weak = []
for k in METAL:
    near = sorted(((sol[k].distance(BODY[r]), r) for r in BODY if r not in SHELL_GND), key=lambda t: t[0])
    weak.append((f'{k} to part body {near[0][1]}', near[0][0]))
    check(f'no {k} metal within {METAL_CLEAR} mm of a part body (GND connector shells excepted)', near[0][0] >= METAL_CLEAR - 1e-6,
          ', '.join(f'{r} {d_:.3f}' for d_, r in near[:4]))
DZ = [0.0049 + 0.025 * i for i in range(12)]
for k in METAL:
    worst = (9.0, None)
    for side, plane in (('B', Z_BOT), ('F', Z_TOP)):
        cu = NONGND[side]
        for dz in DZ:
            for zz in (plane - dz, plane + dz):
                sec = slice_mesh(mesh[k], 2, zz)
                if sec.is_empty:
                    continue
                d3 = math.hypot(sec.distance(cu), dz)
                if d3 < worst[0]:
                    worst = (d3, f'{side}.Cu at z {zz:.3f}')
    weak.append((f'{k} to non-GND copper ({worst[1]})', worst[0]))
    check(f'no {k} metal within {METAL_CLEAR} mm of non-GND copper on either face', worst[0] >= METAL_CLEAR - 1e-6, f'nearest {worst[0]:.3f} mm, {worst[1]}' if worst[1] else 'no section of it within 0.3 mm of either copper face')

vt = {k: vol(sol[k], pcb_case) for k in sol}
check('real PCB solid (outline, holes, slots) against every case part', all(v < 0.01 for v in vt.values()), ', '.join(f'{k} {v:.3f}' for k, v in vt.items()) + ' mm3')
check('PCB z in the case is the stack height', abs(pb.zmin - Z_BOT) < 0.06 and abs(pb.zmax - Z_TOP) < 0.12, f'{pb.zmin:.2f}..{pb.zmax:.2f}')
pairs = [(a, b) for i, a in enumerate(sol) for b in list(sol)[i + 1:]]
vp = {(a, b): vol(sol[a], sol[b]) for a, b in pairs}
check('case parts do not overlap each other', all(v < 0.01 for v in vp.values()), ', '.join(f'{a}/{b} {v:.3f}' for (a, b), v in vp.items()))
edge_gap = min(pb.xmin + half - WALL, half - WALL - pb.xmax, pb.ymin - Y0 - WALL, Y1 - WALL - pb.ymax)
check(f'board to wall gap is {EDGE_GAP} mm per side', abs(edge_gap - EDGE_GAP) < 0.02, f'{edge_gap:.3f} mm')
lcd = cq.Solid.makeCylinder(LCD_D / 2, LCD_T, cq.Vector(0, 0, H - TOP - LCD_T))
vlcd = {k: vol(sol[k], lcd) for k in sol}
check('LCD module (estimate) against every case part', all(v < 0.01 for v in vlcd.values()), ', '.join(f'{k} {v:.3f}' for k, v in vlcd.items()) + ' mm3')
lcd_bottom = H - TOP - LCD_T
top_max = max(Z_TOP + HEIGHT[p['lib']] for p in D['parts'] if p['side'] == 'F')
check('LCD clears the tallest top-side part', lcd_bottom >= top_max, f'LCD bottom {lcd_bottom:.2f}, tallest top {top_max:.2f}')
seat_z = H - TOP - 0.6
sec_seat = slice_mesh(lid_m, 2, seat_z)
rim = {w: thickness(sec_seat, w) for w in OUTER}
check(f'LCD seat ({LCD_D + 0.5:g} mm bore) inside the {S:g} mm lid leaves at least the wall at the four tangent points', all(v >= WALL - 0.01 for v in rim.values()),
      ', '.join(f'{w} {v:.2f}' for w, v in rim.items()) + f' mm metal at z {seat_z:.1f}; LCD edge to outer face {half - LCD_D / 2:.2f} mm')

# J6 mates toward the wall nearest it; its plug and wires need that gap. Sign taken from the real pads: the contact row is behind the mounting tabs.
row = mid([(q[2], q[3]) for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}])
tabs = mid([(q[2], q[3]) for q in pads['J6'] if q[0] in {'9', '10'}])
d6 = np.sign(tabs[0] - row[0])
face = tabs[0] + d6 * 1.2
plug_u = (min(q[3] for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}) - 1.0, max(q[3] for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}) + 1.0)
xa, xb = sorted((face, face + d6 * 2.7))
pk = bx(xa, xb, plug_u[0], plug_u[1], Z_TOP, Z_TOP + 2.9)
say(f'J6 mouth faces {"-x" if d6 < 0 else "+x"}, plug and wire keep-out x {xa:.2f}..{xb:.2f} y {plug_u[0]:.2f}..{plug_u[1]:.2f} z {Z_TOP:.1f}..{Z_TOP + 2.9:.1f}')
vj = {k: vol(sol[k], pk) for k in METAL}
check('J6 plug and wires clear the tray, lid and plate', all(v < 0.01 for v in vj.values()), ', '.join(f'{k} {v:.2f}' for k, v in vj.items()) + ' mm3')
# r8: every shank against every part envelope (r7f checked only J6, the part beside its corner screw)
shank = sorted((ENV2[r].distance(Point(x, y)) - SCREW_MAJOR / 2, r, (x, y)) for r in ENV2 for x, y, _ in holes_real)
weak.append((f'M2 shank to {shank[0][1]} envelope', shank[0][0]))
check('every M2 shank clears every part envelope', shank[0][0] > 0.2, ', '.join(f'{r} {d_:.2f} at ({h_[0]:.0f}, {h_[1]:.0f})' for d_, r, h_ in shank[:3]))

# ---------- r8: boss under U7 for a 0.5 mm gap pad
u7 = np.mean([(q[2], q[3]) for q in pads['U7']], axis=0)
u7_h = HEIGHT[next(p['lib'] for p in D['parts'] if p['ref'] == 'U7')]
col = vol(tray_s, bx(u7[0] - 6, u7[0] + 6, u7[1] - 6, u7[1] + 6, FLOOR + 0.05, Z_BOT))
bs = tray_s.intersect(bx(u7[0] - 6, u7[0] + 6, u7[1] - 6, u7[1] + 6, FLOOR + 0.05, Z_BOT)) if col > 0 else None
if bs is None:
    check('tray boss under U7 is 5.6 x 5.6, centred on the real U7 pads', False, 'no boss')
    check(f'boss leaves {BOSS_GAP} +- {BOSS_TOL} mm under the U7 package', False, 'no boss')
else:
    b_ = bs.BoundingBox()
    off = math.hypot((b_.xmin + b_.xmax) / 2 - u7[0], (b_.ymin + b_.ymax) / 2 - u7[1])
    check('tray boss under U7 is 5.6 x 5.6, centred on the real U7 pads', abs(b_.xlen - BOSS_SIDE) < 0.05 and abs(b_.ylen - BOSS_SIDE) < 0.05 and off < 0.2
          and abs(bs.Volume() - b_.xlen * b_.ylen * b_.zlen) < 0.01 * bs.Volume(), f'{b_.xlen:.2f} x {b_.ylen:.2f}, centre offset {off:.2f} from U7 at ({u7[0]:.2f}, {u7[1]:.2f})')
    g_ = (Z_BOT - u7_h) - b_.zmax
    check(f'boss leaves {BOSS_GAP} +- {BOSS_TOL} mm under the U7 package', abs(g_ - BOSS_GAP) <= BOSS_TOL + 1e-6, f'boss top z {b_.zmax:.3f}, package face z {Z_BOT - u7_h:.3f}, gap {g_:.3f}')

# ---------- r8b: external antenna. SMA bulkhead jack in the -x wall, its body in a floor pocket under the board
h_ant = hole_near(sections['-x'], need['ANT'][1])
if h_ant is None:
    check('SMA hole in the -x wall is round, 6.4 to 6.7 mm, at the required place', False, 'no hole')
else:
    d_ant = 2 * math.sqrt(h_ant.area / math.pi)
    a0, z0_, a1, z1_ = h_ant.bounds
    roundness = abs((a1 - a0) - (z1_ - z0_))
    check('SMA hole in the -x wall is round, 6.4 to 6.7 mm, at the required place', ANT['hole'][0] <= d_ant <= ANT['hole'][1] and roundness < 0.05 and abs((a0 + a1) / 2 - ANT['y']) < 0.1 and abs((z0_ + z1_) / 2 - ANT['z']) < 0.1,
          f'd {d_ant:.2f}, centre y {(a0 + a1) / 2:.2f} z {(z0_ + z1_) / 2:.2f}')
hex_ac = ANT['hex_af'] / math.cos(math.radians(30))
xin = -half + WALL
SEAT = 0.21   # the hex bears on the wall's inner face; the keep-out starts just off it so that the distance below is to the pocket, not to that seat
sma_hex = cq.Solid.makeCylinder(hex_ac / 2, ANT['hex_t'] - SEAT, cq.Vector(xin + SEAT, ANT['y'], ANT['z']), cq.Vector(1, 0, 0))   # any rotation of the hex
sma_slv = cq.Solid.makeCylinder(ANT['sleeve_d'] / 2, ANT['sleeve_l'], cq.Vector(xin + ANT['hex_t'], ANT['y'], ANT['z']), cq.Vector(1, 0, 0))
d_tray = min(tray_s.distance(sma_hex), tray_s.distance(sma_slv))
d_pcb = min(pcb_case.distance(sma_hex), pcb_case.distance(sma_slv))
d_body = sorted((min(BODY[r].distance(sma_hex), BODY[r].distance(sma_slv)), r) for r in BODY)
weak += [('SMA jack to tray pocket', d_tray), ('SMA jack to PCB', d_pcb), (f'SMA jack to part body {d_body[0][1]}', d_body[0][0])]
check(f'floor pocket clears the SMA hex ({hex_ac:.2f} across corners, any rotation) and crimp sleeve by 0.2 mm', vol(tray_s, sma_hex) < 0.01 and vol(tray_s, sma_slv) < 0.01 and d_tray >= 0.2, f'nearest tray metal {d_tray:.2f} mm')
check(f'SMA jack and sleeve clear the PCB and every part body by {METAL_CLEAR} mm', d_pcb >= METAL_CLEAR and d_body[0][0] >= METAL_CLEAR, f'PCB {d_pcb:.2f}, ' + ', '.join(f'{r} {d_:.2f}' for d_, r in d_body[:3]))
nut_low = ANT['z'] - hex_ac / 2
base_gap = (CONN['J5'][1] - PLUG['J5'][0] / 2) - (ANT['y'] + ANT['base_d'] / 2)
check('outside: the SMA nut clears the desk and a 10 mm antenna base clears the J5 plug overmould', nut_low >= 0.5 and ANT['z'] - ANT['base_d'] / 2 >= 0.5 and base_gap >= 1.0,
      f'nut corner {nut_low:.2f} mm above the desk, base to J5 overmould {base_gap:.2f} mm')
m_pig = spec['materials'].get('pigtail', '')
check('case_spec names the U.FL to SMA bulkhead pigtail and has no antenna window', 'U.FL' in m_pig and 'SMA bulkhead' in m_pig and 'antenna' in spec and 'window' not in spec, m_pig or 'no pigtail entry')
check('J8 (U.FL) is on the board for the pigtail', 'J8' in pads and any(n == 'LNA_OUT' for n, g in COPPER['B'] if g.distance(Point(pin_xy('J8', {q[0] for q in pads['J8']}))) < 2.5), 'J8 pads ' + str(sorted({q[0] for q in pads.get('J8', [])})))

# ---------- r8b: lateral tolerance. The board pushed against a wall by the whole stack, then the 0.3 mm rule again; inner layers by the outline.
cav = 2 * (half - WALL)
fit = (cav - 2 * TOL['machining']) - (max(pb.xlen, pb.ylen) + TOL['outline'])
check('the largest board still drops into the smallest cavity', fit >= 0.1, f'cavity {cav:.2f} - {2 * TOL["machining"]:.2f}, board {max(pb.xlen, pb.ylen):.2f} + {TOL["outline"]:.2f}: {fit:.2f} mm to spare')
band = sbox(-half, Y0, half, Y1).difference(sbox(-half + WALL + 0.01, Y0 + WALL + 0.01, half - WALL - 0.01, Y1 - WALL - 0.01))
worst = (9.0, None)
for side, plane in (('B', Z_BOT), ('F', Z_TOP)):
    cu = NONGND[side]
    moved_cu = [(nm, affinity.translate(cu, dx, dy)) for nm, dx, dy in (('+x', SHIFT, 0), ('-x', -SHIFT, 0), ('+y', 0, SHIFT), ('-y', 0, -SHIFT))]
    for dz in DZ:
        for zz in (plane - dz, plane + dz):
            sec = slice_mesh(tray_m, 2, zz).intersection(band)
            if sec.is_empty:
                continue
            for nm, g in moved_cu:
                d3 = math.hypot(sec.distance(g), dz)
                if d3 < worst[0]:
                    worst = (d3, f'{side}.Cu pushed to the {nm} wall, z {zz:.3f}')
weak.append((f'wall to non-GND copper after {SHIFT:.2f} mm push ({worst[1]})', worst[0]))
check(f'with the board pushed {SHIFT:.2f} mm against any wall no wall metal is within {METAL_CLEAR} mm of non-GND copper (outline +-{TOL["outline"]}, hole play {TOL["hole_play"]}, machining {TOL["machining"]})',
      worst[0] >= METAL_CLEAR - 1e-6, f'nearest {worst[0]:.3f} mm, {worst[1]}')
edge_line = OUTLINE.exterior
inner_bad = sorted((round(edge_line.distance(g), 3), k, n) for k, v in INNER.items() for n, g in v if n != 'GND' and edge_line.distance(g) < COPPER_EDGE_MIN - 1e-6)
inner_min = min((edge_line.distance(g), k, n) for k, v in INNER.items() for n, g in v if n != 'GND')
check(f'inner-layer non-GND copper is {COPPER_EDGE_MIN} mm or more inside the real outline', not inner_bad, str(inner_bad[:4]) if inner_bad else f'nearest {inner_min[0]:.3f} mm ({inner_min[2]} on {inner_min[1]})')
outer_near = sorted((round(edge_line.distance(g), 3), k, n) for k in ('F', 'B') for n, g in COPPER[k] if n != 'GND' and edge_line.distance(g) < COPPER_EDGE_MIN - 1e-6)
say(f'outer-layer non-GND copper nearer than {COPPER_EDGE_MIN} mm to the outline (allowed only where the push check above passes, i.e. facing an opening): ' + (', '.join(f'{n} {k}.Cu {d_:.3f}' for d_, k, n in outer_near) or 'none'))
check('tray is anodized inside as well (the wall faces the board edge)', 'inside' in spec['materials']['tray'] and 'anodized all over' in spec['materials']['tray'], spec['materials']['tray'])
pn = spec.get('panel', '')
check('case_spec carries the panel rule (no V-cut, nothing proud of the outline)', 'no V-cut' in pn and 'proud' in pn, pn or 'missing')

# ---------- r8b: z stack over tolerance. One rigid seat (rim / plate / rim, checked below); the board is held by foam washers.
gap_nom = lid_s.BoundingBox().zmin - Z_TOP
dz_tol = (Z_TOP - Z_BOT) * TOL['board_t'] + 2 * TOL['machining']
g_lo, g_hi = gap_nom - dz_tol, gap_nom + dz_tol
w_lo, w_hi = WASHER['t'] * (1 - WASHER_WORK[1]), WASHER['t'] * (1 - WASHER_WORK[0])
check(f'lid posts leave {SLOT_GAP} mm over the PCB', abs(gap_nom - SLOT_GAP) < 0.02, f'lowest lid metal z {lid_s.BoundingBox().zmin:.3f}, PCB top {Z_TOP:.3f}')
check(f'over tolerance the gap stays inside the {WASHER["t"]} mm foam washer\'s working range and never closes', g_lo > 0 and g_lo >= w_lo - 1e-9 and g_hi <= w_hi + 1e-9,
      f'gap {g_lo:.2f}..{g_hi:.2f} mm (board +-{TOL["board_t"] * 100:.0f} %, two machined faces +-{TOL["machining"]}), washer works at {w_lo:.2f}..{w_hi:.2f} mm')
cw = spec.get('compliant', {}).get('washer', {})
check('case_spec names the same foam washer', cw == WASHER and 'foam' in spec['materials'].get('washer', ''), f"{cw}; {spec['materials'].get('washer', 'no washer entry')}")
wd = []
for x, y, _ in holes_real:
    ws_ = cq.Solid.makeCylinder(WASHER['od'] / 2, gap_nom, cq.Vector(x, y, Z_TOP))
    wd += [(BODY[r].distance(ws_), r, (x, y)) for r in BODY if next(p_['side'] for p_ in D['parts'] if p_['ref'] == r) == 'F']
wd.sort(key=lambda t: t[0])
weak.append((f'foam washer to part body {wd[0][1]}', wd[0][0]))
check(f'a {WASHER["od"]} mm washer on each screw clears every top-side part body by 0.1 mm', wd[0][0] >= 0.1, ', '.join(f'{r} {d_:.2f} at ({h_[0]:.0f}, {h_[1]:.0f})' for d_, r, h_ in wd[:3]))

# ---------- r7f: THERMAL_REPORT 6.5 configuration f1 (metal lid, spreader plate, gap filler, grounding); r8 adds the metal tray.
PADS_REQ = {'P4': 12.0, 'C6': 7.0}         # gap filler squares (mm), over the P4 and the C6
gap_s = cq.importers.importStep(os.path.join(A.case_dir, 'mf_kvm_gapfill.step')).val()
pbb = plate_s.BoundingBox()
check(f'plate is 0.8 mm Al at z {PLATE_Z[0]:.1f}..{PLATE_Z[1]:.1f}', abs(pbb.zmin - PLATE_Z[0]) < 0.02 and abs(pbb.zmax - PLATE_Z[1]) < 0.02 and 'Al' in spec['materials']['plate'], f'z {pbb.zmin:.2f}..{pbb.zmax:.2f}, {spec["materials"]["plate"]}')
check('plate spans the case outline (edge clamped between the halves)', pbb.xlen > S - 0.5 and pbb.ylen > (Y1 - Y0) - 0.5, f'{pbb.xlen:.2f} x {pbb.ylen:.2f}')
hit = []
for p in D['parts']:
    if p['side'] == 'F':
        x0d, y0d, x1d, y1d = (p['x'] - 12.6, p['y'] - 12.6, p['x'] + 12.6, p['y'] + 12.6) if p['ref'] == 'U1' else p['bbox']
        v_ = vol(plate_s, bx(-x1d + 0.1, -x0d - 0.1, y0d + 0.1, y1d - 0.1, Z_TOP, Z_TOP + HEIGHT[p['lib']]))
        if v_ > 0.01:
            hit.append((p['ref'], round(v_, 2)))
check('plate clears every top-side part (J6 through its cut-out)', not hit, str(hit[:6]) if hit else f'tallest under the plate {max(Z_TOP + HEIGHT[p["lib"]] for p in D["parts"] if p["side"] == "F" and p["ref"] != "J6"):.2f}, plate bottom {pbb.zmin:.2f}')
gap_lcd = (H - TOP - LCD_T) - pbb.zmax
check('plate clears the LCD (estimate) by 0.5 mm or more', vlcd['plate'] < 0.01 and gap_lcd >= 0.5, f'{gap_lcd:.2f} mm')
gb_ = list(gap_s.Solids())
want = unary_union([sbox(-spec['pads'][k][0] - PADS_REQ[k] / 2, spec['pads'][k][1] - PADS_REQ[k] / 2, -spec['pads'][k][0] + PADS_REQ[k] / 2, spec['pads'][k][1] + PADS_REQ[k] / 2) for k in PADS_REQ])
sec_g = gap_s.Volume() / max(gap_s.BoundingBox().zlen, 1e-6)
check('gap filler covers exactly the P4 12 x 12 and C6 7 x 7 squares', abs(sec_g - want.area) < 0.01 * want.area and all(abs(vol(gap_s, bx(-spec['pads'][k][0] - PADS_REQ[k] / 2, -spec['pads'][k][0] + PADS_REQ[k] / 2, spec['pads'][k][1] - PADS_REQ[k] / 2, spec['pads'][k][1] + PADS_REQ[k] / 2, 0, H)) - PADS_REQ[k] ** 2 * gap_s.BoundingBox().zlen) < 0.01 * PADS_REQ[k] ** 2 for k in PADS_REQ),
      f'footprint {sec_g:.1f} mm2, wanted {want.area:.1f} mm2 (the two squares overlap at the module corner, as in the thermal model)')
u1 = next(p for p in D['parts'] if p['ref'] == 'U1')
inside_mod = all(abs(vol(g, bx(-(u1['x'] + 12.5), -(u1['x'] - 12.5), u1['y'] - 12.5, u1['y'] + 12.5, 0, H)) - g.Volume()) < 0.01 for g in gb_)
ggb = gap_s.BoundingBox()
check('gap filler sits on the module shield and reaches the plate', inside_mod and abs(ggb.zmin - (Z_TOP + 3.31)) < 0.05 and abs(ggb.zmax - pbb.zmin) < 0.02,
      f'z {ggb.zmin:.2f}..{ggb.zmax:.2f}, inside the module outline {inside_mod}')
check('gap filler touches nothing but the shield and the plate', all(vol(gap_s, sol[k]) < 0.01 for k in sol) and vol(gap_s, lcd) < 0.01)
m_ = spec['materials']
check('lid and tray are Al 6061, black anodized', all('Al 6061' in m_[k] and 'anodized' in m_[k] and 'black' in m_[k] for k in ('lid', 'tray')), f"lid {m_['lid']}; tray {m_['tray']}")
# metal to metal: the tray rim carries the plate and the plate carries the lid rim, all the way round
ring_t = slice_mesh(tray_m, 2, PLATE_Z[0] - 0.03)
ring_l = slice_mesh(lid_m, 2, PLATE_Z[1] + 0.03).intersection(sbox(-half, Y0, half, Y1).difference(sbox(-half + WALL, Y0 + WALL, half - WALL, Y1 - WALL)))   # the rim, not the post shoulders
c_t = ring_t.intersection(slice_mesh(plate_m, 2, PLATE_Z[0] + 0.03)).area
c_l = ring_l.intersection(slice_mesh(plate_m, 2, PLATE_Z[1] - 0.03)).area
check('tray rim, plate and lid rim seat metal to metal all round', c_t > 0.95 * ring_t.area and c_l > 0.95 * ring_l.area, f'tray rim {c_t:.1f} of {ring_t.area:.1f} mm2, lid rim {c_l:.1f} of {ring_l.area:.1f} mm2 on the plate')
# grounding: posts bear on plated GND rings top (lid) and bottom (tray); the plate is clamped by the post shoulders
pcbtxt = open(A.pcb, encoding='utf-8').read()
mh = []
for m in re.finditer(r'\(footprint "[^"]*MH[^"]*"', pcbtxt):   # generated (one line per item) or saved by KiCad (tabs, one token per line)
    nx = pcbtxt.find('(footprint ', m.end())
    blk = pcbtxt[m.end():nx if nx > 0 else len(pcbtxt)]
    at = re.search(r'\(translate ([-\d.]+) ([-\d.]+)', blk) or re.search(r'\(at ([-\d.]+) ([-\d.]+)', blk)   # KiCad 9 nightly saves a transform
    pd = re.search(r'\(pad "[^"]*"\s+(\w+)\s+circle.*?\(size ([\d.]+) [\d.]+\)\s*\(drill ([\d.]+)\)', blk, re.S)
    nt = re.search(r'\(net (?:\d+ )?"([^"]+)"\)', blk)
    mh.append((float(at[1]) - 100, float(at[2]) - 100, pd[1], float(pd[2]), float(pd[3]), nt[1] if nt else None))
check('three mounting holes are plated and on GND, ring 2.9 mm', len(mh) == HOLES_N and all(k == 'thru_hole' and n == 'GND' and abs(sz - RING_OD) < 1e-6 and sz > dr for _, _, k, sz, dr, n in mh), str([(round(x), round(y), k, sz, n) for x, y, k, sz, dr, n in mh]))
touch = {'lid': 0, 'tray': 0}
for x, y, k, sz, dr, n in mh:
    ring_cu = Point(-x, y).buffer(sz / 2).difference(Point(-x, y).buffer(dr / 2))
    touch['lid'] += ring_cu.intersection(l_above).area > 0.5
    touch['tray'] += ring_cu.intersection(t_below).area > 0.5
check('all three tray posts bear on a plated GND ring (bottom); no lid post touches the board (r8b)', touch['lid'] == 0 and touch['tray'] == HOLES_N, f"tray {touch['tray']} of {HOLES_N}, lid {touch['lid']}")
clamp = 0
for x, y, _ in holes_real:
    sh_ = slice_mesh(lid_m, 2, PLATE_Z[1] + 0.03).intersection(Point(x, y).buffer(3.0))
    pl_ = slice_mesh(plate_m, 2, PLATE_Z[1] - 0.03).intersection(Point(x, y).buffer(3.0))
    clamp += sh_.intersection(pl_).area > 1.0
check('the plate is clamped by all three post shoulders (metal contact to the lid)', clamp == HOLES_N, f'{clamp} of {HOLES_N}')
# anodize insulates: every contact face that carries ground is masked, the plate is bare, and the ground is measured
mk = spec.get('masked', {})
needm = {'post_end': touch['lid'] > 0, 'post_shoulder': clamp > 0, 'lid_rim': c_l > 0, 'tray_post_end': touch['tray'] > 0, 'tray_rim': c_t > 0}
missm = [k for k, used in needm.items() if used and k not in mk]
check('every lid and tray contact face that carries ground is masked from the anodize', not missm and all('masked' in m_[k] for k in ('lid', 'tray')), f'masked {sorted(mk)}; missing {missm}')
check('the plate is bare metal on its contact faces', 'bare' in m_['plate'] and 'anodiz' not in m_['plate'].replace('no anodize', ''), m_['plate'])
acc = spec.get('acceptance', [])
check('lid-, plate- and tray-to-GND < 1 ohm are assembly acceptance tests', all(any(a_.startswith(k) and '< 1 ohm' in a_ for a_ in acc) for k in ('lid', 'plate', 'tray')), str(acc))

say('weakest clearances: ' + ', '.join(f'{n} {v:.3f}' for n, v in sorted(weak, key=lambda t: t[1])[:8]))
tb, lb = tray_s.BoundingBox(), lid_s.BoundingBox()
say(f'tray bbox {tb.xlen:.2f} x {tb.ylen:.2f} x {tb.zlen:.2f}, lid bbox {lb.xlen:.2f} x {lb.ylen:.2f} x {lb.zlen:.2f}')
n_fail = sum(1 for _, ok in results if not ok)
say(f'RESULT {"PASS" if not n_fail else "FAIL"}: {len(results) - n_fail} passed, {n_fail} failed, case files {os.path.abspath(A.case_dir)}')
if A.report:
    head = f'===== {A.title} =====\n' if A.title else ''
    with open(A.report, 'a' if A.append else 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + '\n'.join(lines) + '\n\n')
sys.exit(0 if not n_fail else 1)
