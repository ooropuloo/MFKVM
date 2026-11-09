# -*- coding: utf-8 -*-
"""Independent checks on the saved board.

r7c rule: no expectation here may be "what the design currently is". Every expected value comes from one of
  - a vendor document (pin names, thresholds, supply ranges), held in data/pin_types.json with document and page,
  - the firmware that will run on the board (firmware/sdkconfig_evidence/sdkconfig.v2r7_rev3: which GPIO does what),
  - a calculation from those and from part values read off the board (regulator outputs from the fitted divider,
    resistor tolerance decoded from the manufacturer part number in stock.json),
  - an ASSUMPTION, marked as such in the printed line.
Connectivity is asserted pin to pin ("module pin GPIO7 meets TC358743 I2C_SDA"), never pin to a net name.
The board file is the truth for connectivity; design.json supplies values, fitted/not fitted and part numbers, and must
agree with the board pin for pin.

usage: verify.py <out_dir> <antmicro net (unused since r7c, kept for the call signature)> [skew limit mm] [--fast]
       --fast skips the Gerber-based mask, hole and body checks (used by tools/mutate.py for the electrical mutations).
"""
import hashlib
import itertools
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schgen

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
FAST = '--fast' in sys.argv
OUT = ARGS[0]
s = open(f'{OUT}/p4_kvm_mini.kicad_pcb', encoding='utf-8').read()
d = json.load(open(f'{OUT}/design.json', encoding='utf-8'))
T = schgen.load_types()
FW = os.path.join(HERE, '..', 'firmware', 'sdkconfig_evidence', 'sdkconfig.v2r7_rev3')
fails, warns = [], []


def check(ok, msg, level='FAIL'):
    tag = 'PASS ' if ok else level + ' '
    print(tag + msg)
    if not ok:
        (fails if level == 'FAIL' else warns).append(msg)


pads = {}
for m in re.finditer(r'\(footprint "mini:[^"]*"(.*?)(?=\n\s*\(footprint "|\Z)', s, re.S):
    b = m.group(1)
    r = re.search(r'\(property "Reference" "([^"]+)"', b)
    if not r:
        continue
    for q in re.finditer(r'\(pad "([^"]*)"\s+\w+\s+\w+.*?\(net (?:\d+ )?"([^"]*)"\)', b, re.S):
        pads[f'{r.group(1)}.{q.group(1)}'] = q.group(2)
print('pads with nets read back', len(pads))

parts = d['parts']
P = {p['ref']: p for p in parts}
FIT = {r: p for r, p in P.items() if not p['dnp']}
KIND = {r: schgen.kind_of(p, T) for r, p in P.items()}


def ptype(p, n):
    """Pin type from data/pin_types.json, None for a part number the table does not know (reported once below)."""
    try:
        return schgen.pin_type(p, n, T)[0]
    except KeyError:
        return None


_untyped = sorted({p['ref'] for p in parts for n in p['nets'] if ptype(p, n) is None})
check(not _untyped, f'every part on the board has its pins in data/pin_types.json {_untyped or ""}')
stock = {r[0]: r for r in json.load(open(f'{OUT}/stock.json', encoding='utf-8'))}

# design.json is what the schematic, ERC and the values below are built from: it must describe this board
_dj = {f"{p['ref']}.{n}": m for p in parts for n, m in p['nets'].items()}
_mh = sorted(k for k in pads if re.match(r'H\d+\.', k))   # r7f: mounting holes are plated GND pads (board_only footprints, not in design.json)
_diff = sorted(k for k in set(_dj) | set(pads) if k not in _mh and _dj.get(k) != pads.get(k) and not (str(_dj.get(k)).startswith('unconnected') and str(pads.get(k)).startswith('unconnected')))
check(not _diff, f'design.json and the board agree pin for pin ({len(pads)} pads) {_diff[:6] or ""}')
check(len(_mh) == len(d['board']['holes']) and all(pads[k] == 'GND' for k in _mh), f'r7f: every mounting hole is a plated pad on GND (lid and plate ground through the posts) {[(k, pads[k]) for k in _mh]}')


def _fp_block(ref):
    i_ = s.find('(property "Reference" "' + ref + '"')
    if i_ < 0:
        return ''
    return s[s.rfind('(footprint ', 0, i_):s.find('\n\t)', i_)]


def _fp_origin(b_):
    m_ = re.search(r'\(translate ([-\d.]+) ([-\d.]+)\)', b_) or re.search(r'\(at ([-\d.]+) ([-\d.]+)', b_[:b_.find('(property')])
    return (float(m_[1]), float(m_[2])) if m_ else None


# board edge: the Edge.Cuts lines (rectangle with 1.5 mm corner chamfers)
_edge = [tuple(map(float, m_.groups())) for m_ in re.finditer(r'\(gr_line\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)(?:(?!\(gr_).)*?\(layer "Edge.Cuts"\)', s, re.S)]


def _seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    t_ = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - x0 - t_ * dx, py - y0 - t_ * dy)


# JLC's copper-to-board-edge minimum is 0.2-0.3 mm (capabilities page, routed edge); this board keeps 0.3 mm (the r7f review fix)
_ring = []
for k in _mh:
    b_ = _fp_block(k.split('.')[0])
    o_ = _fp_origin(b_)
    sz = re.search(r'\(pad "1" thru_hole circle\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\)\s*\(size ([\d.]+) ([\d.]+)\)', b_)
    if not (o_ and sz and _edge):
        _ring.append((k, None, None))
        continue
    cx, cy, dia = o_[0] + float(sz[1]), o_[1] + float(sz[2]), max(float(sz[3]), float(sz[4]))
    _ring.append((k, dia, min(_seg_dist(cx, cy, *e_) for e_ in _edge) - dia / 2))
check(len(_ring) == len(_mh) > 0 and all(dia is not None and (dia <= 2.9 + 1e-6 or e_ >= 0.3 - 1e-6) for _, dia, e_ in _ring),
      f'r7f: mounting hole copper ring <= 2.9 mm or copper to the board edge >= 0.3 mm (REVIEW_r7f fix kept) {[(k, dia, round(e_, 3) if e_ is not None else None) for k, dia, e_ in _ring]}')


def net(pin):
    return pads.get(pin)


def connected(a, b):
    na, nb = net(a), net(b)
    return na is not None and na == nb and not na.startswith('unconnected')


members = defaultdict(list)       # fitted pins per net
for k, n in pads.items():
    ref, pin = k.split('.', 1)
    if ref in FIT and not n.startswith('unconnected'):
        members[n].append((ref, pin))

# ---------- resistor values and tolerances, from the part number JLC lists for the LCSC code


def tolerance(p):
    """Fraction, decoded from the manufacturer part number in stock.json. None if the code is not understood."""
    row = stock.get(p['lcsc'])
    mpn = str(row[1]) if row else ''
    if mpn.startswith(('0402WG', '0805W8')) and len(mpn) > 6:   # UNI-ROYAL 0402WG<tol> / 0805W8<tol>: F 1%, J 5% (UNI-ROYAL part numbering)
        return {'F': 0.01, 'J': 0.05, 'D': 0.005, 'B': 0.001}.get(mpn[6])
    if mpn.startswith('RT0402') and len(mpn) > 6:        # Yageo RT0402<tol>R: B 0.1%, D 0.5%, F 1% (Yageo RT series part numbering)
        return {'B': 0.001, 'C': 0.0025, 'D': 0.005, 'F': 0.01}.get(mpn[6])
    if mpn.startswith('AR02') and len(mpn) > 4:          # Viking AR02<tol>: B 0.1%, D 0.5%, F 1%
        return {'B': 0.001, 'D': 0.005, 'F': 0.01}.get(mpn[4])
    if re.match(r'RC-0\dW\d+R\d[FJ]T$', mpn):            # r7f, UNI-ROYAL RC-01W33R0FT: <value>R<d><tol>T, F 1%, J 5%
        return {'F': 0.01, 'J': 0.05}.get(mpn[-2])
    return None


RES = []   # (ref, net a, net b, rmin, rmax)
_unknown_tol = []
for r, p in FIT.items():
    if not r.startswith('R'):
        continue
    v = schgen.ohms(p['value'])
    if v is None:
        _unknown_tol.append((r, p['value']))
        continue
    a, b = net(f'{r}.1'), net(f'{r}.2')
    if v == 0:
        RES.append((r, a, b, 0.0, 0.05))   # 0 ohm jumper: 50 mOhm max ASSUMED (UNI-ROYAL jumper spec not read)
        continue
    t = tolerance(p)
    if t is None:
        _unknown_tol.append((r, stock.get(p['lcsc'], [None, None])[1]))
        t = 0.05
    RES.append((r, a, b, v * (1 - t), v * (1 + t)))
check(not _unknown_tol, f'every fitted resistor has a value and a tolerance decoded from its part number {_unknown_tol or ""}')
RNOM = {r: (lo + hi) / 2 for r, a, b, lo, hi in RES}
LINKS = schgen.series_links(parts, T)

