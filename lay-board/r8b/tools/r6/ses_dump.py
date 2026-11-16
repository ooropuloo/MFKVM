# -*- coding: utf-8 -*-
"""usage: ses_dump.py <ses> NET [NET...]: prints a net's routed segments and vias in design mm, for writing a patch."""
import re
import sys

s = open(sys.argv[1], encoding='utf-8').read()
i = s.find('network_out')
starts = [(m.start() + i, m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', s[i:])]
for j, (a, net) in enumerate(starts):
    if net not in sys.argv[2:]:
        continue
    block = s[a:starts[j + 1][0] if j + 1 < len(starts) else len(s)]
    print('==', net)
    for m in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', block):
        v = [int(t) for t in m.group(3).split()]
        pts = [(v[k] / 10000, -v[k + 1] / 10000) for k in range(0, len(v), 2)]
        print(' ', m.group(1), int(m.group(2)) / 10000, ' '.join(f'({x:.4f},{y:.4f})' for x, y in pts))
    for m in re.finditer(r'\(via\s+"?([^"\s)]+)"?\s+(-?\d+)\s+(-?\d+)', block):
        print('  via', m.group(1), f'({int(m.group(2)) / 10000:.4f},{-int(m.group(3)) / 10000:.4f})')
