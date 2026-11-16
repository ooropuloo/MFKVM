# -*- coding: utf-8 -*-
"""CPL rotation and pin 1 of every polarized part (r7e, REVIEW_r7d M1).

For each polarized part on the CPL (ICs, connectors, the crystal oscillator, polarized capacitors; plain R/C/L/FB/TP are not polarized):
  - pin 1 (A1 for the BGA, A1B12 for USB-C) from design.json, as an offset from the part centre in the JLC top preview (x right, y down,
    = KiCad screen) and in the JLC bottom preview (x mirrored);
  - pin 1 in the footprint's own frame (rotation and bottom mirror undone; the convention is checked: every part of one footprint gives the
    same vector whatever its angle and side);
  - the JLC angle offset (CPL = KiCad + offset) from data/jlc_offsets.json. Only parts a person verified in JLC's preview have one; for every
    other part the offset is UNKNOWN (not 0) and the row says CHECK IN PREVIEW.
FAIL when: a verified part's CPL angle is not KiCad + offset; its pin 1 (footprint frame) is not where it was when verified (footprint
changed); a polarized part is missing from the CPL; a polarized capacitor has pin 1 on GND or pin 2 off GND, or its + pin does not reach a
positive supply through at most one resistor (C69: + on 5V_DAMP, R68 to 5V, REVIEW_r7d M1).
usage: cpl_pin1.py <out dir> <CPL_JLC.csv> [--report file.md]       exit 1 on any FAIL
"""
import csv
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
out, cpl_path = sys.argv[1:3]
rep = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else None
d = json.load(open(f'{out}/design.json', encoding='utf-8'))
P = {p['ref']: p for p in d['parts']}
pp = d['padpos']
off = json.load(open(os.path.join(HERE, '..', 'data', 'jlc_offsets.json'), encoding='utf-8'))
VER = off['verified']
cpl = {r['Designator']: r for r in csv.DictReader(open(cpl_path, encoding='utf-8-sig'))}
NONPOLAR = re.compile(r'^(R|C|FB|L|TP)\d')
FIRST = {'U7': 'A1', 'J3': 'A1B12', 'J5': 'A1B12'}
POS_RAILS = {'5V', '3V3', 'V2V5', 'V1V2', 'HDMI_5V', 'HOST_VBUS'}


def pin1_board(ref):
    p = P[ref]
    k = f"{ref}.{FIRST.get(ref, '1')}"
    return pp[k][0] - p['x'], pp[k][1] - p['y'], k.split('.', 1)[1]


def pin1_local(ref):
    p = P[ref]
    dx, dy, _ = pin1_board(ref)
    if p['side'] == 'B':
        dx = -dx
    a = math.radians(p['r'])
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def word(dx, dy):
    h = '' if abs(dx) < 0.05 else ('right' if dx > 0 else 'left')
    v = '' if abs(dy) < 0.05 else ('down' if dy > 0 else 'up')
    return '-'.join(x for x in (v, h) if x) or 'centre'


rows, fails = [], []
polar = [p for p in d['parts'] if not p['dnp'] and not p['consign'] and p['lcsc'] and (not NONPOLAR.match(p['ref']) or p['lib'].startswith('CP_'))]
# the footprint-frame convention must give one vector per footprint, whatever the angle and side
by_lib = {}
for p in polar:
    by_lib.setdefault(p['lib'], []).append((p['ref'], tuple(round(v, 3) for v in pin1_local(p['ref']))))
for lib, v in by_lib.items():
    if max(math.dist(a[1], b[1]) for a in v for b in v) > 0.02:
        fails.append(f'{lib}: pin 1 in the footprint frame differs between {v} (rotation convention or footprint copies disagree)')
for p in sorted(polar, key=lambda p: p['ref']):
    r = p['ref']
    if r not in cpl:
        fails.append(f'{r}: polarized part not on the CPL')
        continue
    dx, dy, pin = pin1_board(r)
    lx, ly = pin1_local(r)
    kic = p['r'] % 360
    rot = float(cpl[r]['Rotation']) % 360
    top = f'{word(dx, dy)} ({dx:+.2f}, {dy:+.2f})'
    bot = f'{word(-dx, dy)} ({-dx:+.2f}, {dy:+.2f})' if p['side'] == 'B' else '-'
    v = VER.get(r)
    if v and v['lcsc'] == p['lcsc'] and v['side'] == p['side']:
        o = v['offset']
        st = 'OK (offset verified in JLC preview 2026-11-07)'
        if abs(((kic + o) % 360) - rot) > 0.01:
            st = f'FAIL: CPL {rot:g}, KiCad {kic:g} + verified offset {o} = {(kic + o) % 360:g}'
            fails.append(f'{r}: {st}')
        if math.dist((lx, ly), v['pin1_local']) > 0.05:
            st = f'FAIL: pin 1 in the footprint frame moved from {v["pin1_local"]} to ({lx:.3f}, {ly:.3f}) since the preview check'
            fails.append(f'{r}: {st}')
        o = f'{o}'
    else:
        o = 'UNKNOWN'
        st = 'CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say'
    rows.append((r, p['lcsc'], p['lib'], 'Top' if p['side'] == 'F' else 'Bottom', f'{kic:g}', f'{rot:g}', o, pin, p['nets'].get(pin, ''), top, bot, st))

# polarized capacitors: + is pin 1 (Panasonic POSCAP, IPC-7351 CAPMP), on the supply side, pin 2 on GND
for p in d['parts']:
    if not p['lib'].startswith('CP_'):
        continue
    n1, n2 = p['nets'].get('1'), p['nets'].get('2')
    reach = {n1} | {m for q in d['parts'] if q['lib'] in ('R0402', 'R0603', 'C0805', 'R0805') and q['ref'].startswith('R') and n1 in q['nets'].values() for m in q['nets'].values()}
    ok = n2 == 'GND' and n1 != 'GND' and bool(reach & POS_RAILS)
    if not ok:
        fails.append(f'{p["ref"]}: polarized capacitor pin 1 (+) on {n1}, pin 2 on {n2}: + must reach a supply ({sorted(reach)}), - must be GND')
    rows.append((p['ref'], p['lcsc'], p['lib'], '', '', '', '', '+/-', f'+ {n1}, - {n2}', '', '', 'polarity OK' if ok else 'FAIL polarity'))

hdr = '| Ref | LCSC | Land | Side | KiCad deg | CPL deg | JLC offset | Pin 1 | Net | Pin 1 in JLC top view (mm) | Pin 1 in JLC bottom view | Status |'
lines = [hdr, '|' + '---|' * 12] + ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows]
txt = '\n'.join(lines) + '\n\n' + ('\n'.join('FAIL ' + f for f in fails) + '\n' if fails else '') + \
      f"RESULT {'FAIL' if fails else 'PASS'}: {len(polar)} polarized parts, {sum('OK (' in r[-1] for r in rows)} with a verified JLC offset, " \
      f"{sum(r[6] == 'UNKNOWN' for r in rows)} UNKNOWN (check in JLC preview)\n"
if rep:
    open(rep, 'w', encoding='utf-8').write('# CPL rotation and pin 1 of polarized parts (tools/cpl_pin1.py)\n\n' + __doc__.split('usage')[0].strip() + '\n\n' + txt)
print(txt)
sys.exit(1 if fails else 0)