# ---------- rails: external supplies, regulator outputs from their fitted dividers, then through links
RAIL = {}
RSRC = {}
for pin, e in T['external'].items():
    n = net(pin)
    if n and not n.startswith('unconnected'):
        RAIL[n] = tuple(e['rail'])
        RSRC[n] = f'{pin}: {e["src"]}'


def solve(nodes, edges, fixed, inject):
    """DC node voltages. nodes: unknown nets. edges: (a, b, R). fixed: {net: V}. inject: {net: current out of the node, A}."""
    import numpy as np
    idx = {n: i for i, n in enumerate(nodes)}
    G = np.zeros((len(nodes), len(nodes)))
    I = np.zeros(len(nodes))
    for a, b, R in edges:
        g = 1.0 / max(R, 1e-6)
        for x, y in ((a, b), (b, a)):
            if x in idx:
                G[idx[x], idx[x]] += g
                if y in idx:
                    G[idx[x], idx[y]] -= g
                else:
                    I[idx[x]] += g * fixed[y]
    for n, i in inject.items():
        if n in idx:
            I[idx[n]] -= i
    v = np.linalg.solve(G, I)
    return {n: v[idx[n]] for n in nodes}


def component(start, stop):
    """Nets joined to start through fitted resistors, not passing through nets in stop. Returns (interior nets, boundary nets, edges)."""
    inner, bound, seen, todo = [start], set(), {start}, [start]
    edges = []
    while todo:
        cur = todo.pop()
        for r, a, b, lo, hi in RES:
            if cur not in (a, b):
                continue
            o = b if cur == a else a
            if o is None or o.startswith('unconnected'):
                continue
            if (r, a, b, lo, hi) not in edges:
                edges.append((r, a, b, lo, hi))
            if o in stop:
                bound.add(o)
            elif o not in seen:
                seen.add(o)
                inner.append(o)
                todo.append(o)
    return inner, bound, edges


def corners(edges, extra=()):
    """Every combination of resistor min/max and of the extra two-valued parameters."""
    choices = [(e[3], e[4]) for e in edges] + list(extra)
    if len(choices) > 14:
        raise RuntimeError(f'too many corners: {len(choices)}')
    return itertools.product(*choices)


def buck_out(ref):
    """SY8089 output range from its fitted feedback network: VREF, IFB and every resistor at its tolerance limits."""
    L = T['limits']['SY8089']['5']['buck']
    lx = net(f'{ref}.{L["lx"]}')
    ind = [(r, n) for r, n in members[lx] if r.startswith('L')]
    if len(ind) != 1:
        return None, f'{ref}: LX net {lx} has {len(ind)} inductors'
    lr = ind[0][0]
    out = net(f'{lr}.2') if net(f'{lr}.1') == lx else net(f'{lr}.1')
    fb = net(f'{ref}.5')
    gnd = net(f'{ref}.2')
    inner, bound, edges = component(fb, {out, gnd} | set(RAIL))
    if bound - {out, gnd} or out not in bound or gnd not in bound:
        return None, f'{ref}: feedback network from {fb} reaches {sorted(bound)}, needs exactly {out} and {gnd}'
    vals = []
    for c in corners(edges, [tuple(L['vref']), (-L['ifb'], L['ifb'])]):
        rs, vref, ifb = c[:len(edges)], c[-2], c[-1]
        ed = [(e[1], e[2], R) for e, R in zip(edges, rs)]
        f0 = solve(inner, ed, {out: 0.0, gnd: 0.0}, {fb: ifb})[fb]
        f1 = solve(inner, ed, {out: 1.0, gnd: 0.0}, {fb: ifb})[fb]
        vals.append((vref - f0) / (f1 - f0))
    desc = f"{ref} via {lr}: FB network {', '.join(e[0] for e in edges)}, VREF {L['vref']}, IFB +-{L['ifb'] * 1e9:.0f} nA"
    return (out, (min(vals), max(vals))), desc


# nets driven by a power_out pin (regulator outputs, switch nodes, the module's LDO) take no rail from a neighbour through a link
DRIVEN = {net(f"{p['ref']}.{n}") for p in parts if not p['dnp'] for n in p['nets'] if ptype(p, n) == 'power_out'}
_done = set()
for _ in range(6):
    for r, k in KIND.items():
        if r not in FIT or r in _done:
            continue
        if k == 'SY8089' and net(f'{r}.4') in RAIL:
            res, desc = buck_out(r)
            _done.add(r)
            if res and res[0] not in RAIL:
                RAIL[res[0]] = res[1]
                RSRC[res[0]] = desc
            elif not res:
                RSRC.setdefault(f'?{r}', desc)
        if k == 'TLV73325' and net(f'{r}.1') in RAIL and net(f'{r}.5') not in RAIL:
            RAIL[net(f'{r}.5')] = tuple(T['limits']['TLV73325']['5']['fixed'])
            RSRC[net(f'{r}.5')] = f"{r} fixed output: {T['limits']['TLV73325']['5']['src']}"
        # r7f: the 5 V input eFuse passes IN to OUT (RON drop ignored here) and clamps OUT at VCLAMP max when IN rises above VOVC
        if k == 'TPS259531' and net(f'{r}.3') in RAIL and net(f'{r}.5') not in RAIL:
            _ef = T['limits']['TPS259531']['5']['efuse']
            _vin = RAIL[net(f'{r}.3')]
            RAIL[net(f'{r}.5')] = (min(_vin[0], _ef['clamp'][0]), min(_vin[1], _ef['clamp'][1]))
            RSRC[net(f'{r}.5')] = f"{r} eFuse output from {net(f'{r}.3')}: {T['limits']['TPS259531']['5']['src']}"
    for r, a, b in LINKS:
        for x, y in ((a, b), (b, a)):
            if x in RAIL and y not in RAIL and y not in DRIVEN and not y.startswith('unconnected'):
                RAIL[y] = RAIL[x]
                RSRC[y] = f'{x} through {r} (drop not included here; see the drop terms in the supply rules)'
print('RAILS (derived, V)')
for n in sorted(RAIL, key=lambda x: -RAIL[x][1]):
    print(f'  {n:10s} {RAIL[n][0]:.4f} - {RAIL[n][1]:.4f}   {RSRC.get(n, "")}')
for k, v in RSRC.items():
    if k.startswith('?'):
        check(False, 'regulator output could not be derived: ' + v)

# ---------- drops between a rail node and the pin, with their sources. Only lower limits use them.
# AVDD12: FB3 DCR after test, FB3 to ball and R65 to FB3 copper at 70 C, at the worst AVDD12 current (current_budget.md, tools/r7/budget_r7.py),
# plus the R66 local-fallback pull of the sense node (route drop x Rline/(R66 + Rline)).
_r66 = RNOM.get('R66', 100.0)
DROP = {'AVDD12': (0.09 + (0.0568 + 0.0119) * 1.197) * 0.1244 + 0.0251 * 0.362 / (_r66 + 0.362),
        'BEAD': 0.05}   # FB4, FB5: allowance carried from r7 (current_budget.md: VDDC and VDD_MIPI bead drop well under 50 mV)


_LVL_FAIL = []


def level(n, leak=True, rails=False):
    """Static DC range of a net from the rails it is tied to through fitted resistors (pull-ups, dividers). None if no rail.
    Input leakage: TC358743 inputs +-10 uA (Toshiba p16 IILH/IILL), P4 inputs 50 nA (ESP32-P4 datasheet v0.7 p89 IIH/IIL).
    A leaking pin cannot lift a node above its own supply or above the rails it is tied to, so the result is clamped to the highest of those.
    rails=True also returns the set of rail nets the level comes from."""
    if n in RAIL:
        return (RAIL[n], {n}) if rails else RAIL[n]
    inner, bound, edges = component(n, set(RAIL))
    if not bound:
        return (None, set()) if rails else None
    inj = []
    top = [RAIL[b][1] for b in bound]
    for x in inner:
        for ref, pin in members[x]:
            if KIND.get(ref) == 'TC358743XBG' and leak:
                inj.append((x, 10e-6))
            elif KIND.get(ref) == 'ESP32-P4-Module' and leak:
                inj.append((x, 50e-9))
            else:
                continue
            dom = T['domains'].get(KIND[ref], {}).get('pins', {}).get(pin)
            if dom and pin_of(ref, dom) in RAIL:
                top.append(RAIL[pin_of(ref, dom)][1])
    vals = []
    extra = [tuple(RAIL[b]) for b in sorted(bound)] + [(-i, i) for _, i in inj]
    if len(edges) + len(extra) > 14:   # r7f: corners() would refuse; record it as a failed check instead of crashing
        _LVL_FAIL.append((n, len(edges), sorted(bound)))
        return (None, set()) if rails else None
    for c in corners(edges, extra):
        rs = c[:len(edges)]
        rv = c[len(edges):len(edges) + len(bound)]
        iv = c[len(edges) + len(bound):]
        fixed = dict(zip(sorted(bound), rv))
        injd = defaultdict(float)
        for (x, _), i in zip(inj, iv):
            injd[x] += i
        vals.append(solve(inner, [(e[1], e[2], R) for e, R in zip(edges, rs)], fixed, injd)[n])
    lo = max(float(min(vals)), min(min(RAIL[b][0] for b in bound), 0.0))
    hi = min(float(max(vals)), max(top))
    return ((lo, hi), set(bound)) if rails else (lo, hi)


