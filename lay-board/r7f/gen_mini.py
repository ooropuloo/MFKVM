# -*- coding: utf-8 -*-
"""P4 KVM Mini: writes the KiCad schematic and board, a Specctra DSN for routing, and imports the routed SES.

usage: gen_mini.py <out_dir> [routed.ses]
Board mm: origin at the PCB centre, x right, y toward the back wall, seen from the top. The I/O face is y = -20.
"""
import json
import math
import os
import re
import sys
import uuid

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1]
SES = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT, exist_ok=True)
NAME = 'p4_kvm_mini'
PCB = 40.0
H = PCB / 2
OX, OY = 100.0, 100.0
HOLE = 18.0
YB = H  # back edge (+y). r7c moves it to 25.0 in its own stage, after the routed board is imported
EXO = json.load(open(f'{HERE}/data/exo.json', encoding='utf-8'))
ANT = json.load(open(f'{HERE}/data/ant.json', encoding='utf-8'))
LAND = json.load(open(f'{HERE}/data/land.json', encoding='utf-8'))


def uid(seed=None):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'p4mini-' + seed)) if seed else str(uuid.uuid4())


def pad(n, x, y, w, h, shape='rect', kind='smd', d1=0.0, d2=0.0):
    return dict(n=str(n), x=x, y=y, w=w, h=h, shape=shape, kind=kind, d1=d1, d2=d2)


def from_json(block, swap=False):
    out = []
    for q in block['pads']:
        w, h = q['w'], q['h']
        if swap and round(abs(q['a'])) % 180 == 90 and q['kind'] == 'smd':
            w, h = h, w
        shape = 'circle' if q['shape'] == 'circle' else ('oval' if q['shape'] == 'oval' else 'rect')
        out.append(pad(q['n'], q['x'], q['y'], w, h, shape, 'thru_hole' if q['kind'] == 'thru_hole' else 'smd', q['d1'], q['d2']))
    return out


# ---------- footprints
R0402 = [pad(1, -0.48, 0, 0.56, 0.62), pad(2, 0.48, 0, 0.56, 0.62)]
C0603 = [pad(1, -0.78, 0, 0.8, 0.95), pad(2, 0.78, 0, 0.8, 0.95)]
C0805 = [pad(1, -0.95, 0, 1.0, 1.35), pad(2, 0.95, 0, 1.0, 1.35)]
IND4020 = [pad(1, -1.5, 0, 1.1, 3.7), pad(2, 1.5, 0, 1.1, 3.7)]
SOT235 = [pad(1, -0.95, 1.1375, 0.6, 1.325), pad(2, 0, 1.1375, 0.6, 1.325), pad(3, 0.95, 1.1375, 0.6, 1.325), pad(4, 0.95, -1.1375, 0.6, 1.325), pad(5, -0.95, -1.1375, 0.6, 1.325)]
SOT23 = [pad(1, -0.95, 0.9375, 0.6, 1.475), pad(2, 0.95, 0.9375, 0.6, 1.475), pad(3, 0, -0.9375, 0.6, 1.475)]
MSOP8 = [pad(i + 1, -0.975 + i * 0.65, 2.1125, 0.5, 1.625) for i in range(4)] + [pad(i + 5, 0.975 - i * 0.65, -2.1125, 0.5, 1.625) for i in range(4)]
OSC3225 = [pad(1, -1.05, 0.825, 1.3, 1.1), pad(2, 1.05, 0.825, 1.3, 1.1), pad(3, 1.05, -0.825, 1.3, 1.1), pad(4, -1.05, -0.825, 1.3, 1.1)]
# Everlight EL3H7-G datasheet DPC-0000031 rev 7, p7, recommended land: 1.5 x 0.6, pitch 1.27, inner 4.85, outer 7.85
OPTO = [pad(1, -3.175, -0.635, 1.5, 0.6), pad(2, -3.175, 0.635, 1.5, 0.6), pad(3, 3.175, 0.635, 1.5, 0.6), pad(4, 3.175, -0.635, 1.5, 0.6)]
# Hirose U.FL-R-SMT-1(10), LCSC C88373. Land from the Hirose U.FL catalogue p3 'Recommended PCB Mounting Pattern' (read 2026-11-07):
# GND pads 1.05 x 2.2, 1.9 apart inside and 4.0 outside; SIG pad 1.0 x 1.05, its near edge 1.0 from the centre line. KiCad's own vme-wren demo footprint has the same numbers.
UFL = [pad(1, 0, 1.525, 1.0, 1.05), pad(2, -1.475, 0, 1.05, 2.2), pad(3, 1.475, 0, 1.05, 2.2)]
USBC = from_json(EXO['USB2'])
HDMI = from_json(EXO['HDMI1'])
USON10 = from_json(EXO['D2'])
BGA = from_json(ANT['U1'])


def sh_conn(n):
    # JST SM0xB-SRSS-TB land pattern, from the official KiCad library
    half = (n - 1) / 2
    return [pad(i + 1, -half + i, -2.0, 0.6, 1.55) for i in range(n)] + [pad(n + 1, -half - 1.3, 1.875, 1.2, 1.8), pad(n + 2, half + 1.3, 1.875, 1.2, 1.8)]


def module_pads():
    out = []
    for x, y, w, h in LAND:
        if x == -12.5:
            n = int(round(y + 10.5)) + 1
        elif y == 12.5:
            n = int(round(x + 10.5)) + 23
        elif x == 12.5:
            n = int(round(10.5 - y)) + 45
        else:
            n = int(round(10.5 - x)) + 67
        out.append(pad(n, x, y, w, h))
    assert sorted(int(q['n']) for q in out) == list(range(1, 89))
    return sorted(out, key=lambda q: int(q['n']))


# Molex 104031-0811 push-pull microSD, from the official KiCad library. The card enters from local -y.
_tf = json.load(open(f'{HERE}/data/kicad_official.json', encoding='utf-8'))['microSD_HC_Molex_104031-0811']
_sh = iter(('SH1', 'SH2', 'SH3', 'SH4'))
TF = [pad(next(_sh) if q['n'] == 'SH' else q['n'], q['x'], q['y'], q['w'], q['h']) for q in _tf]

# ---------- parts
parts = []
J8X, J8Y = -12.75, 16.55
# Real part bodies, local footprint frame (x0, y0, x1, y1), at the datasheet's largest size. Courtyards must hold them.
# Sources and the nominal sizes are in tools/bodycheck.py, which is the check that uses them.
BODY = {
    'R0402': (-0.6, -0.3, 0.6, 0.3),            # UNI-ROYAL 1.0+-0.10 x 0.5+-0.05 is the larger of the 0402s used
    'C0603': (-0.95, -0.55, 0.95, 0.55),        # Murata BLM18 1.6+-0.15 x 0.8+-0.15 is the larger of the 0603s used
    'C0805': (-1.2, -0.825, 1.2, 0.825),        # Sunlord GZ2012 2.0+-0.2 x 1.25+-0.2
    'IND4020': (-2.2, -2.2, 2.2, 2.2),          # Sunlord SWPA4020S 4.0+-0.2 square
    'SOT-23-5': (-1.525, -0.875, 1.525, 0.875), # TI DBV0005A 2.75-3.05 x 1.45-1.75, mold flash excluded per its note 4
    'SOT-23': (-1.52, -0.7, 1.52, 0.7),         # TI DBZ0003A 2.80-3.04 x 1.2-1.4, standing in for TO-236: the AOS sheet has no outline
    'MSOP-8': (-1.55, -1.55, 1.55, 1.55),       # TI DGK0008A 2.9-3.1 square
    'OSC3225': (-1.65, -1.3, 1.65, 1.3),        # YXC YSO110TR 3.2+-0.1 x 2.5+-0.1
    'SSOP-4_1.27': (-2.4, -1.55, 2.4, 1.55),    # Everlight EL3H7-G p7, 4.40+-0.2 x 2.70+-0.2
    'USON-10': (-1.3, -0.55, 1.3, 0.55),        # TI DQA0010A 2.4-2.6 x 0.9-1.1
    'JST_SM06B': (-4.0, -1.675, 4.0, 2.575),    # JST eSH p3: B 8.0, depth 4.25, tails 0.7 more, inside the pads
    'JST_SM08B': (-5.0, -1.675, 5.0, 2.575),    # JST eSH p3: B 10.0, same depth
    'U.FL-R-SMT-1': (-1.5, -1.55, 1.5, 1.55),   # Hirose U.FL catalogue p3: 3.0 x 2.6 body, 3.1 over the signal and rear tabs
}
OPTO_NAME, OPTO_CODE = 'EL3H7(C)(TA)-G', 'C92243'


def part(ref, value, lcsc, lib, pads, x, y, r, nets, side='F', dnp=False, body=None, consign=False):
    parts.append(dict(ref=ref, value=value, lcsc=lcsc, lib=lib, pads=[dict(q) for q in pads], x=x, y=y, r=r, nets=dict(nets), side=side, dnp=dnp, body=body or BODY.get(lib), consign=consign))


def R(ref, value, x, y, r, n1, n2, side='B', dnp=False):
    code = {'5.1k': 'C25905', '10k': 'C25744', '100k': 'C25741', '470': 'C25117', '270': 'C25099', '150k': 'C25755', '33k': 'C25779', '51k': 'C25794', '2.2k': 'C25879', '2k': 'C4109', '22': 'C25092', '1k': 'C11702', '1M': 'C26083', '0R': 'C17168', '560': 'C25126', '100': 'C25076'}[value]
    part(ref, f'{value} 0402', code, 'R0402', R0402, x, y, r, {'1': n1, '2': n2}, side, dnp)


def C(ref, value, x, y, r, n1, n2='GND', side='B', dnp=False):
    lib = {'4.7u': ('4.7uF 0603', 'C19666', 'C0603', C0603), '10u': ('10uF 0603', 'C19702', 'C0603', C0603), '22u': ('22uF 0805', 'C45783', 'C0805', C0805)}
    small = {'100n': ('100nF 0402', 'C1525'), '1u': ('1uF 0402', 'C52923'), '470p': ('470pF 0402', 'C1537'), '47p': ('47pF 0402', 'C1567'), '22p': ('22pF 0402', 'C1555')}
    if value in small:
        part(ref, small[value][0], small[value][1], 'R0402', R0402, x, y, r, {'1': n1, '2': n2}, side, dnp)
    elif value in lib:
        v, code, fpn, fpp = lib[value]
        part(ref, v, code, fpn, fpp, x, y, r, {'1': n1, '2': n2}, side, dnp)
    else:
        raise ValueError(value)


def TP(ref, net, x, y):
    part(ref, 'test pad', '', 'TP_1.0', [pad(1, 0, 0, 1.0, 1.0, 'circle')], x, y, 0, {'1': net}, 'B', dnp=True)


# Waveshare ESP32-P4-Module pin map, used as named nets below
M = {i: '' for i in range(1, 89)}
for i in (1, 3, 15, 33, 40, 47, 52, 83):
    M[i] = 'GND'
M.update({2: 'LNA_OUT', 84: '3V3', 85: '3V3', 86: '3V3', 87: 'ESP_EN', 66: 'LDO_VO4',
          4: 'C6_RXD', 5: 'C6_TXD', 9: 'C6_IO9', 10: 'C6_IO8',
          41: 'CSI_D0_N', 42: 'CSI_D0_P', 43: 'CSI_CK_P', 44: 'CSI_CK_N', 45: 'CSI_D1_N', 46: 'CSI_D1_P',
          48: 'USB_DN', 49: 'USB_DP', 50: 'USB2_DN', 51: 'USB2_DP',
          62: 'BOOT', 63: 'GPIO36', 64: 'U0_TX', 65: 'U0_RX',
          67: 'SD_D0', 68: 'SD_D1', 69: 'SD_D2', 70: 'SD_D3', 71: 'SD_CLK', 72: 'SD_CMD', 73: 'SD_PWR_N',
          22: 'I2C_SDA', 23: 'I2C_SCL', 32: 'TC_RST',
          24: 'LCD_DIN', 25: 'LCD_CLK', 26: 'LCD_CS', 27: 'LCD_DC', 28: 'LCD_RST',
          18: 'HOST_VBUS_DIV', 19: 'ATX_PWR', 20: 'ATX_RST', 17: 'ATX_LED'})
part('U1', 'ESP32-P4-Module 28101 base, R99 fitted, consigned', '', 'ESP32-P4-Module', module_pads(), -3.0, 5.4, 90, {str(k): v for k, v in M.items() if v}, consign=True, body=(-12.5, -12.5, 12.5, 12.5))

# Antenna: the base module's RF leaves on pin 2 through its R99 (0R, must stay fitted). See R6_REPORT.md.
part('J8', 'U.FL-R-SMT-1(10) antenna', 'C88373', 'U.FL-R-SMT-1', UFL, J8X, J8Y, 0, {'1': 'LNA_OUT', '2': 'GND', '3': 'GND'}, 'B')
gnd4 = {k: 'GND' for k in ('1', '2', '3', '4', 'A1B12', 'B1A12')}
J3X = 8.75
part('J3', 'USB-C to host', 'C41427493', 'USB-C_HX_16P', USBC, J3X, -14.15, 180, dict(gnd4, A4B9='HOST_VBUS', B4A9='HOST_VBUS', A5='HOST_CC1', B5='HOST_CC2', A6='USB_DP', B6='USB_DP', A7='USB_DN', B7='USB_DN'), body=(-4.47, -3.55, 4.47, 6.45))
part('J5', 'USB-C 5V, flash and console', 'C41427493', 'USB-C_HX_16P', USBC, 14.15, 2.5, 90, dict(gnd4, A4B9='5V', B4A9='5V', A5='PWR_CC1', B5='PWR_CC2', A6='USB2_DP', B6='USB2_DP', A7='USB2_DN', B7='USB2_DN'), body=(-4.47, -3.55, 4.47, 6.45))
part('U3', 'TPD4E05U06DQAR USB ESD', 'C138714', 'USON-10', USON10, 6.0, -11.05, 90, {'1': 'USB_DN', '10': 'USB_DN', '2': 'USB_DP', '9': 'USB_DP', '3': 'GND', '8': 'GND'}, 'B')
part('U14', 'TPD4E05U06DQAR USB2 ESD', 'C138714', 'USON-10', USON10, 16.0, -5.0, 0, {'1': 'USB2_DP', '10': 'USB2_DP', '2': 'USB2_DN', '9': 'USB2_DN', '3': 'GND', '8': 'GND'})
R('R1', '5.1k', 12.2, -9.6, 0, 'HOST_CC1', 'GND', 'F')
R('R2', '5.1k', 12.2, -8.5, 0, 'HOST_CC2', 'GND', 'F')
R('R3', '5.1k', 13.0, -6.6, 0, 'PWR_CC1', 'GND', 'F')
R('R4', '5.1k', 13.0, -5.5, 0, 'PWR_CC2', 'GND', 'F')
R('R60', '1M', 3.05, -7.68, 0, 'USB_DP', 'GND')  # F4: DP pull-down for chip rev v1.0 and v1.3, harmless on v3.0. Stub off the USB_DP via
R('R9', '100k', 15.9, -10.8, 0, 'HOST_VBUS', 'HOST_VBUS_DIV', 'F')
R('R10', '150k', 15.9, -9.7, 0, 'HOST_VBUS_DIV', 'GND', 'F')  # F3: 3.0 V at 5 V, above VIH 0.75 x VDD
C('C50', '100n', 15.9, -8.6, 0, 'HOST_VBUS', 'GND', 'F')

# Round LCD module on a short 8-wire harness; its pinout is 3V3 GND DIN CLK CS DC RST BL
part('J6', 'SM08B-SRSS-TB round LCD', 'C160407', 'JST_SM08B', sh_conn(8), 13.25, 13.3, 90, {'1': '3V3', '2': 'GND', '3': 'LCD_DIN', '4': 'LCD_CLK', '5': 'LCD_CS', '6': 'LCD_DC', '7': 'LCD_RST', '8': '3V3', '9': 'GND', '10': 'GND'})

# Module supply and straps, top side beside its supply pins
C('C1', '10u', -18.3, 14.8, 90, '3V3', 'GND', 'F')
C('C2', '10u', -18.3, 11.6, 90, '3V3', 'GND', 'F')
C('C3', '100n', -17.2, 7.3, 90, '3V3', 'GND', 'F')
C('C4', '100n', -18.3, 8.9, 90, '3V3', 'GND', 'F')
R('R11', '10k', -19.2, 7.3, 90, 'ESP_EN', '3V3', 'F')
C('C5', '1u', -18.3, 6.0, 90, 'ESP_EN', 'GND', 'F')  # F5: 10k + 1 uF, Espressif guideline v1.9
R('R12', '10k', -18.3, 3.0, 90, 'GPIO36', '3V3', 'F')
R('R13', '10k', -18.3, 0.8, 90, 'C6_IO8', '3V3', 'F')
C('C6', '100n', -18.3, -1.4, 90, 'LDO_VO4', 'GND', 'F')

# ---------- HDMI capture, bottom side (Antmicro hdmi-mipi-bridge, Apache-2.0, as the reference)
HCX, HCY = -8.0, -12.48
part('J2', 'HDMI-001S', 'C720616', 'HDMI-001S', HDMI, HCX, HCY, 180, {'1': 'D2_P', '2': 'GND', '3': 'D2_N', '4': 'D1_P', '5': 'GND', '6': 'D1_N', '7': 'D0_P', '8': 'GND', '9': 'D0_N', '10': 'CK_P', '11': 'GND', '12': 'CK_N', '13': 'HDMI_CEC', '15': 'DDC_SCL', '16': 'DDC_SDA', '17': 'GND', '18': 'HDMI_5V', '19': 'HDMI_HPD', '20': 'GND', '21': 'GND', '22': 'GND', '23': 'GND'}, 'B', body=(-7.5, -4.7, 7.5, 8.12))
part('U8', 'TPD4E05U06DQAR TMDS ESD', 'C138714', 'USON-10', USON10, -4.25, -6.2, 180, {'1': 'D1_N', '10': 'D1_N', '2': 'D1_P', '9': 'D1_P', '4': 'D2_N', '7': 'D2_N', '5': 'D2_P', '6': 'D2_P', '3': 'GND', '8': 'GND'}, 'B')
part('U9', 'TPD4E05U06DQAR TMDS ESD', 'C138714', 'USON-10', USON10, -7.75, -6.2, 180, {'1': 'CK_N', '10': 'CK_N', '2': 'CK_P', '9': 'CK_P', '4': 'D0_N', '7': 'D0_N', '5': 'D0_P', '6': 'D0_P', '3': 'GND', '8': 'GND'}, 'B')

