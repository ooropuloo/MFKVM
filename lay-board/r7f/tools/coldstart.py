# -*- coding: utf-8 -*-
"""Cold plug-in with full load on every rail (r7e analysis, REVIEW_r7d m5). r7f: the U16 eFuse as built is modelled in sim_ef().

Time-domain model, 0-60 ms after a USB-C cable from a host port is plugged into J5 with nothing on the board charged:
  host:  Vs behind the port's power switch (on-resistance R_sw, current limit I_lim), port bulk C_host (USB 2.0 7.2.4.1: >= 120 uF)
  cable: R_cable + L_cable (as tools/hotplug.py)
  board 5V: ceramics C60 22u + C64 1u + C32 100n (DC-bias derated) and the damping branch R68 0.15 ohm + C69 330 uF (ESR ASSUMED 25 mOhm)
  U2  SY8089 5V->3V3: on when VIN rises above UVLO 2.5 V (max, rising; 0.2 V hysteresis) with EN = VIN above 1.5 V; soft start 1.2 ms
      (typ, the only number given) from 0 to 3.311 V; output limited to VIN - I x (RON_P 110 mOhm + DCR 80 mOhm); PFET limit 3.5 A (min).
      Input current = output power / 0.90 / VIN.        (SY8089 DS: VIN 2.7-5.5, ILIM >= 3.5 A, VENH 1.5 V, VUVLO 2.5 V max, TSS 1.2 ms)
  3V3 load, full, from the moment 3V3 exists (resistive below 3.3 V): ESP32-P4 380 mA (Espressif HW Design Guidelines p10: minimum
      supply 380 mA incl. flash/PSRAM) + ESP32-C6 Wi-Fi TX 354 mA (C6 DS v1.5 p66, 802.11b 21 dBm) + TC358743 AVDD33/VDDIO 142 mA (DS p8
      88 mA at 1080p60, x1.5 ASSUMED: no max published) + LCD 60 mA (ASSUMED: Waveshare 1.28in wiki gives no current) + microSD 200 mA
      (SD Physical Layer spec, high-speed class, from memory: NOT checked against a document here) + oscillator 15 mA + misc 17 mA
      = 1.168 A; plus U15 and U4 input current below.  3V3 capacitance: C1/C2/C10 10 uF, C61/C62/C65 22 uF, 100 nF x5 at 3.3 V bias
      (ASSUMED 65 %) + 20 uF inside the module (ASSUMED; the module schematic lists several 10 uF on ESP_3V3).
  U15 SY8089 3V3->1V2: on when 3V3 > 2.5 V; soft start 1.2 ms to 1.2102 V; load 274 mA (TC358743 VDDC+VDD_MIPI+AVDD12 1080p60 182 mA,
      DS p8, x1.5 ASSUMED), efficiency 0.85 (ASSUMED); V1V2 capacitance 54 uF + 3 x 4.7 uF at 1.2 V (ASSUMED 85 %).
  U4  TLV73325 3V3->2V5: follows 3V3 less 0.2 V dropout up to 2.5 V; 19 mA.
  CHIP_PU (ESP_EN): R11 10k from 3V3, C5 1 uF; the P4 starts when it crosses 0.75 x 3V3 (ASSUMED threshold; DS Table 2-14 asks the rails
      to be stable 50 us before).
Wi-Fi TX at start-up: in the full-load runs the 354 mA is drawn from t = 0 (worst for the start-up). A separate run starts from a
settled board with the C6 receiving (80 mA, C6 DS p67) and steps to 354 mA TX; it reports the 3V3 dip with the converter's loop modelled
as a 50 kHz crossover (ASSUMED) and the 5V droop through the cable and the port limit.
Corners: Vs 4.75 / 5.0 / 5.25 V; cable 0.1 / 0.3 ohm, 1 uH; port: bench supply (no limit), PC port with a 1.0 A limit switch (typical
TPS2051-class, ASSUMED), strict 0.55 A limit (USB 2.0 high-power port at its 500 mA budget). Everything ASSUMED is listed above;
nothing here is measured.
usage: coldstart.py [--plot out.png] [--report out.txt]
"""
import sys

import os

import numpy as np
from scipy.integrate import solve_ivp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
C_B = 22e-6 * 0.6 + 1e-6 * 0.65 + 0.1e-6 * 0.8      # 5V ceramics at 5 V bias
R68, C69, ESR69 = 0.15, 330e-6, 0.025
C_3 = (3 * 10e-6 + 3 * 22e-6 + 5 * 0.1e-6) * 0.65 + 20e-6
C_12 = (54e-6 + 3 * 4.7e-6) * 0.85
I3, I12, I25 = 1.168, 0.274, 0.019
V3, V12, V25 = 3.311, 1.2102, 2.5
ETA2, ETA15, RDROP = 0.90, 0.85, 0.19
UVLO_ON, UVLO_OFF, TSS = 2.5, 2.3, 1.2e-3
R_EN, C_EN = 10e3, 1e-6