def signal_group(n):
    """Nets joined to n through fitted resistors of 100 ohm or less (series terminations such as R24)."""
    seen, todo = {n}, [n]
    while todo:
        cur = todo.pop()
        for r, a, b, lo, hi in RES:
            if hi <= 101 and cur in (a, b):
                o = b if cur == a else a
                if o not in seen and o not in RAIL and not o.startswith('unconnected'):
                    seen.add(o)
                    todo.append(o)
    return seen


def pin_of(ref, other):
    return net(f'{ref}.{other}')


def domain_max(n, exclude):
    """Highest supply among the IC pins on the signal group of n that can put a voltage on it (each bounded by its own supply domain).
    An input only senses, so it does not count, with one exception: the TC358743 HDMI receiver inputs, whose on-chip sink termination
    holds the TMDS lines near AVDD33 (HDMI receiver termination; Toshiba p10 lists the HDMI PHY on AVDD33)."""
    best, who = None, []
    for x in signal_group(n):
        for ref, pin in members[x]:
            if f'{ref}.{pin}' == exclude:
                continue
            t = ptype(P[ref], pin)
            if t == 'input' and not (KIND.get(ref) == 'TC358743XBG' and T['kinds']['TC358743XBG']['pins'][pin][0].startswith('HDMI')):
                continue
            dom = T['domains'].get(KIND.get(ref), {}).get('pins', {}).get(pin)
            if dom:
                rail = RAIL.get(pin_of(ref, dom))
                if rail and (best is None or rail[1] >= best):
                    best = rail[1]
                    who.append(f'{ref}.{pin} on {pin_of(ref, dom)}')
    return best, who


RULES = []  # (pin, net, text, src, ok, level)


def rule(pin, text, src, ok, level='FAIL'):
    RULES.append((pin, net(pin), text, src, bool(ok), level))


def ref_rail(ref, spec):
    if 'abs' in spec:
        return None
    return RAIL.get(pin_of(ref, spec['of']))


for ref, k in sorted(KIND.items()):
    if ref not in FIT or k not in T['limits']:
        continue
    for pin, L in T['limits'][k].items():
        P_ = f'{ref}.{pin}'
        n = net(P_)
        src = L['src']
        lvl = L.get('level', 'FAIL')
        if n is None or n.startswith('unconnected'):
            if any(x in L for x in ('supply', 'vih', 'vil', 'rext', 'pullup', 'pullup_of')):
                rule(P_, 'pin has a limit but is not connected', src, False)
            continue
        if 'supply' in L:
            lo_s, hi_s = L['supply']
            rr = RAIL.get(n)
            if rr is None:
                rule(P_, f'supply pin on {n}, which has no derived supply (unpowered)', src, False)
            else:
                drop = DROP[L['drop']] if 'drop' in L else 0.0
                rule(P_, f'supply {lo_s}-{hi_s} V: {n} {rr[0] - drop:.4f}-{rr[1]:.4f} V' + (f' (after {L["drop"]} drop {drop * 1000:.1f} mV)' if drop else ''),
                     src, lo_s <= rr[0] - drop and rr[1] <= hi_s, lvl)
                if 'abs' in L:
                    rule(P_, f'absolute max {L["abs"]} V: {rr[1]:.3f} V', src, rr[1] <= L['abs'])
        if 'vih' in L:
            spec = L['vih']
            need = spec['abs'] if 'abs' in spec else (spec['k'] * ref_rail(ref, spec)[1] if ref_rail(ref, spec) else None)
            drv = [(r2, p2) for x in signal_group(n) for r2, p2 in members[x] if 'voh' in T['limits'].get(KIND.get(r2), {}).get(p2, {})]
            if need is None:
                rule(P_, f'VIH reference pin {spec.get("of")} has no supply', src, False)
            elif drv:
                r2, p2 = drv[0]
                vs = T['limits'][KIND[r2]][p2]['voh']
                rr = RAIL.get(pin_of(r2, vs['of']))
                voh = vs['k'] * rr[0] if rr else None
                rule(P_, f'driven by {r2}.{p2}: VOH {vs["k"]} x {pin_of(r2, vs["of"])} >= {voh if voh is None else round(voh, 3)} V against VIH {need:.3f} V',
                     src + '; ' + T['limits'][KIND[r2]][p2]['src'], voh is not None and voh >= need)
            else:
                lv = level(n)
                rule(P_, f'static level of {n} {"unknown" if lv is None else f"{lv[0]:.3f}-{lv[1]:.3f} V"} against VIH {need:.3f} V', src, lv is not None and lv[0] >= need)
        if 'vil' in L:
            spec = L['vil']
            rr = ref_rail(ref, spec)
            lv = level(n)
            lim = spec['k'] * rr[0] if rr else None
            rule(P_, f'must be low: {n} {"unknown" if lv is None else f"{lv[1]:.3f}"} V against VIL {lim if lim is None else round(lim, 3)} V', src, lv is not None and lim is not None and lv[1] <= lim)
        if 'vmax' in L:
            spec = L['vmax']
            lv, lrails = level(n, rails=True)
            dm, who = domain_max(n, P_)
            highs = [v for v in (lv[1] if lv else None, dm) if v is not None]
            hv = max(highs) if highs else None
            srcs = set(lrails) | {w.split(' on ')[1] for w in who}
            if 'abs' in spec:
                lim, how = spec['abs'], 'absolute'
            else:
                refn = pin_of(ref, spec['of'])
                if refn not in RAIL:
                    lim, how = None, 'reference unpowered'
                elif srcs and srcs <= {refn}:
                    # every source of the high level is the reference rail itself: they move together, so compare at the same instant
                    lim, how = RAIL[refn][1] + spec['add'], f'{refn} + {spec["add"]} (same rail, same instant)'
                else:
                    lim, how = RAIL[refn][0] + spec['add'], f'{refn} at its minimum + {spec["add"]}'
            rule(P_, f'highest voltage on {n} {"unknown" if hv is None else f"{hv:.3f}"} V (static {lv and round(lv[1], 3)}, drivers {who[-1:] or "none"}) against {lim if lim is None else round(lim, 3)} V ({how})',
                 src, hv is not None and lim is not None and hv <= lim)
        if 'rext' in L:
            val, tol, of = L['rext']
            hit = [(r, lo, hi) for r, a, b, lo, hi in RES if {a, b} == {n, pin_of(ref, of)}]
            ok = len(hit) == 1 and abs(RNOM[hit[0][0]] - val) <= val * 1e-6 and (hit[0][2] - hit[0][1]) / 2 / RNOM[hit[0][0]] <= tol + 1e-9
            rule(P_, f'{val:g} ohm +-{tol * 100:g}% to {pin_of(ref, of)}: {[(h[0], round(h[1]), round(h[2])) for h in hit]}', src, ok)
        if 'pullup_of' in L:
            want = pin_of(ref, L['pullup_of'])
            hit = [r for r, a, b, lo, hi in RES if {a, b} == {n, want}]
            rule(P_, f'pull-up from {n} to {want} (pin {L["pullup_of"]}): {hit}', src, bool(hit))
        if 'pullup' in L:
            vdd = RAIL.get(pin_of(ref, '85'))
            lv = level(n)
            rule(P_, f'pulled high: {n} static {lv and (round(float(lv[0]), 3), round(float(lv[1]), 3))} V, VIH_nRST 0.75 x VDD = {vdd and round(0.75 * vdd[1], 3)} V', src,
                 lv is not None and vdd is not None and lv[0] >= 0.75 * vdd[1])
        if 'load_pf' in L:
            grp = signal_group(n)
            caps = []
            for x in grp:
                for r2, p2 in members[x]:
                    if r2.startswith('C') and r2 in FIT:
                        mm = re.match(r'([\d.]+)(p|n|u)F', FIT[r2]['value'])
                        caps.append((r2, float(mm[1]) * {'p': 1, 'n': 1e3, 'u': 1e6}[mm[2]]))
            # OSC_OUT + TC_REFCLK 4.96 mm of 0.127 mm microstrip at 0.108 pF/mm (s3_solver: 5.93 ps/mm / 55 ohm), pads about 1.1 pF,
            # REFCLK input 5 pF ASSUMED (not in the Toshiba sheet; P4-class CMOS inputs are 2 pF, ESP32-P4 p89)
            est = 4.96 * 0.108 + 1.1 + 5.0
            tot = est + sum(c for _, c in caps)
            rule(P_, f'output load {tot:.1f} pF (fitted {caps or "none"} + {est:.1f} trace/pad/input estimate) against {L["load_pf"]} pF', src, tot <= L['load_pf'])
        if 'vgs_max' in L:
            src_rail = RAIL.get(pin_of(ref, '2'))
            dm, _ = domain_max(n, P_)
            lv = level(n)
            gmax = max(v for v in (dm, lv and lv[1], 0.0) if v is not None)
            ok = src_rail is not None and max(src_rail[1], gmax) <= L['vgs_max'] and lv is not None
            rule(P_, f'|VGS| at most {max(src_rail[1] if src_rail else 0, gmax):.2f} V against {L["vgs_max"]} V; gate level with the GPIO released: {lv and round(lv[0], 3)} V (must be defined)',
                 src + '; a floating gate leaves the SD supply undefined while GPIO45 is high-Z after reset', ok)