TC = {'A1': 'TC_REXT', 'A2': 'GND', 'A3': 'GND', 'A4': 'TC_BIASDA', 'A6': 'TC_PFIL', 'B1': '3V3', 'B2': 'AVDD12', 'B5': 'AVDD25', 'B6': 'TC_PCKIN',
      'C1': 'CK_P', 'C2': 'CK_N', 'C3': 'VDDC', 'C4': 'GND', 'C5': 'GND', 'C6': 'VDD_MIPI', 'C7': 'CSI_CK_N', 'C8': 'CSI_CK_P',
      'D1': 'D0_P', 'D2': 'D0_N', 'D3': 'AVDD12', 'D4': 'GND', 'D5': 'GND', 'D6': 'GND', 'D7': 'CSI_D1_N', 'D8': 'CSI_D1_P',
      'E1': 'D1_P', 'E2': 'D1_N', 'E3': 'GND', 'E4': 'GND', 'E5': 'GND', 'E6': 'GND', 'E7': 'CSI_D0_N', 'E8': 'CSI_D0_P',
      'F1': 'D2_P', 'F2': 'D2_N', 'F3': '3V3', 'F4': '3V3', 'F5': 'VDDC', 'F6': 'VDD_MIPI',
      'G1': 'HDMI_CEC', 'G2': 'VDDC', 'G3': 'DDC3_SDA', 'G4': 'I2C_SDA', 'G5': 'TC_RST',
      'H1': 'TC_HPDO', 'H2': 'HDMI_5V', 'H3': 'DDC3_SCL', 'H4': 'I2C_SCL', 'H5': 'TC_REFCLK', 'H7': '3V3', 'H8': 'GND'}
TCX, TCY = 5.5, -4.0
part('U7', 'TC358743XBG(EL,NOK', 'C3008606', 'BGA-64_6x6', BGA, TCX, TCY, 180, TC, 'B', body=(-3.0, -3.0, 3.0, 3.0))

part('U4', 'TLV73325PDBVR 2.5V', 'C882825', 'SOT-23-5', SOT235, 0.5, 5.2, 0, {'1': '3V3', '2': 'GND', '3': '3V3', '5': 'V2V5'}, 'B')
part('U5', 'TLV73312PDBVT 1.2V', 'C2871228', 'SOT-23-5', SOT235, 3.8, 5.2, 0, {'1': 'V2V5', '2': 'GND', '3': 'V2V5', '5': 'V1V2'}, 'B')
C('C10', '10u', -0.2, 7.65, 0, '3V3')
C('C11', '10u', 3.8, 7.65, 0, 'V2V5')
C('C12', '10u', 7.5, 7.65, 0, 'V1V2')
part('FB2', '1k@100MHz 500mA', 'C98485', 'C0805', C0805, 7.6, 1.0, 0, {'1': 'V2V5', '2': 'AVDD25'}, 'B')
part('FB3', '220R@100MHz 2A BLM21PG221SN1D', 'C85840', 'C0805', C0805, 7.35, 3.0, 0, {'1': 'V1V2', '2': 'AVDD12'}, 'B')
part('FB4', '1k@100MHz 500mA', 'C98485', 'C0805', C0805, 7.6, 5.0, 0, {'1': 'V1V2', '2': 'VDD_MIPI'}, 'B')
part('FB5', '220R@100MHz 2A BLM21PG221SN1D', 'C85840', 'C0805', C0805, 10.5, 3.0, 0, {'1': 'V1V2', '2': 'VDDC'}, 'B')
C('C13', '470p', -0.4, -1.3, 90, 'AVDD25')
C('C14', '4.7u', -1.7, 1.9, 90, 'AVDD25')
C('C15', '470p', 0.7, -1.3, 90, 'AVDD12')
C('C16', '4.7u', -1.7, -0.9, 90, 'AVDD12')
C('C17', '470p', 9.2, -5.7, -90, 'VDD_MIPI')
C('C18', '4.7u', 9.9, -0.9, 0, 'VDD_MIPI')
C('C19', '470p', -1.4, -5.45, 0, 'VDDC')
C('C20', '4.7u', -1.75, -6.45, 0, 'VDDC')
C('C21', '100n', 0.7, -6.0, 90, 'VDDC')
C('C22', '100n', 3.0, -0.2, 0, '3V3')
C('C23', '100n', 5.0, -0.2, 0, '3V3')
C('C24', '100n', 6.9, -0.2, 0, '3V3')
C('C25', '100n', 2.4, 1.6, 0, 'TC_BIASDA')
C('C26', '100n', 4.4, 1.6, 0, 'TC_PFIL')
C('C27', '100n', 2.4, 2.7, 0, 'TC_PCKIN')
R('R20', '2k', 4.4, 2.7, 0, 'TC_REXT', '3V3')
R('R21', '10k', 0.7, -8.2, 90, '3V3', 'TC_RST')
R('R22', '2.2k', 8.5, 9.2, 0, 'I2C_SDA', '3V3')
R('R23', '2.2k', 8.5, 10.3, 0, 'I2C_SCL', '3V3')
part('Y1', 'OT322527MJBA4SL 27MHz', 'C725995', 'OSC3225', OSC3225, 10.4, -8.0, 0, {'1': 'OSC_VDD', '2': 'GND', '3': 'OSC_OUT', '4': 'OSC_VDD'}, 'B')
part('FB6', '600R@100MHz', 'C19330', 'C0603', C0603, 13.6, -7.2, 90, {'1': '3V3', '2': 'OSC_VDD'}, 'B')
C('C29', '100n', 13.3, -9.6, 90, 'OSC_VDD')
C('C30', '47p', 7.6, -9.4, 0, 'OSC_OUT')
R('R24', '22', 7.4, -8.2, 0, 'OSC_OUT', 'TC_REFCLK')
C('C31', '47p', 5.6, -7.8, 0, 'TC_REFCLK')

part('U6', 'PCA9517DGKR DDC level shift', 'C30348', 'MSOP-8', MSOP8, -12.35, -4.7, 90, {'1': '3V3', '2': 'DDC3_SCL', '3': 'DDC3_SDA', '4': 'GND', '5': '3V3', '6': 'DDC_SDA', '7': 'DDC_SCL', '8': '5V'}, 'B')
R('R25', '10k', -4.0, -1.6, 0, 'DDC3_SCL', '3V3')
R('R26', '10k', -4.0, -0.5, 0, 'DDC3_SDA', '3V3')
R('R27', '10k', -4.0, 0.6, 0, 'DDC_SCL', '5V')
R('R28', '10k', -4.0, 1.7, 0, 'DDC_SDA', '5V')
C('C32', '100n', -4.0, 2.8, 0, '5V')
C('C33', '100n', -4.0, 3.9, 0, '3V3')
# HPD: firmware drives HPDO, a 3.3 V output. R30 is the assembled path. R31 is Antmicro's tie to the source's 5 V;
# fit it only with R30 removed, because HPDO is not 5 V tolerant, and the firmware then loses control of HPD.
R('R30', '1k', -16.0, -6.2, 90, 'TC_HPDO', 'HDMI_HPD')
R('R31', '0R', -17.2, -6.2, 90, 'HDMI_5V', 'HDMI_HPD', dnp=True)
R('R32', '100k', -18.4, -6.2, 90, 'HDMI_HPD', 'GND')

# ---------- microSD, bottom side, card enters through the left wall
part('J7', 'Molex 104031-0811 microSD', 'C585350', 'microSD_Molex_104031-0811', TF, -13.8, 4.1, -90, {'1': 'SD_D2', '2': 'SD_D3', '3': 'SD_CMD', '4': 'SD1_VDD', '5': 'SD_CLK', '6': 'GND', '7': 'SD_D0', '8': 'SD_D1', 'SH1': 'GND', 'SH2': 'GND', 'SH3': 'GND', 'SH4': 'GND'}, 'B', body=(-5.955, -5.7, 5.995, 5.7))
part('Q1', 'AO3401A', 'C15127', 'SOT-23', SOT23, -2.9, 6.2, 0, {'1': 'SD_PWR_N', '2': 'SD_SRC', '3': 'SD1_VDD'}, 'B')
R('R40', '10k', -3.6, 8.5, 0, 'GND', 'SD_PWR_N')
R('R41', '0R', -3.6, 9.6, 0, 'LDO_VO4', 'SD_SRC', dnp=True)  # F1: card power comes from 3V3, Espressif guideline 1.3.11. VO4 is limited to 50 mA
R('R42', '0R', -3.6, 10.7, 0, '3V3', 'SD_SRC')
C('C40', '10u', -6.6, 10.9, 0, 'SD1_VDD')
C('C41', '100n', -3.6, 13.0, 0, 'SD1_VDD')
for i, net in enumerate(('SD_D2', 'SD_D3', 'SD_CMD', 'SD_D0', 'SD_D1')):
    R(f'R{43 + i}', '51k', -5.32, 5.0 + i * 1.1, 0, net, 'LDO_VO4')  # F1: pull-ups on the IO supply, so 3V3 cannot back-feed the pins before VO4 is up

# ---------- power
C('C60', '22u', 17.6, 10.6, 90, '5V')
C('C64', '1u', 13.95, 7.8, 90, '5V')  # review 6.1: beside U2.4, ground into the J5.1 barrel
part('U2', 'SY8089AAAC 3.3V 2A', 'C78988', 'SOT-23-5', SOT235, 14.0, 9.85, 0, {'1': '5V', '2': 'GND', '3': 'SW', '4': '5V', '5': 'FB_3V3'}, 'B', body=(-1.55, -0.85, 1.55, 0.85))
part('L1', 'SWPA4020S2R2MT 2.2uH', 'C83423', 'IND4020', IND4020, 13.6, 13.9, 0, {'1': 'SW', '2': '3V3'}, 'B')
R('R50', '150k', 10.6, 8.6, 90, '3V3', 'FB_3V3')
R('R51', '33k', 11.7, 8.6, 90, 'FB_3V3', 'GND')
C('C63', '22p', 10.8, 10.7, 0, '3V3', 'FB_3V3')
C('C61', '22u', 10.3, 13.9, 90, '3V3')
C('C62', '22u', 8.5, 13.9, 90, '3V3')

# ---------- ATX, bottom side, harness leaves through the back wall
part('J4', 'SM06B-SRSS-TB ATX', 'C160405', 'JST_SM06B', sh_conn(6), -3.7, 16.9, 0, {'1': 'PWR_C', '2': 'PWR_E', '3': 'RST_C', '4': 'RST_E', '5': 'LED_K', '6': 'LED_A', '7': 'GND', '8': 'GND'}, 'B')
part('U10', OPTO_NAME, OPTO_CODE, 'SSOP-4_1.27', OPTO, 3.4, 10.0, 0, {'1': 'PWR_LED', '2': 'GND', '3': 'PWR_E', '4': 'PWR_C'}, 'B')
part('U11', OPTO_NAME, OPTO_CODE, 'SSOP-4_1.27', OPTO, 3.4, 13.6, 0, {'1': 'RST_LED', '2': 'GND', '3': 'RST_E', '4': 'RST_C'}, 'B')
R('R52', '470', -1.9, 11.4, 0, 'ATX_PWR', 'PWR_LED')
R('R53', '470', -1.9, 12.5, 0, 'ATX_RST', 'RST_LED')
part('U12', OPTO_NAME, OPTO_CODE, 'SSOP-4_1.27', OPTO, 10.8, 17.7, 0, {'1': 'LED_IN', '2': 'LED_K', '3': 'ATX_LED', '4': '3V3'}, 'B')
R('R54', '270', 5.65, 17.1, 0, 'LED_A', 'LED_IN')
R('R55', '10k', 5.65, 18.2, 0, 'ATX_LED', 'GND')

# ---------- service pads
for ref, net, x, y in (('TP1', 'BOOT', -15.2, 14.2), ('TP2', 'ESP_EN', -13.6, 14.2), ('TP3', 'U0_TX', -12.0, 14.2), ('TP4', 'U0_RX', -10.4, 14.2), ('TP5', 'C6_RXD', -8.8, 15.25), ('TP6', 'C6_TXD', -8.76, 17.2), ('TP7', 'C6_IO9', -7.4, 13.2), ('TP8', 'GND', -8.8, 13.4)):
    TP(ref, net, x, y)

parts = [p for p in parts if p]

# ---------- r7. Everything above is the r6 board. The plane-escape search below runs on this r6 snapshot, so no r7 edit can ripple through it;
# r7's copper for the changed pads is added by hand after the search. R7_REPORT.md has the reasons and the numbers.
import copy
parts_r6 = copy.deepcopy(parts)
_P = {p['ref']: p for p in parts}
# item 1: U6 becomes TCA9517ADGKR, same DGK0008A pinout (TI SCPS245E p4). EN needs VIH 0.7 x VCCB = 3.5 V (p5), so it is tied to VCCB (5V), not 3V3
_P['U6'].update(value='TCA9517ADGKR DDC level shift', lcsc='C201698')
_P['U6']['nets']['5'] = '5V'
# item 2: the 27 MHz CMOS oscillator drives 15 pF at most (YXC YSO110TR p1). C30 and C31 stay as footprints, not fitted
_P['C30']['dnp'] = True
_P['C31']['dnp'] = True
# item 4: worst-case body gaps (bodycheck.py, +-0.1 mm placement) brought to 0 or more
R7_MOVE = {'Y1': (10.5, -8.0), 'C62': (8.4, 13.9), 'FB2': (7.6, 1.04), 'C24': (6.9, -0.29), 'L1': (13.6, 13.83), 'U12': (10.8, 17.79), 'U4': (0.65, 5.2)}
for _r, (_x, _y) in R7_MOVE.items():
    _P[_r]['x'], _P[_r]['y'] = _x, _y
# item 1, routing: R28 (10k DDC_SDA pull-up to 5V) next to U6; mirrored on B, so pad 1 (now 5V) is the right-hand pad
_P['R28']['x'], _P['R28']['y'] = -10.15, -6.75
_P['R28']['nets'] = {'1': '5V', '2': 'DDC_SDA'}
# item 3: U5 (linear 2.5 V to 1.2 V) goes; 1.2 V comes from its own SY8089 buck on the top side, fed from 3V3, sensed at the beads through R65
parts.remove(_P['U5'])
U15X, U15Y, L2X, L2Y = -8.3, -14.4, -4.0, -16.8
part('U15', 'SY8089AAAC 1.2V buck', 'C78988', 'SOT-23-5', SOT235, U15X, U15Y, 90, {'1': '3V3', '2': 'GND', '3': 'SW_1V2', '4': '3V3', '5': 'FB_1V2'}, 'F', body=(-1.55, -0.85, 1.55, 0.85))
part('L2', 'SWPA4020S2R2MT 2.2uH', 'C83423', 'IND4020', IND4020, L2X, L2Y, 0, {'1': 'SW_1V2', '2': 'V1V2'}, 'F')
C('C65', '22u', -9.4, -17.6, 0, '3V3', 'GND', 'F')       # input, beside IN
C('C66', '22u', -2.6, -12.9, 90, 'GND', 'V1V2', 'F')     # output
C('C67', '22u', -4.6, -12.9, 90, 'GND', 'V1V2', 'F')     # output
R('R61', '33k', -11.2, -13.45, 0, 'FB_MID', 'FB_1V2', 'F')   # top: R61 + R62 = 33.56k
R('R62', '560', -13.0, -12.55, 0, 'V1V2_SNS', 'FB_MID', 'F')
R('R63', '33k', -11.2, -14.35, 0, 'GND', 'FB_1V2', 'F')      # bottom. 0.6 x (1 + 33.56/33) = 1.2102 V at the sense point; R7_REPORT.md item 3 has the worst case
C('C68', '22p', -11.2, -12.55, 0, 'FB_MID', 'FB_1V2', 'F')   # feed-forward across R61, Silergy AN p8
R('R65', '0R', 9.9, 5.6, 90, 'V1V2_SNS', 'V1V2')              # remote sense tie at the bead inputs (FB3, FB4, FB5)
R('R66', '100', -8.3, -11.95, 0, 'V1V2_SNS', 'V1V2', 'F')   # r7b M4: local fallback. If the remote sense line opens, U15 regulates here instead of running to 3.3 V
R7_NEW = {'U15', 'L2', 'C65', 'C66', 'C67', 'R61', 'R62', 'R63', 'C68', 'R65', 'R66'}

# ---------- r7b, from REVIEW_independent.md. R7B_REPORT.md has the numbers.
_P = {p['ref']: p for p in parts}
# M1: the 1.2 V divider in 0.1% thin film (values unchanged)
for _r in ('R61', 'R63'):
    _P[_r].update(value='33k 0.1% 0402', lcsc='C728559')     # Yageo RT0402BRD0733KL, 25 ppm/C
_P['R62'].update(value='560 0.1% 0402', lcsc='C319512')       # Viking AR02BTD5600
# L1: 3V3 nominal 3.327 -> 3.311 V, so its top end clears AVDD33 3.465 V by more
_P['R51'].update(value='33.2k 0402', lcsc='C122548')
# L3: TC358743 RESETN pulled down, so the bridge stays in reset until firmware releases GPIO23
_P['R21']['nets'] = {'1': 'GND', '2': 'TC_RST'}
# M5: HPDI (U7.H2) behind R67 51k from the source's +5V; R67 sits on the top side between J2 and J3
_P['U7']['nets']['H2'] = 'HPDI'
R('R67', '51k', 1.6, -12.5, 0, 'HDMI_5V', 'HPDI', 'F')
# M7: J6 0.2 mm away from the module's pads (gap 0.225 -> 0.425 mm); its plane escapes move with it
J6_DX = 0.2
_P['J6']['x'] += J6_DX
refs = [p['ref'] for p in parts]
assert len(refs) == len(set(refs)), [r for r in refs if refs.count(r) > 1]


