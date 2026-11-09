# -*- coding: utf-8 -*-
"""Schematic writer shared by gen_mini.py and the mutation tests.

Every symbol pin gets the electrical type from data/pin_types.json. There is no default: a pin without an entry stops
the run, so KiCad ERC can never again be fed 512 passive pins.

PWR_FLAG: a net that carries power_in pins but no power_out pin is fed through an inductor, a ferrite bead, a 0 ohm link or
the SD switch MOSFET, or it enters on a connector. KiCad cannot see through those, so such a net gets a flag, but only when
power_source() finds that path in the fitted parts. A power_in pin on a net with no traced source gets no flag, and ERC fails.
"""
import json
import os
import re
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PIN_TYPES = os.path.join(HERE, '..', 'data', 'pin_types.json')
TYPES = {'power_in', 'power_out', 'input', 'output', 'bidirectional', 'tri_state', 'passive', 'free', 'no_connect', 'open_collector', 'open_emitter', 'unspecified'}


def uid(seed=None):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'p4mini-' + seed)) if seed else str(uuid.uuid4())


def load_types(path=PIN_TYPES):
    return json.load(open(path, encoding='utf-8'))


def kind_of(p, T):
    for k, v in T['kinds'].items():
        m = v['match']
        if ('lcsc' in m and p.get('lcsc') == m['lcsc']) or ('lib' in m and p['lib'] == m['lib']):
            return k
    return None


def pin_type(p, n, T):
    """(type, name, source) for pin n of part p."""
    k = kind_of(p, T)
    if k is None:
        if p['lib'] in T['passive_libs'] and p['ref'][0] in 'RCLFT':
            return 'passive', n, f"two-terminal {T['passive_libs'][p['lib']]}"
        raise KeyError(f"{p['ref']} ({p['lib']}, {p.get('lcsc')}) has no entry in pin_types.json")
    e = T['kinds'][k]['pins'].get(str(n))
    if e is None:
        raise KeyError(f"{p['ref']} pin {n} ({k}) has no entry in pin_types.json")
    if e[1] not in TYPES:
        raise ValueError(f"{p['ref']}.{n}: bad type {e[1]}")
    return e[1], e[0], f"{T['kinds'][k]['doc']}: {e[2]}"


def ohms(value):
    """Resistance from a value string such as '33k 0.1% 0402', '0R 0402', '560 0402', '1M 0402'. None if not a resistor value."""
    m = re.match(r'\s*([\d.]+)\s*([kKM]?)(R?)\b', value)
    if not m or 'F' in value.split()[0] or '@' in value:
        return None
    return float(m[1]) * {'': 1, 'k': 1e3, 'K': 1e3, 'M': 1e6}[m[2]]


def series_links(parts, T):
    """Fitted elements that pass DC supply current: inductors, ferrite beads, resistors of 1 ohm or less, the AO3401A channel."""
    out = []
    for p in parts:
        if p['dnp']:
            continue
        r = p['ref']
        if kind_of(p, T) == 'AO3401A':
            out.append((r, p['nets']['2'], p['nets']['3']))
        elif r.startswith(('L', 'FB')) and len(p['nets']) == 2:
            out.append((r, p['nets']['1'], p['nets']['2']))
        elif r.startswith('R') and ohms(p['value']) is not None and ohms(p['value']) <= 1.0:
            out.append((r, p['nets']['1'], p['nets']['2']))
    return out


def power_source(net, parts, T, indirect=False):
    """Path from net to a power_out pin or an external supply pin, through series_links. Returns a list of steps or None.
    indirect: ignore a power_out pin sitting on net itself, so only a source behind a link or a connector counts."""
    drivers = {}
    for p in parts:
        if p['dnp']:
            continue
        for n, m in p['nets'].items():
            if pin_type(p, n, T)[0] == 'power_out':
                drivers.setdefault(m, f"{p['ref']}.{n} power_out")
            key = f"{p['ref']}.{n}"
            if key in T['external']:
                drivers.setdefault(m, f"{key} external: {T['external'][key]['src']}")
    links = series_links(parts, T)
    seen, todo = {net}, [(net, [])]
    while todo:
        cur, path = todo.pop(0)
        if cur in drivers and not (indirect and cur == net and drivers[cur].endswith('power_out')):
            return path + [drivers[cur]]
        for r, a, b in links:
            for x, y in ((a, b), (b, a)):
                if x == cur and y not in seen and not y.startswith('unconnected'):
                    seen.add(y)
                    todo.append((y, path + [f'{r} to {y}']))
    return None


def flags_needed(parts, T):
    """{net: path} for every net with a power_in pin. path is the source found behind a link or a connector, which gets a
    PWR_FLAG; None means no such source (no flag: a net with no power_out pin of its own then fails ERC). A net with its own
    power_out pin AND a flag has two sources, which ERC reports as power_out against power_out."""
    pin_in = set()
    for p in parts:
        for n, m in p['nets'].items():
            if not m.startswith('unconnected') and not p['dnp'] and pin_type(p, n, T)[0] == 'power_in':
                pin_in.add(m)
    return {m: power_source(m, parts, T, indirect=True) for m in sorted(pin_in)}


