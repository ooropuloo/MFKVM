# -*- coding: utf-8 -*-
"""Judges printed case files against the real board, not against the numbers that built the case.

Board facts come from kicad-cli exports of the routed .kicad_pcb, redone on every run:
  STEP: right-handed by the STEP standard, so it fixes handedness. Gives outline, screw holes, shell slots, pads and z.
  Gerber X2: every flash names its ref and pin, which is the only thing taken from it. It is checked against the STEP first.
Board to case is a rotation by 180 degrees about z and a lift. check_case asserts determinant +1 and does not import gen_case.
Openings and labels come from slicing the STL meshes. Bodies are tested against the STEP solids of the same case.
design.json supplies only component envelopes and body heights, and each ref's position there is checked against the real pads.

usage: check_case.py <case_dir> [--design design.json] [--pcb x.kicad_pcb] [--report file] [--append] [--title text]
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
from shapely.geometry import LineString, Point, Polygon, box as sbox
from shapely.ops import polygonize, unary_union

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('case_dir')
ap.add_argument('--design', default=os.path.join(HERE, '..', 'out', 'design.json'))
ap.add_argument('--pcb', default=os.path.join(HERE, '..', 'kicad', 'p4_kvm_mini.kicad_pcb'))
ap.add_argument('--report')
ap.add_argument('--append', action='store_true')
ap.add_argument('--title', default='')
A = ap.parse_args()

KICAD = 'D:/tools/kicad-nightly/app/bin/kicad-cli.exe'
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME='D:/tools/kicad-nightly/home/doc', KICAD_CONFIG_HOME='D:/tools/kicad-nightly/home/cfg', KICAD_CACHE_HOME='D:/tools/kicad-nightly/home/cache')

# The mechanical stack and hardware. These are requirements on the case, written here on purpose rather than read from gen_case.
S, WALL = 44.0, 1.6
half = S / 2
# r7c: the case is no longer square. x walls at +-22; y walls 2 mm outside the board's front and back edges, read from design.json.
_B = json.load(open(A.design, encoding='utf-8')).get('board') or {'y0': -20.0, 'y1': 20.0}
Y0, Y1 = _B['y0'] - 2.0, _B['y1'] + 2.0
Z_BOT, Z_TOP = 8.5, 9.7
H, TOP = 20.0, 1.0
LCD_D, LCD_T = 39.0, 3.6
SCREW_HEAD_D, SCREW_L, SCREW_MAJOR = 3.8, 16.0, 2.0
USB_SHELL, HDMI_SHELL = (8.94, 3.2), (15.0, 6.0)
PLUG = {'J3': (12.0, 8.0), 'J5': (12.0, 8.0), 'J2': (19.5, 11.0)}  # worst case overmoulds, from layout.py's sources
HEIGHT = {'ESP32-P4-Module': 3.31, 'USB-C_HX_16P': 3.2, 'JST_SM08B': 4.25, 'JST_SM06B': 4.25, 'HDMI-001S': 6.0, 'microSD_Molex_104031-0811': 1.42, 'BGA-64_6x6': 1.2,
          'SOT-23-5': 1.45, 'SOT-23': 1.2, 'MSOP-8': 1.1, 'OSC3225': 1.2, 'SSOP-4_1.27': 2.0, 'IND4020': 2.0, 'C0805': 1.4, 'CP_7343': 3.1, 'C0603': 1.0, 'R0402': 0.6, 'USON-10': 0.6, 'TP_1.0': 0.1, 'U.FL-R-SMT-1': 2.5, 'WSON-8_2x2_EP': 0.8, 'X1SON-2_0.6x1': 0.45, 'R0201': 0.3}  # r7f: TI DSG0008A 0.8 max, DPY0002A 0.45 max. U.FL: mated plug, Hirose catalogue p4, 2.5 max with U.FL-LP-040/066; the receptacle alone is 1.25

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
            [KICAD, 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu', '-o', tmp + os.sep, A.pcb]):
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
CX -= (_B.get('x0', -20.0) + _B.get('x1', 20.0)) / 2
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


def parse_gerber(path):
    fs, cur, out = 1e6, None, []
    for raw in open(path, encoding='utf-8', errors='replace'):
        s = raw.strip()
        m = re.match(r'%FSLAX(\d)(\d)Y', s)
        if m:
            fs = 10 ** int(m.group(2))
        m = re.match(r'%TO\.P,([^,*]+),([^,*]+)', s)
        if m:
            cur = (m.group(1), m.group(2))
        elif s.startswith('%TD'):
            cur = None
        m = re.match(r'X(-?\d+)Y(-?\d+)D03\*', s)
        if m and cur:
            out.append((cur[0], cur[1], int(m.group(1)) / fs, int(m.group(2)) / fs))
    return out


def find(ext):
    return next(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(ext))


flash = {'F': parse_gerber(find('F_Cu.gtl')), 'B': parse_gerber(find('B_Cu.gbl'))}
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

pads = {}
for side, fl in flash.items():
    for ref, pin, gx, gy in fl:
        pads.setdefault(ref, []).append((pin, side, *to_case((gx, gy, 0))[:2]))


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
WALLS = {'-y': lambda c: c[1] - Y0, '+y': lambda c: Y1 - c[1], '-x': lambda c: c[0] + half, '+x': lambda c: half - c[0]}


def nearest_wall(c):
    return min(WALLS, key=lambda w: WALLS[w](c))


holes_real = []
for e in body.Edges():
    if e.geomType() == 'CIRCLE' and e.radius() > 0.9 and abs(e.startPoint().z - bb.zmin) < 0.01:
        c = e.Center()
        cx, cy = to_case((c.x, c.y, 0))[:2]
        holes_real.append((round(float(cx), 3), round(float(cy), 3), round(2 * e.radius(), 3)))
check('four screw holes found in the board', len(holes_real) == 4, str(holes_real))
say(f"real connector centres in the case frame: {', '.join(f'{k} ({v[0]:.2f}, {v[1]:.2f}) nearest wall {nearest_wall(v)}' for k, v in CONN.items())}")
say('standing outside the I/O face (-y) +x is on your right: J3 ' + ('LEFT' if CONN['J3'][0] < 0 else 'RIGHT') + ', J2 ' + ('LEFT' if CONN['J2'][0] < 0 else 'RIGHT'))
check('real J3 is left of real J2, seen from outside the I/O face', CONN['J3'][0] < CONN['J2'][0])
SIDE = {'J3': 'F', 'J5': 'F', 'J6': 'F', 'J2': 'B', 'J7': 'B', 'J4': 'B'}
wrong = [r for r, sd in SIDE.items() if not any(q[1] == sd for q in pads[r])]
check('connector sides as the z windows below assume', not wrong, str(wrong) if wrong else 'J3 J5 J6 top, J2 J7 J4 bottom')


# ---------- printed files
def load_stl(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:400]:
        v = np.array(re.findall(rb'vertex\s+(\S+)\s+(\S+)\s+(\S+)', data), dtype=float)
        return v.reshape(-1, 3, 3)
    n = int.from_bytes(data[80:84], 'little')
    a = np.frombuffer(data, dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n, offset=84)
    return a['v'].astype(float)


tray_m, lid_m = (load_stl(os.path.join(A.case_dir, f'mf_kvm_{k}.stl')) for k in ('tray', 'lid'))
tray_s, lid_s = (cq.importers.importStep(os.path.join(A.case_dir, f'mf_kvm_{k}.step')).val() for k in ('tray', 'lid'))


def mesh_volume(t):
    return abs(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()) / 6


for k, m, s in (('tray', tray_m, tray_s), ('lid', lid_m, lid_s)):
    dv = abs(mesh_volume(m) - s.Volume()) / s.Volume()
    check(f'{k} STL and STEP are the same part', dv < 0.01, f'volume differs {dv * 100:.2f}%')


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


def wall_section(wall, depth):
    """Solid material at a given depth inside a wall, tray and lid together, as (u, z): u is x on y walls, y on x walls."""
    axis, sign = (1, -1) if wall == '-y' else (1, 1) if wall == '+y' else (0, -1) if wall == '-x' else (0, 1)
    v = (Y0 + depth) if wall == '-y' else (Y1 - depth) if wall == '+y' else sign * (half - depth)
    return unary_union([slice_mesh(tray_m, axis, v + 1e-5), slice_mesh(lid_m, axis, v + 1e-5)]), axis


def wall_u(c, wall):
    return c[0] if wall in ('-y', '+y') else c[1]


def clear_of(sec, shape):
    """Area of the shape that hits material."""
    return shape.intersection(sec).area


THROAT = WALL - 0.3  # past the outer plug pockets, still inside the wall
SURFACE = 0.4        # inside the plug pockets and the label depth
sections = {w: wall_section(w, THROAT)[0] for w in WALLS}
surface = {w: wall_section(w, SURFACE)[0] for w in WALLS}


def stadium(u, z, w, h):
    return LineString([(u - (w - h) / 2, z), (u + (w - h) / 2, z)]).buffer(h / 2)


usb_z = Z_TOP + USB_SHELL[1] / 2
need = {
    'J2': ('-y', sbox(CONN['J2'][0] - HDMI_SHELL[0] / 2, Z_BOT - HDMI_SHELL[1], CONN['J2'][0] + HDMI_SHELL[0] / 2, Z_BOT), 'HDMI shell 15 x 6'),
    'J3': ('-y', stadium(CONN['J3'][0], usb_z, *USB_SHELL), 'USB-C shell 8.94 x 3.2'),
    'J5': ('-x', stadium(CONN['J5'][1], usb_z, *USB_SHELL), 'USB-C shell 8.94 x 3.2'),
    'J7': ('+x', sbox(CONN['J7'][1] - 5.5, Z_BOT - 1.42, CONN['J7'][1] + 5.5, Z_BOT - 0.4), 'card 11 wide at the shell'),
    'J4': ('+y', sbox(CONN['J4'][0] - 4.0, Z_BOT - 3.5, CONN['J4'][0] + 4.0, Z_BOT - 0.4), 'SHR-06V plug 8 wide'),
}


def hole_near(sec, shape):
    """Void around the shape: the wall rectangle less material, the piece that contains the shape's centre."""
    void = sbox(-half + 3.2, 0.1, half - 3.2, H - TOP).difference(sec)
    pieces = list(void.geoms) if hasattr(void, 'geoms') else [void]
    c = shape.centroid
    best = [g for g in pieces if not g.is_empty and g.contains(c)]
    return best[0] if best else None


