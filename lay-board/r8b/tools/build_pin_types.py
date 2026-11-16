# -*- coding: utf-8 -*-
"""Writes data/pin_types.json: the electrical type of every pin of every part on the board, and the datasheet limits
verify.py applies to them. Each entry names its document and page. Run once by hand; the JSON is the reviewed artifact.

Pin types are KiCad's: power_in, power_out, input, output, bidirectional, tri_state, passive, free (datasheet says
"no internal connection": may be left open or routed through), no_connect (datasheet says do not connect),
open_collector, open_emitter.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data', 'pin_types.json')

WS = 'Waveshare wiki ESP32-P4-Module, "Pinout Description" text table, https://www.waveshare.com/wiki/ESP32-P4-Module oldid=108255, read 2026-11-08'
TOSH = 'Toshiba TC358743XBG datasheet 2014-05-16'
TCA = 'TI TCA9517A SCPS245E (rev. Oct 2025)'
SY = 'Silergy AN_SY8089/A Rev 0.9A'
TLV = 'TI TLV733P SBVS235C'
TPD = 'TI TPDxE05U06 SLVSBO7O (Aug 2024), datasheets_r7/tpd4e05u06_slvsbo7o.pdf'
YXC = 'YXC YSO110TR (LCSC C725995) datasheet, datasheets_r7/dl/C725995_ds.pdf'
AOS = 'AOS AO3401A Rev 3.1'
EVL = 'Everlight EL3H7-G DPC-0000031 rev 7'
P4 = 'Espressif ESP32-P4 datasheet v0.7'

kinds = {}

# ---------- U1 ESP32-P4-Module (Waveshare). Names from the wiki table, types from what the pin is.
names = {1: 'GND', 2: 'LNA_OUT', 3: 'GND', 4: 'C6_U0RXD', 5: 'C6_U0TXD', 6: 'C6_IO15', 7: 'C6_IO14', 8: 'C6_IO13', 9: 'C6_IO9', 10: 'C6_IO8',
         11: 'C6_IO7', 12: 'C6_IO6', 13: 'C6_IO5', 14: 'C6_IO4', 15: 'GND', 16: 'GPIO1', 17: 'GPIO2', 18: 'GPIO3', 19: 'GPIO4', 20: 'GPIO5', 21: 'GPIO6',
         22: 'GPIO7', 23: 'GPIO8', 24: 'GPIO9', 25: 'GPIO10', 26: 'GPIO11', 27: 'GPIO12', 28: 'GPIO13', 29: 'GPIO20', 30: 'GPIO21', 31: 'GPIO22', 32: 'GPIO23',
         33: 'GND', 34: 'DSI_DATAP1', 35: 'DSI_DATAN1', 36: 'DSI_CLKN', 37: 'DSI_CLKP', 38: 'DSI_DATAP0', 39: 'DSI_DATAN0', 40: 'GND',
         41: 'CSI_DATAN0', 42: 'CSI_DATAP0', 43: 'CSI_CLKP', 44: 'CSI_CLKN', 45: 'CSI_DATAN1', 46: 'CSI_DATAP1', 47: 'GND', 48: 'USB_DM', 49: 'USB_DP',
         50: 'GPIO24', 51: 'GPIO25', 52: 'GND', 66: 'ESP_LDO_VO4', 83: 'GND', 84: 'VBAT', 85: 'ESP_3V3', 86: 'ESP_3V3', 87: 'ESP_EN', 88: 'GPIO0'}
for n, g in zip(range(53, 66), range(26, 39)):
    names[n] = f'GPIO{g}'
for n, g in zip(range(67, 83), range(39, 55)):
    names[n] = f'GPIO{g}'
assert sorted(names) == list(range(1, 89))
pins = {}
for n, nm in names.items():
    if nm == 'GND':
        t, why = 'power_in', 'ground'
    elif nm in ('VBAT', 'ESP_3V3'):
        t, why = 'power_in', 'supply input, "recommended to connect 3.3V"'
    elif nm == 'ESP_LDO_VO4':
        t, why = 'power_out', '"ESP32-P4 internal LDO output pin"'
    elif nm == 'ESP_EN':
        t, why = 'input', 'CHIP_PU, "enable pin, default pulled high" (P4 datasheet v0.7 p34: do not leave floating)'
    elif nm == 'LNA_OUT':
        t, why = 'passive', 'RF antenna pin of the ESP32-C6 (50 ohm line, no logic level)'
    elif nm.startswith('CSI_'):
        t, why = 'input', 'MIPI-CSI receiver lane of the P4'
    elif nm.startswith('DSI_'):
        t, why = 'output', 'MIPI-DSI transmitter lane of the P4'
    else:
        t, why = 'bidirectional', 'GPIO (any direction via the IO matrix); USB_DM/DP and C6 UART pins are bidirectional too'
    pins[str(n)] = [nm, t, why]
kinds['ESP32-P4-Module'] = dict(match={'lib': 'ESP32-P4-Module'}, doc=WS, pins=pins)

# ---------- U7 TC358743XBG. Ball names transcribed from Fig. 3.1 (p12); I/O column from Table 3.1 (p10-11).
balls = '''A1 REXT A2 VSS A3 VPGM A4 BIASDA A5 DAOUT A6 PFIL A7 CSID3N A8 CSID3P
B1 AVDD33 B2 AVDD12 B3 INT B4 IR B5 AVDD25 B6 PCKIN B7 CSID2N B8 CSID2P
C1 HDMICP C2 HDMICN C3 VDDC2 C4 VSS C5 VSS C6 VDD_MIPI C7 CSICN C8 CSICP
D1 HDMID0P D2 HDMID0N D3 AVDD12 D4 VSS D5 VSS D6 VSS D7 CSID1N D8 CSID1P
E1 HDMID1P E2 HDMID1N E3 VSS E4 VSS E5 TEST E6 VSS E7 CSID0N E8 CSID0P
F1 HDMID2P F2 HDMID2N F3 AVDD33 F4 VDDIO1 F5 VDDC2 F6 VDD_MIPI F7 A_SCK F8 A_SD
G1 CEC G2 VDDC1 G3 DDC_SDA G4 I2C_SDA G5 RESETN G6 EDID_SDA G7 A_WFS G8 A_OSCK
H1 HPDO H2 HPDI H3 DDC_SCL H4 I2C_SCL H5 REFCLK H6 EDID_SCL H7 VDDIO2 H8 VSS'''.split()
balls = dict(zip(balls[0::2], balls[1::2]))
assert len(balls) == 64


def tc_type(nm):
    if nm in ('VSS', 'VPGM') or nm.startswith(('VDD', 'AVDD')):
        return 'power_in', 'supply / ground (p10 POWER, Ground; p11 VPGM "tie to ground")'
    if nm == 'REXT':
        return 'passive', 'external 2k reference resistor to AVDD33 (p11)'
    if nm.startswith('CSI'):
        return 'output', 'CSI-2 TX lane (p10)'
    if nm.startswith('HDMI'):
        return 'input', 'HDMI RX PHY (p10)'
    if nm in ('RESETN', 'REFCLK', 'TEST', 'HPDI', 'IR', 'PCKIN'):
        return 'input', 'I/O column "I" (p10)'
    if nm in ('INT', 'HPDO', 'A_SCK', 'A_WFS', 'A_SD', 'A_OSCK', 'BIASDA', 'DAOUT', 'PFIL'):
        return 'output', 'I/O column "O" (p10)'
    if nm in ('DDC_SDA', 'DDC_SCL', 'EDID_SDA', 'EDID_SCL', 'CEC', 'I2C_SDA', 'I2C_SCL'):
        return 'bidirectional', 'I/O column "IO", Schmitt (p10, p11 Note2)'
    raise ValueError(nm)


kinds['TC358743XBG'] = dict(match={'lcsc': 'C3008606'}, doc=f'{TOSH} p12 Fig. 3.1 (ball), p10-11 Table 3.1 (I/O)',
                            pins={b: [nm, *tc_type(nm)] for b, nm in balls.items()})

kinds['TCA9517A'] = dict(match={'lcsc': 'C201698'}, doc=f'{TCA} p4 Table 4-1', pins={
    '1': ['VCCA', 'power_in', 'Supply'], '2': ['SCLA', 'bidirectional', 'Input/Output'], '3': ['SDAA', 'bidirectional', 'Input/Output'],
    '4': ['GND', 'power_in', 'Ground'], '5': ['EN', 'input', 'Input'], '6': ['SDAB', 'bidirectional', 'Input/Output'],
    '7': ['SCLB', 'bidirectional', 'Input/Output'], '8': ['VCCB', 'power_in', 'Supply']})
kinds['SY8089'] = dict(match={'lcsc': 'C78988'}, doc=f'{SY} p2 Pin Description', pins={
    '1': ['EN', 'input', 'Enable control, do not float'], '2': ['GND', 'power_in', 'Ground'], '3': ['LX', 'power_out', 'switching node to the inductor'],
    '4': ['IN', 'power_in', 'Input'], '5': ['FB', 'input', 'Output feedback, divider centre']})
kinds['TLV73325'] = dict(match={'lcsc': 'C882825'}, doc=f'{TLV} p4 Pin Functions, DBV', pins={
    '1': ['IN', 'power_in', 'I'], '2': ['GND', 'power_in', 'ground'], '3': ['EN', 'input', 'I'],
    '4': ['NC', 'free', '"No internal connection"'], '5': ['OUT', 'power_out', 'O, regulated output']})
kinds['TPD4E05U06'] = dict(match={'lcsc': 'C138714'}, doc=f'{TPD} p4 Table 4-2 (DQA)', pins={
    '1': ['D1+', 'passive', 'I/O ESD channel: a clamp, it never drives'], '2': ['D1-', 'passive', 'I/O ESD channel'], '3': ['GND', 'power_in', 'Ground'],
    '4': ['D2+', 'passive', 'I/O ESD channel'], '5': ['D2-', 'passive', 'I/O ESD channel'],
    '6': ['NC', 'free', '"Not connected; used for optional straight-through routing. Can be left floating or grounded"'],
    '7': ['NC', 'free', 'as pin 6'], '8': ['GND', 'power_in', 'Ground'], '9': ['NC', 'free', 'as pin 6'], '10': ['NC', 'free', 'as pin 6']})
# r7f: 5 V input eFuse and CEC ESD diode
EFU = 'TI TPS2595xx SLVSE57C (Apr 2018), datasheets_r7f/tps2595.pdf'
kinds['TPS259531'] = dict(match={'lcsc': 'C2155674'}, doc=f'{EFU} p4 Pin Functions (TPS2595x0/1, DSG)', pins={
    '1': ['dVdt', 'passive', 'capacitor to GND sets the output slew rate (analog I/O)'], '2': ['EN/UVLO', 'input', 'active-high enable, divider sets UVLO, "Do not leave floating"'],
    '3': ['IN', 'power_in', 'power input'], '4': ['IN', 'power_in', 'power input'], '5': ['OUT', 'power_out', 'power output'],
    '6': ['FLT', 'open_collector', 'open-drain fault output, needs an external pull-up'], '7': ['ILM', 'passive', 'resistor to GND sets the current limit (analog I/O), "Do not leave floating"'],
    '8': ['GND', 'power_in', 'ground'], '9': ['PAD', 'power_in', 'exposed pad, "must be connected to GND"']})
kinds['TPD1E10B06'] = dict(match={'lcsc': 'C48260'}, doc='TI TPD1E10B06 SLLSEB1G (Aug 2024), datasheets_r7f/tpd1e10b06.pdf p3 (bidirectional, pins interchangeable)', pins={
    '1': ['IO', 'passive', 'ESD clamp terminal, never drives'], '2': ['IO', 'passive', 'ESD clamp terminal (to GND here)']})
kinds['YSO110TR'] = dict(match={'lcsc': 'C725995'}, doc=f'{YXC} p1 (pin function, image)', pins={
    '1': ['OE', 'input', 'tri-state control: high (70% VDD) or floating = output on'], '2': ['GND', 'power_in', 'ground'],
    '3': ['OUT', 'tri_state', 'clock output, high impedance when OE low'], '4': ['VDD', 'power_in', 'supply']})
kinds['AO3401A'] = dict(match={'lcsc': 'C15127'}, doc=f'{AOS} p1 pin configuration (SOT-23: 1 G, 2 S, 3 D)', pins={
    '1': ['G', 'input', 'gate'], '2': ['S', 'passive', 'source: channel terminal'], '3': ['D', 'passive', 'drain: channel terminal']})
kinds['EL3H7'] = dict(match={'lcsc': 'C92243'}, doc=f'{EVL} p1 pin configuration (as checked in the 2026-11-07 pinout audit; p1 not re-read for r7c)', pins={
    '1': ['A', 'passive', 'LED anode'], '2': ['K', 'passive', 'LED cathode'], '3': ['E', 'passive', 'phototransistor emitter'],
    '4': ['C', 'passive', 'phototransistor collector']},
    note='Discrete diode and bipolar terminals: they neither drive nor sense a logic level by themselves, so passive is the true type.')
CONN = 'connector contact: a wire, no driver of its own'
kinds['HDMI-001S'] = dict(match={'lib': 'HDMI-001S'}, doc='HDMI 1.4 Type A pin assignment (1 D2+ ... 19 HPD); Xunpu HDMI-001S drawing marks pins 1 and 19; 20-23 shell',
                          pins={str(i): [n, 'passive', CONN] for i, n in enumerate(
                              ['D2+', 'D2_SH', 'D2-', 'D1+', 'D1_SH', 'D1-', 'D0+', 'D0_SH', 'D0-', 'CK+', 'CK_SH', 'CK-', 'CEC', 'UTILITY', 'SCL', 'SDA', 'DDC_GND', '+5V', 'HPD',
                               'SHELL', 'SHELL', 'SHELL', 'SHELL'], 1)})
kinds['USB-C_HX_16P'] = dict(match={'lib': 'USB-C_HX_16P'}, doc='HX TYPE-C 16P (LCSC C41427493) drawing; USB Type-C receptacle pin names',
                             pins={k: [k, 'passive', CONN] for k in ('1', '2', '3', '4', 'A1B12', 'B1A12', 'A4B9', 'B4A9', 'A5', 'B5', 'A6', 'B6', 'A7', 'B7', 'A8', 'B8')})
kinds['JST_SM06B'] = dict(match={'lib': 'JST_SM06B'}, doc='JST SH SM06B-SRSS-TB, 6 contacts + 2 fixing tabs', pins={str(i): [str(i), 'passive', CONN] for i in range(1, 9)})
kinds['JST_SM08B'] = dict(match={'lib': 'JST_SM08B'}, doc='JST SH SM08B-SRSS-TB, 8 contacts + 2 fixing tabs', pins={str(i): [str(i), 'passive', CONN] for i in range(1, 11)})
kinds['microSD'] = dict(match={'lib': 'microSD_Molex_104031-0811'}, doc='Molex 104031-0811 drawing (LCSC C585350) T1-T8, 9-10 detect switch, SH shell',
                        pins={k: [k, 'passive', CONN] for k in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'SH1', 'SH2', 'SH3', 'SH4')})
kinds['U.FL'] = dict(match={'lib': 'U.FL-R-SMT-1'}, doc='Hirose U.FL catalogue p3: 1 signal, 2-3 ground', pins={'1': ['SIG', 'passive', CONN], '2': ['GND', 'passive', CONN], '3': ['GND', 'passive', CONN]})

passive_libs = {'R0402': 'resistor or 0402 capacitor', 'C0603': 'capacitor or 0603 ferrite bead', 'C0805': 'capacitor or 0805 ferrite bead',
                'IND4020': 'inductor', 'TP_1.0': 'test pad', 'CP_7343': 'polarized capacitor (r7c C69, 5 V damping)',
                'R0201': 'resistor (r7f LCD series 33 ohm)'}

# ---------- limits used by verify.py. Voltages in V. "of" names another pin of the same part; its net's rail is the reference.
limits = {
    'TC358743XBG': {
        'B1': {'supply': [3.135, 3.465], 'src': f'{TOSH} p15 5.2 AVDD33'}, 'F3': {'supply': [3.135, 3.465], 'src': f'{TOSH} p15 5.2 AVDD33'},
        'B2': {'supply': [1.15, 1.25], 'drop': 'AVDD12', 'src': f'{TOSH} p15 5.2 AVDD12'}, 'D3': {'supply': [1.15, 1.25], 'drop': 'AVDD12', 'src': f'{TOSH} p15 5.2 AVDD12'},
        'B5': {'supply': [2.25, 2.75], 'src': f'{TOSH} p15 5.2 AVDD25'},
        'C3': {'supply': [1.1, 1.3], 'drop': 'BEAD', 'src': f'{TOSH} p15 5.2 VDDC'}, 'F5': {'supply': [1.1, 1.3], 'drop': 'BEAD', 'src': f'{TOSH} p15 5.2 VDDC'},
        'G2': {'supply': [1.1, 1.3], 'drop': 'BEAD', 'src': f'{TOSH} p15 5.2 VDDC'},
        'C6': {'supply': [1.1, 1.3], 'drop': 'BEAD', 'src': f'{TOSH} p15 5.2 VDD_MIPI'}, 'F6': {'supply': [1.1, 1.3], 'drop': 'BEAD', 'src': f'{TOSH} p15 5.2 VDD_MIPI'},
        'F4': {'supply': [3.0, 3.6], 'src': f'{TOSH} p15 5.2 VDDIO1'}, 'H7': {'supply': [1.65, 3.6], 'src': f'{TOSH} p15 5.2 VDDIO2'},
        'E5': {'vil': {'k': 0.3, 'of': 'H7'}, 'src': f'{TOSH} p10 TEST "0: Normal mode", p16 VIL 0.3 VDDIO'},
        'A3': {'vil': {'k': 0.0, 'of': 'H7'}, 'src': f'{TOSH} p11 VPGM "please tie to ground"'},
        'B4': {'vil': {'k': 0.3, 'of': 'H7'}, 'src': f'{TOSH} p10 IR, Sch input with no pull and no "when not used" rule: r7c ties it low (VIL 0.3 VDDIO, p16) so it cannot float'},
        'H5': {'vih': {'k': 0.7, 'of': 'H7'}, 'vmax': {'of': 'H7', 'add': 0.3}, 'src': f'{TOSH} p10 REFCLK on VDDIO2, p16 VIH 0.7 VDDIO, p15 VIN_IO max VDDIO+0.3'},
        'G5': {'vmax': {'of': 'H7', 'add': 0.3}, 'src': f'{TOSH} p10 RESETN on VDDIO2, p15 VIN_IO'},
        'G4': {'vmax': {'of': 'H7', 'add': 0.3}, 'src': f'{TOSH} p10 I2C on VDDIO2, p15 VIN_IO'},
        'H4': {'vmax': {'of': 'H7', 'add': 0.3}, 'src': f'{TOSH} p10 I2C on VDDIO2, p15 VIN_IO'},
        'G3': {'vmax': {'abs': 5.5}, 'src': f'{TOSH} p10 DDC on VDDIO1, p11 Note1 "5V tolerant" (5.5 V ASSUMED as the meaning of 5 V tolerant)'},
        'H3': {'vmax': {'abs': 5.5}, 'src': f'{TOSH} p10, p11 Note1'},
        'H2': {'vih': {'k': 0.7, 'of': 'F4'}, 'vmax': {'abs': 5.5}, 'src': f'{TOSH} p10 HPDI on VDDIO1, p11 Note1 5 V tolerant, p16 VIH 0.7 VDDIO, IILH 10 uA'},
        'A1': {'rext': [2000, 0.01, 'B1'], 'src': f'{TOSH} p11 REXT "connect to AVDD33 with a 2K ohm resistor (+-1%)"'},
    },
    'TCA9517A': {
        '1': {'supply': [0.9, 5.5], 'src': f'{TCA} p5 5.3'}, '8': {'supply': [2.7, 5.5], 'src': f'{TCA} p5 5.3'},
        '5': {'vih': {'k': 0.7, 'of': '8'}, 'vmax': {'abs': 5.5}, 'src': f'{TCA} p5 5.3 VIH EN 0.7 x VCCB, max 5.5'},
        '2': {'pullup_of': '1', 'src': f'{TCA} p4: A side "connect to VCCA through a pull-up resistor"'}, '3': {'pullup_of': '1', 'src': f'{TCA} p4'},
        '6': {'pullup_of': '8', 'src': f'{TCA} p4: B side "connect to VCCB through a pull-up resistor"'}, '7': {'pullup_of': '8', 'src': f'{TCA} p4'},
    },
    'SY8089': {
        '4': {'supply': [2.7, 5.5], 'abs': 6.0, 'src': f'{SY} p4 VIN 2.7-5.5, p2 abs 6.0'},
        '1': {'vih': {'abs': 1.5}, 'vmax': {'of': '4', 'add': 0.6}, 'src': f'{SY} p4 VENH 1.5, p2 EN abs VIN+0.6, "do not float"'},
        '5': {'buck': {'vref': [0.588, 0.612], 'ifb': 50e-9, 'lx': '3'}, 'src': f'{SY} p2 Vout=0.6(1+R1/R2), p4 VREF 0.588-0.612 (25 C), IFB +-50 nA'},
    },
    'TLV73325': {
        '1': {'supply': [1.4, 5.5], 'src': f'{TLV} p5 6.3'}, '3': {'vih': {'abs': 0.9}, 'vmax': {'of': '1', 'add': 0.3}, 'src': f'{TLV} p6 VEN(HI) 0.9, p5 VEN abs VIN+0.3'},
        '5': {'fixed': [2.5 * 0.986, 2.5 * 1.014], 'src': f'{TLV} p6 DC output accuracy +-1.4% over temperature'},
    },
    'YSO110TR': {
        '4': {'supply': [1.8, 3.3], 'level': 'WARN', 'src': f'{YXC} p1 supply 1.8-3.3 V (listed values, no tolerance given)'},
        '1': {'vih': {'k': 0.7, 'of': '4'}, 'src': f'{YXC} p1 tri-state high 70% VDD'},
        '3': {'voh': {'k': 0.9, 'of': '4'}, 'load_pf': 15, 'src': f'{YXC} p1 VOH 90% VDD, load 15 pF max'},
    },
    'ESP32-P4-Module': {
        '85': {'supply': [3.0, 3.6], 'src': 'Waveshare ESP32-P4-Module wiki: 3.3 V supply; 3.0-3.6 is the P4 VDDPST range, ESP32-P4 datasheet v0.7 p32 (not re-read for r7c)'},
        '86': {'supply': [3.0, 3.6], 'src': 'as 85'}, '84': {'supply': [3.0, 3.6], 'src': 'as 85'},
        '87': {'pullup': True, 'src': f'{P4} p34 CHIP_PU: do not leave floating; p90 VIH_nRST 0.75 VDD'},
        '18': {'vih': {'k': 0.75, 'of': '85'}, 'vmax': {'of': '85', 'add': 0.3}, 'src': f'{P4} p89 VIH 0.75 VDD, max VDD+0.3'},
    },
    'TPD4E05U06': {k: {'vmax': {'abs': 5.5}, 'src': f'{TPD} p7 VRWM 5.5 V'} for k in ('1', '2', '4', '5')},
    'AO3401A': {'1': {'vgs_max': 12, 'src': f'{AOS} p1 VGS +-12 V'}},
    'TPS259531': {'3': {'supply': [2.7, 18.0], 'abs': 20.0, 'src': f'{EFU} p5 7.3 VIN 2.7-18 V, 7.1 abs 20 V'},
                  '2': {'vmax': {'abs': 6.0}, 'src': f'{EFU} p5 7.3 VEN 0-6 V (7.1 abs 7 V)'},
                  '5': {'efuse': {'from': '3', 'clamp': [5.2, 5.7]}, 'src': f'{EFU} p7 VCLAMP 5.2-5.7 V (TPS25953x), output follows IN below VOVC 5.5-5.9 V'}},
}

# Supply domain of each logic/analog pin: the pin of the same part whose rail bounds the voltage the pin can drive or present.
# verify.py uses it for the highest voltage a net can see.
_tc_dom = {}
for b, nm in balls.items():
    if nm in ('RESETN', 'REFCLK', 'TEST', 'INT', 'EDID_SDA', 'EDID_SCL', 'A_SCK', 'A_WFS', 'A_SD', 'A_OSCK', 'IR', 'I2C_SDA', 'I2C_SCL'):
        _tc_dom[b] = 'H7'   # VDDIO2
    elif nm in ('DDC_SDA', 'DDC_SCL', 'CEC', 'HPDI', 'HPDO'):
        _tc_dom[b] = 'F4'   # VDDIO1
    elif nm.startswith('CSI'):
        _tc_dom[b] = 'C6'   # VDD_MIPI
    elif nm.startswith('HDMI'):
        _tc_dom[b] = 'B1'   # AVDD33
    elif nm in ('BIASDA', 'DAOUT', 'PCKIN', 'PFIL'):
        _tc_dom[b] = 'B5'   # AVDD25 (p15 VOUT_APLL)
domains = {
    'TC358743XBG': {'src': f'{TOSH} p10-11 Table 3.1 "Voltage Supply" column; p15 VOUT_APLL', 'pins': _tc_dom},
    'ESP32-P4-Module': {'src': f'{WS}; GPIO39-48 are on VDD_IO_5 = ESP_LDO_VO4 (wiki pin 66 text), bounded here by the module 3.3 V supply', 'pins':
                        {str(n): '85' for n, nm in names.items() if nm.startswith(('GPIO', 'C6_', 'USB_', 'CSI_', 'DSI_')) or nm == 'ESP_EN'}},
    'TCA9517A': {'src': f'{TCA} p4-5: A side on VCCA, B side and EN on VCCB', 'pins': {'2': '1', '3': '1', '5': '8', '6': '8', '7': '8'}},
    'YSO110TR': {'src': f'{YXC} p1', 'pins': {'1': '4', '3': '4'}},
}

# Supplies that come from outside the board, named by the connector pin they enter on.
external = {
    'J5.A4B9': {'rail': [4.75, 5.5], 'src': 'USB Type-C vSafe5V 4.75-5.5 V (box power input; Rd only, so no higher voltage is negotiated)'},
    'J3.A4B9': {'rail': [4.75, 5.5], 'src': 'USB Type-C vSafe5V 4.75-5.5 V (host port VBUS, used for sensing only)'},
    'J2.18': {'rail': [4.7, 5.3], 'src': 'HDMI 1.4 +5V Power from the source, 4.7-5.3 V (as used in R7B_REPORT M5; spec not re-read for r7c)'},
    'J5.A1B12': {'rail': [0.0, 0.0], 'src': 'USB-C GND: the board ground is the 5 V source return'},
}

# Unconnected pins whose type would normally need a connection. Anything input-like left open and not listed here fails.
open_ok = {
    'ESP32-P4-Module.GPIO': {'level': 'OK', 'why': 'unused P4/C6 GPIO or C6_IO pad: firmware owns it and can enable the internal pull (ESP32-P4 datasheet v0.7 p89 RPU/RPD). '
                                                   'ASSUMED acceptable, no datasheet sentence quoted; the Waveshare DEV-KIT also leaves unused pads open'},
    'TC358743XBG.G6': {'level': 'WARN', 'why': f'EDID_SDA unused. {TOSH} p10 gives no "when not used" rule for EDID, buffer type N (no pull): floating Schmitt input. Same as the Antmicro reference (pinout audit O2)'},
    'TC358743XBG.H6': {'level': 'WARN', 'why': f'EDID_SCL unused, as G6'},
}

json.dump(dict(_doc=__doc__, passive_libs=passive_libs, kinds=kinds, limits=limits, domains=domains, external=external, open_ok=open_ok),
          open(OUT, 'w', encoding='utf-8', newline='\n'), indent=1, ensure_ascii=False)
print('wrote', OUT, sum(len(k['pins']) for k in kinds.values()), 'pin entries in', len(kinds), 'kinds')