def write(parts, out, name, T=None, erc_settings=True):
    """Writes <out>/<name>.kicad_sch and <out>/mini.kicad_sym. parts: gen_mini parts or design.json parts (ref, value, lcsc, lib, dnp, nets[, pads]).
    Returns {net: path or None} for the PWR_FLAG decisions."""
    T = T or load_types()
    root = uid('root')
    sy, inst, labels = [], [], []
    GX, GY = 30.48, 30.48
    cx, cy = GX, GY
    for p in parts:
        pins = list(dict.fromkeys(q['n'] for q in p['pads'])) if 'pads' in p else list(p['nets'])
        h = max(len(pins) * 2.54 + 2.54, 7.62)
        if cy + h > 390:
            cy, cx = GY, cx + 66.04
        sid = 'S_' + p['ref']
        pin_def = []
        for i, n in enumerate(pins):
            t, _, _ = pin_type(p, n, T)
            pin_def.append(f'(pin {t} line (at -7.62 {-i * 2.54:g} 0) (length 2.54) (name "{n}" (effects (font (size 1 1)))) (number "{n}" (effects (font (size 1 1)))))')
        sy.append(f'''(symbol "{sid}" (pin_names (offset 0.5)) (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "{p['ref'][0]}" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "{sid}" (at 0 5 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "{sid}_0_1" (rectangle (start -5.08 1.27) (end 7.62 {-(len(pins) - 1) * 2.54 - 1.27:g}) (stroke (width 0.2) (type default)) (fill (type background))))
      (symbol "{sid}_1_1" {' '.join(pin_def)})
    )''')
        x, y = cx, cy
        uu = ' '.join(f'(pin "{n}" (uuid "{uid()}"))' for n in pins)
        inst.append(f'''(symbol (lib_id "mini:{sid}") (at {x:g} {y:g} 0) (unit 1) (exclude_from_sim no) (in_bom {'no' if p['lib'] == 'TP_1.0' else 'yes'}) (on_board yes) (dnp {'yes' if p['dnp'] and p['lib'] != 'TP_1.0' else 'no'}) (uuid "{uid('sym-' + p['ref'])}")
    (property "Reference" "{p['ref']}" (at {x + 1:g} {y - 3:g} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{p['value']}" (at {x + 10:g} {y:g} 0) (effects (font (size 1 1)) (justify left)))
    (property "Footprint" "mini:{p['lib']}" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "LCSC" "{p['lcsc']}" (at {x:g} {y:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    {uu}
    (instances (project "{name}" (path "/{root}" (reference "{p['ref']}") (unit 1))))
  )''')
        for i, n in enumerate(pins):
            px, py = x - 7.62, y + i * 2.54
            net = p['nets'][n]
            if net.startswith('unconnected-'):
                labels.append(f'(no_connect (at {px:g} {py:g}) (uuid "{uid()}"))')
            else:
                labels.append(f'(global_label "{net}" (shape passive) (at {px:g} {py:g} 180) (fields_autoplaced yes) (effects (font (size 1 1)) (justify right)) (uuid "{uid()}"))')
        cy = round((cy + h + 7.62) / 2.54) * 2.54
    # power flags, one column to the right of the parts
    flags = flags_needed(parts, T)
    fx, fy = cx + 66.04, GY
    flag_lib = '''(symbol "mini:PWR_FLAG" (pin_names (offset 0) (hide yes)) (exclude_from_sim yes) (in_bom no) (on_board no)
      (property "Reference" "#FLG" (at 0 2.54 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "the net is fed through a part KiCad cannot see through; tools/schgen.py power_source() traced it" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "PWR_FLAG_1_1" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
    )'''
    k = 0
    for net, path in flags.items():
        if path is None:
            continue
        k += 1
        ref = f'#FLG{k:02d}'
        inst.append(f'''(symbol (lib_id "mini:PWR_FLAG") (at {fx:g} {fy:g} 0) (unit 1) (exclude_from_sim yes) (in_bom no) (on_board no) (dnp no) (uuid "{uid('flag-' + net)}")
    (property "Reference" "{ref}" (at {fx:g} {fy - 3:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Value" "PWR_FLAG" (at {fx + 3:g} {fy:g} 0) (effects (font (size 1 1)) (justify left)))
    (property "Footprint" "" (at {fx:g} {fy:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "" (at {fx:g} {fy:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "{'; '.join(path).replace(chr(34), chr(39))}" (at {fx:g} {fy:g} 0) (hide yes) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "{uid()}"))
    (instances (project "{name}" (path "/{root}" (reference "{ref}") (unit 1))))
  )''')
        labels.append(f'(global_label "{net}" (shape passive) (at {fx:g} {fy:g} 180) (fields_autoplaced yes) (effects (font (size 1 1)) (justify right)) (uuid "{uid()}"))')
        fy += 7.62
    sch = f'''(kicad_sch (version 20250114) (generator "p4mini") (generator_version "9.0") (uuid "{root}") (paper "A1")
  (title_block (title "P4 KVM Mini") (rev "A") (comment 1 "ESP32-P4-Module + TC358743 + GC9A01 harness") (comment 2 "pin types: data/pin_types.json"))
  (lib_symbols {' '.join(x.replace('(symbol "S_', '(symbol "mini:S_', 1) for x in sy)} {flag_lib})
  {' '.join(inst)}
  {' '.join(labels)}
  (sheet_instances (path "/" (page "1")))
)
'''
    open(f'{out}/{name}.kicad_sch', 'w', encoding='utf-8', newline='\n').write(sch)
    open(f'{out}/mini.kicad_sym', 'w', encoding='utf-8', newline='\n').write('(kicad_symbol_lib (version 20241209) (generator "p4mini") (generator_version "9.0")\n' + '\n'.join(sy) + '\n' + flag_lib.replace('"mini:PWR_FLAG"', '"PWR_FLAG"', 1) + '\n)\n')
    return flags


# ERC settings written into the .kicad_pro. KiCad ignores "Global label only appears once" by default; here it is a warning,
# so a pin cut off from its net (one label left) shows up in ERC as well as in verify.py.
ERC_SETTINGS = {'rule_severities': {'single_global_label': 'warning'}}