for ref, (wall, shape, what) in need.items():
    check(f'{ref} on the {wall} wall is the wall nearest its real position', nearest_wall(CONN[ref]) == wall, f'nearest {nearest_wall(CONN[ref])}')
    hit = clear_of(sections[wall], shape)
    check(f'{ref} opening in {wall} wall clears the {what}', hit < 0.05, f'{hit:.2f} mm2 of wall in the way at u {wall_u(CONN[ref], wall):.2f}')
    h = hole_near(sections[wall], shape)
    if h is None:
        check(f'{ref} opening centred on the connector', False, 'no opening at the connector centre')
    else:
        x0, z0, x1, z1 = h.bounds
        off = (x0 + x1) / 2 - wall_u(CONN[ref], wall)
        check(f'{ref} opening centred on the connector', abs(off) < 0.5, f'offset {off:+.2f}, opening u {x0:.2f}..{x1:.2f} z {z0:.2f}..{z1:.2f}')
    if ref in PLUG:
        w, ht = PLUG[ref]
        z = Z_BOT - HDMI_SHELL[1] / 2 if ref == 'J2' else usb_z
        u = wall_u(CONN[ref], wall)
        plug = sbox(u - w / 2, max(0.02, z - ht / 2), u + w / 2, z + ht / 2)
        hit = clear_of(surface[wall], plug)
        check(f'{ref} plug overmould {w} x {ht} fits its pocket', hit < 0.05, f'{hit:.2f} mm2 in the way')
