# -*- coding: utf-8 -*-
"""r7f: draws the copper of a board window, one panel per layer group, pads labelled ref.pad:net. Read-only.
usage: r7f_plot.py <board.kicad_pcb> <out.png> x0,y0,x1,y1 (design mm, origin at the board centre) [F,In2,B]"""
import os
import sys

sys.path.insert(0, 'D:/git/p4-kvm-box/analysis_r7f/si/scripts')
import brd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches
from shapely.geometry import box

pcb, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = [float(v) + 100 for v in sys.argv[3].split(',')]
layers = (sys.argv[4] if len(sys.argv) > 4 else 'F.Cu,In2.Cu,B.Cu').split(',')
B = brd.load(pcb)
win = box(x0, y0, x1, y1)
fig, axs = plt.subplots(1, len(layers), figsize=(9 * len(layers), 9 * (y1 - y0) / (x1 - x0)))
axs = axs if len(layers) > 1 else [axs]
pal = {}
cols = ['#d62728', '#1f77b4', '#2ca02c', '#9467bd', '#ff7f0e', '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#555555']
for ax, ly in zip(axs, layers):
    for net, kind, poly, lab in brd.copper(B, ly):
        if not poly.intersects(win):
            continue
        if net == 'GND':
            c, a = '#bbbbbb', 0.5
        else:
            c = pal.setdefault(net, cols[len(pal) % len(cols)])
            a = 0.75
        for g in getattr(poly, 'geoms', [poly]):
            if hasattr(g, 'exterior'):
                ax.fill(*g.exterior.xy, color=c, alpha=a, lw=0.3, ec='k' if kind == 'pad' else c)
        if kind == 'pad' and win.contains(poly.centroid):
            ax.text(poly.centroid.x, poly.centroid.y, f'{lab}\n{net[:10]}', fontsize=5, ha='center', va='center')
        elif kind != 'pad' and net != 'GND' and win.contains(poly.centroid) and poly.area > 0.05:
            ax.text(poly.centroid.x, poly.centroid.y, net[:10], fontsize=4, color='k', alpha=0.7)
    import json, os
    D = json.load(open(os.path.join(os.path.dirname(pcb), 'design.json'), encoding='utf-8'))
    side = 'F' if ly == 'F.Cu' else ('B' if ly == 'B.Cu' else None)
    for p in D['parts']:
        if side and p['side'] == side:
            b = p['bbox']
            ax.add_patch(matplotlib.patches.Rectangle((b[0] + 100, b[1] + 100), b[2] - b[0], b[3] - b[1], fill=False, ec='m', lw=0.8, ls='--'))
            if x0 < (b[0] + b[2]) / 2 + 100 < x1 and y0 < (b[1] + b[3]) / 2 + 100 < y1:
                ax.text((b[0] + b[2]) / 2 + 100, b[1] + 100.15, p['ref'], color='m', fontsize=6)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_aspect('equal')
    ax.grid(alpha=0.3)
    ax.set_xticks([v for v in range(int(x0), int(x1) + 1)])
    ax.set_xticklabels([str(v - 100) for v in range(int(x0), int(x1) + 1)], fontsize=6)
    ax.set_yticks([v for v in range(int(y0), int(y1) + 1)])
    ax.set_yticklabels([str(v - 100) for v in range(int(y0), int(y1) + 1)], fontsize=6)
    ax.set_title(ly)
fig.savefig(out, dpi=120, bbox_inches='tight')
print('wrote', out)
