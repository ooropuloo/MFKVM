# -*- coding: utf-8 -*-
"""Lists what the router added: every wire and via in an SES that is not marked (type protect), per net, with layer and length.

r7 hands the r6 routing to Freerouting as protected wiring, so anything unprotected in its output is new copper.
usage: ses_new.py <routed.ses>
"""
import math
import re
import sys
from collections import defaultdict

s = open(sys.argv[1], encoding='utf-8').read()
res = float(re.search(r'\(resolution um (\d+)\)', s).group(1))
k = 1 / res / 1000.0
i = s.find('network_out')
body = s[i:]
nets = [(m.start(), m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', body)]
new = defaultdict(list)
for j, (a, n) in enumerate(nets):
    block = body[a:nets[j + 1][0] if j + 1 < len(nets) else len(body)]
    for m in re.finditer(r'\(wire\s*\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)\s*(\(type protect\))?', block):
        if m.group(4):
            continue
        v = [int(t) for t in m.group(3).split()]
        pts = [(v[t] * k, -v[t + 1] * k) for t in range(0, len(v), 2)]
        L = sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip(pts, pts[1:]))
        new[n].append(('wire', m.group(1), int(m.group(2)) * k, round(L, 3), [(round(x, 3), round(y, 3)) for x, y in pts]))
    for m in re.finditer(r'\(via\s+"?([^"\s]+)"?\s+(-?\d+)\s+(-?\d+)\s*(\(type protect\))?', block):
        if m.group(4):
            continue
        new[n].append(('via', m.group(1), round(int(m.group(2)) * k, 3), round(-int(m.group(3)) * k, 3)))
for n, items in sorted(new.items()):
    w = [x for x in items if x[0] == 'wire']
    print(f'{n}: {len(w)} new wires, {sum(x[3] for x in w):.2f} mm, {len(items) - len(w)} new vias')
    for x in items:
        print('   ', x)
print('nets with new copper:', sorted(new))