gap = abs(CONN['J2'][0] - CONN['J3'][0]) - (PLUG['J2'][0] + PLUG['J3'][0]) / 2
check('HDMI and host USB plugs fit side by side', gap > 0.3, f'{gap:.2f} mm between overmoulds')


# ---------- labels: a cut shows as a void at label depth that is not a void deeper in the wall
def label_islands(wall):
    shallow = wall_section(wall, 0.15)[0]
    deep = wall_section(wall, 0.6)[0]  # below the 0.4 mm text, above the floor of the 0.8 mm plug pockets
    extra = deep.difference(shallow).buffer(0.1)
    return [g for g in (extra.geoms if hasattr(extra, 'geoms') else [extra]) if g.area > 0.1]


LABEL = {'HDMI': ('-y', 'J2', 4.0, 8.5), 'MF KVM': ('-y', 'J2', 11.0, 17.5), 'HOST': ('-y', 'J3', 4.0, 8.0), '5V': ('-x', 'J5', 1.8, 4.5), 'TF': ('+x', 'J7', 1.5, 4.0), 'ATX': ('+y', 'J4', 3.5, 6.5)}
ZLAB = {'HDMI': 14.8, 'MF KVM': 17.0, 'HOST': 17.2, '5V': 17.2, 'TF': 11.0, 'ATX': 10.5}
isl = {w: label_islands(w) for w in WALLS}
for name, (wall, ref, wmin, wmax) in LABEL.items():
    u = wall_u(CONN[ref], wall)
    group = [g for g in isl[wall] if abs(g.centroid.y - ZLAB[name]) < 1.25 and abs(g.centroid.x - u) < 9]
    if group:
        x0 = min(g.bounds[0] for g in group)
        x1 = max(g.bounds[2] for g in group)
        ok = wmin <= x1 - x0 <= wmax and abs((x0 + x1) / 2 - u) < 2.5
        check(f'label {name} is cut in the {wall} wall beside {ref}', ok, f'text u {x0:.1f}..{x1:.1f} z {min(g.bounds[1] for g in group):.1f}..{max(g.bounds[3] for g in group):.1f}, connector u {u:.2f}')
    else:
        check(f'label {name} is cut in the {wall} wall beside {ref}', False, 'no cut there')

# ---------- vents next to the heat, none on the +x wall
real = {r: np.mean([(p[2], p[3]) for p in pads[r]], axis=0) for r in ('U7', 'U2', 'L1')}


def vents(wall):
    void = sbox(-half + 3.2, 2.5, half - 3.2, 5.8).difference(sections[wall])
    gs = list(void.geoms) if hasattr(void, 'geoms') else [void]
    return [g.bounds for g in gs if not g.is_empty and 0.8 < g.bounds[2] - g.bounds[0] < 2.0]


vn = {w: vents(w) for w in WALLS}
say('vents ' + ', '.join(f'{w} {len(v)}' for w, v in vn.items()))
check('no vents on the +x (microSD) wall or the I/O wall', not vn['+x'] and not vn['-y'])
for r, c in real.items():
    du = min((abs((v[0] + v[2]) / 2 - c[1]) for v in vn['-x']), default=99)
    check(f'-x wall vent beside {r}', c[0] < 0 and du < 3.0, f'{r} real at ({c[0]:.2f}, {c[1]:.2f}), nearest slot {du:.2f} mm along the wall')
back = min((abs((v[0] + v[2]) / 2 - real['L1'][0]) for v in vn['+y']), default=99)
check('back wall vent behind the buck stage', back < 3.0, f'{back:.2f} mm from L1 along the wall')

# ---------- screws and posts
z_seat = 1.8
tip = z_seat + SCREW_L


def holes_at(tris, z):
    sec = slice_mesh(tris, 2, z)
    geoms = list(sec.geoms) if hasattr(sec, 'geoms') else [sec]
    return [Polygon(r) for g in geoms if not g.is_empty for r in g.interiors], sec


