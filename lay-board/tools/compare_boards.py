# -*- coding: utf-8 -*-
"""Compares two boards: routed copper per net from the .kicad_pcb, and every Gerber layer and drill file by XOR.

usage: compare_boards.py <old.kicad_pcb> <new.kicad_pcb> <old gerber dir> <new gerber dir> [--report file]
exit 0 when every high-speed net is geometrically identical, 1 when one differs
"""
import os
import re
import sys

import maskcheck
from shapely.ops import unary_union

# TMDS, CSI, both USB pairs, both DDC sides, and the hand-routed clocks
HIGH_SPEED = ['D2_P', 'D2_N', 'D1_P', 'D1_N', 'D0_P', 'D0_N', 'CK_P', 'CK_N', 'CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N',
              'USB_DP', 'USB_DN', 'USB2_DP', 'USB2_DN', 'DDC_SCL', 'DDC_SDA', 'DDC3_SCL', 'DDC3_SDA', 'TC_REFCLK', 'OSC_OUT']


def copper(path):
    s = open(path, encoding='utf-8').read()
    names = dict((int(a), b) for a, b in re.findall(r'\(net (\d+) "([^"]*)"\)', s[:s.find('(footprint')]))
    segs, vias = {}, {}
    for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([-\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net (?:(\d+)|"([^"]+)")\)', s):
        a, b = (round(float(m[1]) - 100, 4), round(float(m[2]) - 100, 4)), (round(float(m[3]) - 100, 4), round(float(m[4]) - 100, 4))
        segs.setdefault(m[8] or names[int(m[7])], set()).add((min(a, b), max(a, b), round(float(m[5]), 4), m[6]))
    for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([-\d.]+)\)\s+\(drill ([-\d.]+)\)\s+\(layers "F.Cu" "B.Cu"\)(.*?)\(uuid', s, re.S):
        n = re.search(r'\(net (?:(\d+)|"([^"]+)")\)', m[5])
        vias.setdefault(n[2] or names[int(n[1])], set()).add((round(float(m[1]) - 100, 4), round(float(m[2]) - 100, 4), float(m[3]), float(m[4])))
    return segs, vias


def gerber_geom(path):
    return unary_union([o['geom'] for o in maskcheck.parse(open(path, encoding='utf-8', errors='replace').read())])


def drills(path):
    return sorted(re.findall(r'^X-?[\d.]+Y-?[\d.]+', open(path, errors='replace').read(), re.M))


def main(a):
    old_pcb, new_pcb, old_g, new_g = a[:4]
    out = sys.stdout
    if '--report' in a:
        out = open(a[a.index('--report') + 1], 'w', encoding='utf-8')
    oldc, newc = copper(old_pcb), copper(new_pcb)
    nets = sorted(set(oldc[0]) | set(newc[0]) | set(oldc[1]) | set(newc[1]))
    changed = []
    print('Copper per net, old against new. Segments and vias match only if every coordinate, width and layer match, to 0.1 um.', file=out)
    for n in nets:
        sa, sb, va, vb = oldc[0].get(n, set()), newc[0].get(n, set()), oldc[1].get(n, set()), newc[1].get(n, set())
        if sa != sb or va != vb:
            changed.append(n)
            print(f'  CHANGED {n}: segments -{len(sa - sb)} +{len(sb - sa)} of {len(sa)}, vias -{len(va - vb)} +{len(vb - va)} of {len(va)}', file=out)
    print(f'{len(changed)} of {len(nets)} routed nets changed', file=out)
    print('\nHigh-speed nets:', file=out)
    bad = []
    for n in HIGH_SPEED:
        same = oldc[0].get(n) == newc[0].get(n) and oldc[1].get(n) == newc[1].get(n)
        print(f"  {'identical' if same else 'DIFFERENT'} {n:10s} {len(newc[0].get(n, ()))} segments, {len(newc[1].get(n, ()))} vias", file=out)
        if not same or not newc[0].get(n):
            bad.append(n)
    print('\nGerber XOR per layer, mm2. Areas are design coordinates, x right and y down:', file=out)
    for name in sorted(n for n in os.listdir(new_g) if n.endswith('.gbr') and 'job' not in n):
        try:
            x = gerber_geom(f'{old_g}/{name}').symmetric_difference(gerber_geom(f'{new_g}/{name}'))
        except Exception as e:
            print(f'  {name}: could not XOR ({e})', file=out)
            continue
        polys = [g for g in getattr(x, 'geoms', [x]) if g.area > 1e-5]
        print(f'  {name}: {x.area:.4f} in {len(polys)} pieces', file=out)
        if polys:
            bx = unary_union(polys).bounds
            print(f'      extent x {bx[0] - 100:.2f}..{bx[2] - 100:.2f}, y {-bx[3] - 100:.2f}..{-bx[1] - 100:.2f}', file=out)
    print('\nDrill files:', file=out)
    for name in ('p4_kvm_mini-PTH.drl', 'p4_kvm_mini-NPTH.drl'):
        o, n = drills(f'{old_g}/{name}'), drills(f'{new_g}/{name}')
        print(f'  {name}: {len(o)} holes, then {len(n)}; removed {sorted(set(o) - set(n))}, added {sorted(set(n) - set(o))}', file=out)
    print('\nRESULT', 'high-speed nets identical' if not bad else f'DIFFERENT {bad}', file=out)
    if out is not sys.stdout:
        out.close()
    print('high-speed', 'identical' if not bad else bad, 'changed nets', changed)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