print('ELECTRICAL RULES (pin, net found, rule, source)')
for pin, got, text, src, ok, level_ in RULES:
    print(f"  {'ok  ' if ok else level_ + ' '} {pin:7s} {str(got):10s} {text}  [{src}]")
_rf = [r for r in RULES if not r[4] and r[5] == 'FAIL']
_rw = [r for r in RULES if not r[4] and r[5] == 'WARN']
check(not _rf, f'electrical rule table: {len(RULES)} rules from data/pin_types.json, {len(_rf)} failed {" ".join(r[0] for r in _rf)}')
for r in _rw:
    check(False, f'{r[0]}: {r[2]} [{r[3]}]', 'WARN')
# every fitted part with a datasheet limit table was evaluated (a part swapped to another LCSC code loses its limits and is caught here)
_ic = [r for r in FIT if r[0] in 'UQY']
_nolim = [r for r in _ic if KIND.get(r) is None or (KIND[r] not in T['limits'] and KIND[r] not in ('EL3H7',))]
check(not _nolim, f'every fitted IC, transistor and oscillator is a known part with its own limit table {_nolim or ""}')

# ---------- driver conflicts on the board netlist (the same matrix ERC uses for these two types, but on the board's own pads)
_drv = defaultdict(list)
for p in parts:
    if p['dnp']:
        continue
    for n_ in p['nets']:
        t = ptype(p, n_)
        m_ = net(f"{p['ref']}.{n_}")
        if t in ('output', 'power_out') and m_ and not m_.startswith('unconnected'):
            _drv[m_].append(f"{p['ref']}.{n_} {t}")
_two = {k: v for k, v in _drv.items() if len(v) > 1}
check(not _two, f'no net has two push-pull or power outputs (pin types from data/pin_types.json) {_two or ""}')

# ---------- every pin in the pin table: power and ground pins on the right rail, connectivity by vendor pin function
WSN = {n: e[0] for n, e in T['kinds']['ESP32-P4-Module']['pins'].items()}
U1 = next((r for r, k in KIND.items() if k == 'ESP32-P4-Module'), None)
U7 = next((r for r, k in KIND.items() if k == 'TC358743XBG'), None)
TCN = {e[0]: b for b, e in T['kinds']['TC358743XBG']['pins'].items()}   # ball name -> ball
gnd = net('J5.A1B12')
_bad = []
for r, k in KIND.items():
    if k is None:
        continue
    for pin, e in T['kinds'][k]['pins'].items():
        if e[0] in ('GND', 'VSS', 'VPGM') or (k in ('HDMI-001S',) and e[0].endswith(('_SH', 'GND', 'SHELL'))) or (k == 'U.FL' and e[0] == 'GND'):
            if net(f'{r}.{pin}') != gnd:
                _bad.append((f'{r}.{pin}', e[0], net(f'{r}.{pin}')))
for r, k in KIND.items():
    if k in ('USB-C_HX_16P',):
        for pin in ('1', '2', '3', '4', 'A1B12', 'B1A12'):
            if net(f'{r}.{pin}') != gnd:
                _bad.append((f'{r}.{pin}', 'GND/shell', net(f'{r}.{pin}')))
    if k == 'microSD':
        for pin in ('6', 'SH1', 'SH2', 'SH3', 'SH4'):
            if net(f'{r}.{pin}') != gnd:
                _bad.append((f'{r}.{pin}', 'VSS/shell', net(f'{r}.{pin}')))
check(not _bad, f'every ground pin named in the vendor tables is on board ground (net of J5 GND) {_bad or ""}')

# firmware: which GPIO the code drives, and the vendor pin it must reach
fw = dict(re.findall(r'^(CONFIG_KVM_\w+_GPIO)=(-?\d+)$', open(FW, encoding='utf-8').read(), re.M))
GPIO_PIN = {nm: n for n, nm in WSN.items()}


def gp(cfg):
    g = int(fw[cfg])
    return f'{U1}.{GPIO_PIN[f"GPIO{g}"]}' if g >= 0 else None


def via_res(a, b):
    """a and b joined by exactly one fitted resistor (not 0 ohm)."""
    return any({net(a), net(b)} == {x, y} and lo > 1 for r, x, y, lo, hi in RES)


J6 = next(r for r, k in KIND.items() if k == 'JST_SM08B')
J4 = next(r for r, k in KIND.items() if k == 'JST_SM06B')
J7 = next(r for r, k in KIND.items() if k == 'microSD')
J2 = next(r for r, k in KIND.items() if k == 'HDMI-001S')
J8 = next(r for r, k in KIND.items() if k == 'U.FL')
OPT = sorted(r for r, k in KIND.items() if k == 'EL3H7')
Q1 = next(r for r, k in KIND.items() if k == 'AO3401A')
U6 = next(r for r, k in KIND.items() if k == 'TCA9517A')
# GC9A01 harness order from the Waveshare 1.28inch LCD Module wiki: VCC GND DIN CLK CS DC RST BL (README, J6 section)
LCD = {'CONFIG_KVM_DISP_MOSI_GPIO': '3', 'CONFIG_KVM_DISP_SCLK_GPIO': '4', 'CONFIG_KVM_DISP_CS_GPIO': '5', 'CONFIG_KVM_DISP_DC_GPIO': '6', 'CONFIG_KVM_DISP_RST_GPIO': '7'}
# microSD contacts, SD Physical Layer Simplified Spec microSD pin assignment: 1 DAT2 2 CD/DAT3 3 CMD 4 VDD 5 CLK 6 VSS 7 DAT0 8 DAT1
SDP = {'CONFIG_KVM_SD_CLK_GPIO': '5', 'CONFIG_KVM_SD_CMD_GPIO': '3', 'CONFIG_KVM_SD_D0_GPIO': '7', 'CONFIG_KVM_SD_D1_GPIO': '8', 'CONFIG_KVM_SD_D2_GPIO': '1', 'CONFIG_KVM_SD_D3_GPIO': '2'}
fwbad = []
for cfg, ball in (('CONFIG_KVM_I2C_SDA_GPIO', 'I2C_SDA'), ('CONFIG_KVM_I2C_SCL_GPIO', 'I2C_SCL'), ('CONFIG_KVM_TC358743_RST_GPIO', 'RESETN')):
    if not connected(gp(cfg), f'{U7}.{TCN[ball]}'):
        fwbad.append((cfg, fw[cfg], ball))
# r7f: the LCD DIN/CLK and the six SD lines pass one series resistor (33 / 22 ohm); up to 100 ohm in series is still the same signal
def _series_ok(a, b):
    return connected(a, b) or any({net(a), net(b)} == {x, y} and 1 < lo and hi <= 100 for r, x, y, lo, hi in RES)


for cfg, jp in LCD.items():
    if not _series_ok(gp(cfg), f'{J6}.{jp}'):
        fwbad.append((cfg, fw[cfg], f'{J6}.{jp}'))
for cfg, jp in SDP.items():
    if not _series_ok(gp(cfg), f'{J7}.{jp}'):
        fwbad.append((cfg, fw[cfg], f'{J7}.{jp}'))
if not connected(gp('CONFIG_KVM_SD_PWR_GPIO'), f'{Q1}.1'):
    fwbad.append(('SD_PWR', 'gate'))
# ATX: PWR and RST drive an opto LED anode through a resistor (active high, CONFIG_KVM_ATX_ACTIVE_HIGH), LED reads an opto emitter
_atx = {}
for cfg in ('CONFIG_KVM_ATX_PWR_GPIO', 'CONFIG_KVM_ATX_RST_GPIO'):
    hit = [o for o in OPT if via_res(gp(cfg), f'{o}.1') and net(f'{o}.2') == gnd]
    _atx[cfg] = hit
    if len(hit) != 1:
        fwbad.append((cfg, fw[cfg], 'opto anode through a resistor, cathode to GND', hit))
_led = [o for o in OPT if connected(gp('CONFIG_KVM_ATX_LED_GPIO'), f'{o}.3')]
if len(_led) != 1:
    fwbad.append(('CONFIG_KVM_ATX_LED_GPIO', 'opto emitter', _led))
for cfg in ('CONFIG_KVM_BRIDGE_INT_GPIO', 'CONFIG_KVM_SD_CD_GPIO'):
    if fw.get(cfg) != '-1':
        fwbad.append((cfg, fw.get(cfg), 'firmware uses a pin this check does not know'))