# ---------- geometry
def bake(p):
    """Turns a part's pose into absolute pad rectangles. Bottom-side parts are mirrored in x, as a flip does."""
    a = math.radians(p['r'])
    c, s = round(math.cos(a), 6), round(math.sin(a), 6)
    res = []
    for q in p['pads']:
        x = q['x'] * c + q['y'] * s
        y = -q['x'] * s + q['y'] * c
        w, h = (q['w'], q['h']) if abs(s) < 0.5 else (q['h'], q['w'])
        if p['side'] == 'B':
            x = -x
        res.append(dict(q, wx=p['x'] + x, wy=p['y'] + y, ww=w, wh=h))
    p['abs'] = res


for p in parts:
    bake(p)
    for q in p['pads']:
        if not p['nets'].get(q['n']):
            p['nets'][q['n']] = f"unconnected-({p['ref']}-Pad{q['n']})"

R7C_NETS = {'5V_DAMP'}  # nets of parts the r7c stage adds after the SES import; listed here so every net id is fixed up front
# r7f (tools/r7f_stage.py): eFuse input side and its pins, and the far (card / panel) side of the new series resistors
R7C_NETS |= {'VBUS_IN', 'EF_DVDT', 'EF_EN', 'EF_ILM', 'unconnected-(U16-Pad6)', 'SD_CLK_C', 'SD_CMD_C', 'SD_D0_C', 'SD_D1_C', 'SD_D2_C', 'SD_D3_C', 'LCD_DIN_J', 'LCD_CLK_J'}
nets = sorted({n for p in parts for n in p['nets'].values()} | R7C_NETS)
for n in ('GND', '3V3', '5V'):
    assert n in nets
netid = {n: i + 1 for i, n in enumerate(nets)}
padpos = {f"{p['ref']}.{q['n']}": (q['wx'], q['wy']) for p in parts for q in p['abs']}
real_nets = [n for n in nets if not n.startswith('unconnected-')]


def bbox(p):
    xs, ys = [], []
    for q in p['abs']:
        xs += [q['wx'] - q['ww'] / 2, q['wx'] + q['ww'] / 2]
        ys += [q['wy'] - q['wh'] / 2, q['wy'] + q['wh'] / 2]
    if p['body']:
        a = math.radians(p['r'])
        c, s = round(math.cos(a), 6), round(math.sin(a), 6)
        x0, y0, x1, y1 = p['body']
        for bx, by in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            x = bx * c + by * s
            y = -bx * s + by * c
            if p['side'] == 'B':
                x = -x
            xs.append(p['x'] + x)
            ys.append(p['y'] + y)
    return min(xs) - 0.1, min(ys) - 0.1, max(xs) + 0.1, max(ys) + 0.1


# ---------- KiCad board
LAYERS = {'F': '"F.Cu" "F.Paste" "F.Mask"', 'B': '"B.Cu" "B.Paste" "B.Mask"', 'TP': '"B.Cu" "B.Mask"'}
sym = {p['ref']: uid('sym-' + p['ref']) for p in parts}


def fp(p):
    x0, y0, x1, y1 = bbox(p)
    side = p['side']
    pads = []
    for q in p['abs']:
        n = p['nets'].get(q['n'], '')
        net = f'(net {netid[n]} "{n}") ' if n else ''
        if q['kind'] == 'thru_hole':
            d1, d2 = q['d1'], q['d2']
            swap = abs(q['ww'] - q['h']) < 1e-6 and q['ww'] != q['wh']
            drill = f'(drill oval {d2 if swap else d1} {d1 if swap else d2}) ' if d2 else f'(drill {d1}) '
            layers = '"*.Cu" "*.Mask"'
            shape = 'oval' if q['shape'] != 'rect' else 'rect'
            pads.append(f'(pad "{q["n"]}" thru_hole {shape} (at {q["wx"] - p["x"]:.4f} {q["wy"] - p["y"]:.4f}) (size {q["ww"]:g} {q["wh"]:g}) {drill}(layers {layers}) {net}(uuid "{uid()}"))')
        else:
            layers = LAYERS['TP'] if p['lib'] == 'TP_1.0' else LAYERS[side]
            if p['dnp'] or q.get('nopaste'):
                layers = layers.replace(f' "{side}.Paste"', '')   # r7b L6: no stencil opening on a part that is not fitted; r7f: a pad whose paste is windowed
            shape = 'circle' if q['shape'] == 'circle' else 'rect'
            pads.append(f'(pad "{q["n"]}" smd {shape} (at {q["wx"] - p["x"]:.4f} {q["wy"] - p["y"]:.4f}) (size {q["ww"]:g} {q["wh"]:g}) (layers {layers}) {net}(uuid "{uid()}"))')
    # r7f: stencil-only apertures as filled rectangles on the paste layer (no copper, not a pad: no tool sees a net-less pad),
    # absolute board-frame rectangles (x, y, w, h)
    for wx, wy, ww, wh in ([] if p['dnp'] else p.get('paste_windows', [])):
        pads.append(f'(fp_rect (start {wx - ww / 2 - p["x"]:.4f} {wy - wh / 2 - p["y"]:.4f}) (end {wx + ww / 2 - p["x"]:.4f} {wy + wh / 2 - p["y"]:.4f}) '
                    f'(stroke (width 0) (type solid)) (fill yes) (layer "{side}.Paste") (uuid "{uid()}"))')
    fab = f'{side}.Fab'
    attr = 'through_hole' if any(q['kind'] == 'thru_hole' for q in p['abs']) else 'smd'
    extra = ' exclude_from_bom exclude_from_pos_files' if p['lib'] == 'TP_1.0' else ''
    dn = ' dnp' if p['dnp'] and p['lib'] != 'TP_1.0' else ''
    mir = ' (justify mirror)' if side == 'B' else ''
    return f'''(footprint "mini:{p['lib']}" (layer "{side}.Cu") (uuid "{uid()}") (at {p['x'] + OX:.4f} {p['y'] + OY:.4f})
    (property "Reference" "{p['ref']}" (at {x0 - p['x']:.3f} {y0 - p['y'] - 0.3:.3f}) (layer "{fab}") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08)){mir}))
    (property "Value" "{p['value']}" (at 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08)){mir}))
    (property "LCSC" "{p['lcsc']}" (at 0 0) (layer "{fab}") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08)){mir}))
    (path "/{sym[p['ref']]}") (sheetname "/") (sheetfile "{NAME}.kicad_sch")
    (attr {attr}{extra}{dn})
    (fp_rect (start {x0 - p['x']:.3f} {y0 - p['y']:.3f}) (end {x1 - p['x']:.3f} {y1 - p['y']:.3f}) (stroke (width 0.05) (type default)) (fill no) (layer "{side}.CrtYd") (uuid "{uid()}"))
    {' '.join(pads)}
  )'''


def rounded_rect():
    r = 1.5
    return [(-H + r, -H), (H - r, -H), (H, -H + r), (H, YB - r), (H - r, YB), (-H + r, YB), (-H, YB - r), (-H, -H + r)]


outline = rounded_rect()
edges = [f'(gr_line (start {a[0] + OX:.3f} {a[1] + OY:.3f}) (end {b[0] + OX:.3f} {b[1] + OY:.3f}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "{uid()}"))' for a, b in zip(outline, outline[1:] + outline[:1])]
holes = [(HOLE, -HOLE), (-HOLE, -HOLE), (HOLE, HOLE), (-HOLE, HOLE)]
MH_CLEARANCE = 0.3  # local to these four NPTH pads: hole wall to any copper. The board-wide min_hole_clearance stays 0.2, vias sit at 0.2000


def mh_fps(holes):
    return [f'''(footprint "mini:MH_2.2" (layer "F.Cu") (uuid "{uid()}") (at {x + OX} {y + OY})
    (property "Reference" "H{i + 1}" (at 0 -2 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (property "Value" "MH" (at 0 2 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (attr board_only exclude_from_pos_files exclude_from_bom)
    (pad "" np_thru_hole circle (at 0 0) (size 2.2 2.2) (drill 2.2) (layers "*.Cu" "*.Mask") (clearance {MH_CLEARANCE}) (uuid "{uid()}"))
  )''' for i, (x, y) in enumerate(holes)]


fps = [fp(p) for p in parts] + mh_fps(holes)


POUR_PULLBACK = 0.45  # r6: copper pours stop this far inside the board edge, on every side and chamfer


def pour_outline():
    i = H - POUR_PULLBACK
    j = YB - POUR_PULLBACK
    r = 1.5 - POUR_PULLBACK * (math.sqrt(2) - 1)  # chamfers offset by the same perpendicular distance
    return [(-i + r, -i), (i - r, -i), (i, -i + r), (i, j - r), (i - r, j), (-i + r, j), (-i, j - r), (-i, -i + r)]


def zone(net, layer):
    pts = ' '.join(f'(xy {x + OX:.3f} {y + OY:.3f})' for x, y in pour_outline())
    return f'''(zone (net {netid[net]}) (net_name "{net}") (layer "{layer}") (uuid "{uid()}") (hatch edge 0.5)
    (connect_pads (clearance 0.12)) (min_thickness 0.13) (filled_areas_thickness no)
    (fill yes (thermal_gap 0.2) (thermal_bridge_width 0.25) (island_removal_mode 0))
    (polygon (pts {pts}))
  )'''


W_POWER = {'5V': 0.4, 'SW': 0.4, 'V2V5': 0.2, 'V1V2': 0.2, 'AVDD25': 0.15, 'AVDD12': 0.15, 'VDD_MIPI': 0.15, 'VDDC': 0.15, 'SD1_VDD': 0.3, 'SD_SRC': 0.3, 'LDO_VO4': 0.3, 'HDMI_5V': 0.2, 'OSC_VDD': 0.2, 'HOST_VBUS': 0.2}
W_DEFAULT = 0.127

tracks = []
nvia = 0

# ---------- plane nets are escaped here, so the router only sees signals
PLANE = ('GND', '3V3')
# r6 added or moved these parts. The plane-escape search below still sees them where r5 had them, so its result cannot ripple;
# the copper that belonged to the old positions is edited by hand right after the search.
R6_NEW = {'J8', 'C64', 'R60'}
R6_WAS = {'C19': (10.4, -5.7, 90), 'C20': (10.6, 1.2, 0), 'TP5': (-15.2, 17.6, 0), 'TP6': (-13.6, 17.6, 0), 'TP7': (-12.0, 17.6, 0), 'TP8': (-10.4, 17.6, 0)}
search_parts = []
for _p in parts_r6:  # r7: the r6 snapshot, see above
    if _p['ref'] in R6_NEW:
        continue
    if _p['ref'] in R6_WAS:
        _p = dict(_p, x=R6_WAS[_p['ref']][0], y=R6_WAS[_p['ref']][1], r=R6_WAS[_p['ref']][2])
    bake(_p)
    for q in _p['pads']:
        if not _p['nets'].get(q['n']):
            _p['nets'][q['n']] = f"unconnected-({_p['ref']}-Pad{q['n']})"
    search_parts.append(_p)
SP = {p['ref']: p for p in search_parts}
VIA_D, VIA_DR = 0.4, 0.2
CLR = 0.11
obst = [dict(x=q['wx'], y=q['wy'], w=q['ww'], h=q['wh'], net=p['nets'][q['n']], side='A' if q['kind'] == 'thru_hole' else p['side'], circ=q['shape'] == 'circle') for p in search_parts for q in p['abs']]
vias = []
stubs = []


def rect_dist(px, py, o):
    if o['circ']:
        return math.hypot(px - o['x'], py - o['y']) - o['w'] / 2
    dx = abs(px - o['x']) - o['w'] / 2
    dy = abs(py - o['y']) - o['h'] / 2
    return math.hypot(max(dx, 0), max(dy, 0)) if (dx > 0 or dy > 0) else max(dx, dy)


def seg_dist(x, y, st):
    ax, ay, bx, by = st[:4]
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def via_ok(x, y, net):
    if max(abs(x), abs(y)) > H - 0.45 or math.hypot(abs(x) - HOLE, abs(y) - HOLE) < 1.6:
        return False
    for o in obst:
        lim = VIA_D / 2 + CLR
        if o['net'] == net:
            lim = VIA_D / 2 + 0.05
            if o['side'] == 'A':
                lim = VIA_D / 2 + 0.1
        if rect_dist(x, y, o) < lim:
            return False
    for v in vias:
        if math.hypot(x - v[0], y - v[1]) < VIA_D + (0.12 if v[2] == net else 0.16):
            return False
    for st in stubs:
        if st[5] != net and seg_dist(x, y, st) < VIA_D / 2 + st[6] / 2 + CLR:
            return False
    return True


def stub_ok(a, b, side, net, w):
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
    for i in range(n + 1):
        x = a[0] + (b[0] - a[0]) * i / n
        y = a[1] + (b[1] - a[1]) * i / n
        for o in obst:
            if o['net'] == net or o['side'] not in (side, 'A'):
                continue
            if rect_dist(x, y, o) < w / 2 + CLR:
                return False
        for v in vias:
            if v[2] != net and math.hypot(x - v[0], y - v[1]) < VIA_D / 2 + w / 2 + CLR:
                return False
        for st in stubs:
            if st[4] == side and st[5] != net and seg_dist(x, y, st) < st[6] / 2 + w / 2 + CLR:
                return False
    return True


unfanned = []
done = set()
W_DIFF, W_USB = 0.127, 0.18
HS_NETS = {'LNA_OUT', 'D2_P', 'D2_N', 'D1_P', 'D1_N', 'D0_P', 'D0_N', 'CK_P', 'CK_N', 'CSI_D0_P', 'CSI_D0_N', 'CSI_D1_P', 'CSI_D1_N', 'CSI_CK_P', 'CSI_CK_N', 'USB_DP', 'USB_DN'}


def wire(net, side, pts, w=W_DIFF):
    for a, b in zip(pts, pts[1:]):
        stubs.append((a[0], a[1], b[0], b[1], side, net, w))


def hs_via(net, x, y):
    vias.append((x, y, net))


def ball(name):
    col = int(name[1]) - 1
    row = 'ABCDEFGH'.index(name[0])
    return (TCX - 2.275 + col * 0.65, TCY + 2.275 - row * 0.65)


# TMDS: connector pad, through the ESD part, along one row each into the BGA.
# r6: the 90 degree corner of each line is a 45 degree chamfer. P is the inner line, N the outer; N's chamfer is 0.365 longer so the pair keeps its 0.325 pitch through the turn.
TMDS_CP, TMDS_DC = 0.15, 0.365


def tooth(start, axis, side, a, c, g):
    """One chamfered tooth off a straight run. axis (dx, dy) is the run direction, side (sx, sy) the way it sticks out, a its height, c the chamfer, g the crown.
    Adds 2a - 2.343c of length and uses 4c + g of run."""
    (x, y), (dx, dy), (sx, sy) = start, axis, side
    at = lambda u, v: (round(x + dx * u + sx * v, 4), round(y + dy * u + sy * v, 4))
    return [at(0, 0), at(c, c), at(c, a - c), at(2 * c, a), at(2 * c + g, a), at(3 * c + g, a - c), at(3 * c + g, c), at(4 * c + g, 0)]


# P length tuning, r6 item 8: (column teeth starting at y) or (row teeth starting at x). Numbers set from the measured skew; R6_REPORT.md lists the result.
TMDS_TUNE = {'D1_P': [((-4.75, -4.89), 'col', 0.77, 0.05, 0.11)],
             'D0_P': [((-6.75, -5.30), 'col', 0.79, 0.08, 0.10)],
             'CK_P': [((-8.25, -4.70), 'col', 0.72, 0.06, 0.11)]}
TMDS_R6 = {}
TMDS_ROW_TUNE = {'D2_P': [(-3.00, 0.51, 0.06, 0.10), (-2.63, 0.51, 0.06, 0.10)]}
for net, jx, ex, bl in (('D2_P', -3.5, -3.25, 'F1'), ('D2_N', -4.5, -3.75, 'F2'), ('D1_P', -5.0, -4.75, 'E1'), ('D1_N', -6.0, -5.25, 'E2'),
                        ('D0_P', -6.5, -6.75, 'D1'), ('D0_N', -7.5, -7.25, 'D2'), ('CK_P', -8.0, -8.25, 'C1'), ('CK_N', -9.0, -8.75, 'C2')):
    bx, by = ball(bl)
    if net.endswith('_P'):
        col = []
        for st, _k, a, c, g in TMDS_TUNE.get(net, []):
            col += tooth(st, (0, 1), (1, 0), a, c, g)
        row = []
        for x0, a, c, g in TMDS_ROW_TUNE.get(net, []):
            row += tooth((x0, by), (1, 0), (0, -1), a, c, g)
        _pp = [(jx, -8.2), (jx, -7.7), (ex, -7.25)] + col + [(ex, by - TMDS_CP), (ex + TMDS_CP, by)] + row + [(bx, by)]
        TMDS_R6[net] = [q for k, q in enumerate(_pp) if k == 0 or q != _pp[k - 1]]
        wire(net, 'B', [(jx, -8.2), (jx, -7.7), (ex, -7.25), (ex, by), (bx, by)])  # what the plane search sees, as in r5
    else:
        cn = TMDS_CP + TMDS_DC
        yn = by + 0.325
        TMDS_R6[net] = [(jx, -8.2), (jx, -7.7), (ex, -7.25), (ex, yn - cn), (ex + cn, yn), (bx - 0.325, yn), (bx, by)]
        wire(net, 'B', [(jx, -8.2), (jx, -7.7), (ex, -7.25), (ex, yn), (bx - 0.325, yn), (bx, by)])