def bore_at(tris, x, y, z):
    """Diameter of the round void around (x, y) at height z, or None when that spot is solid or not enclosed."""
    holes, sec = holes_at(tris, z)
    for h in holes:
        if h.contains(Point(x, y)) and h.area < 40:
            return 2 * math.sqrt(h.area / math.pi), math.hypot(h.centroid.x - x, h.centroid.y - y), sec
    return None, None, sec


def wall_outside(sec, x, y, bore):
    """Thinnest plastic around a bore: distance to the nearest edge of the section other than the bore itself."""
    c, best = Point(x, y), 9.0
    for g in (sec.geoms if hasattr(sec, 'geoms') else [sec]):
        best = min(best, c.distance(g.exterior))
        for r in g.interiors:
            if not Polygon(r).contains(c):
                best = min(best, c.distance(r))
    return best - bore / 2


jc = CONN['J6']
J6_HOLE = min(holes_real, key=lambda h: math.hypot(h[0] - jc[0], h[1] - jc[1]))
for x, y, d in holes_real:
    tag = f'({x:.0f}, {y:.0f})'
    v, off, _ = bore_at(tray_m, x, y, 4.0)
    check(f'tray clearance bore at {tag} lines up', v is not None and off < 0.1 and v >= SCREW_MAJOR + 0.2, f'd {v and round(v, 2)}, offset {off and round(off, 2)}')
    v, off, _ = bore_at(tray_m, x, y, 1.0)
    check(f'tray head recess at {tag} takes the M2 head', v is not None and off < 0.1 and v >= SCREW_HEAD_D, f'd {v and round(v, 2)}')
    # the post top is the seat
    below = slice_mesh(tray_m, 2, Z_BOT - 0.03)
    above = slice_mesh(tray_m, 2, Z_BOT + 0.03)
    seat = Point(x, y).buffer(2.2).difference(Point(x, y).buffer(d / 2))
    check(f'tray post at {tag} seats the PCB at z {Z_BOT}', seat.intersection(below).area > 0.8 * seat.area and seat.intersection(above).area < 0.01, f'{seat.intersection(below).area:.1f} of {seat.area:.1f} mm2')
    ztest = 16.0
    v, off, sec = bore_at(lid_m, x, y, ztest)
    t = wall_outside(sec, x, y, v) if v else 0
    check(f'lid pilot at {tag} lines up at z {ztest}', v is not None and off < 0.1 and 1.4 <= v <= 1.8 and t >= 0.8, f'd {v and round(v, 2)}, wall {t:.2f}')
    if (x, y, d) == J6_HOLE:
        low = slice_mesh(lid_m, 2, Z_TOP + 2.0)
        keep = Point(x, y).buffer(SCREW_MAJOR / 2 + 0.2)
        check(f'J6 corner {tag}: the thread has no thin wall beside J6', keep.intersection(low).area < 0.01 or wall_outside(low, x, y, 1.6) >= 0.8, 'post starts above the J6 relief' if keep.intersection(low).area < 0.01 else 'post runs down beside J6')
    else:
        v, off, sec = bore_at(lid_m, x, y, Z_TOP + 2.0)
        t = wall_outside(sec, x, y, v) if v else 0
        check(f'lid post at {tag} is whole down at the PCB', v is not None and off < 0.1 and t >= 0.8, f'd {v and round(v, 2)}, wall {t:.2f}')
        at_face = slice_mesh(lid_m, 2, Z_TOP + 0.03)
        ring = Point(x, y).buffer(1.85).difference(Point(x, y).buffer(1.1))
        check(f'lid post at {tag} meets the PCB top', ring.intersection(at_face).area > 0.6 * ring.area and ring.intersection(slice_mesh(lid_m, 2, Z_TOP - 0.03)).area < 0.01, f'{ring.intersection(at_face).area:.1f} of {ring.area:.1f} mm2')
top_of_pilot = H - TOP - 0.6
check('M2 x 16 tip stops inside the pilot', tip < top_of_pilot, f'seat z {z_seat}, tip z {tip}, pilot top z {top_of_pilot}')
J6_THREAD = tip - (Z_TOP + 4.6)
check('thread engagement in the J6 corner is at least 1.5 x d', J6_THREAD >= 1.5 * SCREW_MAJOR, f'{J6_THREAD:.1f} mm')


