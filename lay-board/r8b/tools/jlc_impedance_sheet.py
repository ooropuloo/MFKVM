# -*- coding: utf-8 -*-
"""Impedance sheet for the JLC order: table (xlsx) and a picture of where the controlled traces are (jpg)."""
import os, re, sys, io, collections, zipfile, hashlib, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import openpyxl

V2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PCB = f'{V2}/out/p4_kvm_mini.kicad_pcb'
OUT = f'{V2}/fab_r8b'
s = io.open(PCB, encoding='utf-8').read()
seg = re.compile(r'\(segment\s+\(start ([\d.\-]+) ([\d.\-]+)\)\s+\(end ([\d.\-]+) ([\d.\-]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]*)"\)')
S = [(float(a), float(b), float(c), float(d), float(w), ly, n) for a, b, c, d, w, ly, n in seg.findall(s)]
print(len(S), 'segments')
by = collections.defaultdict(lambda: collections.defaultdict(float))
for a, b, c, d, w, ly, n in S:
    by[(ly, w)][n] += ((a - c) ** 2 + (b - d) ** 2) ** 0.5
for k in sorted(by):
    if k[1] in (0.127, 0.18) or any('LNA' in n or 'RF' in n for n in by[k]):
        print(k, {n: round(v, 2) for n, v in sorted(by[k].items())})
if len(sys.argv) < 2:
    sys.exit()

CLS = [('100 ohm differential, 0.127 / 0.198 mm', '#d62728', lambda w, n: abs(w - 0.127) < 1e-6 and (n.startswith('CSI_') or n in ('CK_P', 'CK_N', 'D0_P', 'D0_N', 'D1_P', 'D1_N', 'D2_P', 'D2_N'))),
       ('90 ohm differential, 0.18 / 0.32 mm', '#1f77b4', lambda w, n: abs(w - 0.18) < 1e-6 and n in ('USB_DP', 'USB_DN')),
       ('50 ohm single-ended, 0.15 mm (LNA_OUT)', '#2ca02c', lambda w, n: n == 'LNA_OUT')]
xs = [v for a, b, c, d, w, ly, n in S for v in (a, c)]
ys = [v for a, b, c, d, w, ly, n in S for v in (b, d)]
cx, cy = 100.0, 100.0
fig, axes = plt.subplots(1, 2, figsize=(16, 8.6), dpi=150)
for ax, (ly, title) in zip(axes, (('F.Cu', 'L1 Top (viewed from top), reference L2 GND'), ('B.Cu', 'L6 Bottom (viewed from top, not mirrored), reference L5 GND'))):
    ax.add_collection(LineCollection([[(a, b), (c, d)] for a, b, c, d, w, l, n in S if l == ly], colors='#c8c8c8', linewidths=0.6))
    for name, col, f in CLS:
        sel = [[(a, b), (c, d)] for a, b, c, d, w, l, n in S if l == ly and f(w, n)]
        ax.add_collection(LineCollection(sel, colors=col, linewidths=2.0, label=f'{name}: {len(sel)} segments'))
    ax.plot([cx - 20, cx + 20, cx + 20, cx - 20, cx - 20], [cy - 20, cy - 20, cy + 20, cy + 20, cy - 20], color='k', lw=1)
    ax.set_xlim(cx - 21.5, cx + 21.5)
    ax.set_ylim(cy + 21.5, cy - 21.5)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=12)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.15), fontsize=10, frameon=False)
    ax.set_xticks([]); ax.set_yticks([])
fig.suptitle('MF KVM R8B  40 x 40 mm  stackup JLC06121H-3313  impedance-controlled traces (coloured); other traces grey', fontsize=13, y=0.975)
fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.14, wspace=0.04)
fig.savefig(f'{OUT}/impedance_positions.jpg', pil_kwargs={'quality': 90})

nets = lambda ly, f: ', '.join(sorted({n for a, b, c, d, w, l, n in S if l == ly and f(w, n)}))
rows = [('No', 'Signal layer', 'Reference layer', 'Impedance type', 'Target (ohm)', 'Tolerance', 'Trace width (mm)', 'Trace spacing in pair (mm)', 'Gap to coplanar GND (mm)', 'Nets')]
i = 0
for ly, L, ref in (('F.Cu', 'L1 (Top)', 'L2 (GND)'), ('B.Cu', 'L6 (Bottom)', 'L5 (GND)')):
    for (name, col, f), typ, z, w, sp, gap in zip(CLS, ('Differential', 'Differential', 'Single-ended coplanar'), (100, 90, 50), (0.127, 0.18, 0.15), (0.198, 0.32, ''), ('', '', 0.25)):
        ns = nets(ly, f)
        if ns:
            i += 1
            rows.append((i, L, ref, typ, z, '+/-10%', w, sp, gap, ns))
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Impedance'
ws.append(['MF KVM R8B, 6 layers, 1.2 mm, stackup JLC06121H-3313. L1 Top, L2 GND, L3 signal, L4 power, L5 GND, L6 Bottom.'])
ws.append(['No impedance-controlled traces on L3 or L4. Please adjust trace width to meet the target and keep the pair pitch. Positions: see impedance_positions.jpg.'])
ws.append(['The 50 ohm trace (LNA_OUT) is very short; if it cannot be controlled, please ignore that row.'])
ws.append([])
for r in rows:
    ws.append(list(r))
for col, wd in zip('ABCDEFGHIJ', (5, 13, 15, 22, 12, 10, 16, 24, 24, 90)):
    ws.column_dimensions[col].width = wd
wb.save(f'{OUT}/impedance_table.xlsx')
for r in rows:
    print(r)

src, dst = f'{OUT}/p4_kvm_mini_gerber.zip', f'{OUT}/p4_kvm_mini_gerber_r8b_JLC.zip'
shutil.copyfile(src, dst)
with zipfile.ZipFile(dst, 'a', zipfile.ZIP_DEFLATED) as z:
    z.write(f'{OUT}/impedance_table.xlsx', 'impedance_table.xlsx')
    z.write(f'{OUT}/impedance_positions.jpg', 'impedance_positions.jpg')
a, b = zipfile.ZipFile(src), zipfile.ZipFile(dst)
assert all(a.read(n) == b.read(n) for n in a.namelist()) and len(b.namelist()) == len(a.namelist()) + 2
print('gerbers identical to', src, '; upload zip sha256', hashlib.sha256(open(dst, 'rb').read()).hexdigest())
