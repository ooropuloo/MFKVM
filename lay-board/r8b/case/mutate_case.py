# -*- coding: utf-8 -*-
"""Mutation tests for check_case.py: put one known fault into a copy of the case files and require a named check to FAIL.

The style of tools/mutate.py's case family: the control (unchanged copy) must pass first, and a mutation counts as caught only when
the checker exits non-zero AND a FAIL line matches the check the mutation names (failing for another reason does not count).
Geometry faults are applied to the STEP and re-exported to both STEP and STL, so the files stay one part.

usage: mutate_case.py <case_stl_dir> --design design.json --pcb board.kicad_pcb [--report file] [--only n,n]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import cadquery as cq

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument('case_dir')
ap.add_argument('--design', required=True)
ap.add_argument('--pcb', required=True)
ap.add_argument('--report')
ap.add_argument('--only')
A = ap.parse_args()
SPEC = json.load(open(os.path.join(A.case_dir, 'case_spec.json'), encoding='utf-8'))
ST = SPEC['stack']
WORK = tempfile.mkdtemp(prefix='mutcase_')


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl(x, y, z0, z1, d):
    return cq.Workplane('XY').circle(d / 2).extrude(z1 - z0).translate((x, y, z0))


def edit(part, fn):
    def mod(d):
        w = cq.Workplane('XY').add(cq.importers.importStep(f'{d}/mf_kvm_{part}.step').val())
        w = fn(w)
        cq.exporters.export(w, f'{d}/mf_kvm_{part}.stl', tolerance=0.02, angularTolerance=0.15)
        cq.exporters.export(w, f'{d}/mf_kvm_{part}.step')
    return mod


def spec_edit(fn):
    def mod(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        fn(sp)
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'), indent=1)
    return mod


def both(*mods):
    def mod(d):
        for m in mods:
            m(d)
    return mod


B = SPEC['boss']
bx_, by_, bh = B['centre'][0], B['centre'][1], B['size'] / 2
FL = SPEC['floor']
HOLES = [(-18.0, -18.0), (18.0, -18.0), (18.0, 18.0)]   # world; design (18,-18), (-18,-18), (-18,18)


def boss_shift(w):
    w = w.cut(box(bx_ - bh - 0.01, bx_ + bh + 0.01, by_ - bh - 0.01, by_ + bh + 0.01, FL + 0.001, B['top_z'] + 0.01))
    return w.union(box(bx_ - bh, bx_ + bh, by_ - bh - 1.5, by_ + bh - 1.5, FL - 0.01, B['top_z']))


def r7f_tray_posts(w):
    for x, y in HOLES:
        w = w.union(cyl(x, y, ST['z_bot'] - 0.6, ST['z_bot'], 4.4)).cut(cyl(x, y, ST['z_bot'] - 1, ST['z_bot'] + 1, 2.4))
    return w


def lid_no_neck(w):
    for x, y in HOLES:
        w = w.union(cyl(x, y, ST['z_top'], ST['z_top'] + 1.4, 3.8)).cut(cyl(x, y, ST['z_top'] - 1, ST['z_top'] + 2, 1.6))
    return w


ANT, PK = SPEC['antenna'], SPEC['sma_pocket']
PCB_TXT = open(A.pcb, encoding='utf-8').read()


def lid_posts_down(z_from):
    def fn(w):
        for x, y in HOLES:
            w = w.union(cyl(x, y, ST['z_top'] + z_from, ST['z_top'] + 1.0, 3.2)).cut(cyl(x, y, ST['z_top'] - 1, ST['z_top'] + 2, 1.6))
        return w
    return fn


def sma_moved(w):
    w = w.union(box(-21.0, -20.25, ANT['y'] - 3.5, ANT['y'] + 3.5, ANT['z'] - 3.5, ANT['z'] + 3.5))
    return w.cut(cq.Workplane('YZ').circle(ANT['hole'] / 2).extrude(3).translate((-22, ANT['y'] + 3.0, ANT['z'])))


HO = SPEC['hdmi_opening']
Y_FRONT = -SPEC['envelope'][1] / 2


def hdmi_rect(w):
    """Back to the plain 16.2 x 6.8 rectangle: the cut corners are machined away."""
    return w.cut(box(HO['x'] - HO['w'] / 2, HO['x'] + HO['w'] / 2, Y_FRONT - 1, Y_FRONT + SPEC['wall'] + 1, HO['z'] - HO['h'] / 2, HO['z'] + HO['h'] / 2))


def hdmi_upside_down(w):
    """The same outline turned over: narrow edge toward the floor, as for a receptacle on the top side of a board."""
    a, b, c = HO['w'] / 2, HO['h'] / 2, HO['chamfer']
    w = w.union(box(HO['x'] - a - 0.5, HO['x'] + a + 0.5, Y_FRONT, Y_FRONT + SPEC['wall'], HO['z'] - b - 0.3, HO['z'] + b + 0.3))
    pts = [(-a, b), (a, b), (a, -b + c), (a - c, -b), (-a + c, -b), (-a, -b + c)]
    return w.cut(cq.Workplane('XZ').polyline(pts).close().extrude(SPEC['wall'] + 2).translate((HO['x'], Y_FRONT + SPEC['wall'] + 1, HO['z'])))


def hdmi_cut_too_big(w):
    """Corners cut 3.2 mm instead of 1.8: the sloped edges come onto the shell."""
    a, b = HO['w'] / 2, HO['h'] / 2
    for s in (-1, 1):
        tri = [(s * a, b), (s * (a - 3.2), b), (s * a, b - 3.2)]
        w = w.union(cq.Workplane('XZ').polyline(tri).close().extrude(SPEC['wall']).translate((HO['x'], Y_FRONT + SPEC['wall'], HO['z'])))
    return w


def board_edit(pairs):
    """A board fault: the mutated .kicad_pcb goes into the case copy as _board.kicad_pcb and the run uses it."""
    def mod(d):
        t = PCB_TXT
        for rx, new in pairs:
            n = len(re.findall(rx, t))
            assert n >= 1, (rx, n)
            t = re.sub(rx, new, t)
        open(f'{d}/_board.kicad_pcb', 'w', encoding='utf-8', newline=chr(10)).write(t)
    return mod


MUT = [
    ('control', lambda d: None, None),
    ('boss 0.5 mm too tall (gap 0.0 to U7)', edit('tray', lambda w: w.union(box(bx_ - bh, bx_ + bh, by_ - bh, by_ + bh, B['top_z'] - 0.01, B['top_z'] + 0.5))), r'boss leaves 0\.5'),
    ('boss shifted 1.5 mm toward C21/R21/R60 (world -y)', edit('tray', boss_shift), r'tray boss under U7 is 5\.6 x 5\.6, centred'),
    ('tray post added back at design (18, 18) = world (-18, 18)', edit('tray', lambda w: w.union(cyl(-18.0, 18.0, FL - 0.01, ST['z_bot'], 4.4))), r'tray touches the PCB only at the three screw holes'),
    ('+x wall of tray and lid 0.5 mm thicker (envelope 42.5)', both(edit('tray', lambda w: w.union(box(20.9, 21.5, -20.2, 20.2, 0, ST['split']))),
                                                                  edit('lid', lambda w: w.union(box(20.9, 21.5, -20.2, 20.2, ST['lid_z0'], SPEC['envelope'][2])))), r'outside envelope is exactly'),
    ('tray post tops back to the r7f 4.4 mm (no neck)', edit('tray', r7f_tray_posts), r'no tray metal within 0\.3 mm of non-GND copper'),
    ('lid post ends back to the full 3.8 mm (no neck)', edit('lid', lid_no_neck), r'no lid metal within 0\.3 mm of (non-GND copper|a part body)'),
    ('vent slot 1.4 x 3.8 cut in the -x wall', edit('tray', lambda w: w.cut(box(-22, -20, -6.0, -4.6, FL + 1.0, FL + 4.8))), r'-x wall is sealed'),
    ('vent slot 1.2 x 5 cut in the lid top', edit('lid', lambda w: w.cut(box(-0.6, 0.6, 18.0, 20.0, SPEC['envelope'][2] - 2, SPEC['envelope'][2] + 1))), r'lid top is sealed'),
    ('tray post end faces not masked', spec_edit(lambda sp: sp['masked'].pop('tray_post_end')), r'contact face that carries ground is masked'),
    ('tray-to-GND acceptance test dropped', spec_edit(lambda sp: sp.__setitem__('acceptance', [a for a in sp['acceptance'] if not a.startswith('tray')])), r'acceptance tests'),
    # ---- r8b
    ('lid posts reach the PCB again (two rigid seats)', edit('lid', lid_posts_down(0.0)), r'lid does not touch the PCB'),
    ('lid posts 0.3 mm too long (gap 0.6)', edit('lid', lid_posts_down(0.6)), r'lid posts leave 0\.9|working range'),
    ('SMA hole 3 mm toward J5', edit('tray', sma_moved), r'SMA hole in the -x wall is round'),
    ('HDMI opening back to a plain rectangle', edit('tray', hdmi_rect), r'HDMI opening has the receptacle shape'),
    ('HDMI opening upside down (narrow edge toward the floor)', edit('tray', hdmi_upside_down), r'HDMI opening has the receptacle shape|J2 opening in -y wall clears'),
    ('HDMI opening corners cut 3.2 mm', edit('tray', hdmi_cut_too_big), r'HDMI opening keeps|J2 opening in -y wall clears'),
    ('SMA floor pocket not machined', edit('tray', lambda w: w.union(box(PK['x0'], PK['x1'], PK['y0'], PK['y1'], PK['z0'], FL))), r'floor pocket clears the SMA hex'),
    ('card opening top back under the board (J7 pads and ESP_EN face the wall)', edit('tray', lambda w: w.union(box(20.25, 21.0, -2.2, 10.4, ST['z_bot'] - 0.05, ST['z_bot'] + SPEC['sd_relief']))), r'pushed 0\.35 mm against any wall'),
    ('antenna window cut in the back wall again', edit('tray', lambda w: w.cut(box(-19.0, -3.0, 20.0, 22.0, FL + 0.4, FL + 6.0))), r'\+y wall is sealed'),
    ('tray anodized outside only', spec_edit(lambda sp: sp['materials'].__setitem__('tray', sp['materials']['tray'].replace('all over, inside faces included', 'outside'))), r'tray is anodized inside'),
    ('washer 1.0 mm in the spec', spec_edit(lambda sp: sp['compliant']['washer'].__setitem__('t', 1.0)), r'names the same foam washer'),
    ('panel rule dropped', spec_edit(lambda sp: sp.pop('panel')), r'panel rule'),
    ('board: ATX_LED run back at y 119.68 (0.26 mm from the edge)', board_edit([(r'(?<=\s)119\.5(?=\))', '119.68')]), r'pushed 0\.35 mm against any wall'),
    ('board: SD_CMD_C via and In2 end back at x 80.30', board_edit([(r'\b80\.65(?=\s+93\.2798\b)', '80.3')]), r'inner-layer non-GND copper|pushed 0\.35 mm against any wall'),
]
only = {int(i) for i in A.only.split(',')} if A.only else None
rows = []
for i, (name, mod, rx) in enumerate(MUT):
    if only is not None and i not in only and i != 0:
        continue
    d = os.path.join(WORK, f'm{i}')
    shutil.copytree(A.case_dir, d)
    mod(d)
    pcb = f'{d}/_board.kicad_pcb' if os.path.exists(f'{d}/_board.kicad_pcb') else A.pcb
    p = subprocess.run([sys.executable, os.path.join(HERE, 'check_case.py'), d, '--design', A.design, '--pcb', pcb], capture_output=True, text=True, encoding='utf-8', errors='replace')
    fails = [l for l in p.stdout.splitlines() if l.startswith('FAIL')]
    if rx is None:
        ok = p.returncode == 0
        caught = 'passes' if ok else 'CONTROL FAILS'
    else:
        hit = [l for l in fails if re.search(rx, l)]
        ok = p.returncode != 0 and bool(hit)
        caught = hit[0] if hit else 'NOT CAUGHT (' + ('; '.join(fails)[:200] or p.stderr[-300:]) + ')'
    rows.append((ok, name, caught, len(fails)))
    print(f"{'ok ' if ok else 'BAD'} | {name} | {caught} | {len(fails)} FAIL lines", flush=True)
    if not ok and rx is None:
        break
bad = [r for r in rows if not r[0]]
txt = f'mutation run on {os.path.abspath(A.case_dir)}\n' + '\n'.join(f"{'ok ' if r[0] else 'BAD'} | {r[1]} | {r[2]} | {r[3]} FAIL lines" for r in rows) + \
      f'\n\n{len(rows)} runs, {len(bad)} bad\nMUTATION ' + ('ALL CAUGHT' if not bad else f'{len(bad)} BAD') + '\n'
if A.report:
    open(A.report, 'w', encoding='utf-8', newline='\n').write(txt)
print(txt)
shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if bad else 0)