# CSI: clock and lane 1 go up through vias and run on the top layer under the module, lane 0 stays on the bottom
c8, c7 = ball('C8'), ball('C7')
wire('CSI_CK_P', 'B', [c8, (8.1, -2.7)])
hs_via('CSI_CK_P', 8.1, -2.7)
wire('CSI_CK_P', 'F', [(8.1, -2.7), (8.45, -3.05), (8.45, -3.8), (8.75, -4.1), (9.2, -4.1)])
wire('CSI_CK_N', 'B', [c7, (7.45, -2.7)])
hs_via('CSI_CK_N', 7.45, -2.7)
wire('CSI_CK_N', 'F', [(7.45, -2.7), (8.0, -3.25), (8.0, -4.7), (8.4, -5.1), (9.2, -5.1)])
d8, d7 = ball('D8'), ball('D7')
wire('CSI_D1_P', 'B', [d8, (7.45, -4.0), (6.8, -4.0)])
hs_via('CSI_D1_P', 6.8, -4.0)
wire('CSI_D1_P', 'F', [(6.8, -4.0), (6.62, -4.3), (6.62, -6.4), (6.5, -6.8)])
wire('CSI_D1_N', 'B', [d7, (7.45, -3.35)])
hs_via('CSI_D1_N', 7.45, -3.35)
wire('CSI_D1_N', 'F', [(7.45, -3.35), (7.45, -5.5), (7.5, -6.8)])
e8, e7 = ball('E8'), ball('E7')
wire('CSI_D0_P', 'B', [e8, (8.1, e8[1]), (9.3, -3.125), (10.5, e8[1]), (10.72, e8[1]), (10.72, -3.1)])
hs_via('CSI_D0_P', 10.72, -3.1)
wire('CSI_D0_P', 'F', [(10.72, -3.1), (9.9, -3.1)])
wire('CSI_D0_N', 'B', [e7, (7.45, -4.65), (11.2, -4.65), (11.2, -2.1), (10.72, -2.1)])
hs_via('CSI_D0_N', 10.72, -2.1)
wire('CSI_D0_N', 'F', [(10.72, -2.1), (9.9, -2.1)])

# USB: both connector rows tie together on the bottom, through the ESD part, up to the module
for x in (8.0, 9.0):
    hs_via('USB_DP', x, -10.55)
    wire('USB_DP', 'F', [(x, -11.2), (x, -10.55)], W_USB)
for x in (8.5, 9.5):
    hs_via('USB_DN', x, -10.05)
    wire('USB_DN', 'F', [(x, -11.2), (x, -10.05)], W_USB)
wire('USB_DP', 'B', [(9.0, -10.55), (5.0, -10.55), (3.5, -9.05), (3.5, -8.55)], W_USB)
wire('USB_DN', 'B', [(9.5, -10.05), (5.1, -10.05), (4.5, -9.45), (4.5, -8.55)], W_USB)
hs_via('USB_DP', 3.5, -8.55)
hs_via('USB_DN', 4.5, -8.55)
wire('USB_DP', 'F', [(3.5, -8.55), (3.5, -7.5)], W_USB)
wire('USB_DN', 'F', [(4.5, -8.55), (4.5, -7.5)], W_USB)
RAIL_W = 0.15
rail_wires, rail_vias = [], []


def rail(net, balls, top):
    for b, v in balls:
        rail_wires.append((net, 'B', [ball(b), v]))
        rail_vias.append((net, v[0], v[1]))
        wire(net, 'B', [ball(b), v], RAIL_W)
        hs_via(net, v[0], v[1])
    for pts in top:
        rail_wires.append((net, 'F', pts))
        wire(net, 'F', pts, RAIL_W)


rail('VDDC', [('C3', (4.2, -2.7)), ('F5', (5.5, -5.3)), ('G2', (4.2, -5.3))], [[(4.2, -2.7), (4.2, -5.3), (5.5, -5.3)]])
for _side, _pts in (('F', [(4.2, -4.7), (1.7, -4.7), (1.25, -5.15), (1.25, -5.4)]), ('B', [(1.25, -5.4), (0.7, -5.52)])):
    rail_wires.append(('VDDC', _side, _pts))
    wire('VDDC', _side, _pts, RAIL_W)
rail_vias.append(('VDDC', 1.25, -5.4))
hs_via('VDDC', 1.25, -5.4)
rail('AVDD12', [('B2', (3.55, -2.05)), ('D3', (4.85, -3.35))], [[(3.55, -2.05), (4.85, -2.05), (4.85, -3.35)]])
rail('VDD_MIPI', [('C6', (6.15, -2.7)), ('F6', (6.15, -5.3))], [[(6.15, -2.7), (6.15, -5.3)]])
rail('AVDD25', [('B5', (5.5, -2.05))], [])
# reference clock, hand routed in full
h5 = ball('H5')
wire('TC_REFCLK', 'B', [h5, (6.08, -6.8), (6.08, -7.8), (6.92, -8.2)])
HS_NETS.add('TC_REFCLK')
# DDC clock leaves the front row by a channel, then a via clear of the module pads
h3 = ball('H3')
pts3 = [h3, (4.2, -6.6), (2.35, -6.6), (2.0, -6.25), (2.0, -6.0)]
wire('DDC3_SCL', 'B', pts3, RAIL_W)
hs_via('DDC3_SCL', 2.0, -6.0)
rail_wires.append(('DDC3_SCL', 'B', pts3))
rail_vias.append(('DDC3_SCL', 2.0, -6.0))
# every front-row ball gets its escape here, so the router starts clear of the BGA
for net, b, pts, via in (('DDC3_SDA', 'G3', None, (4.2, -5.95)), ('HPDI', 'H2', None, (3.55, -5.95)), ('TC_HPDO', 'H1', None, (2.75, -6.0)),
                         ('HDMI_CEC', 'G1', [(2.4, -5.625)], (2.0, -5.4)), ('TC_RST', 'G5', None, (6.15, -5.95))):
    path = [ball(b)] + (pts or []) + [via]
    wire(net, 'B', path, RAIL_W)
    hs_via(net, via[0], via[1])
    rail_wires.append((net, 'B', path))
    rail_vias.append((net, via[0], via[1]))
# oscillator output, hand routed in full
wire('OSC_OUT', 'B', [(7.88, -8.2), (8.08, -8.8), (8.08, -9.4)])
wire('OSC_OUT', 'B', [(8.08, -8.8), (9.3, -8.8)])
HS_NETS.add('OSC_OUT')
wire('VDD_MIPI', 'B', [(9.2, -6.18), (8.55, -6.2)], RAIL_W)
hs_via('VDD_MIPI', 8.55, -6.2)
rail_vias.append(('VDD_MIPI', 8.55, -6.2))
rail_wires.append(('VDD_MIPI', 'B', [(9.2, -6.18), (8.55, -6.2)]))
rail_wires.append(('VDD_MIPI', 'In2', [(6.15, -5.3), (8.55, -6.2)]))
# flash and console port: both connector rows tie together behind the pads
for net, x, ys in (('USB2_DP', 12.75, (2.75, 1.75)), ('USB2_DN', 13.15, (2.25, 3.25))):
    for y in ys:
        rail_wires.append((net, 'F', [(11.6, y), (x, y)]))
        wire(net, 'F', [(11.6, y), (x, y)], RAIL_W)
        rail_vias.append((net, x, y))
        hs_via(net, x, y)
    rail_wires.append((net, 'B', [(x, ys[0]), (x, ys[1])]))
    wire(net, 'B', [(x, ys[0]), (x, ys[1])], RAIL_W)
rail('I2C_SDA', [('G4', (5.5, -5.95))], [])
rail('I2C_SCL', [('H4', (4.85, -5.95))], [])
wire('USB2_DN', 'F', [(2.5, -7.5), (2.5, -8.3)], RAIL_W)
hs_via('USB2_DN', 2.5, -8.3)
rail_wires.append(('USB2_DN', 'F', [(2.5, -7.5), (2.5, -8.3)]))
rail_vias.append(('USB2_DN', 2.5, -8.3))
five = [(11.3, 4.9), (10.56, 4.9), (10.56, 0.1), (11.3, 0.1)]
wire('5V', 'F', five, 0.4)
wire('5V', 'F', [(10.56, 4.9), (10.56, 6.4)], 0.4)
vias.append((10.56, 6.4, '5V'))
wire('5V', 'F', [(10.56, 6.4), (10.56, 6.95)], 0.4)
wire('5V', 'In2', [(10.56, 6.4), (10.56, 6.95)], 0.4)
vias.append((10.56, 6.95, '5V'))
RAILS = {'VDDC', 'AVDD12', 'VDD_MIPI', 'AVDD25', 'I2C_SDA', 'I2C_SCL', 'USB2_DN', 'USB2_DP', '5V', 'DDC3_SCL', 'DDC3_SDA', 'HDMI_5V', 'HPDI', 'TC_HPDO', 'HDMI_CEC', 'TC_RST'}
# audio PLL filter cap, hand routed in full
a6 = ball('A6')
wire('TC_PFIL', 'B', [a6, (6.15, -1.4)])
hs_via('TC_PFIL', 6.15, -1.4)
wire('TC_PFIL', 'F', [(6.15, -1.4), (4.88, 0.85)])
hs_via('TC_PFIL', 4.88, 0.85)
wire('TC_PFIL', 'B', [(4.88, 0.85), (4.88, 1.6)])
HS_NETS.add('TC_PFIL')
# 3V3 leaves the buck on a wide strap into four plane vias; 5V gets a second via
W_STRAP = 0.6
wire('3V3', 'B', [(12.1, 14.68), (8.3, 14.68)], W_STRAP)
# four plane vias under the module's blank area: two left of C62, two behind it
wire('3V3', 'B', [(8.3, 14.4), (7.575, 13.6925), (7.3, 13.6), (7.1, 13.6), (6.4, 13.6)], 0.3)  # between U11's two pads and past C62.2
wire('3V3', 'B', [(8.2, 15.0), (8.2, 15.75)], 0.3)
wire('3V3', 'B', [(7.95, 15.0), (7.7, 15.75)], 0.3)
for _v in ((7.1, 13.6), (6.4, 13.6), (8.2, 15.75), (7.7, 15.75)):
    vias.append((_v[0], _v[1], '3V3'))
# F3 and F4 share one dogbone
for _b in ('F3', 'F4'):
    wire('3V3', 'B', [ball(_b), (4.85, -4.65)], 0.15)
    done.add(ball(_b))
vias.append((4.85, -4.65, '3V3'))
for _ref, _n in (('L1', '2'), ('C61', '1'), ('C62', '1')):
    _q = next(q for q in SP[_ref]['abs'] if q['n'] == _n)
    done.add((_q['wx'], _q['wy']))
n_hs_vias = len(vias)
# Plane escapes fixed by hand so a footprint change does not ripple through the search below and into the routed copper.
PLANE_PIN = {
    'C10.2': [(-0.98, 7.65), (-1.222, 8.5531)],
    'C12.2': [(6.72, 7.65), (5.8169, 7.892)],
    'R22.2': [(8.02, 9.2), (7.72, 9.75)],
    'U10.2': [(6.575, 10.635), (6.6, 11.45), (7.83, 11.45), (8.01, 11.27)],
    'U11.2': [(6.575, 14.235), (6.1721, 16.2803)],
    'U4.1': [(1.45, 6.3375), (1.45, 7.1), (0.9, 7.65), (0.58, 7.65)],
    'U4.2': [(0.5, 6.3375), (0.5, 5.2)],
    'U4.3': [(-0.45, 6.3375), (-2.2343, 6.047)],
}
PIN_NO_VIA = {'U4.1'}  # ends on C10.1, which has its own escape
# HDMI ground pads escape forward under the connector body, the lines leave backward
for n in ('2', '5', '8', '11', '17'):
    q = next(q for pp in parts if pp['ref'] == 'J2' for q in pp['abs'] if q['n'] == n)
    vias.append((q['wx'], -10.95, 'GND'))
    stubs.append((q['wx'], q['wy'], q['wx'], -10.95, 'B', 'GND', 0.15))
    done.add((q['wx'], q['wy']))
for p in sorted(search_parts, key=lambda p: (p['lib'] != 'BGA-64_6x6', p['ref'])):
    for q in p['abs']:
        net = p['nets'][q['n']]
        if net not in PLANE or q['kind'] == 'thru_hole':
            continue
        side = p['side']
        px, py = q['wx'], q['wy']
        if (px, py) in done:
            continue
        pin = PLANE_PIN.get(f"{p['ref']}.{q['n']}")
        if pin:
            for _a, _b in zip(pin, pin[1:]):
                stubs.append((_a[0], _a[1], _b[0], _b[1], side, net, 0.15))
            if f"{p['ref']}.{q['n']}" not in PIN_NO_VIA:
                vias.append((pin[-1][0], pin[-1][1], net))
            done.add((px, py))
            continue
        peers = [o for o in obst if o['net'] == net and o['side'] in (side, 'A') and (o['x'], o['y']) != (px, py) and (o['side'] == 'A' or (o['x'], o['y']) in done) and math.hypot(px - o['x'], py - o['y']) < 2.6 and stub_ok((px, py), (o['x'], o['y']), side, net, 0.15)]
        if peers and p['lib'] != 'ESP32-P4-Module':
            o = min(peers, key=lambda o: math.hypot(px - o['x'], py - o['y']))
            stubs.append((px, py, o['x'], o['y'], side, net, 0.15))
            done.add((px, py))
            continue
        reuse = [v for v in vias if v[2] == net and math.hypot(px - v[0], py - v[1]) < 1.0 and stub_ok((px, py), v[:2], side, net, 0.15)]
        if reuse and p['lib'] != 'ESP32-P4-Module':
            v = min(reuse, key=lambda v: math.hypot(px - v[0], py - v[1]))
            stubs.append((px, py, v[0], v[1], side, net, 0.15))
            done.add((px, py))
            continue
        best = None
        half = max(q['ww'], q['wh']) / 2
        for r in [0.46, 0.55, 0.65, 0.75, 0.9, 1.05, 1.2, 1.4, 1.6, 1.9, 2.2, 2.6]:
            d = r if p['lib'] == 'BGA-64_6x6' else r + half
            for k in range(24):
                ang = 2 * math.pi * k / 24
                if p['lib'] == 'BGA-64_6x6' and r == 0.46:
                    ang = math.pi / 4 + k * math.pi / 2 if k < 4 else None
                    if ang is None:
                        continue
                x, y = px + d * math.cos(ang), py + d * math.sin(ang)
                if not via_ok(x, y, net) or not stub_ok((px, py), (x, y), side, net, 0.15):
                    continue
                # prefer pointing away from the board's busiest spot only by distance
                best = (x, y)
                break
            if best:
                break
        if not best:
            unfanned.append(f"{p['ref']}.{q['n']}")
            continue
        done.add((px, py))
        vias.append((best[0], best[1], net))
        stubs.append((px, py, best[0], best[1], side, net, 0.15))
print('plane vias', len(vias), 'stubs', len(stubs), 'not escaped', unfanned)


# ---------- r6 copper on top of the frozen search result, so it cannot move anything else
def r6_drop_via(x, y, net):
    hit = [v for v in vias if v[2] == net and math.hypot(v[0] - x, v[1] - y) < 0.05]
    assert len(hit) == 1, (x, y, net, hit)
    vias.remove(hit[0])


def r6_drop_stubs(x, y, net):
    hit = [t for t in stubs if t[5] == net and (math.hypot(t[0] - x, t[1] - y) < 0.05 or math.hypot(t[2] - x, t[3] - y) < 0.05)]
    assert hit, (x, y, net)
    for t in hit:
        stubs.remove(t)
    return hit


def r6_add(net, side, pts, w):
    for a, b in zip(pts, pts[1:]):
        stubs.append((a[0], a[1], b[0], b[1], side, net, w))


stubs[:] = [t for t in stubs if t[5] not in TMDS_R6]
for _n, _pts in TMDS_R6.items():
    wire(_n, 'B', _pts)
wire('USB_DP', 'B', [(3.5, -8.55), (3.53, -7.85)], 0.18)  # F4 stub to R60.2
W_RF = 0.15  # 50 ohm on JLC06121H-3313 with the 0.25 pour gap, tools/r6/rf_width.py
wire('LNA_OUT', 'F', [(-12.5, 18.4), (-12.5, 18.97)], W_RF)
vias.append((-12.5, 18.97, 'LNA_OUT'))
wire('LNA_OUT', 'B', [(-12.5, 18.97), (-12.5, 18.5)], W_RF)
# J8 grounds: its two pads strap to the module ground vias at y 19.07, and two more vias behind it
vias.append((-11.81, 18.97, 'GND'))  # flanks the LNA_OUT via from the other side, 0.69 mm
r6_add('GND', 'B', [(-14.0, 17.5), (-14.0, 18.9), (-13.19, 19.07)], 0.3)
r6_add('GND', 'B', [(-11.2, 17.5), (-11.19, 19.07)], 0.3)
for _x, _y, _px in ((-13.9, 15.2, -13.9), (-11.0, 15.25, -11.0)):
    vias.append((_x, _y, 'GND'))
    r6_add('GND', 'B', [(_x, _y), (_px, 15.6)], 0.3)
vias.append((-14.2, 17.95, 'GND'))
r6_add('GND', 'B', [(-14.2, 17.95), (-14.2, 17.5)], 0.3)
# TP8 moved: its old via and stub go; the pad straps to a new via
_t8 = r6_drop_stubs(-10.4, 17.6, 'GND')
assert len(_t8) == 1, _t8
_end = (_t8[0][0], _t8[0][1]) if math.hypot(_t8[0][0] + 10.4, _t8[0][1] - 17.6) > 0.05 else (_t8[0][2], _t8[0][3])
r6_drop_via(_end[0], _end[1], 'GND')
vias.append((-9.9, 12.75, 'GND'))
r6_add('GND', 'B', [(-8.8, 13.4), (-9.9, 12.75)], 0.15)
# C19 and C20 grounds at their new places. The old vias stay as stitching. The two stubs through the old C19.2 point stay too: they tie Y1.2 to C17.2.
print('r6 old C20.2 stubs', r6_drop_stubs(9.82, 1.2, 'GND'))
vias.append((-1.85, -5.95, 'GND'))
r6_add('GND', 'B', [(-1.85, -5.95), (-1.88, -5.45)], 0.2)
r6_add('GND', 'B', [(-1.85, -5.95), (-2.53, -6.4)], 0.2)
# C64 ground into the J5.1 barrel, R51 gets its own via off the hot return
r6_add('GND', 'B', [(13.95, 7.32), (13.3, 7.0)], 0.3)
print('r6 old R51.2 stubs', r6_drop_stubs(11.7, 8.12, 'GND'))
vias.append((11.25, 7.7, 'GND'))
r6_add('GND', 'B', [(11.7, 8.12), (11.25, 7.7)], 0.15)
# U8's ground via 0.14 mm toward its pad, so D1_P has room for its tooth
r6_drop_via(-4.25, -5.11, 'GND')
vias.append((-4.25, -5.25, 'GND'))
_u8 = r6_drop_stubs(-4.25, -5.11, 'GND')
for _t in _u8:
    _o = (_t[0], _t[1]) if math.hypot(_t[0] + 4.25, _t[1] + 5.11) > 0.05 else (_t[2], _t[3])
    r6_add('GND', 'B', [_o, (-4.25, -5.25)], _t[6])