def sim(vs, r_cable, l_cable=1e-6, i_lim=None, r_sw=0.08, c_host=120e-6, t_end=60e-3, i3=None, i12=None, c69=C69, r68=R68, t_ss_sw=None):
    I3_, I12_ = (I3 if i3 is None else i3), (I12 if i12 is None else i12)
    st = {'u2_on': None, 'u15_on': None}

    def rails(t, vb, ):
        """3V3 and V1V2 targets from the soft-start ramps"""
        if st['u2_on'] is None:
            return 0.0, 0.0
        ramp = min(1.0, (t - st['u2_on']) / TSS) * V3
        return ramp, None

    def f(t, y):
        vh, ic, vb, vd, v3, v12, ven = y
        # host switch
        isw = (vs - vh) / r_sw
        if i_lim is not None:
            isw = min(isw, i_lim)
        isw = max(isw, 0.0)
        # U2 state
        if st['u2_on'] is None and vb >= UVLO_ON:
            st['u2_on'] = t
        if st['u2_on'] is not None and vb < UVLO_OFF:
            st['u2_on'] = None
        # U15 state
        if st['u15_on'] is None and v3 >= UVLO_ON:
            st['u15_on'] = t
        if st['u15_on'] is not None and v3 < UVLO_OFF:
            st['u15_on'] = None
        # loads
        i3 = I3_ * max(v3, 0) / V3
        i12l = I12_ * max(v12, 0) / V12
        i15_in = (v12 * i12l + 0.0) / ETA15 / max(v3, 0.5) if st['u15_on'] is not None else 0.0
        i25 = I25 if v3 > 1.0 else 0.0
        iload3 = i3 + i15_in + i25 + max(v3 - ven, 0) / R_EN
        # U2: drives v3 toward the soft-start ramp; as a fast regulator with a 20 us time constant, current limited
        if st['u2_on'] is not None:
            tgt = min(min(1.0, (t - st['u2_on']) / TSS) * V3, vb - RDROP * 1.5)
            iout = max(0.0, min(3.5, iload3 + C_3 * (tgt - v3) / 20e-6))
            iu2 = v3 * iout / ETA2 / max(vb, 0.5) if v3 > 0.05 else iout * 0.3
        else:
            iout = iu2 = 0.0
        # U15
        if st['u15_on'] is not None:
            tgt12 = min(min(1.0, (t - st['u15_on']) / TSS) * V12, v3 - 0.2)
            i15 = max(0.0, min(3.5, i12l + C_12 * (tgt12 - v12) / 20e-6))
        else:
            i15 = 0.0
        idamp = (vb - vd) / (r68 + ESR69)
        if t_ss_sw is not None:
            # option A: a soft-start load switch right after J5. Its output (the board 5V node) follows a ramp to the input in t_ss_sw;
            # the current it passes is what the board needs along that ramp. The cable/port side then only sees that current (the cable
            # inductance and the switch's own small input capacitor are left out).
            vtgt = min(1.0, t / t_ss_sw) * (vh - r_cable * ic)
            ic_need = max(0.0, C_B * (vtgt - vb) / 5e-6 + idamp + iu2)
            return [(isw - ic) / c_host, (ic_need - ic) / 1e-6, (ic - idamp - iu2) / C_B, idamp / c69,
                    (iout - iload3) / C_3, (i15 - i12l) / C_12, (v3 - ven) / (R_EN * C_EN)]
        return [(isw - ic) / c_host,
                (vh - r_cable * ic - vb) / l_cable,
                (ic - idamp - iu2) / C_B,
                idamp / c69,
                (iout - iload3) / C_3,
                (i15 - i12l) / C_12,
                (v3 - ven) / (R_EN * C_EN)]

    y0 = [0.0] * 7
    if i_lim is None:
        y0[0] = vs   # bench supply: its own bulk is charged before the plug goes in
    else:
        y0[0] = vs   # host port: VBUS is already up on the port side when the cable is plugged
    sol = solve_ivp(f, (0, t_end), y0, method='LSODA', max_step=2e-6, rtol=1e-6, atol=1e-9)
    return sol


