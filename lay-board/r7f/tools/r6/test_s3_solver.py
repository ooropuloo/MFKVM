# -*- coding: utf-8 -*-
"""Regression test for s3_solver.py with NON-ROUND conductor dimensions (r7e).

Bug (found by the si channel, 2026-11-09): graded() rounds grid lines to 1e-6 mm, but Xsec.assemble() marked conductor nodes with a 1e-9
tolerance, so a conductor edge that is not a round number lost its edge column (up to +7 ohm). Fix: the marking tolerance is 2e-6 (the
minimal patch, analysis_r7d/si/results/solver_ab/minimal_patch.diff). Round dimensions were never affected.
This test solves geometries whose edges are deliberately off the 1e-6 grid and compares them with closed forms:
  Cohn, exact zero-thickness centred stripline (Z0 = 30 pi K(k)/K(k'), k = sech(pi w / 2b))
  Cohn, exact coupled stripline (odd mode, Zdiff = 2 Z0o)
  Hammerstad-Jensen thin microstrip (er 4.1)
Limits: 1.5 % against the closed forms (the round-number validation in s3_solver's __main__ agrees to about 1 %); and continuity: the
same pair with full-precision dimensions and rounded to 0.1 um must agree to 0.5 % (the bug's signature: +3.1 %, si channel saw +7 ohm).
usage: test_s3_solver.py [dir holding the s3_solver.py to test]      exit 1 on a failure
"""
import math
import os
import sys

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
import s3_solver as S
from scipy.special import ellipk

LIMIT = 0.015
fails = []


def check(name, exact, got):
    d = (got - exact) / exact
    ok = abs(d) <= LIMIT
    print(f"{'PASS' if ok else 'FAIL'} {name}: closed form {exact:.2f}, solver {got:.2f} ({100 * d:+.2f} %)")
    if not ok:
        fails.append(name)


# Cohn stripline, w and b off the 1e-6 grid
for w, b in ((0.1234567, 0.4), (0.2003333, 0.5)):
    k = 1 / math.cosh(math.pi * w / (2 * b))
    kp = math.sqrt(1 - k * k)
    zex = 30 * math.pi * ellipk(k * k) / ellipk(kp * kp)
    X = S.stripline([(0, w, 0)], h1=b / 2 - 0.0002, h2=b / 2 - 0.0002, t=0.0004, er1=1, er2=1, halfw=5)
    C, L, *_ = X.matrices([0], 0.002)
    check(f'Cohn stripline w={w} b={b}', zex, S.ze(C, L)[0])
# Cohn coupled stripline, odd mode
w, s, b = 0.1333333, 0.1987654, 0.5
ko = math.tanh(math.pi * w / (2 * b)) / math.tanh(math.pi * (w + s) / (2 * b))
zo = 30 * math.pi * ellipk(1 - ko * ko) / ellipk(ko * ko)
(zd, _), _, _ = S.run_pair(S.stripline(S.pair(w, s), h1=b / 2 - 0.0002, h2=b / 2 - 0.0002, t=0.0004, er1=1, er2=1, halfw=5), 0.002)
check(f'Cohn coupled stripline w={w} s={s} b={b} (Zdiff)', 2 * zo, zd)
# Hammerstad-Jensen thin microstrip
w, h, er = 0.1777777, 0.1, 4.1
u = w / h
a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
bb = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * bb)
fu = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
zhj = 60 / math.sqrt(ee) * math.log(fu / u + math.sqrt(1 + (2 / u) ** 2))
X = S.microstrip([(0, w, 0)], h=h, t=0.0005, er=er, mask=False, halfw=5, air_h=3)
C, L, *_ = X.matrices([0], 0.002)
check(f'H-J microstrip w={w} h={h} er={er}', zhj, S.ze(C, L)[0])
# continuity: a CSI/TMDS-like outer pair with full-precision dimensions (as a Monte Carlo draw gives them) against the same pair rounded to
# 0.1 um. They differ by under 0.1 um, so Zdiff must agree to 0.5 %. Before the fix: 103.91 against 100.82 ohm (+3.1 %); with a thicker
# dielectric off the grid as well: 100.71 against 99.80.
for (w, g, h), (wr, gr, hr) in (((0.12267345678, 0.2025265432, 0.0994), (0.1227, 0.2025, 0.0994)),
                                ((0.127, 0.198, 0.10123456789), (0.127, 0.198, 0.1012346))):
    (z1, _), _, _ = S.run_pair(S.microstrip(S.pair(w, g), h=h), 0.004)
    (z0, _), _, _ = S.run_pair(S.microstrip(S.pair(wr, gr), h=hr), 0.004)
    ok = abs(z1 - z0) / z0 <= 0.005
    print(f"{'PASS' if ok else 'FAIL'} continuity w {w} g {g} h {h} against {wr}/{gr}/{hr}: Zdiff {z1:.2f} / {z0:.2f} ohm ({100 * (z1 - z0) / z0:+.2f} %, limit 0.5 %)")
    if not ok:
        fails.append(f'continuity w={w}')
print('RESULT ' + ('FAIL ' + ', '.join(fails) if fails else 'PASS'))
sys.exit(1 if fails else 0)