check(not fwbad, f'firmware sdkconfig.v2r7_rev3: I2C 7/8, bridge reset 23, LCD 9-13, SD 39-45, ATX 2/4/5 each reach the vendor pin they drive {fwbad or ""}')
# r7f: the 5 V input goes through the eFuse, and CEC has its ESD clamp
_ef = [r for r, k in KIND.items() if k == 'TPS259531' and r in FIT]
_j5 = next((r for r, k in KIND.items() if k == 'USB-C_HX_16P' and net(f'{r}.A1B12') == gnd and any(net(f'{r}.{q}') in (net(f'{e}.3') for e in _ef) for q in ('A4B9', 'B4A9'))), None) if _ef else None
check(len(_ef) == 1 and _j5 is not None and net(f'{_j5}.A4B9') == net(f'{_j5}.B4A9') == net(f'{_ef[0]}.3') == net(f'{_ef[0]}.4') and net(f'{_ef[0]}.5') == '5V'
      and net(f'{_ef[0]}.3') != '5V' and not any(p_['ref'] != _ef[0] and FIT.get(p_['ref']) and net(f"{p_['ref']}.1") in (net(f'{_ef[0]}.3'),) and net(f"{p_['ref']}.2") == '5V' for p_ in parts),
      f'r7f: J5 VBUS reaches 5V only through the eFuse {_ef} (IN {net(f"{_ef[0]}.3") if _ef else None}, OUT {net(f"{_ef[0]}.5") if _ef else None})')
if _ef:
    _u = _ef[0]
    _nin, _nout, _nen, _ndv, _nilm = (net(f'{_u}.{k}') for k in ('3', '5', '2', '1', '7'))
    _others = lambda n_: [(r, k) for r, k in members[n_] if r != _u]
    # any fitted part (other than the eFuse) with pins on both its IN and OUT nets bypasses it, whatever the pin order (0 ohm included)
    _byp = [r for r, p_ in FIT.items() if r != _u and {_nin, _nout} <= {net(f'{r}.{k}') for k in p_['nets']}]
    check(_nin != _nout and not _byp, f'r7f: nothing bypasses the eFuse {_u} between {_nin} and {_nout} (any part, either pin order) {_byp or ""}')
    # ILM: exactly one fitted resistor to GND, 487-5000 ohm at both tolerance ends (TI SLVSE57C p5 7.3 RILM; 'do not leave floating' p4)
    _ilm = [x for x in RES if _nilm in (x[1], x[2])]
    _ok = len(_others(_nilm)) == 1 and len(_ilm) == 1 and {_ilm[0][1], _ilm[0][2]} == {_nilm, gnd} and _ilm[0][3] >= 487 and _ilm[0][4] <= 5000
    _lim = f'{2000 / _ilm[0][4] + 0.04:.2f}-{2000 / _ilm[0][3] + 0.04:.2f} A' if len(_ilm) == 1 and _ilm[0][3] > 0 else 'n/a'
    check(_ok, f'r7f: {_u} ILM ({_nilm}) has one resistor to GND within 487-5000 ohm (SLVSE57C 7.3), current limit {_lim} (Eq. 4) {_others(_nilm)} {_ilm}')
    # DELTA_r7f minor-D1: ILIM at the low end (largest R, Eq. 4, then the -7.5 % ILIM accuracy) above the full-load input current x 1.1.
    # EF_FULL_A is the peak J5 current during the dV/dt ramp at full load from tools/coldstart.py (r7f, every >= 1.5 A source corner,
    # 'Ipk A' column); coldstart.py prints a cross-check against this number. It is a calculation of the board, not a measurement.
    EF_FULL_A, EF_MARGIN = 1.51, 1.1
    _ilim_min = (2000 / _ilm[0][4] + 0.04) * 0.925 if len(_ilm) == 1 and _ilm[0][4] > 0 else 0.0
    check(_ilim_min > EF_FULL_A * EF_MARGIN, f'r7f: {_u} ILIM at its low end {_ilim_min:.2f} A carries the full load {EF_FULL_A} A x {EF_MARGIN} = {EF_FULL_A * EF_MARGIN:.2f} A (Eq. 4 at R max, ILIM -7.5 %)')

    def _farad(v):
        m_ = re.match(r'\s*([\d.]+)\s*(p|n|u)F', v)
        return float(m_[1]) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6}[m_[2]] if m_ else None
    # dVdt: exactly one fitted capacitor to GND, at least 3300 pF (7.3 CdVdt)
    _dv = _others(_ndv)
    _ok = len(_dv) == 1 and _dv[0][0].startswith('C') and {net(f'{_dv[0][0]}.1'), net(f'{_dv[0][0]}.2')} == {_ndv, gnd} and (_farad(FIT[_dv[0][0]]['value']) or 0) >= 3300e-12
    check(_ok, f'r7f: {_u} dVdt ({_ndv}) has one capacitor to GND of at least 3300 pF (SLVSE57C 7.3) {_dv}')
    # DELTA_r7f minor-D1: upper bound. Ramp 0 -> 5 V = tD,ON 0.289 ms + 5 V / SR, SR(V/ms) = 42000 / CdVdt(pF) (Eq. 3), at CdVdt + 10 %
    # (X7R/X5R K tolerance). Budget 30 ms: half of the 60 ms tools/coldstart.py window, so 3V3, 1V2 and CHIP_PU (about 9 ms after the
    # 5V ramp, coldstart.py) finish inside it, well before the USB 2.0 100 ms attach debounce (7.1.7.3) ends. Budget ASSUMED.
    EF_RAMP_MAX_MS = 30.0
    _cdv = (_farad(FIT[_dv[0][0]]['value']) or 0) if len(_dv) == 1 and _dv[0][0].startswith('C') and _dv[0][0] in FIT else 0
    _ramp = 0.289 + 5.0 * (_cdv * 1.1 * 1e12) / 42000 if _cdv else None
    check(_ramp is not None and _ramp <= EF_RAMP_MAX_MS, f'r7f: {_u} dVdt ramp to 5 V {_ramp if _ramp is None else round(_ramp, 1)} ms at CdVdt +10 % within the {EF_RAMP_MAX_MS:g} ms start-up budget (Eq. 3; CdVdt {round(_cdv * 1e9, 1) if _cdv else None} nF)')
    # DELTA_r7f minor-D2: EP paste per TI's DSG0008A stencil: the EP pad has no paste of its own, two paste windows on it, 80-95 % of it
    _bu = _fp_block(_u)
    _side = 'B' if re.search(r'^\s*\(layer "B\.Cu"\)', _bu, re.M) else 'F'
    _ep = re.search(r'\(pad "9" smd \w+\s*\(at ([-\d.]+) ([-\d.]+)[^)]*\)\s*\(size ([\d.]+) ([\d.]+)\)\s*\(layers ([^)]*)\)', _bu)
    _win = [tuple(map(float, m_.groups()[:4])) for m_ in re.finditer(r'\(fp_rect\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)(?:(?!\(fp_|\(pad ).)*?\(layer "([^"]+)"\)', _bu, re.S) if m_[5] == f'{_side}.Paste']
    _cov, _inside = None, False
    if _ep:
        ex, ey, ew, eh = map(float, _ep.groups()[:4])
        _inside = all(min(x0, x1) >= ex - ew / 2 - 1e-6 and max(x0, x1) <= ex + ew / 2 + 1e-6 and min(y0, y1) >= ey - eh / 2 - 1e-6 and max(y0, y1) <= ey + eh / 2 + 1e-6 for x0, y0, x1, y1 in _win)
        _cov = sum(abs(x1 - x0) * abs(y1 - y0) for x0, y0, x1, y1 in _win) / (ew * eh)
    _ok = _ep is not None and 'Paste' not in _ep[5] and len(_win) == 2 and _inside and 0.80 <= _cov <= 0.95
    check(_ok, f'r7f: {_u} EP paste: two {_side}.Paste windows on the EP, {None if _cov is None else round(_cov * 100, 1)} % of it (80-95 %, TI DSG0008A stencil), EP pad itself without paste ({len(_win)} windows, inside {_inside})')
    # EN/UVLO: one resistor from IN, one to GND, nothing else; UVLO rising 1.2 V x (Rt + Rb) / Rb inside 3.0-4.6 V at the tolerance corners
    _rt = [x for x in RES if {x[1], x[2]} == {_nen, _nin}]
    _rb = [x for x in RES if {x[1], x[2]} == {_nen, gnd}]
    _uv = None
    if len(_rt) == 1 and len(_rb) == 1:
        _uv = (1.13 * (_rt[0][3] + _rb[0][4]) / _rb[0][4], 1.27 * (_rt[0][4] + _rb[0][3]) / _rb[0][3])   # VUVLO(R) 1.13-1.27 V (7.5)
    _ok = len(_others(_nen)) == 2 and len(_rt) == 1 and len(_rb) == 1 and _uv[0] >= 3.0 and _uv[1] <= 4.6
    check(_ok, f'r7f: {_u} EN/UVLO divider from {_nin} and to GND, UVLO rising {tuple(round(v, 2) for v in _uv) if _uv else None} V within 3.0-4.6 V (VUVLO(R) 1.13-1.27 V, SLVSE57C 7.5) {_others(_nen)}')
_cec = net(f'{J2}.13')
_esd = [r for r, k in KIND.items() if k == 'TPD1E10B06' and r in FIT and {net(f'{r}.1'), net(f'{r}.2')} == {_cec, gnd}]
check(len(_esd) == 1, f'r7f: HDMI CEC ({_cec}) has a TPD1E10B06 clamp to GND {_esd}')
check(str(net(f'{U7}.{TCN["INT"]}')).startswith('unconnected'),
      'TC358743 INT is open, as the firmware expects (CONFIG_KVM_BRIDGE_INT_GPIO=-1)')