# item 4: U7 centre grounds, each strapped to its neighbour balls
for _v, _balls in (((5.5, -4.0), ('D4', 'D5', 'E4', 'E5')), ((6.8, -3.35), ('D6',)), ((4.85, -4.0), ('D4', 'E3', 'E4'))):
    vias.append((_v[0], _v[1], 'GND'))
    for _b in _balls:
        r6_add('GND', 'B', [ball(_b), _v], 0.15)
# item 6: return vias beside high-speed layer changes, coordinates from review 4.3
R6_RETURN = [(11.66, -3.10), (11.66, -2.40), (6.80, -2.70), (4.00, -8.90), (10.06, -10.29), (10.00, -9.71)]
# item 5: edge stitching, candidates from review 5.3, 0.95 mm in from the edge
R6_EDGE = [(-19.05, -16.70), (-19.05, -12.91), (-19.05, -8.91), (-19.05, -4.91), (-19.05, 11.39), (-19.05, 16.19),
           (-16.70, 19.05), (-10.55, 19.05), (-5.55, 19.05), (-1.55, 19.05), (3.35, 19.05), (7.35, 19.05), (13.25, 19.05),
           (19.05, 16.70), (19.05, 12.90), (19.05, 8.90), (19.05, 4.90), (19.05, 0.90), (19.05, -3.10), (19.05, -7.10), (19.05, -11.10), (19.05, -15.10),
           (16.70, -19.05), (12.95, -19.05), (8.95, -19.05), (4.95, -19.05), (0.95, -19.05), (-3.05, -19.05), (-7.05, -19.05), (-11.05, -19.05), (-15.05, -19.05)]
R6_EDGE += [(16.7, 19.05), (10.3, 19.05)]  # r6 additions to the review's list, into its largest gaps
R6_SKIP = set()  # candidates that fail DRC, with the reason, are listed in R6_REPORT.md
for _v in R6_RETURN + R6_EDGE:
    if _v not in R6_SKIP:
        vias.append((_v[0], _v[1], 'GND'))


# ---------- r7 copper on top of the frozen search
def r7_drop_escape(ref, n):
    """Removes the plane escape the r6 search gave one pad: its stub, and the via at the stub's far end if nothing else uses that via."""
    q = next(q for q in SP[ref]['abs'] if q['n'] == n)
    net = SP[ref]['nets'][n]
    hit = r6_drop_stubs(q['wx'], q['wy'], net)
    for t in hit:
        end = (t[2], t[3]) if math.hypot(t[0] - q['wx'], t[1] - q['wy']) < 0.05 else (t[0], t[1])
        users = [s for s in stubs if s[5] == net and (math.hypot(s[0] - end[0], s[1] - end[1]) < 0.05 or math.hypot(s[2] - end[0], s[3] - end[1]) < 0.05)]
        for v in [v for v in vias if v[2] == net and math.hypot(v[0] - end[0], v[1] - end[1]) < 0.05]:
            if not users:
                vias.remove(v)
    return hit


print('r7 drop U5.2 escape', r7_drop_escape('U5', '2'))
print('r7 drop U6.5 3V3 escape', r7_drop_escape('U6', '5'))
# item 3: the 1.2 V buck's own copper. SW, FB and the divider midpoint are fixed here; V1V2 between L2 and the two output caps is prewired
R7_LOCAL = {'SW_1V2', 'FB_1V2', 'FB_MID'}
HS_NETS.update(R7_LOCAL)
r6_add('SW_1V2', 'F', [(-7.0, -15.35), (-5.5, -15.35)], 0.6)                       # U15.3 LX to L2.1
r6_add('3V3', 'F', [(-10.35, -17.6), (-9.6, -16.85), (-9.6, -15.35)], 0.4)          # C65 to U15.4 IN
for _v, _a in (((-11.4, -17.6), (-10.35, -17.6)), ((-10.5, -16.2), (-9.6, -16.2)), ((-6.2, -12.95), (-6.8, -13.45))):
    vias.append((_v[0], _v[1], '3V3'))                                              # IN and EN (U15.1) to the In3 plane
    r6_add('3V3', 'F', [_a, _v], 0.3 if _v[1] < -16 else 0.2)
for _v, _a in (((-7.5, -17.6), (-8.45, -17.6)), ((-8.45, -18.7), (-8.45, -17.6)), ((-6.2, -14.15), (-6.8, -14.4)), ((-12.5, -14.35), (-11.68, -14.35)), ((-2.6, -10.95), (-2.6, -11.95))):
    vias.append((_v[0], _v[1], 'GND'))                                              # C65, U15.2, R63, C66 grounds to In1/In4
    r6_add('GND', 'F', [_a, _v], 0.3)
r6_add('GND', 'F', [(-4.6, -11.95), (-4.0, -10.95)], 0.3)                          # C67 ground onto the existing J2 ground via
r6_add('FB_1V2', 'F', [(-10.72, -14.35), (-10.72, -12.55)], 0.15)
r6_add('FB_1V2', 'F', [(-10.72, -13.45), (-9.6, -13.45)], 0.15)                   # to U15.5 FB
r6_add('FB_MID', 'F', [(-11.68, -13.45), (-11.68, -12.55), (-12.52, -12.55)], 0.15)
R7_RAILW = [('V1V2', 'F', [(-2.5, -15.5), (-2.6, -13.85)], 0.6), ('V1V2', 'F', [(-2.6, -13.85), (-4.6, -13.85)], 0.6)]
# item 1: U6.5 (EN) to U6.8 (VCCB, 5V) on B, outside the pin row between U6 and U9 (0.55 mm). The DDC_SDA branch to R28 used that gap
# (R7_DROP_BOX); R28 moves to just above U6, between this 5V line and the DDC_SDA line to J2.16. Every way through a via was blocked: see R7_REPORT.md
R7_RAILW += [('5V', 'B', [(-9.67, -6.75), (-9.15, -6.23), (-9.15, -3.725), (-9.6, -3.725)], 0.127), ('5V', 'B', [(-9.6, -5.675), (-9.15, -5.675)], 0.127),
             ('DDC_SDA', 'B', [(-10.63, -6.75), (-11.0, -6.782)], 0.127)]   # R28 (DDC_SDA pull-up) moved here: its old branch ran through that gap
R7_RAILV = []
R7_RAILW += [('V1V2', 'B', [(9.9, 5.12), (9.252, 5.0)], 0.2)]   # R65.2 onto the V1V2 junction that feeds FB3, FB4, FB5
# item 6: CSI_D0 and CSI_CK_P re-drawn with 45 degree corners only, P lengthened to match N
stubs[:] = [t for t in stubs if not (t[4] == 'B' and t[5] in ('CSI_D0_P', 'CSI_D0_N', 'CSI_CK_P'))]
_len = lambda pts: sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
_d0n = [e7, (7.45, -4.65), (10.9, -4.65), (11.2, -4.35), (11.2, -2.58), (10.72, -2.1)]
_c = 0.1
_base = [e8, (8.1, e8[1]), (9.3, e8[1])] + [(9.9, e8[1]), (10.42, e8[1]), (10.72, e8[1] + 0.3), (10.72, -3.1)]
_a = (_len(_d0n) - _len(_base) + (8 - 4 * math.sqrt(2)) * _c) / 2
_d0p = [e8, (8.1, e8[1])] + tooth((9.3, e8[1]), (1, 0), (0, 1), _a, _c, 0.2) + [(10.42, e8[1]), (10.72, e8[1] + 0.3), (10.72, -3.1)]
wire('CSI_D0_N', 'B', _d0n)
wire('CSI_D0_P', 'B', _d0p)
wire('CSI_CK_P', 'B', [c8, (8.15, -3.4), (8.4, -3.4), (8.6, -3.2), (8.6, -2.9), (8.4, -2.7), (8.1, -2.7)])
print(f'r7 CSI_D0 B lengths P {_len(_d0p):.4f} N {_len(_d0n):.4f}, tooth height {_a:.4f}')


# ---------- r7b copper on top of the frozen search
def r7b_escape(ref, n):
    q = next(q for q in SP[ref]['abs'] if q['n'] == n)
    net = SP[ref]['nets'][n]
    hit = [i for i, t in enumerate(stubs) if t[5] == net and (math.hypot(t[0] - q['wx'], t[1] - q['wy']) < 0.05 or math.hypot(t[2] - q['wx'], t[3] - q['wy']) < 0.05)]
    assert hit, (ref, n)
    return q, net, hit


# L3: R21.1 now goes to GND; its plane escape (stub and via) changes net, same place
_q, _n, _hit = r7b_escape('R21', '1')
for _i in _hit:
    _t = stubs[_i]
    _end = (_t[2], _t[3]) if math.hypot(_t[0] - _q['wx'], _t[1] - _q['wy']) < 0.05 else (_t[0], _t[1])
    stubs[_i] = _t[:5] + ('GND',) + _t[6:]
    for _k, _v in enumerate(vias):
        if _v[2] == '3V3' and math.hypot(_v[0] - _end[0], _v[1] - _end[1]) < 0.05:
            vias[_k] = (_v[0], _v[1], 'GND')
print('r7b R21.1 escape to GND', _hit)
# M7: J6's 3V3 and GND pins keep their escapes, moved with the part; the two shell tabs keep their vias and get new stubs
for _pin in ('1', '2', '8'):
    _q, _n, _hit = r7b_escape('J6', _pin)
    for _i in _hit:
        _t = stubs[_i]
        _end = (_t[2], _t[3]) if math.hypot(_t[0] - _q['wx'], _t[1] - _q['wy']) < 0.05 else (_t[0], _t[1])
        stubs[_i] = (_t[0] + J6_DX, _t[1], _t[2] + J6_DX, _t[3]) + _t[4:]
        for _k, _v in enumerate(vias):
            if _v[2] == _n and math.hypot(_v[0] - _end[0], _v[1] - _end[1]) < 0.05:
                vias[_k] = (_v[0] + J6_DX, _v[1], _n)
for _pin in ('9', '10'):
    _q, _n, _hit = r7b_escape('J6', _pin)
    for _i in _hit:
        _t = stubs[_i]
        stubs[_i] = ((_t[0] + J6_DX, _t[1]) + _t[2:]) if math.hypot(_t[0] - _q['wx'], _t[1] - _q['wy']) < 0.05 else (_t[:2] + (_t[2] + J6_DX, _t[3]) + _t[4:])
# the 3V3 via of C63.1 at (12.34, 10.7) would sit under the moved J6.7: C63.1 joins J6.8's 3V3 via instead, on B
print('r7b drop C63.1 escape', r7_drop_escape('C63', '1'))
r6_add('3V3', 'B', [(10.6, 9.08), (11.28, 10.7)], 0.15)   # R50.1 to C63.1, which went with the drop
r6_add('3V3', 'B', [(11.28, 10.7), (12.485 + J6_DX, 9.8)], 0.15)
for name in unfanned:
    r_, n_ = name.split('.')
    pp = next(x for x in parts if x['ref'] == r_)
    qq = next(x for x in pp['abs'] if x['n'] == n_)
    print('   ', name, 'at', round(qq['wx'], 2), round(qq['wy'], 2), 'size', qq['ww'], qq['wh'], 'nearest', sorted((round(rect_dist(qq['wx'], qq['wy'], o), 2), o['net']) for o in obst if o['net'] != pp['nets'][n_] and o['side'] in (pp['side'], 'A'))[:2])
fixed_vias = [v for v in vias if v[2] not in RAILS]
fixed_stubs = [t for t in stubs if t[5] not in RAILS]
for x, y, net in fixed_vias:
    tracks.append(f'(via (at {x + OX:.4f} {y + OY:.4f}) (size {VIA_D}) (drill {VIA_DR}) (layers "F.Cu" "B.Cu") (net {netid[net]}) (uuid "{uid()}"))')
for x0, y0, x1, y1, side, net, w in fixed_stubs:
    tracks.append(f'(segment (start {x0 + OX:.4f} {y0 + OY:.4f}) (end {x1 + OX:.4f} {y1 + OY:.4f}) (width {w}) (layer "{side}.Cu") (net {netid[net]}) (uuid "{uid()}"))')
pre_count = len(tracks)


def ses_items(path, skip_unknown=False):
    """Every routed segment and via in an SES, as board text lines."""
    out = []
    s = open(path, encoding='utf-8').read()
    res = float(re.search(r'\(resolution um (\d+)\)', s).group(1))
    k = 1 / res / 1000.0
    i = s.find('network_out')
    netpos = [(m.start(), m.group(1) or m.group(2)) for m in re.finditer(r'\(net\s+(?:"([^"]+)"|([^\s()]+))', s[i:])]
    for j, (a, n) in enumerate(netpos):
        block = s[i + a:i + (netpos[j + 1][0] if j + 1 < len(netpos) else len(s) - i)]
        n = n.replace('%', '/')
        if n not in netid:
            if skip_unknown:
                print('  SES net not on this board, skipped:', n)
                continue
            raise SystemExit(f'unknown net in SES: {n}')
        for wm in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', block):
            layer = wm.group(1)
            w = max(int(wm.group(2)) * k, 0.09)
            v = [int(t) for t in wm.group(3).split()]
            pts = [(v[t] * k, -v[t + 1] * k) for t in range(0, len(v), 2)]
            for a0, b0 in zip(pts, pts[1:]):
                out.append(f'(segment (start {a0[0] + OX:.4f} {a0[1] + OY:.4f}) (end {b0[0] + OX:.4f} {b0[1] + OY:.4f}) (width {w:.4f}) (layer "{layer}") (net {netid[n]}) (uuid "{uid()}"))')
        for vm in re.finditer(r'\(via\s+"?([^"\s]+)"?\s+(-?\d+)\s+(-?\d+)', block):
            d, dr = (0.5, 0.25) if 'P' in vm.group(1) else (0.4, 0.2)
            x, y = int(vm.group(2)) * k, -int(vm.group(3)) * k
            out.append(f'(via (at {x + OX:.4f} {y + OY:.4f}) (size {d}) (drill {dr}) (layers "F.Cu" "B.Cu") (net {netid[n]}) (uuid "{uid()}"))')
    return out


if SES:
    _ses = ses_items(SES)
    nvia = sum(t.startswith('(via') for t in _ses)
    tracks += _ses

def prune(items):
    segs, vs, keep = [], [], []
    for t in items:
        m = re.match(r'\(segment \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(width ([-\d.]+)\) \(layer "([^"]+)"\) \(net (\d+)\)', t)
        if m:
            segs.append(dict(a=(float(m[1]), float(m[2])), b=(float(m[3]), float(m[4])), ly=m[6], net=int(m[7]), t=t))
            continue
        m = re.match(r'\(via \(at ([-\d.]+) ([-\d.]+)\).*\(net (\d+)\)', t)
        vs.append(dict(p=(float(m[1]), float(m[2])), net=int(m[3]), t=t))
    near = lambda u, v: math.hypot(u[0] - v[0], u[1] - v[1]) < 0.02

    def on_pad(pt, ly, net):
        x, y = pt[0] - OX, pt[1] - OY
        for pp in parts:
            for q in pp['abs']:
                if netid[pp['nets'][q['n']]] != net:
                    continue
                if q['kind'] != 'thru_hole' and ly != f"{pp['side']}.Cu":
                    continue
                if abs(x - q['wx']) <= q['ww'] / 2 + 0.01 and abs(y - q['wy']) <= q['wh'] / 2 + 0.01:
                    return True
        return False

    removed = 0
    changed = True
    while changed:
        changed = False
        for v in list(vs):
            lys = {g['ly'] for g in segs if g['net'] == v['net'] and seg_dist(v['p'][0], v['p'][1], (*g['a'], *g['b'])) < 0.03}
            lys |= {ly for ly in ('F.Cu', 'B.Cu') if on_pad(v['p'], ly, v['net'])}
            if v['net'] in (netid['GND'], netid['3V3']):
                continue
            if len(lys) < 2:
                vs.remove(v)
                removed += 1
                changed = True
        for g in list(segs):
            for end in (g['a'], g['b']):
                other = [h for h in segs if h is not g and h['net'] == g['net'] and h['ly'] == g['ly'] and seg_dist(end[0], end[1], (*h['a'], *h['b'])) < 0.02]
                via = [v for v in vs if v['net'] == g['net'] and near(v['p'], end)]
                if not other and not via and not on_pad(end, g['ly'], g['net']):
                    segs.remove(g)
                    removed += 1
                    changed = True
                    break
    print('pruned dead-end copper items', removed)
    return [g['t'] for g in segs] + [v['t'] for v in vs]


SEG_RE = re.compile(r'\(segment \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(width ([-\d.]+)\) \(layer "([^"]+)"\) \(net (\d+)\)')
VIA_RE = re.compile(r'\(via \(at ([-\d.]+) ([-\d.]+)\) \(size ([-\d.]+)\).*\(net (\d+)\)')


def parse_copper(items):
    segs, vs = [], []
    for t in items:
        m = SEG_RE.match(t)
        if m:
            segs.append((float(m[1]) - OX, float(m[2]) - OY, float(m[3]) - OX, float(m[4]) - OY, float(m[5]), m[6], int(m[7])))
            continue
        m = VIA_RE.match(t)
        if m:
            vs.append((float(m[1]) - OX, float(m[2]) - OY, float(m[3]), int(m[4])))
    return segs, vs


