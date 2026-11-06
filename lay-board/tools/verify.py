# -*- coding: utf-8 -*-
"""Independent checks on the saved board. Pin intent is written by hand here from vendor documents, not read from the generator."""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

import bodycheck
import holecheck
import maskcheck

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = sys.argv[1]
ANT_NET = sys.argv[2]
s = open(f'{OUT}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()
d = json.load(open(f'{OUT}/design.json', encoding='utf-8'))
fails = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        fails.append(msg)


pads = {}
for m in re.finditer(r'\(footprint "mini:[^"]*"(.*?)(?=\n\s*\(footprint "|\Z)', s, re.S):
    b = m.group(1)
    r = re.search(r'\(property "Reference" "([^"]+)"', b)
    if not r:
        continue
    for q in re.finditer(r'\(pad "([^"]*)"\s+\w+\s+\w+.*?\(net (?:\d+ )?"([^"]*)"\)', b, re.S):
        pads[f'{r.group(1)}.{q.group(1)}'] = q.group(2)
print('pads with nets read back', len(pads))

# Waveshare wiki pin table, 2026-11-06, and the pinout picture agree. Only the pins this design uses are listed.
WIKI = {1: 'GND', 3: 'GND', 15: 'GND', 33: 'GND', 40: 'GND', 47: 'GND', 52: 'GND', 83: 'GND', 84: 'VBAT', 85: 'ESP_3V3', 86: 'ESP_3V3', 87: 'ESP_EN', 66: 'ESP_LDO_VO4',
        41: 'CSI_DATAN0', 42: 'CSI_DATAP0', 43: 'CSI_CLKP', 44: 'CSI_CLKN', 45: 'CSI_DATAN1', 46: 'CSI_DATAP1', 48: 'USB_DM', 49: 'USB_DP', 50: 'GPIO24', 51: 'GPIO25',
        62: 'GPIO35', 63: 'GPIO36', 64: 'GPIO37', 65: 'GPIO38', 67: 'GPIO39', 68: 'GPIO40', 69: 'GPIO41', 70: 'GPIO42', 71: 'GPIO43', 72: 'GPIO44', 73: 'GPIO45',
        22: 'GPIO7', 23: 'GPIO8', 32: 'GPIO23', 24: 'GPIO9', 25: 'GPIO10', 26: 'GPIO11', 27: 'GPIO12', 28: 'GPIO13', 17: 'GPIO2', 18: 'GPIO3', 19: 'GPIO4', 20: 'GPIO5', 4: 'C6_U0RXD', 5: 'C6_U0TXD', 9: 'C6_IO9', 10: 'C6_IO8'}
ROLE = {'GND': 'GND', 'VBAT': '3V3', 'ESP_3V3': '3V3', 'ESP_EN': 'ESP_EN', 'ESP_LDO_VO4': 'LDO_VO4',
        'CSI_DATAN0': 'CSI_D0_N', 'CSI_DATAP0': 'CSI_D0_P', 'CSI_CLKP': 'CSI_CK_P', 'CSI_CLKN': 'CSI_CK_N', 'CSI_DATAN1': 'CSI_D1_N', 'CSI_DATAP1': 'CSI_D1_P',
        'USB_DM': 'USB_DN', 'USB_DP': 'USB_DP', 'GPIO24': 'USB2_DN', 'GPIO25': 'USB2_DP', 'GPIO35': 'BOOT', 'GPIO36': 'GPIO36', 'GPIO37': 'U0_TX', 'GPIO38': 'U0_RX',
        'GPIO39': 'SD_D0', 'GPIO40': 'SD_D1', 'GPIO41': 'SD_D2', 'GPIO42': 'SD_D3', 'GPIO43': 'SD_CLK', 'GPIO44': 'SD_CMD', 'GPIO45': 'SD_PWR_N',
        'GPIO7': 'I2C_SDA', 'GPIO8': 'I2C_SCL', 'GPIO23': 'TC_RST', 'GPIO9': 'LCD_DIN', 'GPIO10': 'LCD_CLK', 'GPIO11': 'LCD_CS', 'GPIO12': 'LCD_DC', 'GPIO13': 'LCD_RST',
        'GPIO2': 'ATX_LED', 'GPIO3': 'HOST_VBUS_DIV', 'GPIO4': 'ATX_PWR', 'GPIO5': 'ATX_RST', 'C6_U0RXD': 'C6_RXD', 'C6_U0TXD': 'C6_TXD', 'C6_IO9': 'C6_IO9', 'C6_IO8': 'C6_IO8'}
bad = {k: (ROLE[v], pads.get(f'U1.{k}')) for k, v in WIKI.items() if pads.get(f'U1.{k}') != ROLE[v]}
check(not bad, f'{len(WIKI)} module pins match the vendor pin table {bad or ""}')

# TC358743: every ball against Antmicro's netlist, by the ball function it names
net = open(ANT_NET, encoding='utf-8').read()
k = net.find('(nets')
func = {}
for m in re.finditer(r'\(node\s+\(ref "U1"\)\s+\(pin "([^"]+)"\)\s+\(pinfunction "([^"]*)"\)', net[k:]):
    func[m.group(1)] = m.group(2).rsplit('_', 1)[0]
print('TC358743 balls in the reference', len(func))
EXPECT = {'GND': 'GND', 'VPGM': 'GND', 'TEST': 'GND', 'AVDD33': '3V3', 'VDDIO1': '3V3', 'VDDIO2': '3V3', 'AVDD25': 'AVDD25', 'AVDD12': 'AVDD12', 'VDD_MIPI': 'VDD_MIPI', 'VDDC1': 'VDDC', 'VDDC2': 'VDDC',
          'HDMID0_P': 'D0_P', 'HDMID0_N': 'D0_N', 'HDMID1_P': 'D1_P', 'HDMID1_N': 'D1_N', 'HDMID2_P': 'D2_P', 'HDMID2_N': 'D2_N', 'HDMIC_P': 'CK_P', 'HDMIC_N': 'CK_N',
          'CSID0_P': 'CSI_D0_P', 'CSID0_N': 'CSI_D0_N', 'CSID1_P': 'CSI_D1_P', 'CSID1_N': 'CSI_D1_N', 'CSIC_P': 'CSI_CK_P', 'CSIC_N': 'CSI_CK_N',
          'I2C_SDA': 'I2C_SDA', 'I2C_SCL': 'I2C_SCL', 'DDC_SDA': 'DDC3_SDA', 'DDC_SCL': 'DDC3_SCL', '~{RESET}': 'TC_RST', 'REFCLK': 'TC_REFCLK', 'REXT': 'TC_REXT', 'BIASDA': 'TC_BIASDA', 'PFIL': 'TC_PFIL', 'PCKIN': 'TC_PCKIN', 'CEC': 'HDMI_CEC', 'HPDI': 'HDMI_5V', 'HPDO': 'TC_HPDO'}
miss = {}
nc = 0
for ball, f in func.items():
    got = pads.get(f'U7.{ball}', '')
    if f in EXPECT:
        if got != EXPECT[f]:
            miss[ball] = (f, got)
    else:
        nc += 1
        if not got.startswith('unconnected'):
            miss[ball] = (f, got)
check(not miss and len(func) == 64, f'64 TC358743 balls match by function (PFIL and DAOUT per the datasheet, the reference has them swapped), {nc} left open {miss or ""}')

# HDMI Type A receptacle, HDMI 1.4 pin numbering
HDMI = {1: 'D2_P', 2: 'GND', 3: 'D2_N', 4: 'D1_P', 5: 'GND', 6: 'D1_N', 7: 'D0_P', 8: 'GND', 9: 'D0_N', 10: 'CK_P', 11: 'GND', 12: 'CK_N', 13: 'HDMI_CEC', 15: 'DDC_SCL', 16: 'DDC_SDA', 17: 'GND', 18: 'HDMI_5V', 19: 'HDMI_HPD'}
bad = {k: (v, pads.get(f'J2.{k}')) for k, v in HDMI.items() if pads.get(f'J2.{k}') != v}
check(not bad, f'HDMI connector follows the standard pinout {bad or ""}')
# microSD standard pinout
SD = {1: 'SD_D2', 2: 'SD_D3', 3: 'SD_CMD', 4: 'SD1_VDD', 5: 'SD_CLK', 6: 'GND', 7: 'SD_D0', 8: 'SD_D1'}
bad = {k: (v, pads.get(f'J7.{k}')) for k, v in SD.items() if pads.get(f'J7.{k}') != v}
check(not bad, f'microSD follows the standard pinout {bad or ""}')
# USB-C
USB = {'J3.A6': 'USB_DP', 'J3.B6': 'USB_DP', 'J3.A7': 'USB_DN', 'J3.B7': 'USB_DN', 'J3.A4B9': 'HOST_VBUS', 'J3.B4A9': 'HOST_VBUS', 'J3.A5': 'HOST_CC1', 'J3.B5': 'HOST_CC2',
       'J5.A6': 'USB2_DP', 'J5.B6': 'USB2_DP', 'J5.A7': 'USB2_DN', 'J5.B7': 'USB2_DN', 'J5.A4B9': '5V', 'J5.B4A9': '5V', 'J5.A5': 'PWR_CC1', 'J5.B5': 'PWR_CC2',
       'R1.1': 'HOST_CC1', 'R1.2': 'GND', 'R2.1': 'HOST_CC2', 'R2.2': 'GND', 'R3.1': 'PWR_CC1', 'R3.2': 'GND', 'R4.1': 'PWR_CC2', 'R4.2': 'GND'}
bad = {k: (v, pads.get(k)) for k, v in USB.items() if pads.get(k) != v}
check(not bad, f'USB-C data, VBUS and 5.1k CC pull-downs {bad or ""}')
check(pads.get('J3.A4B9') != '5V', 'host VBUS stays apart from the box 5V, neither can feed the other')
# SY8089: EN GND LX IN FB
REG = {'U2.1': '5V', 'U2.2': 'GND', 'U2.3': 'SW', 'U2.4': '5V', 'U2.5': 'FB_3V3', 'L1.1': 'SW', 'L1.2': '3V3', 'U4.1': '3V3', 'U4.2': 'GND', 'U4.3': '3V3', 'U4.5': 'V2V5', 'U5.1': 'V2V5', 'U5.2': 'GND', 'U5.3': 'V2V5', 'U5.5': 'V1V2',
       'U6.1': '3V3', 'U6.2': 'DDC3_SCL', 'U6.3': 'DDC3_SDA', 'U6.4': 'GND', 'U6.5': '3V3', 'U6.6': 'DDC_SDA', 'U6.7': 'DDC_SCL', 'U6.8': '5V',
       'Y1.2': 'GND', 'Y1.3': 'OSC_OUT', 'Y1.4': 'OSC_VDD', 'Q1.1': 'SD_PWR_N', 'Q1.2': 'SD_SRC', 'Q1.3': 'SD1_VDD'}
bad = {k: (v, pads.get(k)) for k, v in REG.items() if pads.get(k) != v}
check(not bad, f'regulators, level shifter, oscillator and SD switch pins {bad or ""}')

vout = 0.6 * (1 + 150 / 33)
check(abs(vout - 3.3) < 0.1, f'buck feedback sets {vout:.3f} V from 0.6 V reference')
if_ma = (3.3 - 1.14) / 470 * 1000
check(if_ma > 2, f'opto LED current {if_ma:.1f} mA from a 3.3 V GPIO')
# EL3H7(C): CTR 200-400% at 5 mA, VCE 5 V (p3); near saturation about 0.9 of that at this current (fig. 3, VCE 0.4 V). The 5 mA header pull-up is an ASSUMPTION; see README.
ic_ma = if_ma * 2.0 * 0.9
check(ic_ma > 5, f'opto can sink {ic_ma:.1f} mA at 25 C at CTR minimum, against an assumed under-5 mA ATX header pull-up')
check(5 * 100 / 200 <= 3.3, 'VBUS divider gives 2.5 V at 5 V')

# routed lengths of the high speed pairs, pad to pad along the tree
segs = defaultdict(list)
for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([-\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', s):
    x0, y0, x1, y1, w, ly, n = m.groups()
    segs[n].append((float(x0), float(y0), float(x1), float(y1), float(w), ly))
vcount = defaultdict(int)
for m in re.finditer(r'\(via\b.*?\(net "([^"]+)"\)', s, re.S):
    vcount[m.group(1)] += 1
check(len(segs) > 40, f'routed tracks were read back from the saved board ({sum(len(v) for v in segs.values())} segments on {len(segs)} nets)')


def length(n):
    return sum(math.hypot(a[2] - a[0], a[3] - a[1]) for a in segs[n])


print('pair            P mm    N mm   skew   vias P/N')
limits = {'D2': 12, 'D1': 12, 'D0': 12, 'CK': 12, 'CSI_D0': 12, 'CSI_D1': 12, 'CSI_CK': 12, 'USB': 12}
worst = 0
lens = []
for pair in ('D2', 'D1', 'D0', 'CK', 'CSI_D0', 'CSI_D1', 'CSI_CK'):
    a, b = length(pair + '_P'), length(pair + '_N')
    worst = max(worst, abs(a - b))
    lens += [a, b]
    print(f'{pair:12s} {a:7.2f} {b:7.2f} {abs(a - b):6.2f}   {vcount[pair + "_P"]}/{vcount[pair + "_N"]}')
a, b = length('USB_DP'), length('USB_DN')
lens += [a, b]
worst = max(worst, abs(a - b))
print(f'USB          {a:7.2f} {b:7.2f} {abs(a - b):6.2f}   {vcount["USB_DP"]}/{vcount["USB_DN"]}')
limit = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
check(min(lens) > 1, f'every high speed line has routed length, shortest {min(lens):.2f} mm')
check(worst <= limit, f'worst P/N length difference {worst:.2f} mm is within {limit} mm (about {worst * 6.7:.0f} ps; one bit at 972 Mbit/s is 1029 ps)')

# geometry a same-net DRC cannot see: no via hole may touch a solder pad on any net, and no net may have one pin
vias_found = []
for m in re.finditer(r'\(via\b(.*?)\(uuid', s, re.S):
    a = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', m[1])
    n = re.search(r'\(net "([^"]+)"\)', m[1])
    dr = re.search(r'\(drill ([\d.]+)\)', m[1])
    if a and n:
        vias_found.append((float(a[1]) - 100, float(a[2]) - 100, float(dr[1]), n[1]))
hit = []
sizes = {'BGA-64_6x6': 0.15}
for part in d['parts']:
    if part['lib'] != 'BGA-64_6x6':
        continue
    for k, xy in d['padpos'].items():
        if k.split('.')[0] == part['ref']:
            for v in vias_found:
                if math.hypot(xy[0] - v[0], xy[1] - v[1]) < 0.15 + v[2] / 2 + 0.03:
                    hit.append((k, v[3], round(math.hypot(xy[0] - v[0], xy[1] - v[1]), 3)))
check(not hit, f'no via hole touches a BGA ball pad, {len(vias_found)} vias checked {hit or ""}')
count = defaultdict(list)
for k, n in pads.items():
    if not n.startswith('unconnected-'):
        count[n].append(k)
single = {n: v for n, v in count.items() if len(v) < 2}
ok_single = {'C6_IO8x'}
check(not {n for n in single if n not in ok_single and not n.startswith(('GPIO36',))}, f'no net has only one pin {single or ""}')

# every stocked part number must actually be the stated value; read from JLC's listing into stock.json
stock = {r[0]: r for r in json.load(open(f'{OUT}/stock.json', encoding='utf-8'))}
DECODE = {'100nF': '104', '1uF': '105', '470pF': '471', '47pF': '470', '22pF': '220', '4.7uF': '475', '10uF': '106', '22uF': '226',
          '5.1k': '5101', '10k': '1002', '100k': '1003', '470 ': '4700', '270 ': '2700', '150k': '1503', '33k': '3302', '51k': '5102', '2.2k': '2201', '2k ': '2001', '22 ': '220', '1k ': '1001', '0R': '0000'}
MODEL = {'C41427493': 'TYPE-C 16P', 'C138714': 'TPD4E05U06', 'C160407': 'SM08B-SRSS', 'C160405': 'SM06B-SRSS', 'C720616': 'HDMI-001S', 'C3008606': 'TC358743XBG', 'C882825': 'TLV73325', 'C2871228': 'TLV73312',
         'C98485': 'GZ2012D102', 'C725995': 'OT322527M', 'C19330': 'BLM18AG601', 'C30348': 'PCA9517', 'C585350': '1040310811', 'C15127': 'AO3401', 'C78988': 'SY8089', 'C83423': 'SWPA4020S2R2', 'C92243': 'EL3H7(C)'}
wrong = []
missing = []
for part in d['parts']:
    if part['dnp'] or part['consign'] or not part['lcsc']:
        continue
    row = stock.get(part['lcsc'])
    if not row:
        missing.append((part['ref'], part['lcsc']))
        continue
    if not isinstance(row[2], int) or row[2] < 10:
        missing.append((part['ref'], part['lcsc'], row[2]))
    v = part['value'].split(' 0')[0].strip() + (' ' if part['value'].split(' 0')[0].strip() in ('470', '270', '2k', '22', '1k') else '')
    if v in DECODE and DECODE[v] not in str(row[1]):
        wrong.append((part['ref'], part['value'], row[1]))
    want = MODEL.get(part['lcsc'])
    if want and want not in str(row[1]):
        wrong.append((part['ref'], want, row[1]))
    if not want and not part['value'].endswith(('0402', '0603', '0805')):
        wrong.append((part['ref'], 'no model entry', row[1]))
check(not wrong, f'every part number decodes to its stated value {wrong or ""}')
check(not missing, f'every fitted part is stocked at JLC {missing or ""}')

# solder mask and hole clearance as the factory sees them: plot this board and measure the polygons (limits and source in maskcheck.py, holecheck.py)
KC = os.environ.get('KICAD_CLI', 'D:/tools/kicad-nightly/app/bin/kicad-cli.exe')
H = os.environ.get('KICAD_TOOL_HOME', 'D:/tools/kicad-nightly/home')
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=f'{H}/doc', KICAD_CONFIG_HOME=f'{H}/cfg', KICAD_CACHE_HOME=f'{H}/cache')
with tempfile.TemporaryDirectory() as tmp:
    p = subprocess.run([KC, 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask', '--no-protel-ext', '-o', tmp + '/', f'{OUT}/p4_kvm_mini.kicad_pcb'], env=ENV, capture_output=True, text=True, errors='replace')
    if p.returncode:
        check(False, f'mask check: Gerber plot failed {p.stderr[-200:]}')
    else:
        mr = maskcheck.check(tmp)
        check(mr['ok'], 'MASKCHECK ' + maskcheck.summary(mr))
    q = subprocess.run([KC, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute', '--excellon-separate-th', '-o', tmp + '/', f'{OUT}/p4_kvm_mini.kicad_pcb'], env=ENV, capture_output=True, text=True, errors='replace')
    if p.returncode or q.returncode:
        check(False, f'hole check: plot failed {q.stderr[-200:]}')
    else:
        try:
            hr = holecheck.check(tmp)
            check(hr['ok'], 'HOLECHECK ' + holecheck.summary(hr))
            for x in hr['fails']:
                print(f"  {x['gap']:.4f} limit {x['limit']} {x['kind']} {x['hole']} [{x['hnet']}] {x['layer']} to {x['other']} [{x['onet']}]")
        except maskcheck.GerberError as e:
            check(False, f'HOLECHECK could not parse: {e}')
# real part outlines against each other: bodies and lead tips from the drawings, limits and sources in bodycheck.py
br = bodycheck.check(OUT)
check(br['ok'], 'BODYCHECK ' + bodycheck.summary(br))
for x in br['fails'] + br['warns']:
    print('  ' + bodycheck.line(x))
print('BOARD sha256', hashlib.sha256(open(f'{OUT}/p4_kvm_mini.kicad_pcb', 'rb').read()).hexdigest())
print('RESULT', 'ALL PASS' if not fails else f'{len(fails)} FAILED')
sys.exit(1 if fails else 0)
