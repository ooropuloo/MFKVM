# -*- coding: utf-8 -*-
"""Dumps pad geometry from official KiCad footprint files into one JSON, and prints it for review."""
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
out = {}
R = re.compile(r'\(pad\s+"?([^"\s]*)"?\s+(\w+)\s+(\w+)\s+\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)\s+\(size\s+([-\d.]+)\s+([-\d.]+)\)(?:\s+\(drill\s+(oval\s+)?([-\d.]+)(?:\s+([-\d.]+))?\))?', re.S)
for f in sorted(glob.glob(sys.argv[1] + '/*.kicad_mod')):
    s = open(f, encoding='utf-8').read()
    if not s.lstrip().startswith(('(footprint', '(module')):
        continue
    p = [dict(n=m[1], kind=m[2], shape=m[3], x=float(m[4]), y=float(m[5]), a=float(m[6] or 0), w=float(m[7]), h=float(m[8]), d1=float(m[10] or 0), d2=float(m[11] or 0)) for m in R.finditer(s)]
    name = os.path.basename(f)[:-10]
    out[name] = p
    print(name, len(p))
    print('  ', [(q['n'], q['kind'][:2], q['x'], q['y'], q['w'], q['h'], q['a']) for q in p][:14])
    L = re.findall(r'\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)', s)
    if L:
        print('   graphics x', min(float(a) for t in L for a in (t[0], t[2])), max(float(a) for t in L for a in (t[0], t[2])), 'y', min(float(a) for t in L for a in (t[1], t[3])), max(float(a) for t in L for a in (t[1], t[3])))
json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'))