# ---------- r7f: TPS259531 eFuse (U16) between J5 VBUS (VBUS_IN, C70) and the board 5V. TI SLVSE57C numbers:
#   EN/UVLO divider R71 100k / R72 47k: VEN = VIN x 47/147; on at VUVLO(R) 1.2 V typ (1.13-1.27), off at VUVLO(F) 1.1 V typ (1.03-1.17)
#   current limit Eq. 4 RILM = 2000 / (ILIM - 0.04): R73 1k -> 2.04 A typ, +-7.5 % (1.89 A at the low end, used here)
#   slew rate Eq. 3 CdVdt(pF) = 42000 / SR(V/ms): C71 100 nF -> 0.42 V/ms, 0 -> 5 V in about 12 ms
#   turn-on delay tD,ON 289 us at CdVdt 3300 pF (7.6, typ; not given for 100 nF, used as is: ASSUMED)
#   RON 47 mOhm (max at TJ 125 C, 7.5); output clamp VCLAMP 5.45 V typ when VIN > VOVC 5.5-5.9 V (TPS25953x)
#   no current from OUT back to IN is modelled
# DELTA_r7f minor-D1: the eFuse parts are read from design.json (--design, default out/design.json) by the eFuse's pins, not written here:
#   EN top = the resistor from IN to EN, EN bottom = EN to GND, ILM = the resistor on pin 7, CdVdt = the capacitor on pin 1,
#   C_IN = every fitted capacitor from IN to GND, at 55 % of its value at 5 V bias (ASSUMED: typical 0402 X5R DC-bias loss; maker curve not read)
DESIGN = sys.argv[sys.argv.index('--design') + 1] if '--design' in sys.argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'design.json')
C_IN_BIAS = 0.55