def islands(net, segs, vs):
    """Groups a net's copper and pads by actual contact. Returns lists of (kind, data), one list per connected group."""
    nid = netid[net]
    nodes = [('s', g) for g in segs if g[6] == nid] + [('v', v) for v in vs if v[3] == nid]
    pads_ = [(pp, q) for pp in parts for q in pp['abs'] if pp['nets'][q['n']] == net]
    nodes += [('p', x) for x in pads_]
    par = list(range(len(nodes)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def pad_layers(x):
        return None if x[1]['kind'] == 'thru_hole' else f"{x[0]['side']}.Cu"

    def in_pad(pt, x):
        return abs(pt[0] - x[1]['wx']) <= x[1]['ww'] / 2 + 0.02 and abs(pt[1] - x[1]['wy']) <= x[1]['wh'] / 2 + 0.02

    def touch(a, b):
        ka, da, kb, db = a[0], a[1], b[0], b[1]
        if ka == 's' and kb == 's':
            if da[5] != db[5]:
                return False
            return min(seg_dist(da[0], da[1], db[:4]), seg_dist(da[2], da[3], db[:4]), seg_dist(db[0], db[1], da[:4]), seg_dist(db[2], db[3], da[:4])) < 0.02
        if {ka, kb} == {'s', 'v'}:
            g, v = (da, db) if ka == 's' else (db, da)
            return seg_dist(v[0], v[1], g[:4]) < 0.03
        if {ka, kb} == {'s', 'p'}:
            g, x = (da, db) if ka == 's' else (db, da)
            ly = pad_layers(x)
            if ly is not None and ly != g[5]:
                return False
            n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.05))
            return any(in_pad((g[0] + (g[2] - g[0]) * k / n, g[1] + (g[3] - g[1]) * k / n), x) for k in range(n + 1))
        if {ka, kb} == {'v', 'p'}:
            v, x = (da, db) if ka == 'v' else (db, da)
            return in_pad(v[:2], x)
        if ka == 'v' and kb == 'v':
            return math.hypot(da[0] - db[0], da[1] - db[1]) < 0.02
        return False

    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            if find(a) != find(b) and touch(nodes[a], nodes[b]):
                par[find(a)] = find(b)
    groups = {}
    for k, n in enumerate(nodes):
        groups.setdefault(find(k), []).append(n)
    return [g for g in groups.values() if any(n[0] == 'p' for n in g)]


def finish_open(net, items):
    """Joins a net's separate pad groups on In2 with a breadth-first search. Returns new copper."""
    segs, vs = parse_copper(items)
    nid = netid[net]
    grp = islands(net, segs, vs)
    if len(grp) < 2:
        return []
    W, CL, DV = 0.127, 0.1, 0.4
    step = 0.05
    N = int((2 * H) / step) + 1
    blocked = bytearray(N * N)

    def mark(x, y, r):
        for a in range(max(int((x - r + H) / step), 0), min(int((x + r + H) / step) + 1, N - 1) + 1):
            for b in range(max(int((y - r + H) / step), 0), min(int((y + r + H) / step) + 1, N - 1) + 1):
                if math.hypot(a * step - H - x, b * step - H - y) <= r:
                    blocked[a * N + b] = 1

    for v in vs:
        if v[3] != nid:
            mark(v[0], v[1], v[2] / 2 + CL + W / 2)
    for g in segs:
        if g[5] == 'In2.Cu' and g[6] != nid:
            n = max(2, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.04))
            for k in range(n + 1):
                mark(g[0] + (g[2] - g[0]) * k / n, g[1] + (g[3] - g[1]) * k / n, g[4] / 2 + CL + W / 2)
    for pp in parts:
        for q in pp['abs']:
            if q['kind'] == 'thru_hole' and pp['nets'][q['n']] != net:
                mark(q['wx'], q['wy'], max(q['ww'], q['wh']) / 2 + CL + W / 2)
    for c in holes:
        mark(c[0], c[1], 1.1 + 0.2 + W / 2)
    edge = int(0.35 / step)
    for k in range(N):
        for e in range(edge):
            blocked[k * N + e] = blocked[k * N + N - 1 - e] = blocked[e * N + k] = blocked[(N - 1 - e) * N + k] = 1

    def via_free(x, y):
        for pp in parts:
            for q in pp['abs']:
                if pp['nets'][q['n']] == net and q['kind'] != 'thru_hole':
                    continue
                if pp['nets'][q['n']] == net:
                    continue
                if rect_dist(x, y, dict(x=q['wx'], y=q['wy'], w=q['ww'], h=q['wh'], circ=q['shape'] == 'circle')) < DV / 2 + CL:
                    return False
        for v in vs:
            if math.hypot(x - v[0], y - v[1]) < (v[2] + DV) / 2 + CL:
                return False
        for g in segs:
            if g[6] != nid and seg_dist(x, y, g[:4]) < g[4] / 2 + DV / 2 + CL:
                return False
        return True

    def stub_free(a, b, ly):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.04))
        for k in range(n + 1):
            x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
            for pp in parts:
                for q in pp['abs']:
                    if pp['nets'][q['n']] == net or (q['kind'] != 'thru_hole' and f"{pp['side']}.Cu" != ly):
                        continue
                    if rect_dist(x, y, dict(x=q['wx'], y=q['wy'], w=q['ww'], h=q['wh'], circ=q['shape'] == 'circle')) < W / 2 + CL:
                        return False
            for g in segs:
                if g[6] != nid and g[5] == ly and seg_dist(x, y, g[:4]) < g[4] / 2 + W / 2 + CL:
                    return False
            for v in vs:
                if v[3] != nid and math.hypot(x - v[0], y - v[1]) < v[2] / 2 + W / 2 + CL:
                    return False
        return True

    def snap(v):
        return int(round((v + H) / step))

    def starts(group):
        """Grid cells a route may start from: existing vias, new vias on the group's tracks, new vias beside its pads."""
        out = {}
        for kind, d in group:
            if kind == 'v':
                c = (snap(d[0]), snap(d[1]))
                out[c] = dict(at=(d[0], d[1]), via=False, stub=None)
        for kind, d in group:
            if kind == 's':
                n = max(2, int(math.hypot(d[2] - d[0], d[3] - d[1]) / 0.05))
                for k in range(n + 1):
                    x, y = d[0] + (d[2] - d[0]) * k / n, d[1] + (d[3] - d[1]) * k / n
                    c = (snap(x), snap(y))
                    gx, gy = c[0] * step - H, c[1] * step - H
                    if c not in out and not blocked[c[0] * N + c[1]] and seg_dist(gx, gy, d[:4]) < 0.04 and via_free(gx, gy):
                        out[c] = dict(at=(gx, gy), via=True, stub=None, ly=d[5], seg=(x, y))
            elif kind == 'p':
                pp, q = d
                ly = f"{pp['side']}.Cu"
                for r in (0.6, 0.8, 1.0, 1.3, 1.6, 2.0):
                    for ang in range(0, 360, 15):
                        x, y = q['wx'] + (r + max(q['ww'], q['wh']) / 2 - 0.2) * math.cos(math.radians(ang)), q['wy'] + (r + max(q['ww'], q['wh']) / 2 - 0.2) * math.sin(math.radians(ang))
                        c = (snap(x), snap(y))
                        gx, gy = c[0] * step - H, c[1] * step - H
                        if 0 <= c[0] < N and 0 <= c[1] < N and c not in out and not blocked[c[0] * N + c[1]] and via_free(gx, gy) and stub_free((q['wx'], q['wy']), (gx, gy), ly):
                            out[c] = dict(at=(gx, gy), via=True, stub=((q['wx'], q['wy']), ly))
        return out

    a_cells = starts(grp[0])
    b_cells = {}
    for g in grp[1:]:
        b_cells.update(starts(g))
    if not a_cells or not b_cells:
        print('finish', net, 'no room for a via', len(a_cells), len(b_cells))
        return []
    prev = {c: None for c in a_cells}
    frontier = list(a_cells)
    hit = None
    while frontier and not hit:
        nxt = []
        for c in frontier:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                d = (c[0] + dx, c[1] + dy)
                if d in prev or not (0 <= d[0] < N and 0 <= d[1] < N):
                    continue
                if blocked[d[0] * N + d[1]] and d not in b_cells:
                    continue
                prev[d] = c
                if d in b_cells:
                    hit = d
                    break
                nxt.append(d)
            if hit:
                break
        frontier = nxt
    if not hit:
        print('finish', net, 'no In2 path')
        return []
    path = []
    c = hit
    while c:
        path.append(c)
        c = prev[c]
    path.reverse()
    pts = [(c[0] * step - H, c[1] * step - H) for c in path]
    keep = [pts[0]]
    for k in range(1, len(pts) - 1):
        if abs((pts[k][0] - keep[-1][0]) * (pts[k + 1][1] - pts[k][1]) - (pts[k][1] - keep[-1][1]) * (pts[k + 1][0] - pts[k][0])) > 1e-6:
            keep.append(pts[k])
    keep.append(pts[-1])
    out = []
    for info, c_end in ((a_cells[path[0]], 0), (b_cells[path[-1]], -1)):
        keep[c_end] = info['at']
        if info['via']:
            out.append(f'(via (at {info["at"][0] + OX:.4f} {info["at"][1] + OY:.4f}) (size {DV}) (drill 0.2) (layers "F.Cu" "B.Cu") (net {nid}) (uuid "{uid()}"))')
        if info.get('stub'):
            (sx, sy), ly = info['stub']
            out.append(f'(segment (start {sx + OX:.4f} {sy + OY:.4f}) (end {info["at"][0] + OX:.4f} {info["at"][1] + OY:.4f}) (width {W}) (layer "{ly}") (net {nid}) (uuid "{uid()}"))')
    out += [f'(segment (start {u[0] + OX:.4f} {u[1] + OY:.4f}) (end {w[0] + OX:.4f} {w[1] + OY:.4f}) (width {W}) (layer "In2.Cu") (net {nid}) (uuid "{uid()}"))' for u, w in zip(keep, keep[1:])]
    length = sum(math.hypot(w[0] - u[0], w[1] - u[1]) for u, w in zip(keep, keep[1:]))
    print('finish', net, f'{len(grp)} groups, In2 path {length:.1f} mm')
    return out


if SES:
    tracks = tracks[:pre_count] + prune(tracks[pre_count:])
    for _pass in range(3):
        added = 0
        for cnet in real_nets:
            if cnet in PLANE or cnet in HS_NETS:
                continue
            new_cu = finish_open(cnet, tracks)
            tracks += new_cu
            added += len(new_cu)
        if not added:
            break
# ---------- r7c (R7C_REPORT.md). Edits on top of the routed r7b board. They run after the SES import, so the frozen pre-route search
# and the SES stay exactly as they were. Every item is placed by hand here and judged by DRC, verify.py, bodycheck.py and check_case.py.
R7C = bool(SES)
R7C_LOG = []
if R7C:
    _P = {p['ref']: p for p in parts}

    def _seg(net, ly, a, b, w):
        return f'(segment (start {a[0] + OX:.4f} {a[1] + OY:.4f}) (end {b[0] + OX:.4f} {b[1] + OY:.4f}) (width {w}) (layer "{ly}") (net {netid[net]}) (uuid "{uid()}"))'

    def _via(net, x, y):
        return f'(via (at {x + OX:.4f} {y + OY:.4f}) (size 0.4) (drill 0.2) (layers "F.Cu" "B.Cu") (net {netid[net]}) (uuid "{uid()}"))'

    def _find_via(x, y):
        hit = [i for i, t in enumerate(tracks) if VIA_RE.match(t) and abs(float(VIA_RE.match(t)[1]) - OX - x) < 0.02 and abs(float(VIA_RE.match(t)[2]) - OY - y) < 0.02]
        assert len(hit) == 1, (x, y, hit)
        return hit[0]

    def _pad_hit(p, q, pt, ly, nid):
        return (netid[p['nets'][q['n']]] == nid and abs(pt[0] - q['wx']) <= q['ww'] / 2 + 1e-6 and abs(pt[1] - q['wy']) <= q['wh'] / 2 + 1e-6
                and (q['kind'] == 'thru_hole' or ly == p['side'] + '.Cu'))

    def _drag(ref, dx, dy, push=()):
        """Moves a part; every track end lying on one of its pads (same net, pad layer), or on its side's copper under its body
        (a track routed between its pads), moves with it. The far ends stay."""
        p = _P[ref]
        old = [dict(q) for q in p['abs']]
        bx0, by0, bx1, by1 = bbox(p)
        under = lambda pt, ly: ly == p['side'] + '.Cu' and bx0 + 0.1 < pt[0] < bx1 - 0.1 and by0 + 0.1 < pt[1] < by1 - 0.1
        p['x'] += dx
        p['y'] += dy
        bake(p)
        n = 0
        # pass 1: ends on its pads move; a segment with an end under the body moves whole (so its gap to the pads is kept)
        moved_pts = set()
        for i, t in enumerate(tracks):
            m = SEG_RE.match(t)
            if not m:
                continue
            pts = [(float(m[1]) - OX, float(m[2]) - OY), (float(m[3]) - OX, float(m[4]) - OY)]
            # push: other nets' segments on the part's side within 0.6 mm of its body, moved whole with it (slow signals only)
            near_body = lambda pt: bx0 - 0.6 < pt[0] < bx1 + 0.6 and by0 - 0.6 < pt[1] < by1 + 0.6
            whole = any(under(pt, m[6]) for pt in pts) or (int(m[7]) in {netid[x] for x in push} and m[6] == p['side'] + '.Cu' and any(near_body(pt) for pt in pts))
            new = [((pt[0] + dx, pt[1] + dy) if whole or any(_pad_hit(p, q, pt, m[6], int(m[7])) for q in old) else pt) for pt in pts]
            if new != pts:
                tracks[i] = f'(segment (start {new[0][0] + OX:.4f} {new[0][1] + OY:.4f}) (end {new[1][0] + OX:.4f} {new[1][1] + OY:.4f}) (width {m[5]}) (layer "{m[6]}") (net {m[7]}) (uuid "{uid()}"))'
                n += 1
                moved_pts |= {(round(a[0], 3), round(a[1], 3), m[6], m[7]) for a, b in zip(pts, new) if a != b}
        # pass 2: segments that met a moved end there follow it, so nothing is left open
        for i, t in enumerate(tracks):
            m = SEG_RE.match(t)
            if not m:
                continue
            pts = [(float(m[1]) - OX, float(m[2]) - OY), (float(m[3]) - OX, float(m[4]) - OY)]
            new = [((pt[0] + dx, pt[1] + dy) if (round(pt[0], 3), round(pt[1], 3), m[6], m[7]) in moved_pts else pt) for pt in pts]
            if new != pts and not all(a != b for a, b in zip(pts, new)):
                tracks[i] = f'(segment (start {new[0][0] + OX:.4f} {new[0][1] + OY:.4f}) (end {new[1][0] + OX:.4f} {new[1][1] + OY:.4f}) (width {m[5]}) (layer "{m[6]}") (net {m[7]}) (uuid "{uid()}"))'
                n += 1
        R7C_LOG.append(f'{ref} moved ({dx:+.3f}, {dy:+.3f}), {n} track ends dragged')

    # 1. Body gaps: every same-side pair at least 0.05 mm apart at the largest sizes with +-0.1 mm placement (bodycheck.py MARGIN).
    #    Each move is along the line between the two bodies, away from the neighbour that was at 0.000-0.010 mm.
    # U12 moves toward the old back edge; two r6 edge-stitching vias there (now 5 mm inside the new edge) would touch its pads, so they go.
    for _x, _y in ((7.35, 19.05), (13.25, 19.05)):
        del tracks[_find_via(_x, _y)]
        R7C_LOG.append(f'GND stitching via ({_x}, {_y}) removed (was edge stitching; the edge moved 5 mm out, new stitching below)')
    for _r, _dx, _dy, _push in (('C20', 0.0, -0.05, ('HDMI_CEC',)), ('C24', 0.0, -0.05, ()), ('R28', 0.0, -0.08, ()), ('U12', 0.0, 0.08, ())):
        _drag(_r, _dx, _dy, _push)

    # 2. Hole spacing: component hole (PTH pad, slot, NPTH) to any other hole >= 0.45 mm (JLC "pad hole-to-hole"), via to via >= 0.2 mm.
    #    The ground return via beside the D0 layer change (r6 item 6) moves away from the J5 shell slot: 0.259 -> 0.48 mm. Position
    #    searched for >= 0.12 mm to other-net copper on every layer; it is 1.4 mm from the D0 vias (was 1.0).
    _i = _find_via(11.66, -2.40)
    tracks[_i] = _via('GND', 12.05, -2.70)
    R7C_LOG.append('GND return via (11.66, -2.40) -> (12.05, -2.70)')

    # 3. Board grows 5 mm at the back edge only (y -20 .. +25), for the 5 V damping network. The I/O face (J2, J3), J5 and J7 do not move.
    #    J4 stays: it is on the bottom with its mouth toward the back, so the plug lies under the new strip; x -8.2..0.8 there is kept free.
    #    Back mounting holes move with the corners to (+-18, 23).
    YB = H + 5.0
    # new edge stitching along the back edge, 0.95 mm in, clear of J4, the holes and the damping network
    for _x in (-15.5, -11.5, 2.5, 15.5):
        tracks.append(_via('GND', _x, YB - 0.95))
    holes = [(HOLE, -HOLE), (-HOLE, -HOLE), (HOLE, YB - 2.0), (-HOLE, YB - 2.0)]
    outline = rounded_rect()
    edges = [f'(gr_line (start {a[0] + OX:.3f} {a[1] + OY:.3f}) (end {b[0] + OX:.3f} {b[1] + OY:.3f}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "{uid()}"))' for a, b in zip(outline, outline[1:] + outline[:1])]

    # 4. 5 V hot-plug damping (review L2; tools/hotplug.py): 330 uF polymer in series with 0.15 ohm across 5V, after Linear AN-88.
    #    The ring is about 40 kHz, so the network may sit 10 mm from J5 and U2; it hangs off C60's 5 V pad by a 0.5 mm track.
    #    C69 land: IPC-7351 CAPMP7343X200N (KiCad demo library), pin 1 = +.
    CP7343 = [pad(1, -3.1, 0, 2.35, 2.45), pad(2, 3.1, 0, 2.35, 2.45)]
    BODY['CP_7343'] = (-3.65, -2.15, 3.65, 2.15)
    part('C69', 'POSCAP 10TPE330M 330uF 10V polymer', 'C347552', 'CP_7343', CP7343, 8.3, 22.4, 0, {'1': '5V_DAMP', '2': 'GND'}, 'B')
    part('R68', '0.15 0805', 'C247444', 'C0805', C0805, 14.3, 22.4, 0, {'1': '5V', '2': '5V_DAMP'}, 'B')
    for _r in ('C69', 'R68'):
        _P[_r] = parts[-1] if parts[-1]['ref'] == _r else next(p for p in parts if p['ref'] == _r)
        bake(_P[_r])
        sym[_r] = uid('sym-' + _r)
    _q = {f"{r}.{q['n']}": (q['wx'], q['wy']) for r in ('C69', 'R68', 'C60') for q in _P[r]['abs']}
    _c60 = _q['C60.1'] if _P['C60']['nets']['1'] == '5V' else _q['C60.2']
    tracks += [_seg('5V', 'B.Cu', _c60, (_c60[0], 20.6), 0.5), _seg('5V', 'B.Cu', (_c60[0], 20.6), (_q['R68.1'][0] + 0.6, 21.8), 0.5),
               _seg('5V', 'B.Cu', (_q['R68.1'][0] + 0.6, 21.8), _q['R68.1'], 0.5),
               _seg('5V_DAMP', 'B.Cu', _q['R68.2'], _q['C69.1'], 0.5)]
    _g = _q['C69.2']
    for _dy in (-0.6, 0.6):
        tracks += [_via('GND', _g[0] - 1.65, _g[1] + _dy), _seg('GND', 'B.Cu', (_g[0] - 1.65, _g[1] + _dy), (_g[0], _g[1] + _dy), 0.4)]
    R7C_LOG.append(f'C69 at (8.3, 22.4) B, R68 at (14.3, 22.4) B, 5V from C60 at {_c60}')

    # 5. TC358743 IR (B4), a Schmitt input with no pull (Toshiba p10), tied to its VSS neighbour C4 on B.Cu instead of floating
    _P['U7']['nets']['B4'] = 'GND'
    tracks.append(_seg('GND', 'B.Cu', ball('B4'), ball('C4'), 0.15))
    R7C_LOG.append('U7.B4 (IR) tied to U7.C4 (VSS)')

    # ---------- r7d (CSI option B): tools/r7d_stage.py, run here with this script's globals
    exec(open(os.path.join(HERE, 'tools', 'r7d_stage.py'), encoding='utf-8').read())
    # ---------- r7e (review of r7d, REVIEW_r7d.md m1/m2): tools/r7e_stage.py
    exec(open(os.path.join(HERE, 'tools', 'r7e_stage.py'), encoding='utf-8').read())
    # ---------- r7f (six approved changes, R7F_REPORT.md): tools/r7f_stage.py
    if os.environ.get('R7F_DUMP'):   # development only: tools/r7f_dev.py re-runs the r7f stage and the writers from this state
        import dill as _dill
        _dill.dump_module(os.environ['R7F_DUMP'])
    exec(open(os.path.join(HERE, 'tools', 'r7f_stage.py'), encoding='utf-8').read())

    padpos = {f"{p['ref']}.{q['n']}": (q['wx'], q['wy']) for p in parts for q in p['abs']}
    fps = [fp(p) for p in parts] + mh_fps(holes)
    for _l in R7C_LOG:
        print('r7c', _l)
