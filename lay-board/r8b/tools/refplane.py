# -*- coding: utf-8 -*-
"""Reference plane under controlled-impedance pairs (r7e; r7d had it for CSI only, with every CSI via excluded: REVIEW_r7d tool table).

Rule: a segment of a pair on F.Cu needs filled GND on In1 under it, on B.Cu filled GND on In4, as saved after a zone refill.
Two margins, each side of the line:
  FAIL_MARGIN 0.03 mm  the line itself plus an etch/registration allowance (2 x 15 um). Any uncovered area there fails.
  WARN_MARGIN 0.10 mm  r7d's CSI rule (about one dielectric height). Uncovered area in this band is listed, not failed: in r7e every such
                       spot is the edge of a foreign via's antipad 0.42-0.46 mm from the line centre (TMDS vias placed in r6, the D1 fan-out
                       via beside CK), none under the copper. Excluded: a 0.45 mm circle round each via of the SAME pair (the layer change's own antipad) and nothing
else. Pads do not cut inner planes. A pair segment on an inner layer counts as a gap (no checked reference).
Used by verify.py (as a check) and on the command line (exit 1 when any gap is found):
usage: refplane.py <saved .kicad_pcb (zones refilled)> [csi|tmds|usb ...]   (default: all three); exit 1 on any FAIL-margin gap
"""
import re
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

PAIRS = {
    'csi': [('CSI_D0_P', 'CSI_D0_N'), ('CSI_D1_P', 'CSI_D1_N'), ('CSI_CK_P', 'CSI_CK_N')],
    'tmds': [('D0_P', 'D0_N'), ('D1_P', 'D1_N'), ('D2_P', 'D2_N'), ('CK_P', 'CK_N')],
    'usb': [('USB_DP', 'USB_DN')],
}
REF = {'F.Cu': 'In1.Cu', 'B.Cu': 'In4.Cu'}
FAIL_MARGIN, WARN_MARGIN = 0.03, 0.10
SEG = re.compile(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)')
VIA = re.compile(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)(?:(?!\(via|\(segment).)*?\(net "([^"]+)"\)', re.S)


def gnd_fill(s):
    ref = {}
    for zm in re.finditer(r'\(zone\b(.*?)\n\t\)', s, re.S):
        if '(net_name "GND")' not in zm[1] and '(net "GND")' not in zm[1]:
            continue
        for fm in re.finditer(r'\(filled_polygon\s+\(layer "([^"]+)"\)\s+\(pts(.*?)\)\s*\)', zm[1], re.S):
            p = [(float(a), float(b)) for a, b in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', fm[2])]
            if len(p) >= 3:
                ref.setdefault(fm[1], []).append(Polygon(p).buffer(0))
    return {k: unary_union(v) for k, v in ref.items()}


def gaps(s, groups=('csi', 'tmds', 'usb'), margin=FAIL_MARGIN):
    """returns (fill, [(net, layer, area mm2, (x, y) board mm, [other-net vias within 0.8 mm])])"""
    fill = gnd_fill(s)
    vias = [(Point(float(m[1]), float(m[2])), m[3]) for m in VIA.finditer(s)]
    out = []
    for g in groups:
        for p, n in PAIRS[g]:
            own = unary_union([v.buffer(0.45) for v, vn in vias if vn in (p, n)])
            for m in SEG.finditer(s):
                if m[7] not in (p, n):
                    continue
                ly = REF.get(m[6])
                a, b = (float(m[1]), float(m[2])), (float(m[3]), float(m[4]))
                if ly is None:
                    out.append((m[7], m[6], 99.0, a, []))
                    continue
                st = LineString([a, b]).buffer(float(m[5]) / 2 + margin, cap_style=2).difference(own)
                miss = st.difference(fill.get(ly, Polygon()))
                if miss.area > 1e-4:
                    c = miss.centroid
                    near = sorted((round(v.distance(c), 2), vn) for v, vn in vias if v.distance(c) < 0.8 and vn not in (p, n))
                    out.append((m[7], m[6], miss.area, (c.x, c.y), near))
    return fill, out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    groups = sys.argv[2:] or ['csi', 'tmds', 'usb']
    txt = open(sys.argv[1], encoding='utf-8').read()
    fill, gp = gaps(txt, groups, FAIL_MARGIN)
    if not fill.get('In1.Cu') or not fill.get('In4.Cu'):
        print('no filled GND on In1/In4: refill the zones and save the board first')
        sys.exit(2)
    for net, ly, area, (x, y), near in gp:
        print(f'FAIL {net:9s} {ly} gap {area:.4f} mm2 at ({x - 100:.3f}, {y - 100:.3f}); other-net vias within 0.8 mm: {near}')
    _, gw = gaps(txt, groups, WARN_MARGIN)
    for net, ly, area, (x, y), near in gw:
        print(f'warn {net:9s} {ly} gap {area:.4f} mm2 within {WARN_MARGIN} mm at ({x - 100:.3f}, {y - 100:.3f}); other-net vias within 0.8 mm: {near}')
    print(f'{" ".join(groups)}: {len(gp)} gaps within {FAIL_MARGIN} mm of the lines (FAIL), {len(gw)} within {WARN_MARGIN} mm (listed), '
          f'{sum(g[2] for g in gw):.4f} mm2')
    print('RESULT ' + ('FAIL' if gp else 'PASS'))
    sys.exit(1 if gp else 0)