def _val(v):
    import re
    m = re.match(r'\s*([\d.]+)\s*(p|n|u)F', v)
    if m:
        return float(m[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[m[2]]
    m = re.match(r'\s*([\d.]+)\s*([kM]?)', v)
    return float(m[1]) * {'': 1.0, 'k': 1e3, 'M': 1e6}[m[2]]


def efuse_parts(path):
    import json
    parts = [p for p in json.load(open(path, encoding='utf-8'))['parts'] if not p['dnp']]
    u = [p for p in parts if p['value'].startswith('TPS25953')]
    assert len(u) == 1, f'one fitted TPS25953x expected in {path}, found {[p["ref"] for p in u]}'
    n = u[0]['nets']
    on = lambda a, b: [p for p in parts if p is not u[0] and set(p['nets'].values()) == {a, b}]
    rt, rb, ilm = on(n['3'], n['2']), on(n['2'], 'GND'), on(n['7'], 'GND')
    dv, cin = on(n['1'], 'GND'), [p for p in on(n['3'], 'GND') if p['ref'].startswith('C')]
    assert len(rt) == len(rb) == len(ilm) == len(dv) == 1 and cin, f'eFuse support parts not found: {rt} {rb} {ilm} {dv} {cin}'
    return dict(r1=_val(rt[0]['value']), r2=_val(rb[0]['value']), rilm=_val(ilm[0]['value']), cdv=_val(dv[0]['value']),
                cin=sum(_val(c['value']) for c in cin), refs=dict(u=u[0]['ref'], r1=rt[0]['ref'], r2=rb[0]['ref'], ilm=ilm[0]['ref'], cdv=dv[0]['ref'], cin=[c['ref'] for c in cin]))


EFP = efuse_parts(DESIGN)
EF_R1, EF_R2 = EFP['r1'], EFP['r2']
EF_ON, EF_OFF = 1.2 * (EF_R1 + EF_R2) / EF_R2, 1.1 * (EF_R1 + EF_R2) / EF_R2
EF_SR = 42000 / (EFP['cdv'] * 1e12) * 1e3   # V/s (Eq. 3)
EF_TD = 289e-6
EF_RON = 0.047
EF_ILIM = (2000 / EFP['rilm'] + 0.04) * 0.925   # Eq. 4, low end of the 7.5 % ILIM accuracy (1k: 1.89 A)
EF_CLAMP = 5.45
C_IN = EFP['cin'] * C_IN_BIAS


def sim_ef(vs, r_cable, l_cable=1e-6, i_lim=None, r_sw=0.08, c_host=120e-6, t_end=60e-3, i3=None, i12=None, ilim=EF_ILIM, sr=EF_SR, ref=False):
    """eFuse board. ref=True replaces the board by the USB 2.0 7.2.4.1 reference load (10 uF || 44 ohm) for comparison."""
    I3_, I12_ = (I3 if i3 is None else i3), (I12 if i12 is None else i12)
    st = {'u2_on': None, 'u15_on': None, 'en': None, 'n_u2': 0, 'n_en': 0}

    def f(t, y):
        vh, ic, vin, vb, vd, v3, v12, ven, eflim = y
        isw = (vs - vh) / r_sw
        if i_lim is not None:
            isw = min(isw, i_lim)
        isw = max(0.0, isw)
        if ref:
            return [(isw - ic) / c_host, (vh - r_cable * ic - vin) / l_cable, (ic - vin / 44.0) / 10e-6, 0, 0, 0, 0, 0, 0]
        if st['en'] is None and vin * EF_R2 / (EF_R1 + EF_R2) >= 1.2:
            st['en'] = t
            st['n_en'] += 1
        if st['en'] is not None and vin * EF_R2 / (EF_R1 + EF_R2) < 1.1:
            st['en'] = None
        if st['en'] is not None and t - st['en'] > EF_TD:
            vtgt = min(sr * (t - st['en'] - EF_TD), vin, EF_CLAMP)
            ief = max(0.0, min(ilim, (vtgt - vb) / EF_RON))
            lim = 1.0 if (vtgt - vb) / EF_RON > ilim else 0.0
        else:
            ief, lim = 0.0, 0.0
        if st['u2_on'] is None and vb >= UVLO_ON:
            st['u2_on'] = t
            st['n_u2'] += 1
        if st['u2_on'] is not None and vb < UVLO_OFF:
            st['u2_on'] = None
        if st['u15_on'] is None and v3 >= UVLO_ON:
            st['u15_on'] = t
        if st['u15_on'] is not None and v3 < UVLO_OFF:
            st['u15_on'] = None
        i3 = I3_ * max(v3, 0) / V3
        i12l = I12_ * max(v12, 0) / V12
        i15_in = v12 * i12l / ETA15 / max(v3, 0.5) if st['u15_on'] is not None else 0.0
        i25 = I25 if v3 > 1.0 else 0.0
        iload3 = i3 + i15_in + i25 + max(v3 - ven, 0) / R_EN
        if st['u2_on'] is not None:
            tgt = min(min(1.0, (t - st['u2_on']) / TSS) * V3, vb - RDROP * 1.5)
            iout = max(0.0, min(3.5, iload3 + C_3 * (tgt - v3) / 20e-6))
            iu2 = v3 * iout / ETA2 / max(vb, 0.5) if v3 > 0.05 else iout * 0.3
        else:
            iout = iu2 = 0.0
        if st['u15_on'] is not None:
            tgt12 = min(min(1.0, (t - st['u15_on']) / TSS) * V12, v3 - 0.2)
            i15 = max(0.0, min(3.5, i12l + C_12 * (tgt12 - v12) / 20e-6))
        else:
            i15 = 0.0
        idamp = (vb - vd) / (R68 + ESR69)
        idiv = vin / (EF_R1 + EF_R2)
        return [(isw - ic) / c_host, (vh - r_cable * ic - vin) / l_cable, (ic - ief - idiv) / C_IN, (ief - idamp - iu2) / C_B, idamp / C69,
                (iout - iload3) / C_3, (i15 - i12l) / C_12, (v3 - ven) / (R_EN * C_EN), lim]

    y0 = [vs] + [0.0] * 8
    sol = solve_ivp(f, (0, t_end), y0, method='LSODA', max_step=2e-6, rtol=1e-6, atol=1e-9)
    sol.st = st
    return sol


def summarize_ef(sol):
    t = sol.t
    vh, ic, vin, vb, vd, v3, v12, ven, tlim = sol.y
    q = np.concatenate([[0], np.cumsum(0.5 * (ic[1:] + ic[:-1]) * np.diff(t))])
    k_att = np.searchsorted(t, EF_TD + 50e-6)
    k3 = np.argmax(v3 >= 0.95 * V3) if (v3 >= 0.95 * V3).any() else None
    k12 = np.argmax(v12 >= 0.95 * V12) if (v12 >= 0.95 * V12).any() else None
    m_en = (ven >= 0.75 * v3) & (v3 > 3.0)
    ken = np.argmax(m_en) if m_en.any() else None
    late = t > 1e-3
    p_fet = (vin - vb) * np.clip(ic, 0, None)
    return dict(i_att=ic[:k_att].max(), q_att=q[k_att] * 1e6, vin_max=vin.max(), ven_max=vin.max() * EF_R2 / (EF_R1 + EF_R2), vh_min_att=vh[:k_att].min(),
                i_peak_late=ic[late].max() if late.any() else 0.0, vh_min=vh.min(), vb_max=vb.max(), t3=t[k3] * 1e3 if k3 is not None else None,
                t12=t[k12] * 1e3 if k12 is not None else None, ten=t[ken] * 1e3 if ken is not None else None, v3_end=v3[-1], v12_end=v12[-1], vb_end=vb[-1],
                t_ilim=tlim[-1] * 1e3, p_fet_max=p_fet[late].max() if late.any() else 0.0, e_fet=np.trapz(p_fet, t) * 1e3, n_u2=sol.st['n_u2'], n_en=sol.st['n_en'])


def summarize(sol, vs, i_lim, r_sw=0.08):
    t = sol.t
    vh, ic, vb, vd, v3, v12, ven = sol.y
    q = np.concatenate([[0], np.cumsum(0.5 * (ic[1:] + ic[:-1]) * np.diff(t))])
    i_ss = ic[-1]
    k3 = np.argmax(v3 >= 0.95 * V3) if (v3 >= 0.95 * V3).any() else None
    k12 = np.argmax(v12 >= 0.95 * V12) if (v12 >= 0.95 * V12).any() else None
    k25 = np.argmax(v3 - 0.2 >= 0.95 * V25) if (v3 - 0.2 >= 0.95 * V25).any() else None
    m_en = (ven >= 0.75 * v3) & (v3 > 3.0)
    ken = np.argmax(m_en) if m_en.any() else None
    # charge delivered to the board above the steady state current, first 10 ms
    k10 = np.searchsorted(t, 10e-3)
    q_excess = q[k10] - i_ss * t[k10]
    return dict(i_peak=ic.max(), t_ipk=t[ic.argmax()] * 1e6, q10=q[k10] * 1e6, q_excess=q_excess * 1e6, vh_min=vh.min(), vb_min_after=vb[t > 2e-3].min() if (t > 2e-3).any() else 0,
                vb_max=vb.max(), i_ss=i_ss, t3=t[k3] * 1e3 if k3 is not None else None, t12=t[k12] * 1e3 if k12 is not None else None,
                t25=t[k25] * 1e3 if k25 is not None else None, ten=t[ken] * 1e3 if ken is not None else None, v3_end=v3[-1], v12_end=v12[-1])


def tx_step(vs, r_cable, i_lim, i_rx=0.080, i_tx=0.354, fc=50e3):
    """settled board, C6 steps RX -> TX. 5V side: DC droop through r_cable and the port limit; 3V3 dip from a 50 kHz loop on C_3."""
    i3_base = I3 - (i_tx - i_rx)                 # full load with the C6 receiving
    p_in = lambda i3: V3 * (i3 + (V12 * I12 / ETA15 + V25 * I25) / V3) / ETA2
    out = {}
    for name, i3 in (('rx', i3_base), ('tx', I3)):
        p = p_in(i3)
        # solve vb = vs - (r_cable + r_sw) * p / vb, with a port current limit
        vb, lim = vs, False
        for _ in range(60):
            i = p / vb
            if i_lim is not None and i > i_lim:
                i, lim = i_lim, True
                break
            vb = vs - (r_cable + 0.08) * i
        out[name] = (vb, p / vb if not lim else None, lim)
    dv3 = (i_tx - i_rx) / (2 * np.pi * fc * C_3)
    return out, dv3


if __name__ == '__main__':
    rows = []
    cases = [('bench supply, no limit', None), ('PC port, 1.0 A limit', 1.0), ('strict port, 0.55 A limit', 0.55)]
    # boot load: P4 in ROM/2nd-stage boot (DS Table 5-7, 400 MHz dual-core while(1) 112 mA + flash/PSRAM 50 mA ASSUMED), C6 RX 80 mA,
    # TC358743 held in reset by R21 (sleep currents, DS p8: under 1 mA; 10 mA ASSUMED), LCD 30 mA, SD idle 5 mA, oscillator and misc 32 mA
    BOOT3, BOOT12 = 0.112 + 0.050 + 0.080 + 0.010 + 0.030 + 0.005 + 0.032, 0.010
    lines = []
    lines.append('Cold plug-in, full load on every rail (tools/coldstart.py; every input is listed in its docstring)\n')
    lines.append(f"{'port':28s} {'Vs':>5s} {'Rcab':>5s} | {'Ipk A':>6s} {'at us':>6s} {'Q10ms uC':>9s} {'Qexcess':>8s} | {'Vhost min':>9s} "
                 f"{'5V max':>6s} {'5V min>2ms':>10s} | {'3V3 95% ms':>10s} {'2V5 ms':>6s} {'1V2 ms':>6s} {'CHIP_PU ms':>10s} | {'Iss A':>6s} {'3V3 end':>7s}")
    worst = {}
    sols = {}
    for load, i3, i12 in (('FULL', None, None), ('BOOT', BOOT3, BOOT12)):
      lines.append(f'--- load {load}: 3V3 {I3 if i3 is None else i3:.3f} A direct + 1V2 {I12 if i12 is None else i12:.3f} A ---')
      for name, ilim in cases:
        for vs in (4.75, 5.0, 5.25):
            for rc in (0.1, 0.3):
                sol = sim(vs, rc, i_lim=ilim, i3=i3, i12=i12)
                s = summarize(sol, vs, ilim)
                sols[(load, name, vs, rc)] = sol
                fmt = lambda v, f='{:.2f}': (f.format(v) if v is not None else '  never')
                lines.append(f"{name:28s} {vs:5.2f} {rc:5.2f} | {s['i_peak']:6.2f} {s['t_ipk']:6.0f} {s['q10']:9.0f} {s['q_excess']:8.0f} | {s['vh_min']:9.2f} "
                             f"{s['vb_max']:6.2f} {s['vb_min_after']:10.2f} | {fmt(s['t3']):>10s} {fmt(s['t25']):>6s} {fmt(s['t12']):>6s} {fmt(s['ten']):>10s} | {s['i_ss']:6.2f} {s['v3_end']:7.3f}")
    lines.append('\nQ10ms: charge into J5 in the first 10 ms; Qexcess: the same less the steady current x 10 ms (the inrush part).')
    lines.append('USB 2.0 7.2.4.1 attach limit for comparison: 10 uF and 50 uC. Board: 330 uF + ~14 uF ceramics on 5V -> about 1.7 mC to 5 V.\n')
    lines.append('Wi-Fi TX burst on a settled board (C6 80 mA RX -> 354 mA TX), 5V at J5 and 3V3 dip:')
    for name, ilim in cases:
        for vs in (4.75, 5.0):
            for rc in (0.1, 0.3):
                o, dv3 = tx_step(vs, rc, ilim)
                f5 = lambda x: (f"{x[0]:.2f} V at {x[1]:.2f} A" if x[1] else 'needs more than the port limit: 5V collapses')
                lines.append(f"  {name:28s} Vs {vs:4.2f} Rcab {rc:3.1f}: RX {f5(o['rx'])}, TX {f5(o['tx'])}; 3V3 dip about {dv3 * 1000:.0f} mV")
    # ---- options (analysis only, nothing changed on the board)
    lines.append('')
    lines.append('Options, Vs 5.0 V, cable 0.3 ohm / 1 uH, host port bulk 120 uF (USB 2.0 minimum):')
    lines.append(f"{'option':58s} {'port':26s} {'load':5s} | {'Ipk A':>6s} {'Vhost min':>9s} {'charge to 5V uC':>15s} | {'3V3 ms':>6s} {'1V2 ms':>6s} {'3V3 end':>7s}")
    OPT = [('0 as built: R68 0.15 + C69 330 uF', dict()),
           ('A soft-start load switch after J5, 5 ms ramp (C69 kept)', dict(t_ss_sw=5e-3)),
           ('A2 same switch, 2 ms ramp', dict(t_ss_sw=2e-3)),
           ('B C69 47 uF polymer, R68 0.33 ohm', dict(c69=47e-6, r68=0.33)),
           ('C no damping branch (C69/R68 off), TVS for the ring', dict(c69=1e-12, r68=1e6))]
    for oname, kw in OPT:
        for pname, ilim in (('PC port, 1.0 A limit', 1.0), ('strict port, 0.55 A limit', 0.55)):
            for load, i3, i12 in (('BOOT', BOOT3, BOOT12), ('FULL', None, None)):
                sol = sim(5.0, 0.3, i_lim=ilim, i3=i3, i12=i12, **kw)
                sm = summarize(sol, 5.0, ilim)
                c69_ = kw.get('c69', C69)
                cap = (C_B + (c69_ if c69_ > 1e-9 else 0.0)) * 5.0 * 1e6
                fmt = lambda v: f'{v:.2f}' if v is not None else 'never'
                lines.append(f"{oname:58s} {pname:26s} {load:5s} | {sm['i_peak']:6.2f} {sm['vh_min']:9.2f} {cap:15.0f} | {fmt(sm['t3']):>6s} {fmt(sm['t12']):>6s} {sm['v3_end']:7.3f}")
    # ---------- r7f: the eFuse as built
    lines.append('')
    lines.append('r7f AS BUILT (parts read from %s: %s): eFuse after J5 (UVLO %.2f V on / %.2f V off, ILIM %.2f A (low end), dV/dt %.2f V/ms, turn-on delay %.0f us), input capacitance %.2f uF on VBUS_IN (%.2f uF at 5 V bias, assumed)'
                 % (os.path.basename(DESIGN), EFP['refs'], EF_ON, EF_OFF, EF_ILIM, EF_SR / 1e3, EF_TD * 1e6, EFP['cin'] * 1e6, C_IN * 1e6))
    lines.append('Attach transient (the first %.0f us, before the eFuse conducts) against the USB 2.0 7.2.4.1 reference load 10 uF || 44 ohm on the same port and cable:' % ((EF_TD + 50e-6) * 1e6))
    lines.append(f"{'port':28s} {'Vs':>5s} {'Rcab':>5s} | {'Iatt A':>6s} {'Qatt uC':>7s} {'Vhost min':>9s} | {'ref Iatt':>8s} {'ref Q uC':>8s} {'ref Vhost':>9s} | {'VBUS_IN max':>11s} {'EN max':>6s}")
    att_ok = True
    for name, ilim in cases + [('USB-C 1.5 A source', 1.5), ('USB-C 3.0 A source', 3.0)]:
        for vs in (4.75, 5.25):
            for rc in (0.1, 0.3):
                se = summarize_ef(sim_ef(vs, rc, i_lim=ilim, i3=BOOT3, i12=BOOT12, t_end=EF_TD + 60e-6))
                sr_ = sim_ef(vs, rc, i_lim=ilim, ref=True, t_end=EF_TD + 50e-6)
                q_r = np.concatenate([[0], np.cumsum(0.5 * (sr_.y[1][1:] + sr_.y[1][:-1]) * np.diff(sr_.t))])[-1] * 1e6
                ok = se['q_att'] <= 50 and se['i_att'] <= sr_.y[1].max() + 1e-3 and se['vh_min_att'] >= sr_.y[0].min() - 1e-3
                att_ok &= ok
                lines.append(f"{name:28s} {vs:5.2f} {rc:5.2f} | {se['i_att']:6.2f} {se['q_att']:7.1f} {se['vh_min_att']:9.2f} | {sr_.y[1].max():8.2f} {q_r:8.1f} {sr_.y[0].min():9.2f} | {se['vin_max']:11.2f} {se['ven_max']:6.2f} {'OK' if ok else 'WORSE THAN REFERENCE'}")
    lines.append('attach transient no worse than the 10 uF / 50 uC reference in every corner: ' + ('YES' if att_ok else 'NO') + '; VBUS_IN must stay under 20 V (IN abs max), EN under 7 V (abs max)')
    lines.append('')
    lines.append('Cold start through the eFuse (0-60 ms):')
    lines.append(f"{'port':28s} {'load':5s} {'Vs':>5s} {'Rcab':>5s} | {'Ipk A':>6s} {'Vhost min':>9s} {'5V max':>6s} {'5V end':>6s} | {'3V3 ms':>6s} {'1V2 ms':>6s} {'PU ms':>6s} {'3V3 end':>7s} | {'U2 starts':>9s} {'EN starts':>9s} {'in ILIM ms':>10s} {'FET Wpk':>7s} {'FET mJ':>6s}")
    ef_res = {}
    for load, i3, i12 in (('BOOT', BOOT3, BOOT12), ('FULL', None, None)):
        for name, ilim in [('bench supply, no limit', None), ('USB-C 3.0 A source', 3.0), ('USB-C 1.5 A source', 1.5), ('PC port, 1.0 A limit', 1.0), ('strict port, 0.55 A limit', 0.55)]:
            for vs in (4.75, 5.25):
                for rc in (0.1, 0.3):
                    sol = sim_ef(vs, rc, i_lim=ilim, i3=i3, i12=i12)
                    se = summarize_ef(sol)
                    ef_res[(load, name, vs, rc)] = (se, sol)
                    fmt = lambda v: f'{v:.2f}' if v is not None else 'never'
                    good = se['t3'] is not None and se['n_u2'] == 1 and se['v3_end'] > 0.95 * V3 and se['ten'] is not None
                    lines.append(f"{name:28s} {load:5s} {vs:5.2f} {rc:5.2f} | {se['i_peak_late']:6.2f} {se['vh_min']:9.2f} {se['vb_max']:6.2f} {se['vb_end']:6.2f} | {fmt(se['t3']):>6s} {fmt(se['t12']):>6s} {fmt(se['ten']):>6s} {se['v3_end']:7.3f} | {se['n_u2']:9d} {se['n_en']:9d} {se['t_ilim']:10.2f} {se['p_fet_max']:7.2f} {se['e_fet']:6.1f} {'starts' if good else 'DOES NOT START CLEANLY'}")
    full_ok = all(r[0]['t3'] is not None and r[0]['n_u2'] == 1 and r[0]['v3_end'] > 0.95 * V3 and r[0]['ten'] is not None for k, r in ef_res.items() if k[0] == 'FULL' and k[1] in ('bench supply, no limit', 'USB-C 3.0 A source', 'USB-C 1.5 A source'))
    lines.append('full load starts cleanly (one U2 start, 3V3 at 95 %, CHIP_PU released) on every >= 1.5 A source corner: ' + ('YES' if full_ok else 'NO'))
    # cross-check with the full-load number tools/verify.py gates ILIM against (DELTA_r7f minor-D1)
    import re as _re
    _vf = _re.search(r'EF_FULL_A, EF_MARGIN = ([\d.]+), ([\d.]+)', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify.py'), encoding='utf-8').read())
    _pk = max(r[0]['i_peak_late'] for k, r in ef_res.items() if k[0] == 'FULL' and k[1] in ('bench supply, no limit', 'USB-C 3.0 A source', 'USB-C 1.5 A source'))
    lines.append(f"full-load peak during the ramp {_pk:.2f} A; verify.py gates ILIM low end > {_vf[1]} A x {_vf[2]}: "
                 + ('consistent' if _vf and _pk <= float(_vf[1]) + 0.005 else 'STALE: update EF_FULL_A in verify.py'))
    try:
        import hotplug
        worst = {}
        for oname, damp in (('0 as built', (330e-6, 0.15 + 0.025)), ('B 47 uF / 0.33', (47e-6, 0.33 + 0.025)), ('C no damping', None)):
            pk = 0
            for vs_ in hotplug.VS:
                for L in hotplug.LC:
                    for R in hotplug.RC:
                        for C in hotplug.CER:
                            t_, v_ = hotplug.run(vs_, L, R, C, damp=damp)
                            pk = max(pk, v_.max())
            worst[oname] = pk
        lines.append('Hot-plug overshoot at U2 VIN (tools/hotplug.py grid, ceramics only, no TVS): ' + ', '.join(f'{k} {v:.2f} V' for k, v in worst.items()) + '; limit 5.8 V (SY8089 abs max 6 V)')
    except Exception as e:
        lines.append(f'(hot-plug overshoot for the options not computed: {e})')
    txt = '\n'.join(lines)
    print(txt)
    if '--report' in sys.argv:
        open(sys.argv[sys.argv.index('--report') + 1], 'w', encoding='utf-8').write(__doc__ + '\n' + txt + '\n')
    if '--plot' in sys.argv:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(4, 1, figsize=(10, 13), sharex=True)
        for (name, ilim), c in zip(cases, ('C0', 'C1', 'C3')):
            sol = sols[('FULL', name, 5.0, 0.3)]
            t = sol.t * 1e3
            axs[0].plot(t, sol.y[1], c, label=f'{name}: J5 current')
            axs[1].plot(t, sol.y[2], c, label=f'{name}: 5V at U2')
            axs[1].plot(t, sol.y[0], c + '--', lw=0.8, label=f'{name}: host VBUS')
            axs[2].plot(t, sol.y[4], c, label=f'{name}: 3V3')
            axs[2].plot(t, sol.y[5], c + ':', label=f'{name}: 1V2')
        for (nm, il), c in ((('USB-C 1.5 A source', 1.5), 'C2'), (('PC port, 1.0 A limit', 1.0), 'C1')):
            se, sol = ef_res[('FULL', nm, 4.75, 0.3)]
            t = sol.t * 1e3
            axs[3].plot(t, sol.y[1], c, lw=0.8, label=f'r7f eFuse, {nm}, Vs 4.75: J5 current A')
            axs[3].plot(t, sol.y[3], c + '--', label='5V (eFuse out) V')
            axs[3].plot(t, sol.y[5], c + ':', label='3V3 V')
        axs[3].set_ylabel('r7f eFuse')
        axs[0].set_ylabel('A')
        axs[1].set_ylabel('V')
        axs[2].set_ylabel('V')
        axs[2].set_xlabel('ms after plug-in (Vs 5.0 V, cable 0.3 ohm / 1 uH)')
        for a in axs:
            a.grid(alpha=0.3)
            a.legend(fontsize=7)
        axs[0].set_xlim(0, 30)
        fig.tight_layout()
        fig.savefig(sys.argv[sys.argv.index('--plot') + 1], dpi=110)
