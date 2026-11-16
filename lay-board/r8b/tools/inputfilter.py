# -*- coding: utf-8 -*-
"""r8: 5V input-filter damping, read from the board's design.json.

Why this check exists. r7c-r7f carried a 330 uF polymer capacitor (7343) in series with 0.15 ohm across 5V, placed for hot-plug
overshoot (Linear AN-88). Since r7f the eFuse U16 ramps 5V at dV/dt and clamps it, so that overshoot is gone (tools/hotplug.py).
What still needs damping is the USB cable inductance resonating with the 5V ceramics in front of U2: a regulating buck converter is a
negative resistance at its input, -V^2/P, and the source must stay well below it at every frequency (Middlebrook's criterion,
R. D. Middlebrook, "Input filter considerations in design and application of switching regulators", IEEE IAS 1976; the same rule
is in TI SLVA538 "Input filter design for switching power supplies"). r8 uses 2 x 22 uF 0805 in series with 0.47 ohm instead of the
7343 part, which is what lets the board go back to 40 x 40 mm.

Model (lumped, linear):
  source  : ideal Vs -> cable R + L -> VBUS_IN ceramics -> eFuse RON -> 5V node
  5V node : ceramics straight across 5V (DC-bias derated), the damping branch R + C, the converter as a constant-power load
Gate:
  1. |Zs|max / |Rin| <= LIMIT in every corner, Zs = source impedance seen from the 5V node, Rin = V5^2 / P at full load
  2. the damping branch exists: exactly one resistor from 5V to a net that only holds capacitors to GND,
     and its capacitance is at least MIN_CD times the ceramics that sit straight across 5V (nominal values)
  3. Wi-Fi TX burst (C6 80 -> 354 mA on 3V3, 250 Hz) leaves 5V above U2's dropout need and below U2 VIN abs max 6.0 V
Ranges (ASSUMED where marked; nothing is measured):
  Vs 4.75 / 5.0 / 5.25 V; cable L 0.5 / 1.0 / 1.5 / 3.0 uH (about 0.5-3 m, 1 uH/m ASSUMED); cable + contacts R 0.03 / 0.1 / 0.3 ohm
  (the host port switch, typically 0.08 ohm, is left out: less damping, so pessimistic)
  22 uF 0805 25 V X5R at 5 V: 40 / 60 / 80 % of nominal (ASSUMED, as in tools/hotplug.py; DC-bias curve not read); smaller ceramics
  50-80 %; ceramic ESR 5 mOhm; R tolerance +-1 % (0402WGF)
  eFuse RON 34 mOhm typ, 47 mOhm max (TI SLVSE57C 7.5); the low value is used (less damping)
  full-load input power from tools/coldstart.py's rail currents
usage: inputfilter.py --design out/design.json [--out file]      exit 1 when a gate fails
"""
import itertools
import json
import re
import sys

import numpy as np

LIMIT = 0.25                   # |Zs|max / |Rin|: 12 dB below the converter's input resistance
MIN_CD = 1.5                   # damping capacitance / undamped 5V ceramics, nominal values. Below this the branch no longer sets the
                               # damping and the result leans on the cable's own resistance (found by a mutation: one of the two
                               # capacitors wired straight across 5V still met LIMIT at 0.232)
VS = (4.75, 5.0, 5.25)
LC = (0.5e-6, 1.0e-6, 1.5e-6, 3.0e-6)
RC = (0.03, 0.1, 0.3)
BIAS = (0.4, 0.6, 0.8)         # 22 uF 0805 at 5 V
BIAS_SMALL = (0.5, 0.65, 0.8)
ESR = 0.005
RON = 0.034
# rail currents at full load, the numbers tools/coldstart.py uses (I3, I12, I25, V3, V12, V25, ETA2, ETA15)
I3, I12, I25, V3, V12, V25, ETA2, ETA15 = 1.168, 0.274, 0.019, 3.311, 1.2102, 2.5, 0.90, 0.85
I_RX, I_TX = 0.080, 0.354
U2_VIN_MIN, U2_VIN_ABS = 3.311 + 0.19 * 1.5, 6.0   # 3V3 + the drop tools/coldstart.py allows (RDROP x 1.5 A)


