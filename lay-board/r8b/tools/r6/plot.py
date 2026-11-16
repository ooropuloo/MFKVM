# -*- coding: utf-8 -*-
"""usage: plot.py <pcb> <png> <layer> x0 x1 y0 y1 [plane layer]: top-down picture of one copper layer with labels, in board mm."""
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import numpy as np
from shapely.geometry import box

import brd

pcb, png, layer = sys.argv[1:4]
x0, x1, y0, y1 = map(float, sys.argv[4:8])
B = brd.load(pcb)
fig, ax = plt.subplots(figsize=(13, 13 * (y1 - y0) / (x1 - x0)), dpi=100)


def patch(g, **kw):
    for p in getattr(g, 'geoms', [g]):
        if p.geom_type != 'Polygon' or p.is_empty:
            continue
        v, c = [], []
        for r in [p.exterior] + list(p.interiors):
            xy = np.array(r.coords)
            v += list(map(tuple, xy))
            c += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(v, c), **kw))


vp = box(x0, y0, x1, y1)
for net in ('GND', '3V3'):
    g = brd.zone_geom(B, net, layer)
    if not g.is_empty:
        patch(g.intersection(vp), facecolor='#cfeacf' if net == 'GND' else '#f3dede', edgecolor='#88aa88', lw=0.3)
scale = 13 * 72 / (x1 - x0)
for s in B['segs']:
    if s['layer'] == layer:
        ax.plot([s['a'][0], s['b'][0]], [s['a'][1], s['b'][1]], color='#2ca02c' if s['net'] == 'GND' else '#1f77b4', lw=s['w'] * scale * 0.95, solid_capstyle='round', alpha=0.8)
        if x0 < s['a'][0] < x1 and y0 < s['a'][1] < y1:
            ax.text((s['a'][0] + s['b'][0]) / 2, (s['a'][1] + s['b'][1]) / 2, s['net'], fontsize=5, color='#114')
for q in B['pads']:
    if layer in brd.pad_layers(q) and x0 - 2 < q['x'] < x1 + 2 and y0 - 2 < q['y'] < y1 + 2:
        patch(brd.pad_poly(q), facecolor='#2ca02c' if q['net'] == 'GND' else '#888888', edgecolor='k', lw=0.3, alpha=0.6)
        ax.text(q['x'], q['y'], f"{q['ref']}.{q['num']}", fontsize=6, ha='center', va='center')
for v in B['vias']:
    if x0 < v['x'] < x1 and y0 < v['y'] < y1:
        ax.add_patch(plt.Circle((v['x'], v['y']), v['size'] / 2, fill=False, ec='#2ca02c' if v['net'] == 'GND' else 'k', lw=1))
        ax.text(v['x'], v['y'], v['net'][:7], fontsize=4.5, ha='center', va='center', color='#a00')
ax.set_xlim(x0, x1)
ax.set_ylim(y1, y0)
ax.set_aspect('equal')
ax.grid(alpha=0.3)
ax.set_title(f'{layer}: seen from the top of the board')
fig.tight_layout()
fig.savefig(png)