# ATX outputs to the header: each opto transistor C and E on the J4 pins of its own function (J4 order is this design's own harness, README)
_j4 = {(net(f'{o}.4'), net(f'{o}.3')) for o in OPT}
check(all(any(net(f'{J4}.{a}') == c and net(f'{J4}.{b}') == e for c, e in _j4) for a, b in (('1', '2'), ('3', '4'))),
      'ATX PWR and RST opto transistors appear across J4 1-2 and 3-4 (collector, emitter)')

# MIPI CSI: P4 receiver lane to TC358743 transmitter lane, by vendor name (Waveshare table, Toshiba p12)
CSI = {'CSI_DATAN0': 'CSID0N', 'CSI_DATAP0': 'CSID0P', 'CSI_DATAN1': 'CSID1N', 'CSI_DATAP1': 'CSID1P', 'CSI_CLKP': 'CSICP', 'CSI_CLKN': 'CSICN'}
_bad = [(a, b) for a, b in CSI.items() if not connected(f'{U1}.{GPIO_PIN[a]}', f'{U7}.{TCN[b]}')]
check(not _bad, f'CSI-2: 2 lanes and clock, module pin to TC358743 ball by name, P to P and N to N {_bad or ""}')
# HDMI Type A to TC358743, by name
HD = {'D2+': 'HDMID2P', 'D2-': 'HDMID2N', 'D1+': 'HDMID1P', 'D1-': 'HDMID1N', 'D0+': 'HDMID0P', 'D0-': 'HDMID0N', 'CK+': 'HDMICP', 'CK-': 'HDMICN', 'CEC': 'CEC'}
JN = {e[0]: n for n, e in T['kinds']['HDMI-001S']['pins'].items()}
_bad = [(a, b) for a, b in HD.items() if not connected(f'{J2}.{JN[a]}', f'{U7}.{TCN[b]}')]
# DDC through the TCA9517A: connector on the B side, TC358743 DDC on the A side (TI p4)
_bad += [(a, b) for a, b in (('SCL', '7'), ('SDA', '6')) if not connected(f'{J2}.{JN[a]}', f'{U6}.{b}')]
_bad += [(a, b) for a, b in (('DDC_SCL', '2'), ('DDC_SDA', '3')) if not connected(f'{U7}.{TCN[a]}', f'{U6}.{b}')]
_bad += [('HPD', 'HPDO through a resistor')] if not via_res(f'{J2}.{JN["HPD"]}', f'{U7}.{TCN["HPDO"]}') else []
check(not _bad, f'HDMI connector to TC358743 by function: TMDS, CEC, DDC via TCA9517A B to A side, HPD from HPDO through a resistor {_bad or ""}')
# ESD: every TMDS and USB data line carries one TPD4E05U06 channel pin (TI p4: channel pins 1, 2, 4, 5)
_esd = {net(f'{r}.{p}') for r, k in KIND.items() if k == 'TPD4E05U06' and r in FIT for p in ('1', '2', '4', '5')}
_lines = [f'{J2}.{JN[x]}' for x in ('D2+', 'D2-', 'D1+', 'D1-', 'D0+', 'D0-', 'CK+', 'CK-')]
USBC = sorted(r for r, k in KIND.items() if k == 'USB-C_HX_16P')
_lines += [f'{j}.{p}' for j in USBC for p in ('A6', 'A7')]
_bad = [x for x in _lines if net(x) not in _esd]
check(not _bad, f'every TMDS and USB data line has a TPD4E05U06 channel on it {_bad or ""}')
# USB-C: both orientations joined, data to the right module pins, Rd on each CC, host VBUS kept apart
_usbn = {net(f'{U1}.{GPIO_PIN["USB_DP"]}'), net(f'{U1}.{GPIO_PIN["USB_DM"]}')}
_host = next((j for j in USBC if net(f'{j}.A6') in _usbn or net(f'{j}.A7') in _usbn), USBC[0])
_pwr = next(j for j in USBC if j != _host)
_bad = []
for j in USBC:
    for a, b in (('A6', 'B6'), ('A7', 'B7'), ('A4B9', 'B4A9')):
        if not connected(f'{j}.{a}', f'{j}.{b}'):
            _bad.append((j, a, b))
    for cc in ('A5', 'B5'):
        rd = [(r, lo, hi) for r, a, b, lo, hi in RES if {a, b} == {net(f'{j}.{cc}'), gnd}]
        # USB Type-C spec Rd = 5.1 kOhm +-20% (from memory, not re-read for r7c)
        if len(rd) != 1 or rd[0][1] < 5.1e3 * 0.8 or rd[0][2] > 5.1e3 * 1.2:
            _bad.append((j, cc, 'Rd', rd))
if not (connected(f'{_host}.A6', f'{U1}.{GPIO_PIN["USB_DP"]}') and connected(f'{_host}.A7', f'{U1}.{GPIO_PIN["USB_DM"]}')):
    _bad.append('host port to USB_DP/DM')
if not (connected(f'{_pwr}.A6', f'{U1}.{GPIO_PIN["GPIO25"]}') and connected(f'{_pwr}.A7', f'{U1}.{GPIO_PIN["GPIO24"]}')):
    _bad.append('power port to GPIO25 (USB1P1_P0) / GPIO24 (USB1P1_N0)')
check(not _bad, f'USB-C: A/B sides joined, Rd 5.1k +-20% on each CC, host port on USB_DP/DM, power port on GPIO25/24 (Waveshare alt names) {_bad or ""}')
# r7f: the box supply is now two nets, J5 VBUS (VBUS_IN, ahead of the eFuse) and 5V behind it; host VBUS must touch neither
_box = {net(f'{_pwr}.A4B9'), '5V'}
check(net(f'{_host}.A4B9') not in _box and not any(net(f'{_host}.A4B9') in (a, b) and ({a, b} & _box) for r, a, b in LINKS),
      f'host VBUS and box 5 V are separate nets with no link: neither can feed the other (box: {sorted(_box)})')
# antenna: module pin 2 to the U.FL centre contact (Hirose p3)
check(connected(f'{U1}.{GPIO_PIN["LNA_OUT"]}', f'{J8}.1'), 'antenna: module LNA_OUT (pin 2) to the U.FL signal contact')
# microSD: card VDD from the switch drain; pull-ups on CMD and DAT to the IO supply of GPIO39-48 (ESP_LDO_VO4), per the Espressif hardware
# design guidelines section 1.3.11 as quoted in the 2026-11-07 pinout audit (F1)
_vo4 = net(f'{U1}.{GPIO_PIN["ESP_LDO_VO4"]}')
_bad = [jp for jp in ('3', '7', '8', '1', '2') if not any({a, b} == {net(f'{J7}.{jp}'), _vo4} for r, a, b, lo, hi in RES)]
check(connected(f'{Q1}.3', f'{J7}.4') and not _bad, f'microSD: VDD from {Q1} drain, CMD and DAT0-3 pulled up to ESP_LDO_VO4 {_bad or ""}')
# card supply from the module's 3.3 V rail and never from ESP_LDO_VO4 (VO4 max 50 mA, ESP32-P4 datasheet v0.7 p32; Espressif hardware design
# guidelines 1.3.11; pinout audit F1). Also catches R41 and R42 both fitted (README: 3V3 shorted to VO4).
_reach, _todo = {net(f'{Q1}.2')}, [net(f'{Q1}.2')]
while _todo:
    _c = _todo.pop()
    for r, a, b in LINKS:
        if r == Q1:
            continue
        for x, y in ((a, b), (b, a)):
            if x == _c and y not in _reach:
                _reach.add(y)
                _todo.append(y)
check(net(f'{U1}.85') in _reach and _vo4 not in _reach, f'SD switch source fed from the module 3.3 V rail, not from ESP_LDO_VO4 (reached through links: {sorted(_reach)})')
# P4 chip rev v1.0/v1.3 USB DP pull-down (pinout audit F4): a resistor of 1 Mohm order from USB_DP to GND
check(any({a, b} == {net(f'{U1}.{GPIO_PIN["USB_DP"]}'), gnd} and 0.5e6 <= lo for r, a, b, lo, hi in RES), 'USB_DP has a high-value pull-down to GND (pinout audit F4, chip rev < 3)')
# HPDI must not see HDMI +5V directly: a series resistor limits back-feed into an unpowered TC358743 (review M5).
# 0.5 mA is an ASSUMED injection limit: Toshiba gives VIN_IO <= VDDIO + 0.3 (p15) and no clamp current.
_h5, _hp = net(f'{J2}.{JN["+5V"]}'), net(f'{U7}.{TCN["HPDI"]}')
_ser = [(r, lo) for r, a, b, lo, hi in RES if {a, b} == {_h5, _hp} and lo > 1]
_vh = T['external'][f'{J2}.{JN["+5V"]}']['rail'][1] if f'{J2}.{JN["+5V"]}' in T['external'] else 5.3
check(_h5 != _hp and bool(_ser) and _vh / min(lo for _, lo in _ser) <= 0.5e-3,
      f'HDMI +5V reaches HPDI only through a series resistor {_ser}: back-feed into an unpowered bridge at most {_vh / min([lo for _, lo in _ser] or [1]) * 1e3:.2f} mA (limit 0.5 mA ASSUMED)')

