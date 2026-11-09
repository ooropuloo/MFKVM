# -*- coding: utf-8 -*-
"""r7f gate: parts next to the module U1, which the user solders by hand with an iron after assembly.
Requirement (team lead, 2026-11-09): every top-side pad within 1 mm of a U1 pad (any part; the LCD 0201s R80/R81 included) is >= 0.2 mm
(edge to edge) from every U1 pad, with a solder-mask web between them
(the mask openings, pad + the board's pad_to_mask_clearance + any pad margin, must not touch: web >= 0.1 mm, JLC green web); and the
two resistors' pads >= 0.15 mm from each other.
Reads the saved or generated .kicad_pcb only (pads rotated and placed as KiCad sees them).
usage: hand_solder_gap.py <board.kicad_pcb>       exit 1 on any violation
"""
import re
import sys

sys.path.insert(0, 'D:/git/p4-kvm-box/analysis_r7f/si/scripts')
import brd

PCB = sys.argv[1]
txt = open(PCB, encoding='utf-8').read()
m = re.search(r'\(pad_to_mask_clearance ([-\d.]+)\)', txt)
MASK = float(m[1]) if m else 0.0
B = brd.load(PCB)
pads = {(q['ref'], q['num']): q for q in B['pads']}
RS, U = ('R80', 'R81'), 'U1'
GAP, WEB, MUTUAL = 0.2, 0.1, 0.15
fails, lines = [], []
# every top-side copper pad (any part except U1 and the mounting holes) within 1 mm of a U1 pad (team lead, 2026-11-09: the risk applies
# to everything next to U1, not only the 0201s)
u1 = [u for k, u in pads.items() if k[0] == U]
u1g = [(brd.pad_poly(u), u['num']) for u in u1]
seen = 0
for (r, n), q in sorted(pads.items()):
    if r == U or re.match(r'H\d+$', r) or 'F.Cu' not in brd.pad_layers(q):
        continue
    g = brd.pad_poly(q)
    d, un = min(((ug.distance(g), num) for ug, num in u1g), key=lambda t: t[0])
    if d >= 1.0:
        continue
    seen += 1
    ug = next(x for x, num in u1g if num == un)
    web = ug.buffer(MASK).distance(g.buffer(MASK))
    lines.append(f'{r}.{n} ({q["x"] - 100:.3f}, {q["y"] - 100:.3f}): nearest U1 pad U1.{un} {d:.3f} mm, mask web {web:.3f} mm')
    if d < GAP - 1e-6:
        fails.append(f'{r}.{n} is {d:.3f} mm from U1.{un} (limit {GAP})')
    if web < WEB - 1e-6:
        fails.append(f'{r}.{n}: mask web to U1.{un} {web:.3f} mm (limit {WEB})')
for r in RS:
    if len([k for k in pads if k[0] == r]) != 2:
        fails.append(f'{r}: missing')
lines.append(f'{seen} top-side pads within 1 mm of a U1 pad checked')
mut = min((brd.pad_poly(a).distance(brd.pad_poly(b)) for (ka, a) in pads.items() if ka[0] == RS[0] for (kb, b) in pads.items() if kb[0] == RS[1]), default=None)
lines.append(f'R80 to R81 pad to pad {mut:.3f} mm' if mut is not None else 'R80/R81 missing')
if mut is None or mut < MUTUAL - 1e-6:
    fails.append(f'R80 to R81 {mut} mm (limit {MUTUAL})')
print(f'board {PCB}; pad_to_mask_clearance {MASK}')
print('\n'.join(lines))
for f in fails:
    print('FAIL', f)
print('RESULT', 'FAIL' if fails else 'PASS')
sys.exit(1 if fails else 0)
