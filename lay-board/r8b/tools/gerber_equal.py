# -*- coding: utf-8 -*-
"""Are two Gerber/drill sets the same artwork? Text comparison fails on harmless differences (creation date, object order,
aperture numbering), so this compares what the factory makes:
  - every layer: union of all copper/mask/paste/silk shapes, symmetric difference area must be under 1e-6 mm2;
  - every layer: the multiset of (aperture function, pad ref.pin, net, centroid to 1 um, area to 1e-6 mm2) per object;
  - drill files: the multiset of (tool diameter, x, y) per hole, plated and non-plated separately.

usage: gerber_equal.py <dir or zip A> <dir or zip B>      exit 0 equal, 1 different
"""
import collections
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.ops import unary_union

import maskcheck

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def files(src):
    if os.path.isdir(src):
        return {n: open(os.path.join(src, n), encoding='utf-8', errors='replace').read() for n in os.listdir(src) if n.endswith(('.gbr', '.drl'))}
    z = zipfile.ZipFile(src)
    return {os.path.basename(n): z.read(n).decode('utf-8', 'replace') for n in z.namelist() if n.endswith(('.gbr', '.drl'))}


def drill(text):
    tools, cur, out = {}, None, collections.Counter()
    for line in text.splitlines():
        m = re.match(r'T(\d+)C([\d.]+)', line)
        if m:
            tools[m[1]] = float(m[2])
            continue
        m = re.match(r'T(\d+)$', line.strip())
        if m:
            cur = m[1]
            continue
        m = re.match(r'X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?', line.strip())
        if m and cur:
            out[(tools.get(cur), m[0])] += 1
    return out


def layer_sig(text):
    objs = maskcheck.parse(text)
    sig = collections.Counter((o['func'], o['pad'] and f'{o["pad"][0]}.{o["pad"][1]}', o['net'], round(o['geom'].centroid.x, 3), round(o['geom'].centroid.y, 3), round(o['geom'].area, 6)) for o in objs if not o['geom'].is_empty)
    return sig, unary_union([o['geom'] for o in objs])


def compare(a, b):
    A, B = files(a), files(b)
    notes = []
    if sorted(A) != sorted(B):
        notes.append(f'file lists differ: only A {sorted(set(A) - set(B))}, only B {sorted(set(B) - set(A))}')
    for n in sorted(set(A) & set(B)):
        if n.endswith('.drl'):
            if drill(A[n]) != drill(B[n]):
                notes.append(f'{n}: holes differ')
            continue
        if 'drl_map' in n or n.endswith('job.gbrjob'):
            continue
        sa, ua = layer_sig(A[n])
        sb, ub = layer_sig(B[n])
        x = ua.symmetric_difference(ub).area
        if x > 1e-6 or sa != sb:
            notes.append(f'{n}: area differs by {x:.6f} mm2, objects only in A {sum((sa - sb).values())}, only in B {sum((sb - sa).values())}')
    return notes, len(set(A) & set(B))


if __name__ == '__main__':
    notes, n = compare(sys.argv[1], sys.argv[2])
    for x in notes:
        print('DIFF', x)
    print(f'{n} files compared;', 'EQUAL' if not notes else f'{len(notes)} DIFFERENT')
    sys.exit(1 if notes else 0)