# ---------- opto drive, with the numbers it rests on
_vdd = RAIL.get(net(f'{U1}.85'), (0, 0))
for cfg, hit in _atx.items():
    if len(hit) != 1:
        continue
    o = hit[0]
    rr = [lo for r, a, b, lo, hi in RES if {a, b} == {net(gp(cfg)), net(f'{o}.1')}]
    if_ma = (0.8 * _vdd[0] - 1.4) / max(rr) * 1000   # VOH 0.8 VDD (ESP32-P4 p89); VF 1.4 V ASSUMED (EL3H7 VF max not re-read)
    ic_ma = if_ma * 2.0 * 0.9                        # CTR 200% min at 5 mA (EL3H7(C) p3, as cited in r6), 0.9 for saturation (fig. 3)
    check(ic_ma > 1.0, f'{cfg} through {max(rr):.0f} ohm: IF {if_ma:.2f} mA, opto sinks {ic_ma:.2f} mA at CTR min; header pull-up current ASSUMED under 1 mA '
          '(ATX front-panel switch inputs are pulled up through kilo-ohms; motherboard specs vary)', 'WARN')

# ---------- the rest is geometry and stock, as in r7b
_P = P
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


# Pair nets found by the pins they join, not by name: each pair is the two nets of a P/N pin pair on the TC358743 (HDMI, CSI) or the module (USB).
PAIRS = [(f'HDMI {x}', net(f'{U7}.{TCN["HDMI" + x + "P"]}'), net(f'{U7}.{TCN["HDMI" + x + "N"]}')) for x in ('D2', 'D1', 'D0', 'C')]
PAIRS += [(f'CSI {x}', net(f'{U7}.{TCN["CSI" + x + "P"]}'), net(f'{U7}.{TCN["CSI" + x + "N"]}')) for x in ('D0', 'D1', 'C')]
PAIRS += [('USB', net(f'{U1}.{GPIO_PIN["USB_DP"]}'), net(f'{U1}.{GPIO_PIN["USB_DM"]}'))]
print('pair            P mm    N mm   skew   vias P/N')
worst = 0
lens = []
for name, a_, b_ in PAIRS:
    a, b = length(a_), length(b_)
    worst = max(worst, abs(a - b))
    lens += [a, b]
    print(f'{name:12s} {a:7.2f} {b:7.2f} {abs(a - b):6.2f}   {vcount[a_]}/{vcount[b_]}')
limit = float(ARGS[2]) if len(ARGS) > 2 else 3.0
check(min(lens) > 1, f'every high speed line has routed length, shortest {min(lens):.2f} mm')
# 3.0 mm is a project budget, not a standard: 3.0 mm x 6.7 ps/mm = 20 ps, 2% of one 972 Mbit/s CSI bit. Sum of segment lengths; pairs.py measures pad to pad.
check(worst <= limit, f'worst P/N length difference {worst:.2f} mm is within {limit} mm (about {worst * 6.7:.0f} ps; one bit at 972 Mbit/s is 1029 ps)')
# r7c: MIPI CSI rules from Espressif ESP32-P4 Hardware Design Guidelines (Nov 05 2026 release, PDF p28, "MIPI"): "The length difference between two MIPI
# traces in a pair should be ... kept within 10 mil; the length difference between different MIPI trace pairs ... within 30 mil."
# Within a pair this board holds 0.15 mm (team lead's target, tighter than 10 mil = 0.254 mm). Board copper only: the module's own P4-to-pad
# routing is not published, so it is not in these numbers. Length = sum of the net's segments (no stubs on these nets; pairs.py gives pad to pad).
_csi = [(nm, length(a_), length(b_)) for nm, a_, b_ in PAIRS if nm.startswith('CSI')]
_intra = max(abs(a - b) for _, a, b in _csi)
check(_intra <= 0.15, f'CSI within each pair: worst {_intra:.3f} mm against 0.15 mm (Espressif 10 mil = 0.254 mm)')
_mean = [(nm, (a + b) / 2) for nm, a, b in _csi]
_inter = max(m for _, m in _mean) - min(m for _, m in _mean)
# r7c accepted this as a WARN (option A). r7d (option B, R7D_REPORT.md) moved the TC358743 and matched the pairs, so it is a hard limit again.
# CSI_INTER_LEVEL=WARN brings back the r7c behaviour for an old board.
CSI_INTER_LEVEL = os.environ.get('CSI_INTER_LEVEL', 'FAIL')
check(_inter <= 0.762, f'CSI between pairs: {", ".join(f"{nm} {m:.2f}" for nm, m in _mean)} mm, spread {_inter:.3f} mm against 0.762 mm (Espressif 30 mil); about {_inter * 6.7:.0f} ps', CSI_INTER_LEVEL)
check(_inter <= 0.5, f'CSI between pairs within the project aim of 0.5 mm: spread {_inter:.3f} mm', 'WARN')

# r7e: reference plane under every controlled-impedance pair (CSI, HDMI TMDS, USB HS), tools/refplane.py. r7d checked CSI only and excluded
# every CSI via; now only the pair's own vias are excluded (REVIEW_r7d tool table, injections 5 and 6).
import refplane
_fill, _gap = refplane.gaps(s, ('csi', 'tmds', 'usb'), refplane.FAIL_MARGIN)
check(bool(_fill.get('In1.Cu')) and bool(_fill.get('In4.Cu')), 'filled GND on In1 and In4 read back from the saved board (zones refilled)')
check(not _gap, f'CSI, TMDS and USB lines have GND under them (In1 under F.Cu, In4 under B.Cu, line +{refplane.FAIL_MARGIN} mm each side) '
                f'{[(g[0], g[1], round(g[2], 4)) for g in _gap] or ""}')
# r7e: pair gap -> differential impedance along every pair (tools/pairgap.py, solver table); no sample outside target +-10%
import pairgap
_pg = pairgap.measure(s)
_pgbad = [(r[1], len(r[7]), r[7][0]) for r in _pg if r[7]] + [(r[1], 'alone', round(r[8], 2)) for r in _pg if r[8] > r[4] / 2]
check(len(_pg) == 16 and not _pgbad, f'differential pairs: gap to the partner keeps Zdiff within +-10% on all {len(_pg)} lines (CSI/TMDS 100, USB 90 ohm) {_pgbad or ""}')
_, _gw = refplane.gaps(s, ('csi', 'tmds', 'usb'), refplane.WARN_MARGIN)
check(not _gw, f'reference plane within {refplane.WARN_MARGIN} mm of the pair lines: {len(_gw)} spots at foreign-via antipad edges, '
               f'{sum(g[2] for g in _gw):.4f} mm2 {sorted({g[0] for g in _gw}) or ""}', 'WARN')

# impedance_r7.py solves fixed geometries (TMDS/CSI 0.127 mm, USB HS 0.18 mm, LNA_OUT 0.15 mm CPWG). Its numbers only mean something if the
# board uses those widths: every segment of those nets must have exactly that width. Pair gap and reference plane are NOT checked here.
_wbad = {}
for name, a_, b_ in PAIRS:
    want_w = 0.18 if name == 'USB' else 0.127
    for n_ in (a_, b_):
        ws = sorted({round(x[4], 4) for x in segs[n_]})
        if ws != [want_w]:
            _wbad[n_] = ws
_lna = net(f'{U1}.{GPIO_PIN["LNA_OUT"]}')
if sorted({round(x[4], 4) for x in segs[_lna]}) != [0.15]:
    _wbad[_lna] = sorted({round(x[4], 4) for x in segs[_lna]})
check(not _wbad, f'controlled-impedance nets use only the width impedance_r7.py solved for (TMDS/CSI 0.127, USB HS 0.18, LNA_OUT 0.15) {_wbad or ""}')

# geometry a same-net DRC cannot see: no via hole may touch a solder pad on any net, and no net may have one pin
vias_found = []
for m in re.finditer(r'\(via\b(.*?)\(uuid', s, re.S):
    a = re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', m[1])
    n = re.search(r'\(net "([^"]+)"\)', m[1])
    dr = re.search(r'\(drill ([\d.]+)\)', m[1])
    if a and n:
        vias_found.append((float(a[1]) - 100, float(a[2]) - 100, float(dr[1]), n[1]))
hit = []
for part in d['parts']:
    if part['lib'] != 'BGA-64_6x6':
        continue
    for k, xy in d['padpos'].items():
        if k.split('.')[0] == part['ref']:
            for v in vias_found:
                if math.hypot(xy[0] - v[0], xy[1] - v[1]) < 0.15 + v[2] / 2 + 0.03:
                    hit.append((k, v[3], round(math.hypot(xy[0] - v[0], xy[1] - v[1]), 3)))
