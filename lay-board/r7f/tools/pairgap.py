# -*- coding: utf-8 -*-
"""Differential-pair gap and coupling (r7e, REVIEW_r7d: verify.py never checked pair spacing).

Each line of a pair is sampled every 0.05 mm; at each sample the edge-to-edge gap to the partner line ON THE SAME LAYER is measured and
turned into a differential impedance with the field solver's table below (tools/r7/impedance_r7.py's solver, this stackup, solder mask,
2026-11-09). This board's pairs are weakly coupled (outer dielectric 0.0994 mm), so an uncoupled stretch is only ~10% above target while a
tight one drops fast.
  FAIL  any sample whose impedance is outside target +-10% (CSI/TMDS 100 ohm: gap under 0.12 mm; USB HS 90 ohm: gap under 0.14 mm),
        or a line with no partner segment on its layer for more than half its length.
  report  coupled length (gap within +-0.03 mm of the solved gap) and uncoupled length (fan-outs at balls, pads, vias, matching bumps).
usage: pairgap.py <.kicad_pcb> [--report file]          exit 1 on any FAIL
"""
import math
import re
import sys

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

# solver: (gap mm, Zdiff ohm); beyond the last row the pair counts as uncoupled at the last value
ZTAB = {0.127: [(0.12, 89.9), (0.14, 93.0), (0.16, 95.6), (0.18, 97.5), (0.20, 99.2), (0.24, 101.7), (0.28, 103.4), (0.32, 104.7), (0.5, 107.6), (1.0, 109.5)],
        0.18: [(0.12, 77.8), (0.14, 80.1), (0.16, 82.1), (0.18, 83.6), (0.20, 84.8), (0.24, 86.7), (0.28, 88.1), (0.32, 89.1), (0.5, 91.4), (1.0, 93.0)]}
TARGET = {'csi': 100, 'tmds': 100, 'usb': 90}


def zdiff(w, gap):
    t = ZTAB[round(w, 3)]
    if gap <= t[0][0]:
        (g0, z0), (g1, z1) = t[0], t[1]
    elif gap >= t[-1][0]:
        return t[-1][1]
    else:
        (g0, z0), (g1, z1) = next((a, b) for a, b in zip(t, t[1:]) if a[0] <= gap <= b[0])
    return z0 + (z1 - z0) * (gap - g0) / (g1 - g0)


GROUPS = {'csi': ([('CSI_D0_P', 'CSI_D0_N'), ('CSI_D1_P', 'CSI_D1_N'), ('CSI_CK_P', 'CSI_CK_N')], 0.198),
          'tmds': ([('D0_P', 'D0_N'), ('D1_P', 'D1_N'), ('D2_P', 'D2_N'), ('CK_P', 'CK_N')], 0.198),
          'usb': ([('USB_DP', 'USB_DN')], 0.32)}
TOL, STEP = 0.03, 0.05
SEG = re.compile(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)')


def measure(s):
    segs = {}
    for m in SEG.finditer(s):
        segs.setdefault(m[7], []).append((m[6], LineString([(float(m[1]), float(m[2])), (float(m[3]), float(m[4]))]), float(m[5])))
    rows = []
    for g, (pairs, gap) in GROUPS.items():
        for p, n in pairs:
            for a, b in ((p, n), (n, p)):
                other = {}
                for ly, l, w in segs.get(b, []):
                    other.setdefault(ly, []).append(l.buffer(w / 2))
                other = {k: unary_union(v) for k, v in other.items()}
                total = coupled = alone = 0.0
                tight = []
                zmin, zmax = 999.0, 0.0
                for ly, l, w in segs.get(a, []):
                    k = max(1, int(l.length / STEP))
                    for i in range(k):
                        pt = l.interpolate((i + 0.5) / k, normalized=True)
                        total += l.length / k
                        o = other.get(ly)
                        if o is None:
                            alone += l.length / k
                            continue
                        e = o.distance(pt) - w / 2
                        if round(w, 3) not in ZTAB:   # a width the solver table does not cover: no impedance claim, so it fails
                            tight.append((round(pt.x - 100, 2), round(pt.y - 100, 2), round(e, 3), f'width {w} not solved'))
                            continue
                        z = zdiff(w, e)
                        zmin, zmax = min(zmin, z), max(zmax, z)
                        if abs(z - TARGET[g]) > 0.1 * TARGET[g]:
                            tight.append((round(pt.x - 100, 2), round(pt.y - 100, 2), round(e, 3), round(z, 1)))
                        elif abs(e - gap) <= TOL:
                            coupled += l.length / k
                rows.append((g, a, b, gap, total, coupled, total - coupled, tight, alone, zmin, zmax))
    return rows


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rows = measure(open(sys.argv[1], encoding='utf-8').read())
    fails = []
    out = ['| group | line | partner | solved gap | length mm | coupled mm | uncoupled mm | no partner on layer mm | Zdiff min-max ohm | out of +-10% |', '|---|---|---|---|---|---|---|---|---|---|']
    for g, a, b, gap, t, c, u, tight, alone, zmin, zmax in rows:
        out.append(f'| {g} | {a} | {b} | {gap} | {t:.2f} | {c:.2f} | {u:.2f} | {alone:.2f} | {zmin:.1f}-{zmax:.1f} | {len(tight)} {tight[:2] if tight else ""} |')
        if tight:
            fails.append(f'{a}: impedance outside {TARGET[g]} ohm +-10% at {len(tight)} samples (gap to {b}), first {tight[:3]}')
        if alone > t / 2:
            fails.append(f'{a}: {alone:.2f} of {t:.2f} mm has no {b} on the same layer')
    txt = '\n'.join(out) + '\n' + ''.join(f'FAIL {f}\n' for f in fails) + f"RESULT {'FAIL' if fails else 'PASS'}\n"
    if '--report' in sys.argv:
        open(sys.argv[sys.argv.index('--report') + 1], 'w', encoding='utf-8').write('# Differential pair gap and coupling (tools/pairgap.py)\n\n' + __doc__.split('usage')[0].strip() + '\n\n' + txt)
    print(txt)
    sys.exit(1 if fails else 0)
