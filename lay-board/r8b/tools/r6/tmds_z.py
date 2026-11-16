# -*- coding: utf-8 -*-
"""TMDS impedance over the r6 gap range with the review's solver and its assumed dielectric constants. Pass the solver's directory."""
import sys
sys.path.insert(0, sys.argv[1])
import s3_solver as S

for g in (0.198, 0.373, 0.70, 0.873, 1.163):
    (Zd, td), (Zs, ts), _ = S.run_pair(S.microstrip(S.pair(0.127, g)), 0.004)
    print(f'0.127/{g:<5}  Zdiff {Zd:6.1f}  single {Zs:5.1f}  {td:.2f} ps/mm')
(Zd, td), (Zs, ts), _ = S.run_pair(S.microstrip(S.pair(0.127, 0.198), pours=((-4, -0.1625 - 0.0635 - 0.12), (0.1625 + 0.0635 + 0.12, 4))), 0.004)
print(f'0.127/0.198 pour 0.12 both sides  Zdiff {Zd:.1f}')
# a tooth leg next to its own return leg, pitch 0.237 and 0.28 mm: each leg with the other at the same potential (even mode), the extreme for that stretch
for p in (0.21, 0.237, 0.26):
    C, L, *_ = S.microstrip([(-p / 2, 0.127, 0), (p / 2, 0.127, 1)]).matrices([0, 1], 0.004)
    ev = S.modal(C, L, [1, 1])
    print(f'tooth legs pitch {p}: even-mode Z of the two legs together x2 = {ev[0]:.1f} (one line, both legs in phase); isolated single 55')
