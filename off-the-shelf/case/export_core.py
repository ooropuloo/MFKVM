# -*- coding: utf-8 -*-
"""Writes asm/core_board.stl and asm/core_parts.stl from the official FireBeetle STEP, coarse, for the page. Small parts are left out of the page only, the fit check uses all of them.
usage: export_core.py <firebeetle.step>"""
import os
import sys

import cadquery as cq
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
core = cq.importers.importStep(sys.argv[1]).val()
board, parts = [], []
kept = dropped = 0
for s in core.Solids():
    b = s.BoundingBox()
    v = b.xlen * b.ylen * b.zlen
    if b.xlen > 24 and b.ylen > 55 and b.zlen < 2:
        target = board
    elif v > 1.2:
        target = parts
    else:
        dropped += 1
        continue
    kept += 1
    vs, ts = s.tessellate(0.2, 0.9)
    target.append(trimesh.Trimesh(np.array([(p.x, p.y, p.z) for p in vs]), np.array(ts), process=False))
for name, lst in (('core_board', board), ('core_parts', parts)):
    m = trimesh.util.concatenate(lst)
    m.export(os.path.join(HERE, 'asm', name + '.stl'))
    print(name, len(lst), 'solids', len(m.faces), 'faces')
print('kept', kept, 'dropped from the page', dropped)
