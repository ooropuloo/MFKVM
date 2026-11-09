# -*- coding: utf-8 -*-
"""5 V hot-plug: peak voltage at U2 (SY8089) VIN when a live USB-C cable is plugged into J5.

Model (lumped, per Linear AN-88 "Ceramic Input Capacitors Can Cause Overvoltage Transients", and TI SLVA670):
  ideal source step Vs -> cable series R_cable + L_cable -> board 5V node.
  board 5V node: ceramic capacitance (DC-bias derated, own ESR), optional damping capacitor (C_d with series ESR R_d),
  optional TVS (piecewise: off below V_br, then V_clamp-style slope from the datasheet two-point line), U2 input current 0
  (SY8089 soft start 1.2 ms, AN p4, is far longer than the ring, so the converter draws nothing during the first peak).
Board copper from J5 to U2 (about 10 mm of 0.4-0.8 mm track, 6-8 nH) is ignored next to 0.5-1.5 uH of cable.

Parameter ranges (ASSUMED where marked, nothing here is measured):
  Vs       5.0, 5.25 V            USB 2.0 VBUS at the source port (5.25 max)
  L_cable  0.5 - 1.5 uH           0.5-1.5 m USB-C cable, about 1 uH/m loop (ASSUMED, the usual estimate; not measured)
  R_cable  30 - 200 mOhm          VBUS + GND round trip incl. contacts (ASSUMED)
  ceramic  C60 22 uF 0805 25 V X5R (Samsung CL21A226MAQNNNE) at 5 V: 40-80 % of nominal (ASSUMED; DC-bias curve not read);
           C64 1 uF 0402 25 V X5R and C32 100 nF: 50-80 %; ESR 5 mOhm total (ASSUMED)
usage: hotplug.py [--fix] [--plot out.png]    prints the worst case over the grid; exit 1 if the worst peak exceeds 5.8 V
"""
import itertools
import sys

import numpy as np
from scipy.integrate import solve_ivp

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
VS = (5.0, 5.25)
LC = (0.5e-6, 1.0e-6, 1.5e-6)
RC = (0.03, 0.06, 0.1, 0.2)
CER = [(22e-6 * k + 1.1e-6 * k2) for k, k2 in ((0.4, 0.5), (0.6, 0.65), (0.8, 0.8))]
ESR_CER = 0.005


def run(vs, L, R, C, damp=None, tvs=None, t_end=150e-6):   # r7c: 150 us; with 330 uF the latest peak is at 49 us (checked to 800 us)
    """state: i_L, v_C (ceramic), v_d (damping cap internal). damp = (C_d, R_d). tvs = (V_br, V_c_at_I, I) linearised."""
    Cd, Rd = damp if damp else (None, None)

    def i_tvs(v):
        if not tvs:
            return 0.0
        vbr, vc, ipp = tvs
        return max(0.0, (v - vbr) / ((vc - vbr) / ipp))

    def node_v(iL, vc, vd):
        # node voltage v: (iL - (v-vc)/ESR - (v-vd)/Rd - itvs(v)) = 0, solve by a few Newton steps (TVS is piecewise linear)
        g = 1 / ESR_CER + (1 / Rd if damp else 0)
        v = (iL + vc / ESR_CER + (vd / Rd if damp else 0)) / g
        for _ in range(3):
            if tvs and v > tvs[0]:
                gt = 1 / ((tvs[1] - tvs[0]) / tvs[2])
                v = (iL + vc / ESR_CER + (vd / Rd if damp else 0) + gt * tvs[0]) / (g + gt)
        return v

    def f(t, y):
        iL, vc, vd = y
        v = node_v(iL, vc, vd)
        return [(vs - R * iL - v) / L, (v - vc) / ESR_CER / C, ((v - vd) / Rd / Cd) if damp else 0.0]

    sol = solve_ivp(f, (0, t_end), [0.0, 0.0, 0.0], max_step=5e-8, rtol=1e-7, atol=1e-9)
    v = np.array([node_v(*sol.y[:, i]) for i in range(sol.y.shape[1])])
    return sol.t, v


def grid(damp=None, tvs=None):
    rows = []
    for vs, L, R, C in itertools.product(VS, LC, RC, CER):
        t, v = run(vs, L, R, C, damp, tvs)
        rows.append((v.max(), vs, L, R, C))
    return sorted(rows, reverse=True)


