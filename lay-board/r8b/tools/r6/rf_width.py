# -*- coding: utf-8 -*-
"""50 ohm width of the LNA_OUT line on JLC06121H-3313 outer layers, with the independent review's solver.
h 0.0994 mm, 1 oz (0.035), reference In1 for F and In4 for B. Same dielectric on both sides, so one table covers both.
ASSUMPTIONS (solver constants, not checked against a JLC document): PP 3313 er 4.1, mask er 3.8, mask 20 um on substrate, 12 um on copper."""
import sys
sys.path.insert(0, sys.argv[1])
import s3_solver as S

print('single-ended Z0 ohm, and delay ps/mm; g is the gap from the track edge to the same-side GND pour on both sides')
print('w mm  ' + ''.join(f'{"g=" + g:>12}' for g in ('none', '0.40', '0.30', '0.25', '0.20', '0.12')))
for w in (0.12, 0.14, 0.15, 0.16, 0.17, 0.18, 0.20):
    row = []
    for g in (None, 0.40, 0.30, 0.25, 0.20, 0.12):
        pours = () if g is None else ((-4, -w / 2 - g), (w / 2 + g, 4))
        C, L, *_ = S.microstrip([(0, w, 0)], pours=pours).matrices([0], 0.004)
        z, t = S.ze(C, L)
        row.append(f'{z:6.1f}/{t:4.2f} ')
    print(f'{w:.2f}  ' + ''.join(f'{r:>12}' for r in row))
print('no mask, w 0.16, g 0.25:')
C, L, *_ = S.microstrip([(0, 0.16, 0)], mask=False, pours=((-4, -0.33), (0.33, 4))).matrices([0], 0.004)
print(round(S.ze(C, L)[0], 1))
for h, er in ((0.0894, 4.1), (0.1094, 4.1), (0.0994, 3.8), (0.0994, 4.4)):
    C, L, *_ = S.microstrip([(0, 0.16, 0)], h=h, er=er, pours=((-4, -0.33), (0.33, 4))).matrices([0], 0.004)
    print(f'sensitivity w 0.16 g 0.25 h {h} er {er}: {S.ze(C, L)[0]:.1f}')
C, L, *_ = S.microstrip([(0, 0.16, 0)], pours=((-4, -0.33), (0.33, 4))).matrices([0], 0.002)
print('convergence fine 0.002 w 0.16 g 0.25:', round(S.ze(C, L)[0], 2))