# ---------- bodies against the solids
def bx(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def vol(a, b):
    try:
        return a.intersect(b).Volume()
    except Exception:
        return 0.0


D = json.load(open(A.design, encoding='utf-8'))
fails, moved = [], []
OPENING = {'J2', 'J3', 'J5', 'J7', 'J4'}
for p in D['parts']:
    x0d, y0d, x1d, y1d = p['bbox']
    if p['ref'] == 'U1':
        x0d, y0d, x1d, y1d = p['x'] - 12.6, p['y'] - 12.6, p['x'] + 12.6, p['y'] + 12.6
    if p['ref'] == 'J2':
        x0d, y0d, x1d, y1d = p['x'] - 7.6, -20.7, p['x'] + 7.6, -8.0
    # design to case for the envelope only. It must hold every real pad of the ref, or the envelope is checked in the wrong place.
    x0, x1, y0, y1 = -x1d, -x0d, y0d, y1d
    if p['ref'] in pads:
        out = [q[0] for q in pads[p['ref']] if not (x0 - 0.6 <= q[2] <= x1 + 0.6 and y0 - 0.6 <= q[3] <= y1 + 0.6)]
        if out:
            moved.append((p['ref'], out[:3]))
    h = HEIGHT[p['lib']]
    z0, z1 = (Z_TOP, Z_TOP + h) if p['side'] == 'F' else (Z_BOT - h, Z_BOT)
    b = bx(x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, z0, z1)
    vt, vl = vol(tray_s, b), vol(lid_s, b)
    limit = 0.25 if p['ref'] in ('J3', 'J5') else 0.01  # the USB-C box corners overstate the rounded shell at the wall
    if vt > limit or vl > limit:
        fails.append((p['ref'], round(vt, 2), round(vl, 2)))
check('every part envelope holds its real pads after the design-to-case map', not moved, str(moved[:5]) if moved else f"{len(D['parts'])} parts")
check('no part body touches the tray or lid', not fails, str(fails[:12]) if fails else 'none')

pcb_case = body.rotate(cq.Vector(CX, CY, 0), cq.Vector(CX, CY, 1), 180).translate(cq.Vector(-CX, -CY, T[2]))
probe = np.array([CX + 7.0, CY - 3.0, 0.5])
assert np.allclose(to_case(probe), [-7.0, 3.0, 0.5 + T[2]]), 'to_case must be the same move as the solid'
vt, vl = vol(tray_s, pcb_case), vol(lid_s, pcb_case)
check('real PCB solid (outline, holes, slots) against tray and lid', vt < 0.01 and vl < 0.01, f'tray {vt:.3f}, lid {vl:.3f} mm3')
pb = pcb_case.BoundingBox()
check('PCB z in the case is the stack height', abs(pb.zmin - Z_BOT) < 0.06 and abs(pb.zmax - Z_TOP) < 0.12, f'{pb.zmin:.2f}..{pb.zmax:.2f}')
vtl = vol(tray_s, lid_s)
check('tray against lid', vtl < 0.01, f'{vtl:.3f} mm3')
lcd = cq.Solid.makeCylinder(LCD_D / 2, LCD_T, cq.Vector(0, 0, H - TOP - LCD_T))
a, b = vol(lid_s, lcd), vol(tray_s, lcd)
check('LCD module (estimate) against lid and tray', a < 0.01 and b < 0.01, f'lid {a:.3f}, tray {b:.3f} mm3')
lcd_bottom = H - TOP - LCD_T
top_max = max(Z_TOP + HEIGHT[p['lib']] for p in D['parts'] if p['side'] == 'F')
check('LCD clears the tallest top-side part', lcd_bottom >= top_max, f'LCD bottom {lcd_bottom:.2f}, tallest top {top_max:.2f}')

# J6 mates toward the wall nearest it; its plug and wires need that gap. Sign taken from the real pads: the contact row is behind the mounting tabs.
row = mid([(q[2], q[3]) for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}])
tabs = mid([(q[2], q[3]) for q in pads['J6'] if q[0] in {'9', '10'}])
d6 = np.sign(tabs[0] - row[0])
face = tabs[0] + d6 * 1.2
plug_u = (min(q[3] for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}) - 1.0, max(q[3] for q in pads['J6'] if q[0] in {str(i) for i in range(1, 9)}) + 1.0)
xa, xb = sorted((face, face + d6 * 2.7))
pk = bx(xa, xb, plug_u[0], plug_u[1], Z_TOP, Z_TOP + 2.9)
say(f'J6 mouth faces {"-x" if d6 < 0 else "+x"}, plug and wire keep-out x {xa:.2f}..{xb:.2f} y {plug_u[0]:.2f}..{plug_u[1]:.2f} z {Z_TOP}..{Z_TOP + 2.9:.1f}')
v = vol(lid_s, pk)
check('J6 plug and wires clear the lid', v < 0.01, f'{v:.2f} mm3')
j6 = next(p for p in D['parts'] if p['ref'] == 'J6')
# r7f: the true distance from the screw axis to J6's envelope (case frame). Up to r7e this was the x gap only, written when the J6-corner
# screw sat level with J6 (40 x 40 board, hole at y 18); since r7c the hole is at y 23, 4.2 mm past J6's end, and the x gap understated it.
_j6env = sbox(-j6['bbox'][2], j6['bbox'][1], -j6['bbox'][0], j6['bbox'][3])
gap_j6 = _j6env.distance(Point(J6_HOLE[0], J6_HOLE[1])) - SCREW_MAJOR / 2
check('M2 shank clears the J6 envelope', gap_j6 > 0.2, f'{gap_j6:.2f} mm (x gap alone {abs(J6_HOLE[0] - -j6["bbox"][2]) - SCREW_MAJOR / 2:.2f} mm)')