def from_design(path):
    """Ceramic capacitance range and damping corners read from the board's design.json (fitted parts on the 5V net only).
    Ceramic: 22 uF and up at 40-80 % of nominal, smaller at 50-80 % (DC bias at 5 V, ASSUMED as above).
    Damping: a resistor from 5V to a net that holds a polarized capacitor (lib CP_*) to GND: C +-20 % (10TPE330M, LCSC listing),
    R +-1 % (UNI-ROYAL 0805W8F), plus the capacitor's ESR 0-25 mOhm (LCSC listing: 25 mOhm max at 100 kHz)."""
    import json
    import re as _re
    d = json.load(open(path, encoding='utf-8'))
    fit = [p for p in d['parts'] if not p['dnp']]

    def farad(v):
        m = _re.match(r'([\d.]+)\s*(p|n|u)F', v)
        return float(m[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[m[2]] if m else None
    lo = hi = 0.0
    damp = []
    for p in fit:
        nets = set(p['nets'].values())
        if p['ref'].startswith('C') and nets == {'5V', 'GND'} and not p['lib'].startswith('CP_'):
            c = farad(p['value'])
            k = (0.4, 0.8) if c >= 10e-6 else (0.5, 0.8)
            lo += c * k[0]
            hi += c * k[1]
    for r in fit:
        if r['ref'].startswith('R') and '5V' in r['nets'].values():
            other = [n for n in r['nets'].values() if n != '5V'][0]
            caps = [p for p in fit if p['lib'].startswith('CP_') and set(p['nets'].values()) == {other, 'GND'}]
            if caps:
                ohm = float(r['value'].split()[0])
                c = farad(caps[0]['value'].replace('POSCAP 10TPE330M ', ''))
                damp.append((r['ref'], caps[0]['ref'], ohm, c))
    return (lo, hi), damp


if __name__ == '__main__':
    if '--design' in sys.argv:
        path = sys.argv[sys.argv.index('--design') + 1]
        import hashlib
        # r7f: with the eFuse (U16, TPS259531, LCSC C2155674) between J5 and 5V, the cable rings into VBUS_IN (its ceramics only) while
        # the eFuse is still off (turn-on delay 289 us, TI SLVSE57C 7.6), and 5V/U2 see a 12 ms ramp clamped at VCLAMP <= 5.7 V (7.5).
        # Limits on the ring: IN abs max 20 V (7.1; 18 V used, the top of the operating range 7.3); EN/UVLO abs max 7 V through the
        # R71/R72 divider (6 V used, 7.3 operating maximum).
        import json as _json
        _d = _json.load(open(path, encoding='utf-8'))
        _ef = [p for p in _d['parts'] if p['lcsc'] == 'C2155674' and not p['dnp']]
        if _ef:
            _ef = _ef[0]
            vin_net, en_net = _ef['nets']['3'], _ef['nets']['2']
            fit = [p for p in _d['parts'] if not p['dnp']]
            _f = lambda v: float(__import__('re').match(r'([\d.]+)\s*(p|n|u)F', v)[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[__import__('re').match(r'([\d.]+)\s*(p|n|u)F', v)[2]]
            cs = [_f(p['value']) for p in fit if p['ref'].startswith('C') and set(p['nets'].values()) == {vin_net, 'GND'}]
            clo, chi = sum(c * (0.4 if c >= 10e-6 else 0.5) for c in cs), sum(c * 0.8 for c in cs)
            rtop = [float(p['value'].split()[0].replace('k', '')) * (1e3 if 'k' in p['value'].split()[0] else 1) for p in fit if p['ref'].startswith('R') and set(p['nets'].values()) == {vin_net, en_net}]
            rbot = [float(p['value'].split()[0].replace('k', '')) * (1e3 if 'k' in p['value'].split()[0] else 1) for p in fit if p['ref'].startswith('R') and set(p['nets'].values()) == {en_net, 'GND'}]
            k_en = rbot[0] / (rtop[0] + rbot[0]) if rtop and rbot else (1.0 if rtop or not rbot else 0.0)   # no bottom resistor: EN sees VBUS_IN
            CER = [clo, (clo + chi) / 2, chi]
            rows = grid(None)
            pk = rows[0][0]
            lines = [f'design {path} sha256 {hashlib.sha256(open(path, "rb").read()).hexdigest()}',
                     f'r7f eFuse {_ef["ref"]}: J5 rings into {vin_net} ({clo * 1e6:.2f}-{chi * 1e6:.2f} uF effective, no damping) while the eFuse is off',
                     f'  worst {vin_net} peak {pk:.3f} V at Vs {rows[0][1]} L {rows[0][2] * 1e6:.1f} uH R {rows[0][3] * 1e3:.0f} mOhm C {rows[0][4] * 1e6:.2f} uF; {len(rows)} cases (limit 18 V, IN abs max 20 V)',
                     f'  EN/UVLO peak {pk * k_en:.3f} V through {rtop and rtop[0] / 1e3}k/{rbot and rbot[0] / 1e3}k (limit 6 V, abs max 7 V)',
                     '  5V (U2 VIN): the eFuse output is a 12 ms dV/dt ramp, clamped at VCLAMP 5.7 V max (TPS25953x): <= 5.7 V, under 5.8 V']
            ok = pk <= 18.0 and pk * k_en <= 6.0
            lines.append(f'HOTPLUG WORST {pk:.3f} V at VBUS_IN, {pk * k_en:.3f} V at EN, U2 VIN <= 5.70 V ' + ('OK' if ok else 'OVER LIMIT'))
            txt = '\n'.join(lines) + '\n'
            print(txt, end='')
            if '--out' in sys.argv:
                open(sys.argv[sys.argv.index('--out') + 1], 'w', encoding='utf-8', newline='\n').write(txt)
            sys.exit(0 if ok else 1)
        (clo, chi), damp = from_design(path)
        CER = [clo, (clo + chi) / 2, chi]
        lines = [f'design {path} sha256 {hashlib.sha256(open(path, "rb").read()).hexdigest()}',
                 f'ceramic on 5V: {clo * 1e6:.2f}-{chi * 1e6:.2f} uF effective; damping networks found: {damp or "none"}']
        corners = [None] if not damp else [(c * kc, ohm * kr + esr) for _, _, ohm, c in damp[:1] for kc in (0.8, 1.2) for kr in (0.99, 1.01) for esr in (0.0, 0.025)]
        worst = 0.0
        for dmp in corners:
            rows = grid(dmp)
            worst = max(worst, rows[0][0])
            lines.append(f'  damping {dmp and (round(dmp[0] * 1e6), round(dmp[1], 4))}: worst {rows[0][0]:.3f} V at Vs {rows[0][1]} L {rows[0][2] * 1e6:.1f} uH R {rows[0][3] * 1e3:.0f} mOhm C {rows[0][4] * 1e6:.1f} uF; {len(rows)} cases')
        lines.append(f'HOTPLUG WORST {worst:.3f} V ' + ('OK (<= 5.8 V)' if worst <= 5.8 else 'OVER 5.8 V'))
        txt = '\n'.join(lines) + '\n'
        print(txt, end='')
        if '--out' in sys.argv:
            open(sys.argv[sys.argv.index('--out') + 1], 'w', encoding='utf-8', newline='\n').write(txt)
        sys.exit(0 if worst <= 5.8 else 1)
    fix = '--fix' in sys.argv
    # Fix: damping capacitor C_d with ESR R_d (Linear AN-88: C_d >= 4 x ceramic, R_d near sqrt(L/C_ceramic)).
    DAMP = None
    if fix:
        DAMP = (float(sys.argv[sys.argv.index('--fix') + 1]), float(sys.argv[sys.argv.index('--fix') + 2]))
    rows = grid(DAMP)
    print(f'damping: {DAMP or "none (r7b: ceramic only)"}')
    print(f'{"peak V":>8s} {"Vs":>5s} {"L uH":>5s} {"R mOhm":>7s} {"C_cer uF":>9s}')
    for r in rows[:6]:
        print(f'{r[0]:8.3f} {r[1]:5.2f} {r[2] * 1e6:5.2f} {r[3] * 1e3:7.0f} {r[4] * 1e6:9.2f}')
    print(f'... {len(rows)} cases, lowest peak {rows[-1][0]:.3f} V')
    worst = rows[0][0]
    if '--plot' in sys.argv:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        out = sys.argv[sys.argv.index('--plot') + 1]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for r in rows[:1] + rows[len(rows) // 2:len(rows) // 2 + 1] + rows[-1:]:
            t, v = run(r[1], r[2], r[3], r[4], DAMP)
            ax.plot(t * 1e6, v, label=f'Vs {r[1]} L {r[2] * 1e6:.1f}uH R {r[3] * 1e3:.0f}mOhm C {r[4] * 1e6:.1f}uF: peak {r[0]:.2f} V')
        ax.axhline(6.0, color='r', ls='--', lw=0.8, label='SY8089 VIN abs max 6.0 V')
        ax.axhline(5.8, color='orange', ls=':', lw=0.8, label='target 5.8 V')
        ax.set_xlabel('us'); ax.set_ylabel('U2 VIN, V'); ax.set_title('J5 hot-plug ' + (f'with damping {DAMP[0] * 1e6:.0f} uF / {DAMP[1] * 1e3:.0f} mOhm' if DAMP else '(r7b, ceramic only)'))
        ax.legend(fontsize=7); ax.grid(lw=0.3); plt.tight_layout(); plt.savefig(out, dpi=110)
    print('WORST PEAK', f'{worst:.3f} V', 'OK (<= 5.8 V)' if worst <= 5.8 else 'OVER 5.8 V')
    sys.exit(0 if worst <= 5.8 else 1)
