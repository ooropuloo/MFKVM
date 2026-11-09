# -*- coding: utf-8 -*-
"""Builds the JLC package. Refuses when any check has not passed on this exact board file, or when the
files it is about to ship fail the solder mask check or the hole clearance check, or real part outlines overlap. Never writes over an existing package.

usage: fab_pack.py <out_dir> <target_dir>
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bodycheck
import drc_accept
import holecheck
import maskcheck

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT, DEST = sys.argv[1], sys.argv[2]
NAME = 'p4_kvm_mini'
KC = os.environ.get('KICAD_CLI', 'kicad-cli')
H = os.environ.get('KICAD_TOOL_HOME', os.path.expanduser('~/.kicad-tool-home'))
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=f'{H}/doc', KICAD_CONFIG_HOME=f'{H}/cfg', KICAD_CACHE_HOME=f'{H}/cache')
OX, OY = 100.0, 100.0

r = json.load(open(f'{OUT}/drc.json', encoding='utf-8'))
errs = [v for v in r['violations'] if v['severity'] == 'error']
ver = open(f'{OUT}/verify.out', encoding='utf-8').read()
# r7c: ERC counts only with real pin types. erc_check.py runs KiCad ERC, compares the schematic's pin types with data/pin_types.json and
# accepts a violation only through data/erc_waivers.json. Its report must name this exact schematic.
ercc = open(f'{OUT}/erc_check.out', encoding='utf-8').read() if os.path.exists(f'{OUT}/erc_check.out') else ''
gates = {
    'DRC errors': len(errs) == 0,
    # r7e: per instance, not per type (tools/drc_accept.py, REVIEW_r7d tool table)
    'DRC warnings only accepted instances (data/drc_accepted.json)': not drc_accept.check(r)[0],
    'unconnected': len(r['unconnected_items']) == 0,
    'schematic parity': len(r['schematic_parity']) == 0,
    'ERC check (typed pins) passed': 'ERC_CHECK PASS' in ercc,
    'ERC check ran on this exact schematic': 'SCHEMATIC sha256 ' + hashlib.sha256(open(f'{OUT}/{NAME}.kicad_sch', 'rb').read()).hexdigest() in ercc,
    'verify ALL PASS': 'RESULT ALL PASS' in ver,
    'verify ran the mask check': 'PASS MASKCHECK' in ver,
    'verify ran the hole check': 'PASS HOLECHECK' in ver,
    'verify ran the body check': 'PASS BODYCHECK' in ver,
    'verify ran on this exact board': 'BOARD sha256 ' + hashlib.sha256(open(f'{OUT}/{NAME}.kicad_pcb', 'rb').read()).hexdigest() in ver,
    # r7c: 5 V hot-plug peak at U2 VIN from tools/hotplug.py --design, run on this exact design.json
    # r7f: with the eFuse the line reads 'HOTPLUG WORST <V> at VBUS_IN, <V> at EN, U2 VIN <= 5.70 V OK' (tools/hotplug.py)
    '5V hot-plug simulation OK on this design': (lambda t: 'HOTPLUG WORST' in t and (('OK (<= 5.8 V)' in t) or re.search(r'HOTPLUG WORST .* OK$', t, re.M) is not None) and 'sha256 ' + hashlib.sha256(open(f'{OUT}/design.json', 'rb').read()).hexdigest() in t)(
        open(f'{OUT}/hotplug.out', encoding='utf-8').read() if os.path.exists(f'{OUT}/hotplug.out') else ''),
    'target has no package yet': not os.path.exists(f'{DEST}/{NAME}_gerber.zip'),
}
for k, v in gates.items():
    print(('ok   ' if v else 'FAIL ') + k)
if not all(gates.values()):
    print('REFUSED: nothing written')
    sys.exit(2)

body = bodycheck.check(OUT)
print(('ok   ' if body['ok'] else 'FAIL ') + 'bodies: ' + bodycheck.summary(body))
if not body['ok']:
    bodycheck.report(body)
    print('REFUSED: nothing written')
    sys.exit(2)

STAGE = tempfile.mkdtemp(prefix='fab_pack_')
pcb = f'{OUT}/{NAME}.kicad_pcb'
layers = 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'
for args in ([KC, 'pcb', 'export', 'gerbers', '--layers', layers, '--no-protel-ext', '-o', STAGE, pcb],
             [KC, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', '-o', STAGE + '/', pcb]):
    p = subprocess.run(args, env=ENV, capture_output=True, text=True, errors='replace')
    if p.returncode:
        print(args[3], p.stdout[-400:], p.stderr[-400:])
        sys.exit(3)

# the files that ship are the files measured
mask = maskcheck.check(STAGE)
print(('ok   ' if mask['ok'] else 'FAIL ') + 'mask: ' + maskcheck.summary(mask))
if not mask['ok']:
    maskcheck.report(mask)
    shutil.rmtree(STAGE)
    print('REFUSED: nothing written')
    sys.exit(2)
try:
    hole = holecheck.check(STAGE)
except maskcheck.GerberError as ex:
    print('FAIL hole check could not parse:', ex)
    shutil.rmtree(STAGE)
    print('REFUSED: nothing written')
    sys.exit(2)
print(('ok   ' if hole['ok'] else 'FAIL ') + 'holes: ' + holecheck.summary(hole))
if not hole['ok']:
    holecheck.report(hole)
    shutil.rmtree(STAGE)
    print('REFUSED: nothing written')
    sys.exit(2)
os.makedirs(DEST, exist_ok=True)
shutil.rmtree(f'{DEST}/gerber', ignore_errors=True)
shutil.move(STAGE, f'{DEST}/gerber')
with open(f'{DEST}/mask_report.txt', 'w', encoding='utf-8') as f:
    maskcheck.report(mask, f)
with open(f'{DEST}/hole_report.txt', 'w', encoding='utf-8') as f:
    holecheck.report(hole, f)
with open(f'{DEST}/body_report.txt', 'w', encoding='utf-8') as f:
    bodycheck.report(body, f)

d = json.load(open(f'{OUT}/design.json', encoding='utf-8'))
parts = d['parts']
rows = defaultdict(list)
for p in parts:
    if p['dnp'] or p['consign'] or not p['lcsc']:
        continue
    rows[(p['value'], p['lib'], p['lcsc'])].append(p['ref'])
with open(f'{DEST}/BOM_JLC.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for (val, lib, lc), refs in sorted(rows.items(), key=lambda x: x[0][2]):
        w.writerow([val, ','.join(sorted(refs)), lib, lc])
# JLC's part library has its own 0 degree for these parts, so the KiCad angle lands them wrong.
# Checked 2026-11-07 in JLC's placement preview against pin 1 in the KiCad board; re-check if a part changes.
# r7: U5 is gone (its 0 was the one confirmed in the JLC 3D preview for C2871228). NOT CHECKED in a JLC preview, see R7_REPORT.md:
# U15 (C78988 on the top side; U2 is the same part on the bottom at 270), L2, C65-C68, R61-R63, R65 (new), U6 (now C201698), R28 (moved, same part).
# r7e: the angles come from data/jlc_offsets.json as offsets (CPL = KiCad + offset), so rotating a part in the layout keeps its CPL right;
# tools/cpl_pin1.py checks the written CPL against the same file. Same values as r7d's fixed table (U15 0, U2/U4/Q1/U10-U12 270, J7 90).
_off = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'jlc_offsets.json'), encoding='utf-8'))
_offs = {r: v['offset'] for r, v in {**_off['verified'], **_off['unverified_assumption']}.items()}
JLC_ROT = {p['ref']: (p['r'] + _offs[p['ref']]) % 360 for p in parts if p['ref'] in _offs}
with open(f'{DEST}/CPL_JLC.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for p in parts:
        if p['dnp'] or p['consign'] or not p['lcsc']:
            continue
        w.writerow([p['ref'], f"{p['x'] + OX:.3f}mm", f"{-(p['y'] + OY):.3f}mm", 'Top' if p['side'] == 'F' else 'Bottom', f"{JLC_ROT.get(p['ref'], p['r'] % 360):g}"])
with open(f'{DEST}/CONSIGNED_AND_NOT_FITTED.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Ref', 'Value', 'Handling', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for p in parts:
        if p['consign']:
            w.writerow([p['ref'], p['value'], 'Not in BOM, not placed by JLC: the customer solders it by hand after assembly (pads keep solder paste). Waveshare ESP32-P4-Module base, SKU 28101; R99 on the module must stay fitted', f"{p['x'] + OX:.3f}mm", f"{-(p['y'] + OY):.3f}mm", 'Top', f"{p['r'] % 360:g}"])
        elif p['dnp'] and p['lib'] != 'TP_1.0':
            w.writerow([p['ref'], p['value'], 'Do not fit (no paste on its pads)', f"{p['x'] + OX:.3f}mm", f"{-(p['y'] + OY):.3f}mm", 'Top' if p['side'] == 'F' else 'Bottom', f"{p['r'] % 360:g}"])

zp = f'{DEST}/{NAME}_gerber.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in sorted(os.listdir(f'{DEST}/gerber')):
        z.write(f'{DEST}/gerber/{n}', n)

# read the Gerbers back
names = sorted(os.listdir(f'{DEST}/gerber'))
print('files', len(names))
edge = next(n for n in names if 'Edge_Cuts' in n)
t = open(f'{DEST}/gerber/{edge}', encoding='utf-8', errors='replace').read()
scale = 1e6 if '%FSLAX46Y46*%' in t else 1e5
pts = [(int(a) / scale, int(b) / scale) for a, b in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]', t)]
xs, ys = [a for a, _ in pts], [b for _, b in pts]
print('outline from Gerber', round(max(xs) - min(xs), 3), 'x', round(max(ys) - min(ys), 3))
# r7c: the expected size is the board's own Edge.Cuts (40 x 45 since r7c), not a constant
_e = [(float(a), float(b)) for a, b in re.findall(r'\(gr_line\s+\(start ([-\d.]+) ([-\d.]+)\)(?:(?!gr_line).)*?\(layer "Edge.Cuts"\)', open(pcb, encoding='utf-8').read(), re.S)]
_ew, _eh = max(a for a, _ in _e) - min(a for a, _ in _e), max(b for _, b in _e) - min(b for _, b in _e)
print('outline from the board file', round(_ew, 3), 'x', round(_eh, 3))
assert abs(max(xs) - min(xs) - _ew) < 0.05 and abs(max(ys) - min(ys) - _eh) < 0.05
cu = [n for n in names if re.search(r'(F_Cu|In\d_Cu|B_Cu)\.', n)]
print('copper layers', cu)
assert len(cu) == 6
drills = [n for n in names if n.endswith('.drl')]
holes = 0
for n in drills:
    holes += len(re.findall(r'^X-?[\d.]+Y-?[\d.]+', open(f'{DEST}/gerber/{n}', errors='replace').read(), re.M))
print('drill files', drills, 'holes', holes)
print('BOM lines', len(rows), 'placed parts', sum(len(v) for v in rows.values()))
# everything else a reader of the package needs, so it cannot drift from the Gerbers
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shutil.copy(f'{OUT}/verify.out', f'{DEST}/verify_report.txt')
shutil.copy(f'{ROOT}/README.md', f'{DEST}/README.md')
shutil.copy(f'{ROOT}/firmware/p4_kvm_mini.defaults', DEST)
# the case STLs are not packaged: gen_case.py is mirrored in x against the board, see README.md
p = subprocess.run([KC, 'sch', 'export', 'pdf', '-o', f'{DEST}/{NAME}_schematic.pdf', f'{OUT}/{NAME}.kicad_sch'], env=ENV, capture_output=True, text=True, errors='replace')
print('schematic pdf', 'ok' if p.returncode == 0 else p.stderr[-200:])
for side in ('top', 'bottom'):
    p = subprocess.run([KC, 'pcb', 'render', '--side', side, '--width', '1400', '--height', '1400', '--quality', 'high', '--background', 'opaque', '-o', f'{DEST}/board_{side}.png', pcb], env=ENV, capture_output=True, text=True, errors='replace')
    print('render', side, 'ok' if p.returncode == 0 else p.stderr[-200:])
sha = hashlib.sha256(open(zp, 'rb').read()).hexdigest()
open(f'{DEST}/SHA256.txt', 'w').write(f'{sha}  {NAME}_gerber.zip\n')
print('package', zp, os.path.getsize(zp), 'bytes sha256', sha)
print('RELEASE WRITTEN')