# ---------- r7f: THERMAL_REPORT 6.5 configuration f1 (metal lid, spreader plate, gap filler, lid vents, heat-resistant tray, grounding).
# Requirements written here, judged on the files gen_case wrote: mf_kvm_plate.step/stl, mf_kvm_gapfill.step, case_spec.json.
PLATE_Z = (13.8, 14.6)                     # 0.8 mm plate at the split
VENT_N, VENT_AREA = 12, 72.0               # 12 slots 1.2 x 5
PADS_REQ = {'P4': 12.0, 'C6': 7.0}         # gap filler squares (mm), over the P4 and the C6
OK_TRAY = ('ASA', 'ABS', 'PC', 'PA12')
spec_p = os.path.join(A.case_dir, 'case_spec.json')
have = all(os.path.exists(os.path.join(A.case_dir, f)) for f in ('mf_kvm_plate.step', 'mf_kvm_plate.stl', 'mf_kvm_gapfill.step', 'case_spec.json'))
check('r7f plate, gap filler and case_spec files exist', have)
if have:
    spec = json.load(open(spec_p, encoding='utf-8'))
    plate_s = cq.importers.importStep(os.path.join(A.case_dir, 'mf_kvm_plate.step')).val()
    gap_s = cq.importers.importStep(os.path.join(A.case_dir, 'mf_kvm_gapfill.step')).val()
    plate_m = load_stl(os.path.join(A.case_dir, 'mf_kvm_plate.stl'))
    dv = abs(mesh_volume(plate_m) - plate_s.Volume()) / plate_s.Volume()
    check('plate STL and STEP are the same part', dv < 0.01, f'volume differs {dv * 100:.2f}%')
    pbb = plate_s.BoundingBox()
    check('plate is 0.8 mm Al at z 13.8..14.6', abs(pbb.zmin - PLATE_Z[0]) < 0.02 and abs(pbb.zmax - PLATE_Z[1]) < 0.02 and 'Al' in spec['materials']['plate'], f'z {pbb.zmin:.2f}..{pbb.zmax:.2f}, {spec["materials"]["plate"]}')
    check('plate spans the case outline (edge clamped between the halves)', pbb.xlen > S - 0.5 and pbb.ylen > (Y1 - Y0) - 0.5, f'{pbb.xlen:.2f} x {pbb.ylen:.2f}')
    vpt, vpl = vol(plate_s, tray_s), vol(plate_s, lid_s)
    check('plate against tray and lid', vpt < 0.01 and vpl < 0.01, f'tray {vpt:.3f}, lid {vpl:.3f} mm3')
    # plate against every part envelope (same envelopes as above)
    hit = []
    for p in D['parts']:
        x0d, y0d, x1d, y1d = p['bbox']
        if p['ref'] == 'U1':
            x0d, y0d, x1d, y1d = p['x'] - 12.6, p['y'] - 12.6, p['x'] + 12.6, p['y'] + 12.6
        if p['side'] != 'F':
            continue
        h_ = HEIGHT[p['lib']]
        v_ = vol(plate_s, bx(-x1d + 0.1, -x0d - 0.1, y0d + 0.1, y1d - 0.1, Z_TOP, Z_TOP + h_))
        if v_ > 0.01:
            hit.append((p['ref'], round(v_, 2)))
    check('plate clears every top-side part (J6 through its cut-out)', not hit, str(hit[:6]) if hit else f'tallest under the plate {max(Z_TOP + HEIGHT[p["lib"]] for p in D["parts"] if p["side"] == "F" and p["ref"] != "J6"):.2f}, plate bottom {pbb.zmin:.2f}')
    vplcd = vol(plate_s, lcd)
    gap_lcd = (H - TOP - LCD_T) - pbb.zmax
    check('plate clears the LCD (estimate) by 0.5 mm or more', vplcd < 0.01 and gap_lcd >= 0.5, f'{gap_lcd:.2f} mm')
    v_pk = vol(plate_s, pk)
    check('J6 plug and wires clear the plate', v_pk < 0.01, f'{v_pk:.2f} mm3')
    # gap filler: two pads, P4 12 x 12 and C6 7 x 7, from the module shield top to the plate bottom, inside the module outline
    gb = [sol for sol in (gap_s.Solids() if hasattr(gap_s, 'Solids') else [gap_s])]
    want = unary_union([sbox(-spec['pads'][k][0] - PADS_REQ[k] / 2, spec['pads'][k][1] - PADS_REQ[k] / 2, -spec['pads'][k][0] + PADS_REQ[k] / 2, spec['pads'][k][1] + PADS_REQ[k] / 2) for k in PADS_REQ])
    got = unary_union([sbox(g.BoundingBox().xmin, g.BoundingBox().ymin, g.BoundingBox().xmax, g.BoundingBox().ymax) for g in gb])
    fp_ = unary_union([sbox(*[f(g.BoundingBox()) for f in (lambda b: b.xmin, lambda b: b.ymin, lambda b: b.xmax, lambda b: b.ymax)]) for g in gb])
    sec_g = gap_s.Volume() / max(gap_s.BoundingBox().zlen, 1e-6)
    check('gap filler covers exactly the P4 12 x 12 and C6 7 x 7 squares', abs(sec_g - want.area) < 0.01 * want.area and all(abs(vol(gap_s, bx(-spec['pads'][k][0] - PADS_REQ[k] / 2, -spec['pads'][k][0] + PADS_REQ[k] / 2, spec['pads'][k][1] - PADS_REQ[k] / 2, spec['pads'][k][1] + PADS_REQ[k] / 2, 0, H)) - PADS_REQ[k] ** 2 * gap_s.BoundingBox().zlen) < 0.01 * PADS_REQ[k] ** 2 for k in PADS_REQ),
          f'footprint {sec_g:.1f} mm2, wanted {want.area:.1f} mm2 (the two squares overlap at the module corner, as in the thermal model)')
    u1 = next(p for p in D['parts'] if p['ref'] == 'U1')
    mod = bx(-(u1['x'] + 12.5), -(u1['x'] - 12.5), u1['y'] - 12.5, u1['y'] + 12.5, Z_TOP, Z_TOP + 3.31)
    inside_mod = all(abs(vol(g, bx(-(u1['x'] + 12.5), -(u1['x'] - 12.5), u1['y'] - 12.5, u1['y'] + 12.5, 0, H)) - g.Volume()) < 0.01 for g in gb)
    ggb = gap_s.BoundingBox()
    check('gap filler sits on the module shield and reaches the plate', inside_mod and abs(ggb.zmin - (Z_TOP + 3.31)) < 0.05 and abs(ggb.zmax - pbb.zmin) < 0.02,
          f'z {ggb.zmin:.2f}..{ggb.zmax:.2f}, inside the module outline {inside_mod}')
    check('gap filler touches nothing but the shield and the plate', vol(gap_s, lid_s) < 0.01 and vol(gap_s, tray_s) < 0.01 and vol(gap_s, lcd) < 0.01)
    # vents through the lid top, outside the LCD window
    sec = slice_mesh(lid_m, 2, H - TOP / 2)
    outer = sec.buffer(0)
    holes_ = [Polygon(r) for g in getattr(outer, 'geoms', [outer]) for r in g.interiors]
    vents_ = [h_ for h_ in holes_ if h_.centroid.distance(Point(0, 0)) > (LCD_D - 5.6) / 2 + 0.5 and h_.area < 20]
    va = sum(h_.area for h_ in vents_)
    check('lid top has 12 vent slots, about 72 mm2', len(vents_) == VENT_N and abs(va - VENT_AREA) < 0.1 * VENT_AREA, f'{len(vents_)} slots, {va:.1f} mm2')
    ring_ = Point(0, 0).buffer((LCD_D + 3.0) / 2)
    check('vent slots stay outside the LCD seat ring', all(not v_.intersects(ring_) for v_ in vents_))
    # materials: metal lid (black anodized), heat-resistant plastic tray
    m_ = spec['materials']
    check('lid is aluminium, black anodized; tray is heat resistant (not PLA)', 'Al' in m_['lid'] and 'anodized' in m_['lid'] and 'black' in m_['lid']
          and m_['tray'].split()[0] in OK_TRAY and 'PLA' not in m_['tray'].replace('not PLA', ''), f"lid {m_['lid']}; tray {m_['tray']}")
    # grounding: each lid post that reaches the PCB bears on a plated GND pad; the plate is clamped by the post shoulders
    pcbtxt = open(A.pcb, encoding='utf-8').read()
    mh = []
    for m in re.finditer(r'\(footprint "[^"]*MH[^"]*"', pcbtxt):   # generated (one line per item) or saved by KiCad (tabs, one token per line)
        nx = pcbtxt.find('(footprint ', m.end())
        blk = pcbtxt[m.end():nx if nx > 0 else len(pcbtxt)]
        at = re.search(r'\(translate ([-\d.]+) ([-\d.]+)', blk) or re.search(r'\(at ([-\d.]+) ([-\d.]+)', blk)   # KiCad 9 nightly saves a transform
        pd = re.search(r'\(pad "[^"]*"\s+(\w+)\s+circle.*?\(size ([\d.]+) [\d.]+\)\s*\(drill ([\d.]+)\)', blk, re.S)
        nt = re.search(r'\(net (?:\d+ )?"([^"]+)"\)', blk)
        mh.append((float(at[1]) - 100, float(at[2]) - 100, pd[1], float(pd[2]), float(pd[3]), nt[1] if nt else None))
    check('four mounting holes are plated and on GND', len(mh) == 4 and all(k == 'thru_hole' and n == 'GND' and sz > dr for _, _, k, sz, dr, n in mh), str([(round(x), round(y), k, sz, n) for x, y, k, sz, dr, n in mh]))
    touch = 0
    for x, y, k, sz, dr, n in mh:
        wx, wy = -x, y
        at_face = slice_mesh(lid_m, 2, Z_TOP + 0.03)
        ring_cu = Point(wx, wy).buffer(sz / 2).difference(Point(wx, wy).buffer(dr / 2))
        c_area = ring_cu.intersection(at_face).area
        if c_area > 0.5:
            touch += 1
    check('at least three lid posts bear on a plated GND ring (the J6-corner post stops above J6)', touch >= 3, f'{touch} of 4')
    clamp = 0
    for x, y in [(-hx, hy) for hx, hy in _B['holes']]:
        sh_ = slice_mesh(lid_m, 2, PLATE_Z[1] + 0.03).intersection(Point(x, y).buffer(3.0))
        pl_ = slice_mesh(plate_m, 2, PLATE_Z[1] - 0.03).intersection(Point(x, y).buffer(3.0))
        if sh_.intersection(pl_).area > 1.0:
            clamp += 1
    check('the plate is clamped by all four post shoulders (metal contact to the lid)', clamp == 4, f'{clamp} of 4')
    # REVIEW_r7f major-2: the contact faces must be free of anodize (it insulates), the plate bare, and the ground measured
    mk = spec.get('masked', {})
    need = {'post_end': touch > 0, 'post_shoulder': clamp > 0, 'lid_rim': True}
    lid_anod = 'anodiz' in m_['lid']
    miss = [k for k, used in need.items() if used and lid_anod and k not in mk]
    check('every lid contact face that carries ground is masked from the anodize', not miss and ('masked' in m_['lid'] or not lid_anod), f'masked {sorted(mk)}; missing {miss}')
    check('the plate is bare metal on its contact faces', 'bare' in m_['plate'] and 'anodiz' not in m_['plate'].replace('no anodize', ''), m_['plate'])
    acc = spec.get('acceptance', [])
    check('lid-to-GND and plate-to-GND < 1 ohm are assembly acceptance tests', any('lid' in a_ and '< 1 ohm' in a_ for a_ in acc) and any('plate' in a_ and '< 1 ohm' in a_ for a_ in acc), str(acc))
