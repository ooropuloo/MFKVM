# -*- coding: utf-8 -*-
"""Builds v3/fab_atx/. Refuses unless ERC, DRC, parity, the routed net check, the Gerber mask check and JLC stock all pass on this exact board.

usage: fab_atx.py <out_dir> <target_dir>     needs shapely; run with the v3cad python
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
MINI_TOOLS = os.path.join(HERE, '..', '..', 'lay-board', 'tools')
sys.path.insert(0, MINI_TOOLS)  # read only, the same checkers the 6 layer board uses
import maskcheck  # noqa: E402

sys.path.insert(0, os.path.join(HERE, 'tools'))
import bodycheck  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT, DEST = sys.argv[1], sys.argv[2]
NAME = 'mf_kvm_atx'
KC = os.environ.get('KICAD_CLI', 'D:/tools/kicad-nightly/app/bin/kicad-cli.exe')
H = os.environ.get('KICAD_TOOL_HOME', 'D:/tools/kicad-nightly/home')
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=f'{H}/doc', KICAD_CONFIG_HOME=f'{H}/cfg', KICAD_CACHE_HOME=f'{H}/cache')
OX, OY = 100.0, 100.0
lines = []


def gate(ok, msg):
    t = ('PASS ' if ok else 'FAIL ') + msg
    print(t)
    lines.append(t)
    if not ok:
        print('REFUSED: nothing released')
        sys.exit(2)


# the board's nets, written by hand from mini's circuit, not read from the generator
INTENT = {'U1': {'1': 'PWR_LED', '2': 'GND', '3': 'PWR_E', '4': 'PWR_C'}, 'U2': {'1': 'RST_LED', '2': 'GND', '3': 'RST_E', '4': 'RST_C'}, 'U3': {'1': 'LED_IN', '2': 'LED_K', '3': 'ATX_LED', '4': '3V3'},
          'J1': {'1': 'PWR_C', '2': 'PWR_E', '3': 'RST_C', '4': 'RST_E', '5': 'LED_K', '6': 'LED_A'}, 'R1': {'1': 'ATX_PWR', '2': 'PWR_LED'}, 'R2': {'1': 'ATX_RST', '2': 'RST_LED'},
          'R3': {'1': 'LED_A', '2': 'LED_IN'}, 'R4': {'1': 'ATX_LED', '2': 'GND'}, 'H1': {'1': '3V3'}, 'H2': {'1': 'GND'}, 'H3': {'1': 'ATX_PWR'}, 'H4': {'1': 'ATX_RST'}, 'H5': {'1': 'ATX_LED'}}
r = json.load(open(f'{OUT}/drc.json', encoding='utf-8'))
e = json.load(open(f'{OUT}/erc.json', encoding='utf-8'))
errs = [v for v in r['violations'] if v['severity'] == 'error']
erc = [v for s in e.get('sheets', []) for v in s.get('violations', [])]
gate(not erc, f'ERC {len(erc)} violations')
gate(not errs, f'DRC {len(errs)} errors, {len(r["violations"]) - len(errs)} warnings')
gate(not r['unconnected_items'], f'unconnected {len(r["unconnected_items"])}')
gate(not r['schematic_parity'], f'schematic parity {len(r["schematic_parity"])}')

# real outlines, worst case, every pair. The earlier layout is kept as a fixture: a checker that passes it cannot see the R4 over U1 overlap.
_bc = bodycheck.check(f'{OUT}/design.json')
_tight = _bc['rows'][:3]
gate(_bc['ok'], f"real part outlines, worst case with +-{bodycheck.PLACE} placement (assumption), minimum gap {bodycheck.MIN_GAP}, opto pitch {_bc['pitch']}. Tightest: " + ', '.join(f"{q['a']}/{q['b']} {q['gap']} ({q['what']})" for q in _tight) + (f" BAD {_bc['bad']}" if _bc['bad'] else ''))
_saved = bodycheck.board_positions(f'{OUT}/{NAME}.kicad_pcb')
_des = json.load(open(f'{OUT}/design.json', encoding='utf-8'))['parts']
gate(len(_saved) == len(_des) and all(abs(_saved[q['ref']][0] - q['x']) < 0.001 and abs(_saved[q['ref']][1] - q['y']) < 0.001 for q in _des), f'part positions the body check used match the saved board, {len(_des)} parts')
gate(_bc['jlc'] and all(q['gap'] >= q['rule'] for q in _bc['jlc']), 'JLC spacing page, closest to its rule: ' + ', '.join(f"{q['a']}/{q['b']} {q['gap']} (rule {q['rule']})" for q in _bc['jlc'][:3]))
_old = bodycheck.check(os.path.join(HERE, 'tools', 'prev_layout_design.json'))
gate(not _old['ok'], f"the same check refuses the earlier layout: {[(q['a'], q['b'], q['gap'], q['what']) for q in _old['bad']]}")

pcb = f'{OUT}/{NAME}.kicad_pcb'
s = open(pcb, encoding='utf-8').read()
gate('(allow_soldermask_bridges_in_footprints no)' in s, 'allow_soldermask_bridges_in_footprints is off in the saved board')
got = {}
for blk in re.split(r'\(footprint "atx:', s)[1:]:
    ref = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', blk)[1]
    for pm in re.finditer(r'\(pad\s+"([^"]*)"(.*?)\(uuid', blk, re.S):
        n = re.search(r'\(net\s+(?:\d+\s+)?"([^"]+)"\)', pm[2])
        got.setdefault(ref, {})[pm[1]] = n[1] if n else ''
bad = [(ref, n, want, got.get(ref, {}).get(n)) for ref, pins in INTENT.items() for n, want in pins.items() if got.get(ref, {}).get(n) != want]
gate(not bad, f'saved board pad nets match the hand written intent, {sum(len(v) for v in INTENT.values())} pads {bad or ""}')
gate(all(got['J1'][k] == '' or 'unconnected' in got['J1'][k] for k in ('MP1', 'MP2')), 'JST mount tabs tied to nothing, so the header side stays apart from logic ground')

# LED current, using LTV-357T Vf 1.2 V typical
for name, rv, vin in (('PWR/RST LED from a 3.3 V GPIO, 470 ohm', 470, 3.3), ('front panel LED input from 5 V, 270 ohm plus board LED drop ignored', 270, 5.0)):
    i = (vin - 1.2) / rv * 1000
    gate(2 < i < 20, f'{name}: {i:.1f} mA, limit 50 mA')

stage = f'{OUT}/_gerber'
shutil.rmtree(stage, ignore_errors=True)
os.makedirs(stage)
layers = 'F.Cu,B.Cu,F.Paste,B.Paste,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts'
for args in ([KC, 'pcb', 'export', 'gerbers', '--layers', layers, '--no-protel-ext', '-o', stage, pcb],
             [KC, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute', '--excellon-separate-th', '-o', stage + '/', pcb]):
    p = subprocess.run(args, env=ENV, capture_output=True, text=True, errors='replace')
    gate(p.returncode == 0, 'export ' + args[3])
mask = maskcheck.check(stage)
gate(mask['ok'], 'mask on real Gerber polygons, JLCPCB 0.10 mm: ' + maskcheck.summary(mask))
# maskcheck only lists bridges under its search distance, so a clean board reports None. Measure the real minimum between any two openings.
_ly = maskcheck.Layers(stage)
_min = 9.0
for _side in 'TB':
    _o = maskcheck.parse(_ly.txt['mask', _side])
    for _i, _a in enumerate(_o):
        for _b in _o[_i + 1:]:
            _min = min(_min, _a['geom'].distance(_b['geom']))
gate(_min >= 0.10, f'smallest mask web between any two openings, measured directly on the Gerber: {_min:.4f} mm')
hc = subprocess.run([sys.executable, 'holecheck.py', os.path.abspath(stage)], cwd=MINI_TOOLS, capture_output=True, text=True, errors='replace')
hc_out = hc.stdout.strip()
gate(hc.returncode == 0, 'hole rules, lay-board/tools/holecheck.py on real drill and copper: ' + hc_out.replace('\n', ' | ')[:600])

# outline read back from the Gerber
names = sorted(os.listdir(stage))
edge = next(n for n in names if 'Edge_Cuts' in n)
t = open(f'{stage}/{edge}', encoding='utf-8', errors='replace').read()
scale = 1e6 if '%FSLAX46Y46*%' in t else 1e5
pts = [(int(a) / scale, int(b) / scale) for a, b in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]', t)]
sx, sy = max(a for a, _ in pts) - min(a for a, _ in pts), max(b for _, b in pts) - min(b for _, b in pts)
gate(abs(sx - 11.05) < 0.1 and abs(sy - 35.4) < 0.1, f'outline from the Gerber {sx:.2f} x {sy:.2f}')

# JLC stock. Read only, same public search mini uses.
d = json.load(open(f'{OUT}/design.json', encoding='utf-8'))
codes = {}
for q in d['parts']:
    if q['lcsc']:
        codes.setdefault(q['lcsc'], []).append(q['ref'])
URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
rows = []
for c, refs in sorted(codes.items()):
    body = json.dumps({'keyword': c, 'currentPage': 1, 'pageSize': 3}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = json.load(urllib.request.urlopen(req, timeout=25))
    hit = [x for x in (((res.get('data') or {}).get('componentPageInfo') or {}).get('list') or []) if x.get('componentCode') == c]
    x = hit[0] if hit else {}
    rows.append(dict(code=c, model=x.get('componentModelEn'), stock=x.get('stockCount') or 0, kind=x.get('componentLibraryType'), price=(x.get('componentPrices') or [{}])[0].get('productPrice'), refs=refs))
    time.sleep(0.25)
gate(all(q['stock'] > 20 for q in rows), 'every fitted part stocked at JLC: ' + ', '.join(f"{q['code']} {q['model']} {q['stock']} ({q['kind']})" for q in rows))
cost = sum((q['price'] or 0) * len(q['refs']) for q in rows)

os.makedirs(DEST, exist_ok=True)
shutil.rmtree(f'{DEST}/gerber', ignore_errors=True)
shutil.copytree(stage, f'{DEST}/gerber')
zp = f'{DEST}/{NAME}_gerber.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in names:
        z.write(f'{stage}/{n}', n)
sha = hashlib.sha256(open(zp, 'rb').read()).hexdigest()
with open(f'{DEST}/BOM_JLC.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for q in rows:
        first = next(p for p in d['parts'] if p['ref'] == q['refs'][0])
        w.writerow([first['value'], ','.join(sorted(q['refs'])), first['lib'], q['code']])
with open(f'{DEST}/CPL_JLC.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for p in d['parts']:
        if p['lcsc']:
            w.writerow([p['ref'], f"{p['x'] + OX:.3f}mm", f"{-(p['y'] + OY):.3f}mm", 'Top', f"{p['r'] % 360:g}"])
for side, fn in (('top', 'board_top.png'), ('bottom', 'board_bottom.png')):
    subprocess.run([KC, 'pcb', 'render', '--side', side, '--width', '900', '--height', '1200', '--quality', 'high', '-o', f'{DEST}/{fn}', pcb], env=ENV, capture_output=True)
subprocess.run([KC, 'sch', 'export', 'pdf', '-o', f'{DEST}/{NAME}_schematic.pdf', f'{OUT}/{NAME}.kicad_sch'], env=ENV, capture_output=True)
lines.append(f'mask web minimum {_min:.4f} mm, opening to other-net copper minimum {mask["min_trace"]} mm')
lines.append(f'package sha256 {sha}')
open(f'{DEST}/hole_report.txt', 'w', encoding='utf-8').write(hc_out + '\n')
open(f'{DEST}/verify_report.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
maskcheck.report(mask, open(f'{DEST}/mask_report.txt', 'w', encoding='utf-8'))
readme = f'''# MF KVM v3 ATX board, rev B: fab package

**Status: NOT ORDERED. Not built, not tested on any motherboard.** Passing the checks below means the files are consistent, nothing more.

Plugs straight into the FireBeetle's P1 header with 5 pins. No wires between the two boards.

| | |
|---|---|
| Size | {sx:.2f} x {sy:.2f} mm, L shape with a tongue and a notch, 2 layers, 1.0 mm, 1 oz, green mask |
| Upload | `{NAME}_gerber.zip`, sha256 `{sha[:16]}` |
| Assembly | Top side only. `BOM_JLC.csv`, `CPL_JLC.csv` |
| Parts cost | about US$ {cost:.2f} per board at JLC's single price |
| Pins, not in the BOM | 5 pieces of 0.64 mm round solid tinned copper wire (AWG 22), about 10 mm each, cut after soldering. **Not a 0.64 mm square header pin:** its diagonal is 0.905 mm against a 0.9 mm hole. A header housing does not fit either, the gap is only 1.2 mm |

**At order time:**
1. Check the rotation of U1, U2, U3 and J1 in JLC's preview. Pin 1 of each opto is on the +x side.
2. The narrow tongue is close to JLC's SMT minimum. If the order page asks for it, add edge rails.
3. Green mask only. On black or white the 0.13 mm rule applies, see `mask_report.txt`.

## Connections

| Hole | Net | FireBeetle P1 pin | y on the core (mm) | | J1 pin | Front panel |
|---|---|---|---|---|---|---|
| H1 | 3V3 | pin 2, 3V3 | 45.85 | | 1 | PWR switch + (C) |
| H2 | GND | pin 4, GND | 40.77 | | 2 | PWR switch - (E) |
| H3 | ATX_PWR | pin 6, GPIO28 | 35.69 | | 3 | RST switch + (C) |
| H4 | ATX_RST | pin 7, GPIO29 | 33.15 | | 4 | RST switch - (E) |
| H5 | ATX_LED | pin 8, GPIO30 | 30.61 | | 5 | Power LED - (K) |
| | | | | | 6 | Power LED + (A) |

P1 pins 1 (RST), 3 and 5 (NC) have no hole on this board. Silk on the bottom side names each hole. The bottom side faces the tray floor, the top side faces the core. `case/pinmap_check.py` proves the holes against the STEP.

Circuit and values are the same as `lay-board/`: 470 ohm into each drive opto, 270 ohm into the LED sense opto, 10k pull-down on ATX_LED. Footprints are the official KiCad SO-4_4.4x3.6mm_P2.54mm and JST_SH_SM06B-SRSS-TB. The JST mount tabs connect to nothing.

## Rebuild
```
sh build_atx.sh                 # generate, route, ERC, DRC
<v3cad python> fab_atx.py out ../fab_atx_b
```
'''
open(f'{DEST}/README.md', 'w', encoding='utf-8', newline='\n').write(readme)
print('RELEASE WRITTEN', DEST, f'{sha[:16]}')