# r7 item 5: the board's stackup is the ordered JLC06121H-3313, so the Gerber job file and any field solver read the same numbers.
# Thicknesses from the order (outer prepreg 3313 0.0994, core 0.35, inner prepreg 2116 0.1088, Cu 0.035 outer and 0.0152 inner, 1.1384 copper and
# dielectric). The dielectric constants are the ones tools/r6/s3_solver.py uses; they are not from a JLC document in this package.
STACK = [('F.Cu', 'copper', 0.035), ('dielectric 1', 'prepreg', 0.0994, '3313', 4.1), ('In1.Cu', 'copper', 0.0152), ('dielectric 2', 'core', 0.35, 'FR4', 4.6),
         ('In2.Cu', 'copper', 0.0152), ('dielectric 3', 'prepreg', 0.1088, '2116', 4.16), ('In3.Cu', 'copper', 0.0152), ('dielectric 4', 'core', 0.35, 'FR4', 4.6),
         ('In4.Cu', 'copper', 0.0152), ('dielectric 5', 'prepreg', 0.0994, '3313', 4.1), ('B.Cu', 'copper', 0.035)]
MASK_T = 0.01
STACK_T = sum(x[2] for x in STACK) + 2 * MASK_T
assert abs(sum(x[2] for x in STACK) - 1.1384) < 1e-6


def _sl(x):
    if x[1] == 'copper':
        return f'(layer "{x[0]}" (type "copper") (thickness {x[2]}))'
    return f'(layer "{x[0]}" (type "{x[1]}") (thickness {x[2]}) (material "{x[3]}") (epsilon_r {x[4]}) (loss_tangent 0.02))'


STACKUP = ('(stackup (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste")) (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01)) '
           + ' '.join(_sl(x) for x in STACK)
           + ' (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01)) (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen")) (copper_finish "ENIG") (dielectric_constraints no))')
head = f'''(kicad_pcb (version 20241229) (generator "p4mini") (generator_version "9.0")
  (general (thickness {STACK_T:.4f}) (legacy_teardrops no))
  (paper "A4")
  (layers (0 "F.Cu" signal) (4 "In1.Cu" power) (6 "In2.Cu" signal) (8 "In3.Cu" power) (10 "In4.Cu" power) (2 "B.Cu" signal)
    (9 "F.Adhes" user "F.Adhesive") (11 "B.Adhes" user "B.Adhesive") (13 "F.Paste" user) (15 "B.Paste" user)
    (5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen") (1 "F.Mask" user) (3 "B.Mask" user)
    (17 "Dwgs.User" user "User.Drawings") (19 "Cmts.User" user "User.Comments") (21 "Eco1.User" user "User.Eco1") (23 "Eco2.User" user "User.Eco2")
    (25 "Edge.Cuts" user) (27 "Margin" user) (31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard") (35 "F.Fab" user) (33 "B.Fab" user))
  (setup {STACKUP}
    (pad_to_mask_clearance 0) (allow_soldermask_bridges_in_footprints no))
  (net 0 "")
''' + ''.join(f'  (net {netid[n]} "{n}")\n' for n in nets)
BRAND, REV = 'MF KVM', 'R7F'


def silk_text(t, x, y, h, w, layer='F.SilkS', angle=0):
    mir = ' (justify mirror)' if layer.startswith('B') else ''
    return f'(gr_text "{t}" (at {x + OX:.2f} {y + OY:.2f} {angle}) (layer "{layer}") (uuid "{uid()}") (effects (font (size {h} {h}) (thickness {w})){mir}))'


silk = [silk_text('ANT', -15.4, 16.2, 0.8, 0.15, 'B.SilkS'), silk_text(BRAND, 1.55, -16.1, 1.0, 0.15, angle=90), silk_text(REV, 3.25, -16.1, 1.0, 0.15, angle=90),  # r7b: R67 took the lower half
        silk_text('1', 12.75, 17.6, 0.8, 0.15), silk_text('1', -1.2, 13.4, 0.8, 0.15, 'B.SilkS')]
# r7b M3: U1 outline, cut corner and pin-1 dot on F.SilkS for the person soldering the module by hand. Lines stay 0.15 mm clear of
# every top-side pad (pads are 1:1 mask openings, so this also clears the mask) and are dropped where shorter than 0.4 mm.
from shapely.geometry import LineString as _LS, Point as _Pt, box as _box
from shapely.ops import unary_union as _uu
_U1 = next(p for p in parts if p['ref'] == 'U1')
_keep = _uu([_box(q['wx'] - q['ww'] / 2, q['wy'] - q['wh'] / 2, q['wx'] + q['ww'] / 2, q['wy'] + q['wh'] / 2) for p in parts for q in p['abs']
             if p['side'] == 'F' or q['kind'] == 'thru_hole'] + [_Pt(x, y).buffer(1.1) for x, y in holes]).buffer(0.15 + 0.075)
_e, _c = 13.45, 1.5   # outline half size (pads reach 13.25 from the module centre) and the cut at pin 1's corner
_p1 = next(q for q in _U1['abs'] if q['n'] == '1')
_sx, _sy = (1 if _p1['wx'] > _U1['x'] else -1), (1 if _p1['wy'] > _U1['y'] else -1)   # pin 1's corner
_cx, _cy = _U1['x'], _U1['y']
_pts = [(-_e, -_e), (_e, -_e), (_e, _e), (-_e, _e)]
_ring = []
for _i, (_x, _y) in enumerate(_pts):
    if _x * _sx > 0 and _y * _sy > 0:   # pin 1's corner: cut it
        for _o in (_pts[_i - 1], _pts[(_i + 1) % 4]):
            _l = math.hypot(_o[0] - _x, _o[1] - _y)
            _ring.append((_x + _c * (_o[0] - _x) / _l, _y + _c * (_o[1] - _y) / _l))
    else:
        _ring.append((_x, _y))
_ring = [(_cx + x, _cy + y) for x, y in _ring]
_out = _LS(_ring + _ring[:1]).difference(_keep)
_n_u1 = 0
for _g in getattr(_out, 'geoms', [_out]):
    _cs = list(_g.coords)
    for _a, _b2 in zip(_cs, _cs[1:]):
        if math.hypot(_b2[0] - _a[0], _b2[1] - _a[1]) >= 0.4:
            silk.append(f'(gr_line (start {_a[0] + OX:.3f} {_a[1] + OY:.3f}) (end {_b2[0] + OX:.3f} {_b2[1] + OY:.3f}) (stroke (width 0.15) (type default)) (layer "F.SilkS") (uuid "{uid()}"))')
            _n_u1 += 1
_dot = (_cx + _sx * (_e + 0.55), _cy + _sy * (_e - 1.0))   # beside the cut corner, outside the outline, on pin 1's row
_d = 0.0
while _Pt(_dot).buffer(0.35).intersects(_keep) and _d < 3:
    _d += 0.1
    _dot = (_cx + _sx * (_e + 0.55), _cy + _sy * (_e - 1.0 - _d))
assert not _Pt(_dot).buffer(0.35).intersects(_keep), 'no room for the pin-1 dot'
silk.append(f'(gr_circle (center {_dot[0] + OX:.3f} {_dot[1] + OY:.3f}) (end {_dot[0] + 0.25 + OX:.3f} {_dot[1] + OY:.3f}) (stroke (width 0.2) (type default)) (fill yes) (layer "F.SilkS") (uuid "{uid()}"))')
print(f'r7b U1 silk: {_n_u1} outline pieces, pin 1 at ({_p1["wx"]:.2f}, {_p1["wy"]:.2f}), dot at ({_dot[0]:.2f}, {_dot[1]:.2f})')
for t, x, y in [('BOOT', -15.2, 15.5), ('EN', -13.6, 15.5), ('TX', -12.0, 15.5), ('RX', -10.4, 15.5), ('C6R', -7.9, 15.25), ('C6T', -8.76, 18.3), ('C6B', -6.55, 13.2), ('GND', -8.8, 12.45)]:
    silk.append(f'(gr_text "{t}" (at {x + OX:.2f} {y + OY:.2f}) (layer "B.SilkS") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08)) (justify mirror)))')
_kx0, _kx1, _ky0, _ky1 = J8X - 0.95 + OX, J8X + 0.95 + OX, J8Y - 1.1 + OY, J8Y + 1.0 + OY
keep_j8 = f'''(zone (net 0) (net_name "") (layer "B.Cu") (uuid "{uid()}") (name "J8 no conductive traces") (hatch edge 0.5)
    (connect_pads (clearance 0)) (min_thickness 0.13) (filled_areas_thickness no)
    (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))
    (fill (thermal_gap 0.2) (thermal_bridge_width 0.25))
    (polygon (pts (xy {_kx0:.3f} {_ky0:.3f}) (xy {_kx1:.3f} {_ky0:.3f}) (xy {_kx1:.3f} {_ky1:.3f}) (xy {_kx0:.3f} {_ky1:.3f})))
  )'''
if R7C:   # C69 polarity: "+" on the bottom silk beside pin 1, 0.2 mm clear of its pad and of U12
    _p1 = next(q for q in _P['C69']['abs'] if q['n'] == '1')
    silk.append(f'(gr_text "+" (at {_p1["wx"] + OX:.2f} {_p1["wy"] - 1.95 + OY:.2f}) (layer "B.SilkS") (uuid "{uid()}") (effects (font (size 1.0 1.0) (thickness 0.15)) (justify mirror)))')
body = fps + edges + tracks + [zone('GND', 'In1.Cu'), zone('3V3', 'In3.Cu'), zone('GND', 'In4.Cu'), zone('GND', 'F.Cu'), zone('GND', 'B.Cu'), keep_j8] + silk
open(f'{OUT}/{NAME}.kicad_pcb', 'w', encoding='utf-8', newline='\n').write(head + '  ' + '\n  '.join(body) + '\n)\n')

# ---------- schematic: one symbol per part, every pin carries its net as a global label.
# r7c: pin electrical types come from data/pin_types.json (tools/schgen.py); r7b and earlier wrote every pin as passive, so ERC checked nothing.
sys.path.insert(0, os.path.join(HERE, 'tools'))
import schgen
_flags = schgen.write(parts, OUT, NAME)
for _n, _path in _flags.items():
    print('PWR_FLAG', _n, '<-', ' / '.join(_path) if _path else 'NO SOURCE FOUND, no flag (ERC will report the power pins)')
open(f'{OUT}/sym-lib-table', 'w', newline='\n').write('(sym_lib_table (version 7) (lib (name "mini") (type "KiCad") (uri "${KIPRJMOD}/mini.kicad_sym") (options "") (descr "")))\n')
open(f'{OUT}/fp-lib-table', 'w', newline='\n').write('(fp_lib_table (version 7) (lib (name "mini") (type "KiCad") (uri "${KIPRJMOD}/mini.pretty") (options "") (descr "")))\n')
os.makedirs(f'{OUT}/mini.pretty', exist_ok=True)
seen = set()
for p in parts:
    if p['lib'] in seen:
        continue
    seen.add(p['lib'])
    t = fp(dict(p, nets={}))
    t = re.sub(r'\(at [-\d.]+ [-\d.]+\)\n', '\n', t, count=1)
    t = re.sub(r'\(path "[^"]*"\) \(sheetname "/"\) \(sheetfile "[^"]*"\)\n', '', t)
    t = t.replace(f'"mini:{p["lib"]}"', f'"{p["lib"]}" (version 20241229) (generator "p4mini") (generator_version "9.0")', 1)
    t = re.sub(r'\(property "Reference" "[^"]*"', '(property "Reference" "REF**"', t, count=1)
    open(f'{OUT}/mini.pretty/{p["lib"]}.kicad_mod', 'w', encoding='utf-8', newline='\n').write(t + '\n')