# ---------- r7f fan duct (user decision: external 5 V fan, own USB supply). Requirements written here, judged on mf_kvm_fanduct.*.
dpath = os.path.join(A.case_dir, 'mf_kvm_fanduct.step')
check('fan duct files exist', os.path.exists(dpath) and os.path.exists(os.path.join(A.case_dir, 'mf_kvm_fanduct.stl')))
if os.path.exists(dpath) and have:
    duct_s = cq.importers.importStep(dpath).val()
    duct_m = load_stl(os.path.join(A.case_dir, 'mf_kvm_fanduct.stl'))
    dbb = duct_s.BoundingBox()
    check('fan duct against lid, tray, plate', vol(duct_s, lid_s) < 0.01 and vol(duct_s, tray_s) < 0.01 and vol(duct_s, plate_s) < 0.01, f'lid {vol(duct_s, lid_s):.3f}, tray {vol(duct_s, tray_s):.3f} mm3')
    check('fan duct sits on the lid top', abs(dbb.zmin - H) < 0.02, f'duct bottom z {dbb.zmin:.2f}, lid top {H}')
    # interior footprint just above the lid top: every lid slot must open into it, the LCD window must stay clear of the duct
    inner = slice_mesh(duct_m, 2, H + 0.6)
    outline_ = Polygon(sbox(dbb.xmin, dbb.ymin, dbb.xmax, dbb.ymax).exterior)
    open_ = outline_.difference(inner.buffer(0))
    covered = [v_ for v_ in vents_ if open_.buffer(1e-3).contains(v_)]
    check('every lid slot opens into the duct', len(covered) == len(vents_) == VENT_N, f'{len(covered)} of {len(vents_)} slots inside the duct opening')
    win = Point(0, 0).buffer((LCD_D - 5.6) / 2)
    check('the duct stays clear of the LCD window', outline_.distance(win) > 0.2, f'{outline_.distance(win):.2f} mm')
    # past the back wall the duct has a floor, so the fan can draw only through the slots
    beyond = sbox(dbb.xmin + 0.01, Y1 + 0.2, dbb.xmax - 0.01, dbb.ymax - 0.01)
    fl = slice_mesh(duct_m, 2, H + 0.6).buffer(0)
    check('the duct floor closes the part that overhangs the case', fl.intersection(beyond).area > 0.95 * beyond.area, f'{fl.intersection(beyond).area:.1f} of {beyond.area:.1f} mm2')
    top_ = slice_mesh(duct_m, 2, dbb.zmax - 0.6).buffer(0)
    holes_t = [Polygon(r_) for g_ in getattr(top_, 'geoms', [top_]) for r_ in g_.interiors]
    big = [h_ for h_ in holes_t if h_.area > 100]
    small = sorted(h_.centroid.coords[0] for h_ in holes_t if 3 < h_.area < 10)
    pitch_ok = len(small) == 4 and all(abs(abs(small[i][0] - small[j][0]) - 24.0) < 0.05 or abs(small[i][0] - small[j][0]) < 0.05 for i in range(4) for j in range(4))
    check('fan seat: one opening and four screw holes on a 24 mm pitch (30 mm fan)', len(big) == 1 and pitch_ok, f'{len(big)} opening(s), screw holes {[(round(x, 1), round(y, 1)) for x, y in small]}')
    fs = spec.get('fan', {})
    check('the fan is powered from its own USB supply, not from the board', 'NOT from the board' in fs.get('fan', '') and 'budget unchanged' in fs.get('fan', ''), fs.get('fan', ''))
tb, lb = tray_s.BoundingBox(), lid_s.BoundingBox()
say(f'tray bbox {tb.xlen:.2f} x {tb.ylen:.2f} x {tb.zlen:.2f}, lid bbox {lb.xlen:.2f} x {lb.ylen:.2f} x {lb.zlen:.2f}')
n_fail = sum(1 for _, ok in results if not ok)
say(f'RESULT {"PASS" if not n_fail else "FAIL"}: {len(results) - n_fail} passed, {n_fail} failed, case files {os.path.abspath(A.case_dir)}')
if A.report:
    head = f'===== {A.title} =====\n' if A.title else ''
    with open(A.report, 'a' if A.append else 'w', encoding='utf-8', newline='\n') as f:
        f.write(head + '\n'.join(lines) + '\n\n')
sys.exit(0 if not n_fail else 1)