def _farad(v):
    m = re.match(r'\s*([\d.]+)\s*(p|n|u)F', v)
    return float(m[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[m[2]] if m else None


def _ohm(v):
    """'0.47 0402', '10k 0402' and the BOM spellings '0R', '4R7', '0.47R' -> ohms. Anything else stops the check with a clear error
    (REVIEW_r8: '0R' used to come back as None and crash later in the arithmetic)."""
    t = v.strip().split()[0] if v.strip() else ''
    m = re.fullmatch(r'([\d.]+)([RkM]?)', t)
    if m:
        return float(m[1]) * {'': 1.0, 'R': 1.0, 'k': 1e3, 'M': 1e6}[m[2]]
    m = re.fullmatch(r'(\d+)([RkM])(\d+)', t)
    if m:
        return float(f'{m[1]}.{m[3]}') * {'R': 1.0, 'k': 1e3, 'M': 1e6}[m[2]]
    raise ValueError(f'resistor value not understood: {v!r}')


def parts_5v(path):
    """(direct ceramics on 5V [F], damping branches [(R ohm, [C F], R ref, [C refs])]) from fitted parts."""
    fit = [p for p in json.load(open(path, encoding='utf-8'))['parts'] if not p['dnp']]
    two = lambda p: set(p['nets'].values()) if len(p['nets']) == 2 else set()
    direct = [(p['ref'], _farad(p['value'])) for p in fit if p['ref'][0] == 'C' and two(p) == {'5V', 'GND'} and _farad(p['value'])]
    branches = []
    for r in fit:
        if r['ref'][0] != 'R' or '5V' not in two(r) or len(two(r)) != 2:
            continue
        mid = (two(r) - {'5V'}).pop()
        on_mid = [p for p in fit if p is not r and mid in p['nets'].values()]
        if on_mid and all(p['ref'][0] == 'C' and two(p) == {mid, 'GND'} and _farad(p['value']) for p in on_mid):
            branches.append((_ohm(r['value']), [_farad(p['value']) for p in on_mid], r['ref'], [p['ref'] for p in on_mid]))
    return direct, branches


def p_in(i3):
    return V3 * (i3 + (V12 * I12 / ETA15 + V25 * I25) / V3) / ETA2


def derate(c, k, ks):
    return c * (k if c >= 20e-6 else ks)


def worst_ratio(direct, branch):
    w = np.logspace(3, 7, 3000) * 2 * np.pi
    rows = []
    for vs, L, R, (k, ks) in itertools.product(VS, LC, RC, zip(BIAS, BIAS_SMALL)):
        C = sum(derate(c, k, ks) for _, c in direct)
        y = 1 / (R + RON + 1j * w * L) + 1 / (ESR + 1 / (1j * w * C))
        variants = [None]
        if branch:
            rd, cds = branch[0], branch[1]
            variants = [(rd * t, sum(derate(c, kd, kd) for c in cds)) for t in (0.99, 1.01) for kd in BIAS]
        P = p_in(I3)
        v5 = vs
        for _ in range(40):
            v5 = vs - (R + RON) * P / v5
        rin = v5 * v5 / P
        for v in variants:
            yy = y + (1 / (v[0] + ESR + 1 / (1j * w * v[1])) if v else 0)
            z = np.abs(1 / yy)
            rows.append((z.max() / rin, z.max(), rin, vs, L, R, k, v, w[z.argmax()] / 2 / np.pi))
    return max(rows, key=lambda r: r[0]), len(rows)


def tx_burst(direct, branch):
    """5V node during a 250 Hz Wi-Fi TX burst train on a settled board; returns (min V, max V, corner of the min)."""
    from scipy.integrate import solve_ivp
    p_rx, p_tx = p_in(I3 - (I_TX - I_RX)), p_in(I3)
    lo, hi = (9.0, None), (0.0, None)
    for vs, L, R, (k, ks) in itertools.product(VS, (0.5e-6, 3.0e-6), (0.03, 0.3), zip(BIAS, BIAS_SMALL)):
        C = sum(derate(c, k, ks) for _, c in direct)
        rd, cd = (branch[0], sum(derate(c, k, k) for c in branch[1])) if branch else (1e6, 1e-12)

        def f(t, y):
            ic, vb, vd = y
            p = p_tx if (t % 4e-3) < 2e-3 else p_rx
            idamp = (vb - vd) / (rd + ESR)
            return [(vs - (R + RON) * ic - vb) / L, (ic - idamp - p / max(vb, 1.0)) / C, idamp / cd]
        i0 = p_rx / vs
        v0 = vs - (R + RON) * i0
        sol = solve_ivp(f, (0, 10e-3), [i0, v0, v0], method='LSODA', max_step=2e-6, rtol=1e-7, atol=1e-9)
        vb = sol.y[1][sol.t > 4e-3]
        if vb.min() < lo[0]:
            lo = (float(vb.min()), (vs, L, R, k))
        if vb.max() > hi[0]:
            hi = (float(vb.max()), (vs, L, R, k))
    return lo, hi


def main():
    path = sys.argv[sys.argv.index('--design') + 1]
    direct, branches = parts_5v(path)
    out, ok = [], True
    import hashlib
    out.append(f'design {path} sha256 ' + hashlib.sha256(open(path, 'rb').read()).hexdigest())
    out.append('5V ceramics straight across 5V: ' + ', '.join(f'{r} {c * 1e6:g} uF' for r, c in direct))
    if len(branches) != 1:
        out.append(f'FAIL damping branch: exactly one resistor from 5V into capacitors to GND expected, found {[(b[2], b[3]) for b in branches]}')
        ok = False
        branch = None
    else:
        branch = branches[0]
        out.append(f'damping branch: {branch[2]} {branch[0]:g} ohm in series with ' + ' + '.join(f'{r} {c * 1e6:g} uF' for r, c in zip(branch[3], branch[1])))
        cd_ratio = sum(branch[1]) / sum(c for _, c in direct)
        out.append(f'{"FAIL " if cd_ratio < MIN_CD else ""}damping capacitance / direct 5V ceramics = {cd_ratio:.2f} (at least {MIN_CD})')
        ok = ok and cd_ratio >= MIN_CD
    (ratio, zmax, rin, vs, L, R, k, v, fpk), n = worst_ratio(direct, branch)
    out.append(f'source impedance against the converter input resistance, {n} corners:')
    out.append(f'  worst |Zs|max / |Rin| = {ratio:.3f} (limit {LIMIT}): |Zs| {zmax:.2f} ohm at {fpk / 1e3:.1f} kHz against Rin {rin:.2f} ohm; '
               f'Vs {vs} V, cable {L * 1e6:g} uH / {R:g} ohm, 22 uF bias x{k}' + (f', damping {v[0]:.3f} ohm / {v[1] * 1e6:.1f} uF' if v else ''))
    (bare, *_), _ = worst_ratio(direct, None)
    out.append(f'  for reference, the same board without the damping branch: {bare:.3f}')
    if ratio > LIMIT:
        ok = False
    lo, hi = tx_burst(direct, branch)
    out.append(f'Wi-Fi TX burst train (3V3 {I_RX * 1e3:.0f} -> {I_TX * 1e3:.0f} mA, 250 Hz): 5V min {lo[0]:.3f} V (need > {U2_VIN_MIN:.2f} V) at Vs {lo[1][0]} L {lo[1][1] * 1e6:g} uH R {lo[1][2]:g}; '
               f'5V max {hi[0]:.3f} V (U2 VIN abs max {U2_VIN_ABS} V)')
    if lo[0] <= U2_VIN_MIN or hi[0] >= U2_VIN_ABS - 0.2:
        ok = False
    if branch:
        e = 0.5 * sum(branch[1]) * 5.5 ** 2
        out.append(f'{branch[2]} pulse when 5V is shorted or the box is unplugged under load: at most 1/2 C V^2 = {e * 1e3:.2f} mJ (0402 thick film; single event, not steady heat)')
    out.append(f'INPUTFILTER {"OK" if ok else "FAIL"} ratio {ratio:.3f} limit {LIMIT}')
    txt = '\n'.join(out)
    print(txt)
    if '--out' in sys.argv:
        open(sys.argv[sys.argv.index('--out') + 1], 'w', encoding='utf-8').write(txt + '\n')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
