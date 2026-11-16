# -*- coding: utf-8 -*-
"""r7f gate: every via that is not GND and not a CSI via stays at least 0.62 mm (centre to line centre) from every CSI segment.
0.62 mm is the rule r7d/r7e used when placing vias (tools/r7e_stage.py _Geo.via_ok): a 0.4 mm via antipad at that distance leaves the
GND reference under the 0.127 mm line whole (refplane.py measures the reference itself; this checks the placement rule directly).
No exceptions: r7f moved the one r7d VDD_MIPI via that was at 0.585 mm.
usage: csi_via.py <board.kicad_pcb>       exit 1 if any via is closer
"""
import re
import sys

from shapely.geometry import LineString, Point

s = open(sys.argv[1], encoding='utf-8').read()
ids = dict(re.findall(r'\(net (\d+) "([^"]*)"\)', s))
nm = lambda t: ids.get(t, t)
segs = []
for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width [\d.]+\)\s+\(layer "[^"]+"\)\s+\(net (?:(\d+)|"([^"]*)")\)', s):
    n = nm(m[5]) if m[5] else m[6]
    if n.startswith('CSI_'):
        segs.append((n, LineString([(float(m[1]), float(m[2])), (float(m[3]), float(m[4]))])))
vias = []
for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)(?:(?!\(via|\(segment).)*?\(net (?:(\d+)|"([^"]*)")\)', s, re.S):
    n = nm(m[3]) if m[3] else m[4]
    vias.append((n, Point(float(m[1]), float(m[2]))))
assert segs and vias, (len(segs), len(vias))
bad, worst = [], (9.0, None)
for n, p in vias:
    if n == 'GND' or n.startswith('CSI_'):
        continue
    d, sn = min((l.distance(p), sn_) for sn_, l in segs)
    if d < worst[0]:
        worst = (d, (n, round(p.x - 100, 3), round(p.y - 100, 3), sn))
    if d < 0.62:
        bad.append((n, round(p.x - 100, 3), round(p.y - 100, 3), sn, round(d, 3)))
print(f'{len(segs)} CSI segments, {len(vias)} vias; closest non-GND via {worst[0]:.3f} mm {worst[1]}')
for b in bad:
    print('FAIL via', b)
print('RESULT', 'FAIL' if bad else 'PASS')
sys.exit(1 if bad else 0)
