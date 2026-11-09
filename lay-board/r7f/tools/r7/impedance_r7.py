# -*- coding: utf-8 -*-
"""r7 item 5: impedance of the controlled lines on the ordered stackup, with the stackup read from the board file itself.

Method 1, the number used: tools/r6/s3_solver.py, a 2D quasi-static finite-volume field solver (written for the r6 review; validated in
its own __main__ against Cohn's exact stripline and coupled-stripline results, and against Hammerstad-Jensen microstrip). Solder mask included.
Method 2, an independent cross-check with no mask: closed-form Hammerstad-Jensen microstrip with Kirschning-Jansen even/odd coupling
(the formulas behind most online calculators), and the IPC-2141A approximation.

usage: impedance_r7.py <board.kicad_pcb>
ASSUMED, not from a JLC document in this package: dielectric constants (3313 4.1, 2116 4.16, core 4.6), mask 20 um on laminate and 12 um
on copper, mask er 3.8. JLC's own impedance calculator was not run (web tool); its numbers are therefore not recorded here.
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'r6'))
import s3_solver as S

sys.stdout.reconfigure(encoding='utf-8')
pcb = open(sys.argv[1], encoding='utf-8').read()
stack = re.findall(r'\(layer "([^"]+)"\s*\(type "([^"]+)"\)\s*(?:\(thickness ([\d.]+)\))?(?:\s*\(material "([^"]*)"\))?(?:\s*\(epsilon_r ([\d.]+)\))?', pcb[pcb.find('(stackup'):pcb.find('(copper_finish')])
print('stackup read from the board:')
for n, t, th, mat, er in stack:
    print(f'  {n:14s} {t:22s} {th or "":8s} {mat or "":6s} {er or ""}')
L = {n: (t, float(th) if th else None, float(er) if er else None) for n, t, th, mat, er in stack}
h_outer, er_outer = L['dielectric 1'][1], L['dielectric 1'][2]
t_outer = L['F.Cu'][1]
assert (h_outer, er_outer, t_outer) == (S.H_PP, S.ER_PP, S.T_OUT) == (L['dielectric 5'][1], L['dielectric 5'][2], L['B.Cu'][1]), 'solver constants differ from the board stackup'
print(f'solver uses h {S.H_PP} er {S.ER_PP} t {S.T_OUT} for F/In1 and B/In4: same as the board stackup')
total = sum(v[1] for k, v in L.items() if v[1] and 'Mask' not in k)
print(f'copper + dielectric {total:.4f} mm (order: 1.1384)\n')

# ---- method 2: closed forms, no mask, thin strip corrected for thickness (Hammerstad-Jensen; Kirschning-Jansen coupled)


def hj_single(w, h, er, t=0.0):
    if t:
        w = w + t / math.pi * (1 + math.log(4 * math.e / math.sqrt((t / h) ** 2 + (1 / math.pi / (w / t + 1.1)) ** 2))) * (1 + 1 / math.cosh(math.sqrt(er - 1))) / 2
    u = w / h
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    fu = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    return 60 / math.sqrt(ee) * math.log(fu / u + math.sqrt(1 + (2 / u) ** 2)), ee


def kj_diff(w, s, h, er):
    """Kirschning-Jansen 1984 static even/odd impedances of edge-coupled microstrip (zero thickness). Returns Zdiff = 2 Zodd."""
    u, g = w / h, s / h
    z0, ee0 = hj_single(w, h, er)
    v = u * (20 + g * g) / (10 + g * g) + g * math.exp(-g)
    ae = 1 + math.log((v ** 4 + (v / 52) ** 2) / (v ** 4 + 0.432)) / 49 + math.log(1 + (v / 18.1) ** 3) / 18.7
    be = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    eee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / v) ** (-ae * be)
    a0 = 0.7287 * (ee0 - (er + 1) / 2) * (1 - math.exp(-0.179 * u))
    b0 = 0.747 * er / (0.15 + er)
    c0 = b0 - (b0 - 0.207) * math.exp(-0.414 * u)
    d0 = 0.593 + 0.694 * math.exp(-0.562 * u)
    eeo = ((er + 1) / 2 + a0 - ee0) * math.exp(-c0 * g ** d0) + ee0
    q1 = 0.8695 * u ** 0.194
    q2 = 1 + 0.7519 * g + 0.189 * g ** 2.31
    q3 = 0.1975 + (16.6 + (8.4 / g) ** 6) ** -0.387 + math.log(g ** 10 / (1 + (g / 3.4) ** 10)) / 241
    q4 = 2 * q1 / q2 / (math.exp(-g) * u ** q3 + (2 - math.exp(-g)) * u ** -q3)
    q5 = 1.794 + 1.14 * math.log(1 + 0.638 / (g + 0.517 * g ** 2.43))
    q6 = 0.2305 + math.log(g ** 10 / (1 + (g / 5.8) ** 10)) / 281.3 + math.log(1 + 0.598 * g ** 1.154) / 5.1
    q7 = (10 + 190 * g * g) / (1 + 82.3 * g ** 3)
    q8 = math.exp(-6.5 - 0.95 * math.log(g) - (g / 0.15) ** 5)
    q9 = math.log(q7) * (q8 + 1 / 16.5)
    q10 = (q2 * q4 - q5 * math.exp(math.log(u) * q6 * u ** -q9)) / q2
    zo = z0 * math.sqrt(ee0 / eeo) / (1 - z0 / 377 * math.sqrt(ee0) * q10)
    return 2 * zo


def ipc2141(w, s, h, er, t):
    z0 = 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (0.8 * w + t))
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s / h)), z0


print('Method 1 (field solver) and method 2 (closed form, no mask; Kirschning-Jansen is for zero-thickness copper, see the check below). Ohm.')
print(f'{"line":40s} {"solver mask":>12s} {"solver no mask":>15s} {"K-J t=0":>12s} {"IPC-2141A":>10s}  target')
rows = [('TMDS, CSI: 0.127 / 0.198, F ref In1, B ref In4', 0.127, 0.198, 100),
        ('TMDS ESD flow-through 0.127 / 0.373', 0.127, 0.373, 100),
        ('USB HS: 0.18 / 0.32', 0.18, 0.32, 90)]
res = {}
off = []   # r7c: a line outside +-10% now makes the script exit 1; before, it only printed OFF
for name, w, s, tgt in rows:
    (zd, td), _, _ = S.run_pair(S.microstrip(S.pair(w, s)))
    (zn, _), _, _ = S.run_pair(S.microstrip(S.pair(w, s), mask=False))
    kj = kj_diff(w, s, h_outer, er_outer)
    ipc, _ = ipc2141(w, s, h_outer, er_outer, t_outer)
    res[name] = zd
    print(f'{name:40s} {zd:12.1f} {zn:15.1f} {kj:12.1f} {ipc:10.1f}  {tgt} +-10%  {"OK" if abs(zd - tgt) <= 0.1 * tgt else "OFF"}  ({td:.2f} ps/mm)')
    if abs(zd - tgt) > 0.1 * tgt:
        off.append(name)
for w, g in ((0.15, 0.25),):
    C, Lm, *_ = S.microstrip([(0, w, 0)], pours=((-4, -w / 2 - g), (w / 2 + g, 4))).matrices([0], 0.004)
    z, t = S.ze(C, Lm)
    C, Lm, *_ = S.microstrip([(0, w, 0)], mask=False, pours=((-4, -w / 2 - g), (w / 2 + g, 4))).matrices([0], 0.004)
    zn = S.ze(C, Lm)[0]
    hj, _ = hj_single(w, h_outer, er_outer, t_outer)
    if abs(z - 50) > 5:
        off.append('LNA_OUT')
    print(f'{"LNA_OUT 0.15, pour gap 0.25 (CPWG)":40s} {z:12.1f} {zn:15.1f} {hj:12.1f}{"(no pour)":>11s}  50 +-10%  {"OK" if abs(z - 50) <= 5 else "OFF"}')
print('\nThe closed forms are for a zero-thickness strip; at t/h = 0.35 that is not this board. So the coupled formula checks the solver with the')
print('copper made thin (t 0.5 um), where both describe the same geometry:')
for name, w, s, tgt in rows:
    (zt, _), _, _ = S.run_pair(S.microstrip(S.pair(w, s), mask=False, t=0.0005, air_h=3))
    kj = kj_diff(w, s, h_outer, er_outer)
    print(f'  {name:40s} solver thin {zt:6.1f}   Kirschning-Jansen {kj:6.1f}   difference {100 * (zt - kj) / kj:+.1f}%')
print('\nSensitivity of TMDS/CSI 0.127 / 0.198 (solver, mask), pitch held at 0.325:')
for k, vals in (('w', (0.107, 0.147)), ('h', (0.0894, 0.1094)), ('er', (3.8, 4.4))):
    for v in vals:
        w, s, h, er = 0.127, 0.198, h_outer, er_outer
        if k == 'w':
            s, w = 0.325 - v, v
        elif k == 'h':
            h = v
        else:
            er = v
        (zd, _), _, _ = S.run_pair(S.microstrip(S.pair(w, s), h=h, er=er))
        print(f'  {k} {v}: {zd:.1f}')
print('\nIn2 (In3 3V3 below, In1 GND above), solver; In2 has no impedance-controlled line in r7. H_MID 0.1164 in the solver against 0.1088 ordered:')
for hm in (0.1088, S.H_MID):
    C, Lm, *_ = S.stripline([(0, 0.127, 0)], h1=hm).matrices([0], 0.003)
    print(f'  w 0.127 single-ended, prepreg {hm}: {S.ze(C, Lm)[0]:.1f} ohm')
print('IMPEDANCE', 'ALL ON TARGET' if not off else f'OFF: {off}')
sys.exit(1 if off else 0)