rules = dict(min_clearance=0.09, min_track_width=0.09, min_via_diameter=0.35, min_via_annular_width=0.075, min_through_hole_diameter=0.15, min_hole_to_hole=0.2, min_hole_clearance=0.2, min_copper_edge_clearance=0.2, min_silk_clearance=0, min_text_height=0.5, min_text_thickness=0.08, solder_mask_clearance=0, min_connection=0.09)
pro = {'board': {'design_settings': {'rules': rules, 'defaults': {}, 'rule_severities': {'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore', 'silk_over_copper': 'ignore', 'silk_overlap': 'ignore', 'silk_edge_clearance': 'ignore', 'courtyards_overlap': 'warning', 'solder_mask_bridge': 'error', 'hole_to_hole': 'error', 'starved_thermal': 'warning', 'text_height': 'ignore', 'text_thickness': 'ignore'}}},
       'net_settings': {'classes': [{'name': 'Default', 'clearance': 0.1, 'track_width': W_DEFAULT, 'via_diameter': 0.4, 'via_drill': 0.2, 'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.127, 'diff_pair_gap': 0.198, 'wire_width': 6, 'bus_width': 12, 'line_style': 0, 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'pcb_color': 'rgba(0, 0, 0, 0.000)', 'priority': 2147483647}], 'meta': {'version': 4}},
       'erc': schgen.ERC_SETTINGS,
       'meta': {'filename': f'{NAME}.kicad_pro', 'version': 3}}
json.dump(pro, open(f'{OUT}/{NAME}.kicad_pro', 'w'), indent=1)
# r6: nothing runs beside the antenna line. Pours keep this gap too, which is the gap its width was solved for.
open(f'{OUT}/{NAME}.kicad_dru', 'w', newline='\n').write('(version 1)\n(rule "LNA_OUT clearance"\n  (layer outer)\n  (condition "A.NetName == \'LNA_OUT\'")\n  (constraint clearance (min 0.25mm)))\n'
                                                     # r7c: JLC "Pad hole-to-hole spacing 0.45mm", applied to a pad hole (PTH, slot, NPTH) against any hole, vias included.
                                                     # Via to via stays at the board rule, 0.2 mm (JLC "Via-to-via hole spacing").
                                                     '(rule "component hole to any hole"\n  (condition "A.Type == \'Pad\' || B.Type == \'Pad\'")\n  (constraint hole_to_hole (min 0.45mm)))\n')
json.dump({'parts': [{k: p[k] for k in ('ref', 'value', 'lcsc', 'lib', 'x', 'y', 'r', 'side', 'dnp', 'consign', 'nets')} | {'bbox': bbox(p)} for p in parts], 'padpos': padpos, 'nets': real_nets, 'board': {'x0': -H, 'x1': H, 'y0': -H, 'y1': YB, 'holes': holes}}, open(f'{OUT}/design.json', 'w', encoding='utf-8'), indent=0)


# ---------- Specctra DSN for Freerouting
def um(v):
    return round(v * 1000)


def dsn_name(n):
    return n if re.fullmatch(r'[A-Za-z0-9_.\-]+', n) else '"' + n + '"'


stacks, images, places = {}, [], []
for p in parts:
    pins = []
    for q in p['abs']:
        dx, dy = q['wx'] - p['x'], -(q['wy'] - p['y'])
        if p['side'] == 'B':
            dx = -dx  # the DSN "back" placement mirrors the image back
        kind = q['kind'] == 'thru_hole'
        key = ('T' if kind else 'S') + ('C' if q['shape'] == 'circle' else 'R') + f"{um(q['ww'])}x{um(q['wh'])}"
        stacks[key] = (kind, q['shape'] == 'circle', q['ww'], q['wh'])
        pins.append(f'(pin {key} "{q["n"]}" {um(dx)} {um(dy)})')
    images.append(f'(image IM_{p["ref"]} {" ".join(pins)})')
    places.append(f'(component IM_{p["ref"]} (place {p["ref"]} {um(p["x"])} {um(-p["y"])} {"front" if p["side"] == "F" else "back"} 0))')


def stack_shape(key, v):
    kind, circ, w, h = v
    ws, hs = um(w), um(h)
    layers = ['signal'] if kind else ['F.Cu']
    if kind:
        return f'(padstack {key} ' + ' '.join(f'(shape (rect {ly} {-ws // 2} {-hs // 2} {ws // 2} {hs // 2}))' for ly in ('F.Cu', 'In2.Cu', 'B.Cu')) + ' (attach off))'
    if circ:
        return f'(padstack {key} (shape (circle F.Cu {ws})) (attach off))'
    return f'(padstack {key} (shape (rect F.Cu {-ws // 2} {-hs // 2} {ws // 2} {hs // 2})) (attach off))'


pad_txt = ' '.join(stack_shape(k, v) for k, v in stacks.items())
via_txt = ' '.join(f'(padstack {name} ' + ' '.join(f'(shape (circle {ly} {d}))' for ly in ('F.Cu', 'In2.Cu', 'B.Cu')) + ' (attach off))' for name, d in (('Via400', 400), ('ViaP600', 500)))
netlist = []
for n in real_nets:
    if n in PLANE or n in HS_NETS:
        continue
    pins = ' '.join(f'{p["ref"]}-"{q}"' for p in parts for q, m in p['nets'].items() if m == n)
    netlist.append(f'(net {dsn_name(n)} (pins {pins}))')
power_vias = {'5V', '3V3', 'SW', 'V2V5', 'V1V2', 'SD1_VDD', 'SD_SRC', 'LDO_VO4', 'GND'}
classes = []
# r7: what the router uses for the connections it still has to make. V1V2 now runs from the top-side buck to the beads, so it is wider;
# the only 5V connection left to make is U6.5 (EN), which takes a 0.2 mm line between the MSOP pins. Existing copper keeps its own widths.
W_DSN = dict(W_POWER, V1V2=0.3, **{'5V': 0.2})
for name, w, cvia, members in [(f'P{int(w * 1000)}', w, 'ViaP600' if w >= 0.3 else 'Via400', [n for n, v in W_DSN.items() if v == w]) for w in sorted(set(W_DSN.values()))]:
    classes.append(f'(class {name} {" ".join(dsn_name(m) for m in members)} (circuit (use_via {cvia})) (rule (width {um(w)}) (clearance {um(0.1)})))')
others = [n for n in real_nets if n not in W_POWER and n not in PLANE and n not in HS_NETS]
classes.append(f'(class SIG {" ".join(dsn_name(m) for m in others)} (circuit (use_via Via400)) (rule (width {um(W_DEFAULT)}) (clearance {um(0.1)})))')
area = f'{um(-H - 0.0)} {um(-H)} {um(H)} {um(-H)} {um(H)} {um(H)} {um(-H)} {um(H)} {um(-H)} {um(-H)}'
outline_pts = ' '.join(f'{um(x)} {um(-y)}' for x, y in outline + outline[:1])
keepout = ' '.join(f'(keepout "hole{i}" (circle signal {um(2.6)} {um(x)} {um(-y)}))' for i, (x, y) in enumerate(holes))
fixed = ' '.join(f'(keepout "pv{i}" (circle signal {um(VIA_D)} {um(x)} {um(-y)}))' for i, (x, y, _) in enumerate(fixed_vias))
fixed += ' ' + ' '.join(f'(keepout "ps{i}" (path {st[4]}.Cu {um(st[6])} {um(st[0])} {um(-st[1])} {um(st[2])} {um(-st[3])}))' for i, st in enumerate(fixed_stubs))
# r7: R7_KO="layer:x0,y0,x1,y1;..." adds router keepouts for one routing pass (design mm), used to keep the V1V2 sense line away from Y1, USB and the I/O edge
for _i, _k in enumerate(filter(None, os.environ.get('R7_KO', '').split(';'))):
    _ly, _r = _k.split(':')
    _x0, _y0, _x1, _y1 = map(float, _r.split(','))
    fixed += f' (keepout "r7ko{_i}" (rect {_ly}.Cu {um(_x0)} {um(-_y1)} {um(_x1)} {um(-_y0)}))'
prewire = ' '.join(f'(wire (path {side}.Cu {um(RAIL_W)} ' + ' '.join(f'{um(x)} {um(-y)}' for x, y in pts) + f') (net {net}) (type protect))' for net, side, pts in rail_wires)
prewire += ' ' + ' '.join(f'(via Via400 {um(x)} {um(-y)} (net {net}) (type protect))' for net, x, y in rail_vias)
prewire += ' ' + ' '.join(f'(wire (path F.Cu {um(0.4)} ' + ' '.join(f'{um(x)} {um(-y)}' for x, y in pts) + ') (net 5V) (type protect))' for pts in (five, [(10.56, 4.9), (10.56, 6.4)], [(10.56, 6.4), (10.56, 6.95)]))
prewire += f' (wire (path In2.Cu {um(0.4)} {um(10.56)} {um(-6.4)} {um(10.56)} {um(-6.95)}) (net 5V) (type protect)) (via Via400 {um(10.56)} {um(-6.95)} (net 5V) (type protect))'
prewire += f' (via Via400 {um(10.56)} {um(-6.4)} (net 5V) (type protect))'
# r7: with R7_KEEP=<previous SES>, that routing (which already holds every prewire above) is handed to the router as protected wiring,
# less what r7 has to re-route, so the router only adds r7's connections and nothing else moves
R7_KEEP = os.environ.get('R7_KEEP')
R7_DROP_BOX = [({'DDC_SDA'}, (-9.4, -5.1, -8.8, -2.3)), ({'HDMI_5V'}, (1.5, -10.2, 4.2, -5.5))]  # (nets, (x0, y0, x1, y1)): kept copper handed back to the router
R7_DROP_NETS = set(filter(None, os.environ.get('R7_DROP_NETS', '').split(',')))      # whole nets handed back to the router
if R7_KEEP and not SES:
    _names = {v: k for k, v in netid.items()}

    def _dropped(t):
        m = SEG_RE.match(t)
        if m:
            net, ends = _names[int(m[7])], [(float(m[1]) - OX, float(m[2]) - OY), (float(m[3]) - OX, float(m[4]) - OY)]
        else:
            m = VIA_RE.match(t)
            net, ends = _names[int(m[4])], [(float(m[1]) - OX, float(m[2]) - OY)]
        return net in R7_DROP_NETS or any(net in nets_ and any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for x, y in ends) for nets_, b in R7_DROP_BOX)

    if R7_KEEP.endswith('.kicad_pcb'):
        # a saved board holds everything, including the In2 joins finish_open() added on import, which the SES does not
        _b = open(R7_KEEP, encoding='utf-8').read()
        _old = []
        for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', _b):
            if m[7] in netid and m[7] not in PLANE and m[7] not in HS_NETS:
                _old.append(f'(segment (start {m[1]} {m[2]}) (end {m[3]} {m[4]}) (width {m[5]}) (layer "{m[6]}") (net {netid[m[7]]}) (uuid "{uid()}"))')
        for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)\s+\(drill ([\d.]+)\)(?:(?!\(via|\(segment).)*?\(net "([^"]+)"\)', _b, re.S):
            if m[5] in netid and m[5] not in PLANE and m[5] not in HS_NETS:
                _old.append(f'(via (at {m[1]} {m[2]}) (size {m[3]}) (drill {m[4]}) (layers "F.Cu" "B.Cu") (net {netid[m[5]]}) (uuid "{uid()}"))')
    else:
        _old = ses_items(R7_KEEP, skip_unknown=True)
    # R7_KEEP2=<board>:<net,net>: those nets come from a later board instead (the r7 routes the router made in an earlier pass)
    if os.environ.get('R7_KEEP2'):
        _p2, _n2 = os.environ['R7_KEEP2'].rsplit(':', 1)
        _n2 = set(_n2.split(','))
        _b = open(_p2, encoding='utf-8').read()
        # copper that is already in the first board (to 2 um) keeps the first board's exact coordinates; only the rest is taken from the later one
        _s1, _v1 = parse_copper(_old)
        _near = lambda a, b: abs(a[0] - b[0]) < 0.002 and abs(a[1] - b[1]) < 0.002
        for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', _b):
            if m[7] in _n2:
                a_, b_ = (float(m[1]) - OX, float(m[2]) - OY), (float(m[3]) - OX, float(m[4]) - OY)
                if not any(g[6] == netid[m[7]] and g[5] == m[6] and ((_near(a_, g[:2]) and _near(b_, g[2:4])) or (_near(b_, g[:2]) and _near(a_, g[2:4]))) for g in _s1):
                    _old.append(f'(segment (start {m[1]} {m[2]}) (end {m[3]} {m[4]}) (width {m[5]}) (layer "{m[6]}") (net {netid[m[7]]}) (uuid "{uid()}"))')
        for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)\s+\(drill ([\d.]+)\)(?:(?!\(via|\(segment).)*?\(net "([^"]+)"\)', _b, re.S):
            if m[5] in _n2 and not any(v[3] == netid[m[5]] and _near((float(m[1]) - OX, float(m[2]) - OY), v[:2]) for v in _v1):
                _old.append(f'(via (at {m[1]} {m[2]}) (size {m[3]}) (drill {m[4]}) (layers "F.Cu" "B.Cu") (net {netid[m[5]]}) (uuid "{uid()}"))')
    # r7b M5: the H2 end of HDMI_5V becomes HPDI, and both ends meet R67 through two vias
    _seg = lambda net, ly, a, b, w: f'(segment (start {a[0] + OX:.4f} {a[1] + OY:.4f}) (end {b[0] + OX:.4f} {b[1] + OY:.4f}) (width {w}) (layer "{ly}") (net {netid[net]}) (uuid "{uid()}"))'
    _via = lambda net, x, y: f'(via (at {x + OX:.4f} {y + OY:.4f}) (size 0.4) (drill 0.2) (layers "F.Cu" "B.Cu") (net {netid[net]}) (uuid "{uid()}"))'
    _ren = []
    for t in _old:
        m = SEG_RE.match(t) or VIA_RE.match(t)
        nid = int(m[7] if SEG_RE.match(t) else m[4])
        pts = [(float(m[1]) - OX, float(m[2]) - OY)] + ([(float(m[3]) - OX, float(m[4]) - OY)] if SEG_RE.match(t) else [])
        if _names[nid] == 'HDMI_5V' and all(1.5 <= x <= 4.2 and -10.2 <= y <= -5.5 for x, y in pts):
            t = t.replace(f'(net {nid})', f'(net {netid["HPDI"]})')
        _ren.append(t)
    _old = _ren + [_seg('HDMI_5V', 'In2.Cu', (0.038, -11.916), (0.55, -12.5), 0.2), _via('HDMI_5V', 0.55, -12.5), _seg('HDMI_5V', 'F.Cu', (0.55, -12.5), (1.12, -12.5), 0.2),
                   _seg('HPDI', 'F.Cu', (2.08, -12.5), (2.65, -12.5), 0.2), _via('HPDI', 2.65, -12.5),
                   _seg('HPDI', 'In2.Cu', (2.65, -12.5), (1.877, -11.727), 0.2), _seg('HPDI', 'In2.Cu', (1.877, -11.727), (1.877, -10.077), 0.2)]
    _kept = prune([t for t in _old if not _dropped(t)])
    print('r7 keep: SES items', len(_old), 'kept after drops and pruning', len(_kept))
    _ks, _kv = parse_copper(_kept)
    _u = lambda v: f'{v * 1000:.1f}'  # 0.1 um, the DSN resolution, so kept copper comes back from the router unchanged
    prewire = ' '.join(f'(wire (path {ly} {_u(w)} {_u(x0)} {_u(-y0)} {_u(x1)} {_u(-y1)}) (net {dsn_name(_names[n])}) (type protect))' for x0, y0, x1, y1, w, ly, n in _ks)
    prewire += ' ' + ' '.join(f'(via {"ViaP600" if sz >= 0.5 else "Via400"} {_u(x)} {_u(-y)} (net {dsn_name(_names[n])}) (type protect))' for x, y, sz, n in _kv)
    _have = {(_names[n], ly, round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)) for x0, y0, x1, y1, w, ly, n in _ks}
    _have |= {(k[0], k[1], k[4], k[5], k[2], k[3]) for k in _have}
    _rw = [(net, side, [a_, b_], w) for net, side, pts, w in R7_RAILW for a_, b_ in zip(pts, pts[1:])
           if (net, side + '.Cu', round(a_[0], 3), round(a_[1], 3), round(b_[0], 3), round(b_[1], 3)) not in _have]
    prewire += ' ' + ' '.join(f'(wire (path {side}.Cu {um(w)} ' + ' '.join(f'{um(x)} {um(-y)}' for x, y in pts) + f') (net {net}) (type protect))' for net, side, pts, w in _rw)
    prewire += ' ' + ' '.join(f'(via Via400 {um(x)} {um(-y)} (net {net}) (type protect))' for net, x, y in R7_RAILV)
# r7d: R7D_DSN=1 with an SES: the board as it stands after the r7d stage goes to the router. Signal copper is protected wiring,
# plane and high-speed copper are keepouts, so the router only makes the connections the r7d stage handed back.
if SES and os.environ.get('R7D_DSN'):
    _ks, _kv = parse_copper(tracks)
    _u = lambda v: f'{v * 1000:.1f}'
    _sig = lambda n: _names[n] not in PLANE and _names[n] not in HS_NETS
    _dly = ('F.Cu', 'In2.Cu', 'B.Cu')
    prewire = ' '.join(f'(wire (path {ly} {_u(w)} {_u(x0)} {_u(-y0)} {_u(x1)} {_u(-y1)}) (net {dsn_name(_names[n])}) (type protect))' for x0, y0, x1, y1, w, ly, n in _ks if _sig(n) and ly in _dly)
    prewire += ' ' + ' '.join(f'(via {"ViaP600" if sz >= 0.5 else "Via400"} {_u(x)} {_u(-y)} (net {dsn_name(_names[n])}) (type protect))' for x, y, sz, n in _kv if _sig(n))
    fixed = ' '.join(f'(keepout "rv{i}" (circle signal {_u(sz)} {_u(x)} {_u(-y)}))' for i, (x, y, sz, n) in enumerate(_kv) if not _sig(n))
    fixed += ' ' + ' '.join(f'(keepout "rs{i}" (path {ly} {_u(w)} {_u(x0)} {_u(-y0)} {_u(x1)} {_u(-y1)}))' for i, (x0, y0, x1, y1, w, ly, n) in enumerate(_ks) if not _sig(n) and ly in _dly)
    outline_pts = ' '.join(f'{um(x)} {um(-y)}' for x, y in outline + outline[:1])
    keepout = ' '.join(f'(keepout "hole{i}" (circle signal {um(2.6)} {um(x)} {um(-y)}))' for i, (x, y) in enumerate(holes))
dsn = f'''(pcb {NAME}.dsn
  (parser (string_quote ") (space_in_quoted_tokens on) (host_cad "KiCad") (host_version "9"))
  (resolution um 10)
  (unit um)
  (structure
    (layer F.Cu (type signal) (property (index 0)))
    (layer In2.Cu (type signal) (property (index 1)))
    (layer B.Cu (type signal) (property (index 2)))
    (boundary (path pcb 0 {outline_pts}))
    {keepout}
    {fixed}
    (via Via400 ViaP600)
    (rule (width {um(W_DEFAULT)}) (clearance {um(0.1)}) (clearance {um(0.1)} (type wire_pin)) (clearance {um(0.1)} (type smd_via_same_net)) (clearance {um(0.15)} (type wire_area)))
  )
  (placement {' '.join(places)})
  (library {' '.join(images)} {pad_txt} {via_txt})
  (network {' '.join(netlist)} {' '.join(classes)})
  (wiring {prewire})
)
'''
open(f'{OUT}/{NAME}.dsn', 'w', encoding='utf-8', newline='\n').write(dsn)
print('parts', len(parts), 'nets', len(real_nets), 'pads', sum(len(p['abs']) for p in parts), 'pre', pre_count, 'total items', len(tracks), 'routed vias', nvia)

# footprint overlap check, same side
bad = []
for i, a in enumerate(parts):
    A = bbox(a)
    for b in parts[i + 1:]:
        if a['side'] != b['side']:
            continue
        B = bbox(b)
        if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
            bad.append((a['ref'], b['ref'], round(min(A[2], B[2]) - max(A[0], B[0]), 2), round(min(A[3], B[3]) - max(A[1], B[1]), 2)))
    if max(abs(A[0]), abs(A[2])) > H + 1.3 or A[1] < -H - 1.3 or A[3] > YB + 1.3:
        bad.append((a['ref'], 'outside', A))
    for c in holes:
        dx = max(A[0] - c[0], 0, c[0] - A[2])
        dy = max(A[1] - c[1], 0, c[1] - A[3])
        if (dx * dx + dy * dy) ** 0.5 < 1.5:
            bad.append((a['ref'], 'hole', c))
print('placement problems', len(bad))
for b in bad:
    print(' ', b)