check(not hit, f'no via hole touches a BGA ball pad, {len(vias_found)} vias checked {hit or ""}')
# r7e (REVIEW_r7d M1, injection 3): a polarized capacitor reversed passed every check. Pin 1 is + (Panasonic POSCAP, IPC-7351 CAPMP7343):
# pin 2 must be GND and pin 1 must reach a positive supply directly or through one resistor (C69: 5V_DAMP, R68 to 5V).
_cpbad = []
for _p in parts:
    if _p['lib'].startswith('CP_'):
        _n1, _n2 = _p['nets'].get('1'), _p['nets'].get('2')
        _reach = {_n1} | {m for q in parts if q['ref'].startswith('R') and _n1 in q['nets'].values() for m in q['nets'].values()}
        if not (_n2 == 'GND' and _n1 != 'GND' and _reach & {'5V', '3V3', 'V2V5', 'V1V2', 'HDMI_5V', 'HOST_VBUS'}):
            _cpbad.append((_p['ref'], f'+ {_n1}', f'- {_n2}'))
check(not _cpbad, f'polarized capacitors: + (pin 1) on the supply side, - (pin 2) on GND {_cpbad or ""}')
# r7e (REVIEW_r7d m2): no via drill inside any pad that gets solder paste, on any part. The vias are not plugged, so a drill in a pasted
# land wicks the solder away from the joint (C21.2 in r7d). Pad centres from design.json, sizes and angles from the board's footprints.
_vip = []
_pastepads = []
for _fm in re.finditer(r'\n\t\(footprint "[^"]*"(.*?)\n\t\)', s, re.S):
    _f = _fm[1]
    _ref = re.search(r'\(property "Reference" "([^"]+)"', _f)
    _rot = re.search(r'\(transform\s*\(translate [-\d.]+ [-\d.]+\)\s*\(rotate ([-\d.]+)\)', _f)
    if not _ref:
        continue
    for _pm in re.finditer(r'\(pad "([^"]*)" smd (\w+)\s*\(at [-\d.]+ [-\d.]+(?: ([-\d.]+))?\)\s*\(size ([\d.]+) ([\d.]+)\)\s*\(layers ([^)]*)\)', _f):
        if 'Paste' not in _pm[6] or f'{_ref[1]}.{_pm[1]}' not in d['padpos']:
            continue
        _ang = (float(_rot[1]) if _rot else 0) + float(_pm[3] or 0)
        _w, _h = float(_pm[4]), float(_pm[5])
        if round(_ang / 90) % 2:
            _w, _h = _h, _w
        _cx, _cy = d['padpos'][f'{_ref[1]}.{_pm[1]}']
        _pastepads.append((f'{_ref[1]}.{_pm[1]}', _cx, _cy, _w, _h, _pm[2]))
for _k, _cx, _cy, _w, _h, _shape in _pastepads:
    for v in vias_found:
        _dx, _dy = max(abs(v[0] - _cx) - _w / 2, 0), max(abs(v[1] - _cy) - _h / 2, 0)
        _dist = math.hypot(v[0] - _cx, v[1] - _cy) - _w / 2 if _shape == 'circle' else math.hypot(_dx, _dy)
        if _dist < v[2] / 2:
            _vip.append((_k, v[3], (round(v[0], 3), round(v[1], 3))))
check(len(_pastepads) > 300 and not _vip, f'no via drill inside a pasted pad, {len(_pastepads)} pads checked {_vip or ""}')
count = defaultdict(list)
for k, n in pads.items():
    if not n.startswith('unconnected-'):
        count[n].append(k)
check(not _LVL_FAIL, f'every pin level could be bounded (resistor networks small enough to solve at the tolerance corners) {_LVL_FAIL[:4] or ""}')
single = {n: v for n, v in count.items() if len(v) < 2}
check(not single, f'no net has only one pin {single or ""}')

# every stocked part number must actually be the stated value; read from JLC's listing into stock.json
DECODE = {'100nF': '104', '1uF': '105', '2.2uF': '225', '470pF': '471', '47pF': '470', '22pF': '220', '4.7uF': '475', '10uF': '106', '22uF': '226',
          '1M': '1004', '560 ': '5600', '100 ': '1000', '33.2k': '3322', '5.1k': '5101', '10k': '1002', '100k': '1003', '470 ': '4700', '270 ': '2700', '150k': '1503', '33k': '3302', '51k': '5102', '2.2k': '2201', '2k ': '2001', '22 ': '220', '1k ': '1001', '0R': '0000', '0.15': '150L', '47k': '4702', '33 ': '33R0'}
MODEL = {'C41427493': 'TYPE-C 16P', 'C138714': 'TPD4E05U06', 'C160407': 'SM08B-SRSS', 'C160405': 'SM06B-SRSS', 'C720616': 'HDMI-001S', 'C3008606': 'TC358743XBG', 'C882825': 'TLV73325', 'C2871228': 'TLV73312',
         'C98485': 'GZ2012D102', 'C85840': 'BLM21PG221', 'C725995': 'OT322527M', 'C19330': 'BLM18AG601', 'C30348': 'PCA9517', 'C201698': 'TCA9517A', 'C728559': 'RT0402BRD0733K', 'C319512': 'AR02BTD5600', 'C585350': '1040310811', 'C15127': 'AO3401', 'C78988': 'SY8089', 'C83423': 'SWPA4020S2R2', 'C92243': 'EL3H7(C)', 'C88373': 'U.FL-R-SMT-1', 'C347552': '10TPE330M', 'C2155674': 'TPS259531', 'C48260': 'TPD1E10B06'}
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
    v = part['value'].split(' 0')[0].strip() + (' ' if part['value'].split(' 0')[0].strip() in ('470', '270', '2k', '22', '1k', '560', '100', '33') else '')
    v = re.sub(r' 0\.1%$', '', v)
    if v in DECODE and DECODE[v] not in str(row[1]) and part['lcsc'] not in MODEL:
        wrong.append((part['ref'], part['value'], row[1]))
    want = MODEL.get(part['lcsc'])
    if want and want not in str(row[1]):
        wrong.append((part['ref'], want, row[1]))
    if not want and not part['value'].endswith(('0201', '0402', '0603', '0805')):
        wrong.append((part['ref'], 'no model entry', row[1]))
    if part['ref'][0] == 'R' and schgen.ohms(part['value']) is not None and not want:
        code = DECODE.get(v)
        if code is None:
            wrong.append((part['ref'], part['value'], 'value not in the decode table'))
check(not wrong, f'every part number decodes to its stated value {wrong or ""}')
check(not missing, f'every fitted part is stocked at JLC {missing or ""}')

if FAST:
    print('FAST: mask, hole and body checks skipped')
else:
    import bodycheck
    import holecheck
    import maskcheck
    KC = os.environ.get('KICAD_CLI', 'kicad-cli')
    H = os.environ.get('KICAD_TOOL_HOME', os.path.expanduser('~/.kicad-tool-home'))
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
            # r7c: component hole (PTH pad hole or slot, 0.5 mm and up) to any other hole, edge to edge, along the whole slot.
            # JLC capabilities page (read 2026-11-08): "Pad hole-to-hole spacing 0.45mm", "Via-to-via hole spacing 0.2mm"; it does not say which
            # applies between a pad hole and a via, and KiCad DRC has one min_hole_to_hole (0.2) for all. Reported as WARN for a CAM answer.
            from shapely.geometry import LineString as _LS, Point as _Pt
            _dt = open(f'{tmp}/p4_kvm_mini-PTH.drl', encoding='utf-8', errors='replace').read()
            _tools = dict(re.findall(r'^T(\d+)C([\d.]+)', _dt, re.M))
            _cur, _hs = None, []
            for _l in _dt.splitlines():
                _m = re.match(r'^T(\d+)$', _l)
                if _m:
                    _cur = float(_tools[_m[1]])
                    continue
                _m = re.match(r'^X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?', _l)
                if _m and _cur:
                    a_ = (float(_m[1]), float(_m[2]))
                    _hs.append((_LS([a_, (float(_m[3]), float(_m[4]))]) if _m[3] else _Pt(a_), _cur))
            _near = sorted((round(g_.distance(h_) - d_ / 2 - e_ / 2, 3), round(g_.centroid.x - 100, 2), round(-g_.centroid.y - 100, 2), d_, e_)
                           for i, (g_, d_) in enumerate(_hs) if d_ >= 0.5 for j, (h_, e_) in enumerate(_hs) if j != i and (e_ < 0.5 or j > i)
                           and g_.distance(h_) - d_ / 2 - e_ / 2 < 0.45)
            # r7c: decided conservative (team lead 2026-11-08): FAIL, not WARN. The project DRC rule file has the same rule.
            check(not _near, f'component hole to any hole at least 0.45 mm edge to edge (JLC pad hole-to-hole, applied to vias too); under it: {_near} (gap, x, y, component hole, other hole)')
    br = bodycheck.check(OUT)
    check(br['ok'], 'BODYCHECK ' + bodycheck.summary(br))
    for x in br['fails'] + br['warns']:
        print('  ' + bodycheck.line(x))
print('BOARD sha256', hashlib.sha256(open(f'{OUT}/p4_kvm_mini.kicad_pcb', 'rb').read()).hexdigest())
print(f'WARNINGS {len(warns)}')
print('RESULT', 'ALL PASS' if not fails else f'{len(fails)} FAILED')
sys.exit(1 if fails else 0)
