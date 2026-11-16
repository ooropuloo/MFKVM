# -*- coding: utf-8 -*-
"""r7b M2: one row per placed part: CPL angle, KiCad angle, and where pin 1 must appear in JLC's placement preview.

Pin 1 is read from the saved board (pad "1", or A1 for the BGA, or the first pad of the connectors), as an offset from the part centre in
board coordinates seen from the top (x right, y toward the back wall = down in KiCad and in JLC's top preview). For bottom-side parts the
same offset is also given as seen in JLC's bottom preview, which shows the board flipped about the vertical axis (x mirrored).
The JLC angle convention is per LCSC part (r6/r7 history: C2871228 at 0 and C78988 at 270 on the same SOT-23-5 land), so nothing here
predicts JLC's angle; the table only says what the preview must show. "verified" means checked by a person in JLC's preview (2026-11-07).
usage: cpl_table.py <out dir> <CPL_JLC.csv> <output.md>
"""
import csv
import json
import math
import re
import sys

out, cpl_path, dest = sys.argv[1:4]
d = json.load(open(f'{out}/design.json', encoding='utf-8'))
P = {p['ref']: p for p in d['parts']}
pad = d['padpos']
cpl = {r['Designator']: r for r in csv.DictReader(open(cpl_path, encoding='utf-8-sig'))}
VERIFIED = {'U2', 'U4', 'Q1', 'U10', 'U11', 'U12', 'J7'}
NONPOLAR = re.compile(r'^(R|C|FB|L)\d')
R7C_NEW = {'C69': 'new in r7c: polarized (pin 1 = +, silk + beside it)', 'R68': 'new in r7c', 'U12': 'moved 0.08 mm in r7c', 'C20': 'moved 0.05 mm in r7c', 'C24': 'moved 0.05 mm in r7c', 'R28': 'moved 0.08 mm in r7c'}
# r7d (CSI option B): the TC358743 group moved 2.5 mm toward -x; C13, C15, C16, C17 and C21 have new places (R7D_REPORT.md)
for _r in ('U7', 'C18', 'C22', 'C23', 'C24', 'C25', 'C26', 'C27', 'R20'):
    R7C_NEW[_r] = R7C_NEW.get(_r, '') + ('; ' if _r in R7C_NEW else '') + 'moved -2.5 mm in x in r7d'
for _r in ('C13', 'C15', 'C16', 'C17', 'C21'):
    R7C_NEW[_r] = 'new place and rotation in r7d'
FIRST = {'U7': 'A1', 'J3': 'A1B12', 'J5': 'A1B12', 'J2': '1', 'J7': '1', 'J8': '1'}


def word(dx, dy):
    h = '' if abs(dx) < 0.05 else ('right' if dx > 0 else 'left')
    v = '' if abs(dy) < 0.05 else ('down' if dy > 0 else 'up')
    return '-'.join(x for x in (v, h) if x) or 'centre'


rows = []
for ref, r in cpl.items():
    p = P[ref]
    k = f"{ref}.{FIRST.get(ref, '1')}"
    if k not in pad:
        k = next(x for x in pad if x.startswith(ref + '.'))
    dx, dy = pad[k][0] - p['x'], pad[k][1] - p['y']
    kic = p['r'] % 360
    jlc = float(r['Rotation'])
    side = 'Top' if p['side'] == 'F' else 'Bottom'
    top = f'{word(dx, dy)} ({dx:+.2f}, {dy:+.2f})'
    bot = f'{word(-dx, dy)} ({-dx:+.2f}, {dy:+.2f})' if side == 'Bottom' else ''
    pol = not NONPOLAR.match(ref) or p['lib'].startswith('CP_')
    status = ('CHECK in preview (seen right on 2026-11-07; re-check, review M2)' if ref in VERIFIED else 'CHECK in preview') if pol else 'non-polar, either way works'
    status += ('; ' + R7C_NEW[ref]) if ref in R7C_NEW else ''
    rows.append((0 if pol else 2, ref, p['lcsc'], p['lib'], side, kic, jlc, (jlc - kic) % 360, k.split('.')[1], top, bot, status))
rows.sort()
with open(dest, 'w', encoding='utf-8') as f:
    f.write('# CPL rotation and pin-1 check table (r7d)\n\n')
    f.write(__doc__.split('usage')[0].strip() + '\n\n')
    f.write('| Ref | LCSC | Land | Side | KiCad deg | CPL deg | CPL-KiCad | Pin | Pin 1 from centre, top view (mm) | Same pin in JLC bottom view | Status |\n|---|---|---|---|---:|---:|---:|---|---|---|---|\n')
    for _, *x in rows:
        f.write('| ' + ' | '.join(str(v) for v in x) + ' |\n')
print('rows', len(rows), 'to check', sum(1 for r in rows if r[0] == 0))
