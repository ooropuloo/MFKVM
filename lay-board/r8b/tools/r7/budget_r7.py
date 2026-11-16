# -*- coding: utf-8 -*-
"""r7 item 3: current budget and the 1.2 V rail, recomputed for U15 (SY8089 buck from 3V3, sensed at R65) in place of U5 (TLV73312).

Load currents are the r6 budget's (current_budget.md 1.1-1.5); only what r7 changes is recomputed here. Copper resistance is solved on the
saved board with tools/r6/power_paths.py (nodal analysis; rho 1.72e-5 ohm mm; 35 um outer, 15.2 um In2; via plating 18 um ASSUMED).
usage: budget_r7.py <board.kicad_pcb>
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'r6'))
sys.argv = [sys.argv[0], sys.argv[1]]
import brd  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'r6', 'power_paths.py'), encoding='utf-8').read()
_ns = {}
exec(_src.split('\npcb = sys.argv[1]')[0], _ns)  # the solver only, not its report
solve = _ns['solve']
B = brd.load(sys.argv[1])
pad = {f"{q['ref']}.{q['num']}": q for q in B['pads']}


def P(n):
    return (pad[n]['x'], pad[n]['y'], 'F.Cu' if pad[n]['side'] == 'F' else 'B.Cu')


def R(net, a, b):
    return solve(B, net, P(a), P(b))


HOT = 1.197  # copper at 70 C against 25 C, as in current_budget.md
I = dict(AVDD12=(82.9, 124.4), VDDC=(76.6, 114.9), VDD_MIPI=(22.8, 34.2), AVDD25=(12.8, 19.2))  # mA typ, worst: current_budget.md 1.1
i12 = tuple(I['AVDD12'][k] + I['VDDC'][k] + I['VDD_MIPI'][k] for k in (0, 1))
print(f'V1V2 load {i12[0]:.1f} mA typical, {i12[1]:.1f} mA worst (AVDD12 + VDDC + VDD_MIPI)')

print('\nCopper, solved on the board (25 C):')
r_route = R('V1V2', 'L2.2', 'R65.2')
r_fb3 = R('V1V2', 'R65.2', 'FB3.1')
r_fb4 = R('V1V2', 'R65.2', 'FB4.1')
r_fb5 = R('V1V2', 'R65.2', 'FB5.1')
r_sns = R('V1V2_SNS', 'R62.1', 'R65.1')
r_25 = R('V2V5', 'U4.5', 'FB2.1')
for k, v in (('V1V2 L2.2 to R65.2 (sense point), power path', r_route), ('V1V2 R65.2 to FB3.1', r_fb3), ('V1V2 R65.2 to FB4.1', r_fb4), ('V1V2 R65.2 to FB5.1', r_fb5),
             ('V1V2_SNS R62.1 to R65.1 (carries the divider current only)', r_sns), ('V2V5 U4.5 to FB2.1', r_25)):
    print(f'  {k:58s} {v * 1000:7.1f} mOhm')

# U15 output at the sense point: VREF 0.588-0.612 (AN p4, at 25 C), R61 33k + R62 560 = 33.56k over R63 33k, all 1%, FB current +-50 nA through the top
rt, rb = 33.56e3, 33e3
TOL = 0.001   # r7b: R61-R63 are 0.1% (r7 had 1%)
lo = 0.588 * (1 + rt * (1 - TOL) / (rb * (1 + TOL))) - 50e-9 * rt
hi = 0.612 * (1 + rt * (1 + TOL) / (rb * (1 - TOL))) + 50e-9 * rt
for t in (0.01, 0.001):
    print(f'  resistors {t * 100:g}%: sense point {0.588 * (1 + rt * (1 - t) / (rb * (1 + t))) - 50e-9 * rt:.4f} to {0.612 * (1 + rt * (1 + t) / (rb * (1 - t))) + 50e-9 * rt:.4f} V')
nom = 0.6 * (1 + rt / rb)
print(f'\nU15 at the sense point: nominal {nom:.4f} V, worst {lo:.4f} to {hi:.4f} V')
# AVDD12 at the ball: sense point, then R65 to FB3 copper, FB3 DCR (BLM21PG221SN1D 0.045 max, 0.09 after test, current_budget.md 3.1), FB3 to ball copper 56.8 mOhm (r6 measure)
for label, dcr, i, hot in (('typical current, 25 C, DCR 0.045', 0.045, I['AVDD12'][0], 1.0), ('worst current, 70 C copper, DCR 0.09 (after test)', 0.09, I['AVDD12'][1], HOT)):
    drop = (r_fb3 * hot + dcr + 0.0568 * hot) * i / 1000  # only AVDD12 current flows R65 -> FB3
    print(f'  AVDD12 at the ball, {label}: drop {drop * 1000:.1f} mV -> {lo - drop:.4f} to {hi:.4f} V  (limit 1.15-1.25, Toshiba p15)')
for name, lim in (('VDDC', 1.1), ('VDD_MIPI', 1.1)):
    print(f'  {name}: at least {lo - 0.05:.4f} V before the ball (50 mV allowed for bead and copper; r6 measured 68-83 mOhm) against {lim} V')
# r7b M4: R66 100R ties the sense node to U15's output as well. With both ends connected the node sits between the two by the divider of
# R66 and the sense line (R65 0R + copper), so it moves toward the local end by route drop x Rline / (100 + Rline). If the remote line opens,
# U15 regulates at its own output through R66 (100R + 33.56k in the top of the divider: the set point moves 0.6 x 100/33000 = 1.8 mV up).
_dv = r_route * HOT * i12[1]
print(f'  R66 100R fallback, both paths intact: sense node {_dv * r_sns / (100 + r_sns):.3f} mV toward U15 at worst current (included in the window)')
_loc_lo = lo + 0.6 * 100 / 33e3 - (_dv + 0.09 * 124.4 + 0.0568 * HOT * 124.4 + r_fb3 * HOT * 124.4) / 1000
print('  If the remote sense opens (R65, the line): U15 regulates at its output through R66; the power path drop adds', f'{_dv:.1f} mV at worst current: AVDD12 down to {_loc_lo:.4f} V. Out of spec but no overvoltage')
print('  R61 or R62 open: not covered by R66; R63 pulls FB to 0, U15 goes to 100% duty and V1V2 follows 3V3. R63 open: FB follows the output, V1V2 about 0.6 V (safe)')

# U15 input and the 3V3 rail
for label, k, eta, vin, vout in (('typical', 0, 0.88, 3.3, nom), ('worst', 1, 0.85, 3.2, hi)):
    iin = vout * i12[k] / (eta * vin)
    ploss = vout * i12[k] * (1 / eta - 1) / 1000
    print(f'\nU15 {label}: Iout {i12[k]:.1f} mA, efficiency {eta} ASSUMED (the AN p5 curves are for 5 V in), Iin {iin:.1f} mA from 3V3, loss {ploss * 1000:.0f} mW in U15 + L2')
    print(f'  U15 junction rise if all the loss were in U15: {ploss * 170:.0f} C (theta JA 170 C/W, AN p2); U5 was +54 / +81 C')
    i3 = (652, 1461)[k] - (195.2, 292.8)[k] + I['AVDD25'][k] + iin
    print(f'  3V3 rail {i3:.0f} mA (r6 {(652, 1461)[k]}): U4 now carries only AVDD25 {I["AVDD25"][k]} mA instead of {(195.2, 292.8)[k]} mA')
    eta2, v5 = (0.94, 5.0) if k == 0 else (0.90, 4.75)
    i5 = 3.3 * i3 / (eta2 * v5) + (1.5, 5)[k] + (0, 1)[k]
    print(f'  5V in {i5:.0f} mA (r6 about {(460, 1134)[k]}), U2 at {i3 / 2000 * 100:.0f}% of its 2 A')
pu4 = (3.4407 - 2.5) * 19.2e-3   # 3V3 top with R51 33.2k (r7b)
print(f'\nU4 TLV73325: {19.2} mA of 300 mA ({19.2 / 3:.0f}%), dissipation {pu4 * 1000:.0f} mW, rise {pu4 * 228.4:.0f} C (RthJA 228.4, SBVS235 p5). r6: 293 mA (98%)')

# ripple at U15's output, first order: inductor ripple into the output capacitance
for f in (1.0e6,):
    for L, vin in ((2.2e-6, 3.3), (1.76e-6, 3.4407)):
        di = 1.21 * (1 - 1.21 / vin) / (L * f)
        for c in (44e-6, 30e-6):
            print(f'ripple: L {L * 1e6:.2f} uH, VIN {vin} V: inductor {di * 1000:.0f} mA p-p, peak {i12[1] + di * 500:.0f} mA; '
                  f'on {c * 1e6:.0f} uF {di / (8 * f * c) * 1000:.1f} mV p-p (capacitive part only; ESL spikes and light-load pulse skipping not modelled)')
print('AVDD12 limit is 40 mV p-p (Toshiba p15 VSN12); FB3 and C15/C16 filter further. Not measured.')
