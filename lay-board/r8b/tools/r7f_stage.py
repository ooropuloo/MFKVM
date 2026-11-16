# -*- coding: utf-8 -*-
# r7f stage of gen_mini.py (exec'd right after tools/r7e_stage.py, with its globals). R7F_REPORT.md has the reasons and the numbers.
# The six changes the user approved on 2026-11-09:
#   1. 5 V input eFuse U16 TPS259531DSGR (TI SLVSE57C) between J5 VBUS (new net VBUS_IN) and the board 5V, with dV/dt, UVLO and ILIM parts
#   2. CEC ESD diode D1 TPD1E10B06DPYR beside the CEC via of J2.13
#   3. SD: 22 ohm in series with CLK, CMD, D0-D3, on B beside each line's first via (about 1 mm from the U1 pad); card side nets *_C
#   4. LCD: 33 ohm in series with LCD_DIN and LCD_CLK (see the LCD block for the placement)
#   5/6. mounting holes become plated GND pads, so the metal lid posts tie to board ground (the case work is in case/)
import math as _m

R7F_LOG = []
_items = [_item(t) for t in tracks]


def _new_part(ref, value, lcsc, lib, pads, x, y, r, nets, side, body):
    BODY.setdefault(lib, body)
    part(ref, value, lcsc, lib, pads, x, y, r, nets, side, body=body)
    p = parts[-1]
    bake(p)
    for q in p['pads']:
        if not p['nets'].get(q['n']):
            p['nets'][q['n']] = f"unconnected-({ref}-Pad{q['n']})"
    _P[ref] = p
    sym[ref] = uid('sym-' + ref)
    return p


def _pad_xy(ref, n):
    q = next(q for q in _P[ref]['abs'] if q['n'] == str(n))
    return (round(q['wx'], 4), round(q['wy'], 4))


def _S(net, ly, a, b, w):
    _items.append(dict(k='s', a=tuple(a), b=tuple(b), w=w, ly=ly, net=net))


def _V(net, x, y, size=0.4):
    _items.append(dict(k='v', a=(x, y), w=size, ly='*', net=net))


def _drop(pred, why):
    global _items
    hit = [it for it in _items if pred(it)]
    _items = [it for it in _items if not any(it is h for h in hit)]
    R7F_LOG.append(f'r7f: removed {len(hit)} item(s): {why}')
    return hit


def _near(a, b, tol=0.003):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _is_seg(it, net, ly, a, b):
    return it['k'] == 's' and it['net'] == net and it['ly'] == ly and ((_near(it['a'], a) and _near(it['b'], b)) or (_near(it['a'], b) and _near(it['b'], a)))


def _is_via(it, net, x, y):
    return it['k'] == 'v' and it['net'] == net and _near(it['a'], (x, y))


def _rename(pred, new):
    n = 0
    for it in _items:
        if pred(it):
            it['net'] = new
            n += 1
    return n


R0402P = [pad(1, -0.48, 0, 0.56, 0.62), pad(2, 0.48, 0, 0.56, 0.62)]

# ============ 1. eFuse U16 on the bottom, between the J5 shell legs (x 14.8..19.3, y -0.5..6.2 was empty on B) ============
# TPS2595x DSG0008A land (SLVSE57C p47 example board layout): pads 0.5 x 0.25 at 0.5 pitch, rows 1.9 apart; exposed pad 0.9 x 1.6.
# Pin 1 top-left, 1-4 down the left, 5-8 up the right. The exposed pad gets no via inside (verify: no drill in a pasted pad).
WSON8 = [pad(i + 1, -0.95, -0.75 + 0.5 * i, 0.5, 0.25) for i in range(4)] + [pad(5 + i, 0.95, 0.75 - 0.5 * i, 0.5, 0.25) for i in range(4)] + [pad(9, 0, 0, 0.9, 1.6)]
EFX, EFY = 16.0, 3.2
# bottom, rotation 90: south row (y = EFY + 0.95) pins 4 3 2 1 west to east, north row (y = EFY - 0.95) pins 5 6 7 8
_new_part('U16', 'TPS259531DSGR eFuse 5.7V clamp', 'C2155674', 'WSON-8_2x2_EP', WSON8, EFX, EFY, 90,
          {'1': 'EF_DVDT', '2': 'EF_EN', '3': 'VBUS_IN', '4': 'VBUS_IN', '5': '5V', '7': 'EF_ILM', '8': 'GND', '9': 'GND'}, 'B', (-1.05, -1.05, 1.05, 1.05))
# exposed pad: no via (optional per TI note 5; the 0.1 W of conduction loss does not need them, and a via in this pad would need plugging),
# paste as TI's DSG0008A example stencil (SLVSE57C p48): two 0.9 x 0.7 mm windows 0.45 mm either side of the centre along the long axis,
# 87 % of the pad instead of 100 %
_u16 = _P['U16']
_ep = next(q for q in _u16['abs'] if q['n'] == '9')
_ep['nopaste'] = True
assert _ep['ww'] > _ep['wh']   # long axis along x on the board
_u16['paste_windows'] = [(_ep['wx'] + d, _ep['wy'], 0.7, 0.9) for d in (-0.45, 0.45)]
for _n, (_ex, _ey) in {'1': (EFX + 0.75, EFY + 0.95), '4': (EFX - 0.75, EFY + 0.95), '5': (EFX - 0.75, EFY - 0.95), '8': (EFX + 0.75, EFY - 0.95)}.items():
    assert _near(_pad_xy('U16', _n), (_ex, _ey)), ('U16 pin', _n, _pad_xy('U16', _n))
# input cap (TI 9.2.3; 1 uF so the VBUS bypass is at the USB minimum), dV/dt cap, UVLO divider, ILIM resistor
# C70: 2.2 uF 25 V X5R 0402 (Murata GRM155R61E225KE11D): TI asks for >= 0.01 uF (SLVSE57C 11.1); 2.2 uF keeps >= 1 uF left at 5 V DC bias
# (review r7f minor-8: the 1 uF 0402 drops below 1 uF). Same 0402 land.
_new_part('C70', '2.2uF 0402', 'C385032', 'R0402', R0402P, 15.5, 5.4, 90, {'1': 'GND', '2': 'VBUS_IN'}, 'B', BODY['R0402'])
_new_part('C71', '100nF 0402', 'C1525', 'R0402', R0402P, 18.05, 4.1, 0, {'1': 'GND', '2': 'EF_DVDT'}, 'B', BODY['R0402'])
_new_part('R72', '47k 0402', 'C25792', 'R0402', R0402P, 17.45, 5.45, 90, {'1': 'GND', '2': 'EF_EN'}, 'B', BODY['R0402'])
_new_part('R71', '100k 0402', 'C25741', 'R0402', R0402P, 18.35, 5.45, 90, {'1': 'VBUS_IN', '2': 'EF_EN'}, 'B', BODY['R0402'])
_new_part('R73', '1k 0402', 'C11702', 'R0402', R0402P, 16.35, 0.95, 90, {'1': 'EF_ILM', '2': 'GND'}, 'B', BODY['R0402'])
for _r in ('C70', 'C71', 'R72', 'R71', 'R73'):
    R7F_LOG.append(f"r7f: {_r} pads " + ', '.join(f"{q['n']}:{_P[_r]['nets'][q['n']]}@({q['wx']:.2f},{q['wy']:.2f})" for q in _P[_r]['abs']))

# J5 VBUS side: the F strap and the three vias between J5 and the old B track become VBUS_IN.
#   kept as 5V: the B track from (14.75, 5.75) on to U2/C60/R68, the In2 branch to U6/R27/R28/C32 and its two vias at x 10.56
_vb = {(13.2, 4.9), (13.75, 4.9), (13.75, 4.35)}
_n = _rename(lambda it: it['net'] == '5V' and ((it['k'] == 'v' and any(_near(it['a'], v) for v in _vb))
                                                or (it['k'] == 's' and it['ly'] == 'F.Cu' and not _is_seg(it, '5V', 'F.Cu', (10.56, 6.4), (10.56, 6.95)) and not _is_seg(it, '5V', 'F.Cu', (10.56, 4.9), (10.56, 6.4)))
                                                or (it['k'] == 's' and it['ly'] == 'B.Cu' and (_is_seg(it, '5V', 'B.Cu', (13.2, 4.9), (13.9, 4.9)) or _is_seg(it, '5V', 'B.Cu', (13.75, 4.35), (13.75, 4.9))))), 'VBUS_IN')
R7F_LOG.append(f'r7f: {_n} J5-side 5V items renamed VBUS_IN')
_P['J5']['nets']['A4B9'] = _P['J5']['nets']['B4A9'] = 'VBUS_IN'
_drop(lambda it: _is_seg(it, '5V', 'F.Cu', (10.56, 4.9), (10.56, 6.4)), 'F strap J5 -> In2 5V branch (the branch is fed from the eFuse output now)')
_drop(lambda it: _is_seg(it, '5V', 'B.Cu', (13.9, 4.9), (14.75, 5.75)), 'B link J5 vias -> U2 track (the eFuse sits in this path now)')
for _p, _k in (((13.2, 4.9), 'v'), ((13.75, 4.9), 'v'), ((13.75, 4.35), 'v')):
    assert any(it['net'] == 'VBUS_IN' and it['k'] == 'v' and _near(it['a'], _p) for it in _items), _p
# VBUS_IN on B: via (13.75, 4.35) to pins 4 and 3, and pin 3/4 to C70
_p4, _p3, _p2, _p1 = (_pad_xy('U16', n) for n in (4, 3, 2, 1))
_p5, _p6, _p7, _p8 = (_pad_xy('U16', n) for n in (5, 6, 7, 8))
_S('VBUS_IN', 'B.Cu', (13.75, 4.35), (14.9, _p4[1]), 0.4)
_S('VBUS_IN', 'B.Cu', (14.9, _p4[1]), _p4, 0.4)
_S('VBUS_IN', 'B.Cu', _p4, _p3, 0.25)
_c70v = _pad_xy('C70', 2)
_S('VBUS_IN', 'B.Cu', ((_p4[0] + _p3[0]) / 2, _p4[1]), _c70v, 0.25)
# VBUS_IN to R71 (UVLO divider top) on F under the J5 body, through a via beside R71
_r71v = _pad_xy('R71', 1)
_S('VBUS_IN', 'F.Cu', (13.75, 4.35), (17.9, 4.35), 0.2)
_S('VBUS_IN', 'F.Cu', (17.9, 4.35), (18.35, 4.8), 0.2)
_S('VBUS_IN', 'F.Cu', (18.35, 4.8), (18.35, 6.55), 0.2)
_V('VBUS_IN', 18.35, 6.55)
_S('VBUS_IN', 'B.Cu', (18.35, 6.55), _r71v, 0.2)
# 5V out: pin 5 to two 0.5 mm vias, In2 down to a via on the old 5V B track, In2 west to the U6 branch vias at x 10.56
_S('5V', 'B.Cu', _p5, (14.8, _p5[1]), 0.4)
_V('5V', 14.8, 2.25, 0.5)
_V('5V', 14.75, 2.85, 0.5)
_S('5V', 'B.Cu', (14.8, 2.25), (14.75, 2.85), 0.5)
_S('5V', 'In2.Cu', (14.8, 2.25), (14.75, 2.85), 0.5)
_S('5V', 'In2.Cu', (14.75, 2.85), (14.75, 5.75), 0.5)
_S('5V', 'In2.Cu', (14.75, 5.75), (14.75, 6.3), 0.5)
_V('5V', 14.75, 6.3, 0.5)
_S('5V', 'In2.Cu', (14.75, 5.75), (11.2, 5.75), 0.4)
_S('5V', 'In2.Cu', (11.2, 5.75), (10.56, 6.39), 0.4)
_S('5V', 'In2.Cu', (10.56, 6.39), (10.56, 6.4), 0.4)
# EN: pin 2 south, east to R72/R71
_r72e, _r71e = _pad_xy('R72', 2), _pad_xy('R71', 2)
_S('EF_EN', 'B.Cu', _p2, (_p2[0], 4.85), 0.15)
_S('EF_EN', 'B.Cu', (_p2[0], 4.85), (_r72e[0], 4.85), 0.15)
_S('EF_EN', 'B.Cu', (_r72e[0], 4.85), _r72e, 0.15)
_S('EF_EN', 'B.Cu', _r72e, _r71e, 0.15)
# dV/dt: pin 1 east to C71
_S('EF_DVDT', 'B.Cu', _p1, _pad_xy('C71', 2), 0.15)
# ILIM: pin 7 north to R73
_S('EF_ILM', 'B.Cu', _p7, _pad_xy('R73', 1), 0.15)
# grounds: exposed pad to pin 8, vias beside them; C70, R72, C71, R73 grounds to their own vias
_ep = _pad_xy('U16', 9)
_S('GND', 'B.Cu', (_p8[0], _ep[1] - 0.3), _p8, 0.25)
_S('GND', 'B.Cu', _p8, (17.35, _p8[1]), 0.25)
_V('GND', 17.35, _p8[1])
_S('GND', 'B.Cu', (_ep[0] + 0.7, _ep[1]), (17.4, _ep[1]), 0.4)
_V('GND', 17.4, _ep[1])
_c70g = _pad_xy('C70', 1)
_S('GND', 'B.Cu', _c70g, (16.2, 5.9), 0.25)
_V('GND', 16.2, 5.9)
_S('GND', 'B.Cu', _pad_xy('R72', 1), (16.2, 5.9), 0.25)
_c71g = _pad_xy('C71', 1)
_S('GND', 'B.Cu', _c71g, (19.1, 3.5), 0.25)
_V('GND', 19.1, 3.5)
_r73g = _pad_xy('R73', 2)
_S('GND', 'B.Cu', _r73g, (_r73g[0], -0.1), 0.25)
_V('GND', _r73g[0], -0.1)
R7F_LOG.append(f'r7f: U16 at ({EFX}, {EFY}) B; pins 4/3 {_p4}/{_p3} VBUS_IN, 5 {_p5} 5V, 2 {_p2} EN, 1 {_p1} dVdt, 7 {_p7} ILM, 8 {_p8} GND')

# ============ 2. CEC ESD diode D1 on F, between the CEC via and an existing GND via (J2 itself and its pads are on B) ============
# TPD1E10B06 DPY0002A land (SLLSEB1G p20): two 0.3 x 0.5 pads, 0.7 apart. Bidirectional, so pin order does not matter.
X1SON2 = [pad(1, -0.35, 0, 0.3, 0.5), pad(2, 0.35, 0, 0.3, 0.5)]
_new_part('D1', 'TPD1E10B06DPYR CEC ESD', 'C48260', 'X1SON-2_0.6x1', X1SON2, -9.0, -10.0, 0, {'1': 'HDMI_CEC', '2': 'GND'}, 'F', (-0.53, -0.33, 0.53, 0.33))
assert any(_is_via(it, 'HDMI_CEC', -9.436, -10.722) for it in _items)
assert any(_is_via(it, 'GND', -8.5, -10.95) for it in _items)
_S('HDMI_CEC', 'F.Cu', (-9.436, -10.722), _pad_xy('D1', 1), 0.15)
_S('GND', 'F.Cu', _pad_xy('D1', 2), (-8.5, -10.95), 0.2)
R7F_LOG.append(f"r7f: D1 at (-9.0, -10.0) F, CEC pad {_pad_xy('D1', 1)}, GND pad {_pad_xy('D1', 2)}")

# ============ 5/6. mounting holes: plated, on GND, 3.5 mm pad on both sides with the mask open (lid post seat is 3.8 mm) ============
MH_PAD = 2.9   # review r7f minor-3: 0.318 mm from the 1.5 mm corner chamfer (was 3.1 / 0.218 mm); the lid post (3.8 mm) bears on the 2.2-2.9 mm ring


def mh_fps(holes):
    return [f'''(footprint "mini:MH_2.2_PTH_GND" (layer "F.Cu") (uuid "{uid()}") (at {x + OX} {y + OY})
    (property "Reference" "H{i + 1}" (at 0 -2.3 0) (layer "F.Fab") (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (property "Value" "MH plated GND" (at 0 2.3 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))
    (attr board_only exclude_from_pos_files exclude_from_bom)
    (pad "1" thru_hole circle (at 0 0) (size {MH_PAD} {MH_PAD}) (drill 2.2) (layers "*.Cu" "*.Mask") (net {netid['GND']} "GND") (zone_connect 2) (uuid "{uid()}"))
  )''' for i, (x, y) in enumerate(holes)]


R7F_LOG.append(f'r7f: mounting holes {holes} plated, GND, pad {MH_PAD} mm')

# ============ VDD_MIPI via 0.585 mm from CSI_CK_P (there since r7d; the rule for non-GND vias is 0.62 mm): 0.07 mm east, its two stubs follow
_old_v, _new_v = (8.18, -1.686), (8.25, -1.686)
assert any(_is_via(it, 'VDD_MIPI', *_old_v) for it in _items)
for it in _items:
    if it['net'] == 'VDD_MIPI':
        if it['k'] == 'v' and _near(it['a'], _old_v):
            it['a'] = _new_v
        elif it['k'] == 's':
            if _near(it['a'], _old_v):
                it['a'] = _new_v
            if _near(it['b'], _old_v):
                it['b'] = _new_v
R7F_LOG.append(f'r7f: VDD_MIPI via {_old_v} -> {_new_v} (CSI_CK_P line at x 7.596: 0.584 -> 0.654 mm)')

# ============ 3. SD series 22 ohm, on B beside each line's first via ============
_new_pads = _pad_items()
_mhp = [dict(ref='H', n='1', net='GND', g=_PT(x, y).buffer(MH_PAD / 2), lys=('F.Cu', 'In2.Cu', 'B.Cu'), q=dict(kind='thru_hole', wx=x, wy=y), side='A') for x, y in holes]
_new_pads += _mhp


def _conn(a_it, b_it):
    la = _layers(a_it) if 'k' in a_it else a_it['lys']
    lb = _layers(b_it) if 'k' in b_it else b_it['lys']
    if not set(la) & set(lb):
        return False
    ga = _geom(a_it) if 'k' in a_it else a_it['g']
    gb = _geom(b_it) if 'k' in b_it else b_it['g']
    return ga.distance(gb) < 0.005


def _chain(net, via_pt, ly):
    """points of the copper run leaving via_pt on layer ly, followed until it forks or meets a pad/via: [(segment, start, end), ...]"""
    out, cur, used = [], via_pt, set()
    while True:
        nxt = [it for it in _items if it['k'] == 's' and it['net'] == net and it['ly'] == ly and id(it) not in used and (_near(it['a'], cur, 0.005) or _near(it['b'], cur, 0.005))]
        if len(nxt) != 1:
            return out
        s = nxt[0]
        used.add(id(s))
        e = s['b'] if _near(s['a'], cur, 0.005) else s['a']
        out.append((s, cur, e))
        if any(it['k'] == 'v' and it['net'] == net and _near(it['a'], e, 0.005) for it in _items) or any(d['net'] == net and d['g'].distance(_PT(e)) < 0.005 and ly in d['lys'] for d in _new_pads):
            return out
        cur = e


def _clear_poly(g, ly, net, G):
    for j in G.t.query(g.buffer(0.2)):
        gg, it = G.g[j]
        if it['net'] != net and ly in _layers(it) and gg.distance(g) < _CL + 0.01:
            return False
    for j in G.pt.query(g.buffer(0.2)):
        d = _new_pads[j]
        if d['net'] != net and ly in d['lys'] and d['g'].distance(g) < _CL + 0.01:
            return False
    return True


def _bbox_free(bb, side, skip=()):
    for p in parts:
        if p['side'] != side or p['ref'] in skip:
            continue
        o = bbox(p)
        if bb[0] < o[2] and o[0] < bb[2] and bb[1] < o[3] and o[1] < bb[3]:
            return False
    return True


def _place_series(ref, value, lcsc, net, far, via_pt, ly, sides=('B', 'F'), rng=3.2):
    """series resistor: old via (source side) -> pad A; pad B -> a point J on the downstream run (layer ly), with a new via at J when ly != side.
    The downstream run from the via to J is removed; everything beyond the via on the downstream side becomes net `far`."""
    global _items
    run = _chain(net, via_pt, ly)
    assert run, (net, via_pt, ly)
    # downstream becomes `far` up front: the run's segments, then whatever the source side no longer reaches
    for s_, a_, b_ in run:
        s_['net'] = far
    _flood_rename(net, far, via_pt)
    js, acc = [], 0.0
    for i_, (s, a, b) in enumerate(run):
        L = math.dist(a, b)
        k = 0.0
        while k <= L + 1e-9:
            t = k / L if L else 0
            js.append((acc + k, (round(a[0] + (b[0] - a[0]) * t, 3), round(a[1] + (b[1] - a[1]) * t, 3)), i_))
            k += 0.1
        acc += L
    js = [j for j in js if 0.45 <= j[0] <= 7.0]
    runids = {id(r_[0]) for r_ in run}
    saved = _items
    _items = [it for it in saved if id(it) not in runids]
    globals()['_new_pads'] = _pad_items() + _mhp
    G = _Geo()
    vgrid = []
    for ix in range(-int((rng + 1.5) / 0.1), int((rng + 1.5) / 0.1) + 1):
        for iy in range(-int((rng + 1.5) / 0.1), int((rng + 1.5) / 0.1) + 1):
            x_, y_ = round(via_pt[0] + ix * 0.1, 3), round(via_pt[1] + iy * 0.1, 3)
            if math.dist((x_, y_), via_pt) >= 0.5 and G.via_ok(x_, y_, far) and not any(d['g'].distance(_PT(x_, y_)) < 0.2 + _CL + 0.005 for d in _new_pads if d['net'] == far and d['q']['kind'] != 'thru_hole'):
                vgrid.append((x_, y_))

    def rest(i_, J):
        """copper of the run that stays when it is cut at J inside segment i_"""
        s, a, b = run[i_]
        out = [_LS([J, b]).buffer(s['w'] / 2)] if math.dist(J, b) > 0.005 else []
        return out + [_LS([r_[1], r_[2]]).buffer(r_[0]['w'] / 2) for r_ in run[i_ + 1:] if r_[0]['ly'] == ly]

    best = None
    why = {}
    _w = lambda k: why.__setitem__(k, why.get(k, 0) + 1)
    for side, rot in [(sd, rt) for sd in sides for rt in (0, 90)]:
      sly = side + '.Cu'
      for _once in (1,):
        for ix in range(-int(rng / 0.1), int(rng / 0.1) + 1):
            for iy in range(-int(rng / 0.1), int(rng / 0.1) + 1):
                cx, cy = round(via_pt[0] + ix * 0.1, 3), round(via_pt[1] + iy * 0.1, 3)
                dx, dy = (0.48, 0) if rot == 0 else (0, 0.48)
                pa, pb = sorted([(cx - dx, cy - dy), (cx + dx, cy + dy)], key=lambda p_: math.dist(p_, via_pt))
                if math.dist(pa, via_pt) < 0.55 or math.dist(pa, via_pt) > 2.0:
                    continue
                pw, ph = (0.56, 0.62) if rot == 0 else (0.62, 0.56)
                ga = _BOX(pa[0] - pw / 2, pa[1] - ph / 2, pa[0] + pw / 2, pa[1] + ph / 2)
                gb = _BOX(pb[0] - pw / 2, pb[1] - ph / 2, pb[0] + pw / 2, pb[1] + ph / 2)
                bb = (cx - (0.86 if rot == 0 else 0.41), cy - (0.41 if rot == 0 else 0.86), cx + (0.86 if rot == 0 else 0.41), cy + (0.41 if rot == 0 else 0.86))
                if not _bbox_free(bb, side):
                    _w('bbox'); continue
                if not (_clear_poly(ga, sly, net, G) and _clear_poly(gb, sly, far, G)):
                    _w('padclear'); continue
                if gb.distance(_PT(via_pt)) < 0.2 + _CL + 0.01:
                    _w('pb-via'); continue
                sa = _LS([via_pt, pa]).buffer(0.0635)
                if not G.stub_ok(via_pt, pa, sly, 0.127, net) or sa.distance(gb) < _CL + 0.01:
                    _w('stubA'); continue
                _w('Rok')
                base = math.dist(via_pt, pa)
                if best and base >= best[0]:
                    continue
                if ly == sly:
                    for dist, J, i_ in js:
                        cost = base + math.dist(pb, J) + 0.3 * dist
                        if best and cost >= best[0]:
                            continue
                        if math.dist(pb, J) > 2.5:
                            _w('Jfar'); continue
                        sb = _LS([pb, J]).buffer(0.0635)
                        if not G.stub_ok(pb, J, sly, 0.127, far) or sb.distance(ga) < _CL + 0.01 or sb.distance(_PT(via_pt).buffer(0.2)) < _CL + 0.01:
                            _w('stubB'); continue
                        if any(g_.distance(ga) < _CL + 0.01 or g_.distance(sa) < _CL + 0.01 for g_ in rest(i_, J)):
                            _w('rest'); continue
                        best = (cost, rot, (cx, cy), pa, pb, J, i_, dist, side, None)
                    continue
                # other layer: a new via N clear of everything, a stub pad B -> N on the part's side, a stub N -> J on the run's layer
                for N in sorted((n_ for n_ in vgrid if math.dist(n_, pb) <= 1.5), key=lambda n_: math.dist(n_, pb)):
                    c1 = base + math.dist(pb, N)
                    if best and c1 >= best[0]:
                        break
                    if ga.distance(_PT(N)) < 0.2 + _CL + 0.01 or sa.distance(_PT(N)) < 0.2 + _CL + 0.01:
                        _w('Nnear'); continue
                    sb = _LS([pb, N]).buffer(0.0635)
                    if math.dist(pb, N) > 0.01 and (not G.stub_ok(pb, N, sly, 0.127, far) or sb.distance(ga) < _CL + 0.01 or sb.distance(_PT(via_pt).buffer(0.2)) < _CL + 0.01):
                        _w('stubB'); continue
                    if gb.distance(_PT(N)) < 0.001 and math.dist(pb, N) < 0.35:
                        _w('Ninpad'); continue
                    for dist, J, i_ in sorted(js, key=lambda j_: math.dist(j_[1], N))[:8]:
                        cost = c1 + math.dist(N, J) + 0.3 * dist
                        if best and cost >= best[0]:
                            continue
                        if math.dist(N, J) > 2.0:
                            break
                        if math.dist(N, J) > 0.005 and not G.stub_ok(N, J, ly, 0.127, far):
                            _w('stubJ'); continue
                        best = (cost, rot, (cx, cy), pa, pb, J, i_, dist, side, N)
    if not best:
        for dist, J, i_ in js[::3]:
            v = _PT(J).buffer(0.2)
            bl = [(it['net'], it['k'], it['ly'], [tuple(round(c, 2) for c in p_) for p_ in _pts(it)]) for g_, it in G.g if it['net'] != far and g_.distance(v) < _CL + 0.005]
            bl += [(it['net'], 'via<0.45') for g_, it in G.g if it['k'] == 'v' and math.dist(it['a'], J) < 0.45]
            bl += [('pad', d['ref'], d['n'], d['net']) for d in _new_pads if d['net'] != far and d['g'].distance(v) < _CL + 0.005]
            print('   J', round(dist, 2), J, bl[:4])
    _items = saved
    assert best, f'no place for {ref} on {net}: {why}'
    cost, rot, (cx, cy), pa, pb, J, i_, dist, side, N = best
    sly = side + '.Cu'
    s, a, b = run[i_]
    gone = {id(r_[0]) for r_ in run[:i_ + 1]}
    _items = [it for it in _items if id(it) not in gone]
    if math.dist(J, b) > 0.005:
        _S(far, ly, J, b, s['w'])
    loc = {}
    for n_, (xx, yy) in (('1', (-0.48, 0)), ('2', (0.48, 0))):
        aa = math.radians(rot)
        c_, s_ = round(math.cos(aa), 6), round(math.sin(aa), 6)
        wx, wy = xx * c_ + yy * s_, -xx * s_ + yy * c_
        if side == 'B':
            wx = -wx
        loc[n_] = (round(cx + wx, 3), round(cy + wy, 3))
    na = '1' if _near(loc['1'], pa, 0.01) else '2'
    nb = '2' if na == '1' else '1'
    _new_part(ref, value, lcsc, 'R0402', R0402P, cx, cy, rot, {na: net, nb: far}, side, BODY['R0402'])
    _S(net, sly, via_pt, pa, 0.127)
    if N is None:
        _S(far, sly, pb, J, 0.127)
    else:
        if math.dist(pb, N) > 0.005:
            _S(far, sly, pb, N, 0.127)
        _V(far, N[0], N[1])
        if math.dist(N, J) > 0.005:
            _S(far, ly, N, J, 0.127)
    R7F_LOG.append(f'r7f: {ref} {value} at ({cx}, {cy}) rot {rot} {side}: via {via_pt} -> pad {na} {pa}; pad {nb} {pb} -> {"via " + str(N) + " -> " if N else ""}{J} on the {ly} run ({dist:.2f} mm from the via); cost {cost:.2f}')


def _flood_rename(net, far, src_pt):
    pads_ = _pad_items()
    nodes = [it for it in _items if it['net'] == net] + [d for d in pads_ if d['net'] == net]
    start = [n_ for n_ in nodes if 'k' in n_ and n_['k'] == 'v' and _near(n_['a'], src_pt)]
    seen = set(id(x) for x in start)
    todo = list(start)
    while todo:
        cur = todo.pop()
        for o in nodes:
            if id(o) not in seen and _conn(cur, o):
                seen.add(id(o))
                todo.append(o)
    n_it = 0
    for it in _items:
        if it['net'] == net and id(it) not in seen:
            it['net'] = far
            n_it += 1
    n_pd = []
    for d in pads_:
        if d['net'] == net and id(d) not in seen:
            _P[d['ref']]['nets'][d['n']] = far
            n_pd.append(f"{d['ref']}.{d['n']}")
    R7F_LOG.append(f'r7f: {far}: {n_it} items and pads {n_pd} moved from {net}')


def _f_chain(net, via_pt, pad_pt):
    """F.Cu segments from the via back to the pad (the module-side stub)"""
    out, cur, used = [], via_pt, set()
    for _k in range(8):
        nxt = [it for it in _items if it['k'] == 's' and it['net'] == net and it['ly'] == 'F.Cu' and id(it) not in used and (_near(it['a'], cur, 0.005) or _near(it['b'], cur, 0.005))]
        if not nxt:
            break
        s_ = min(nxt, key=lambda it: min(math.dist(it['a'], pad_pt), math.dist(it['b'], pad_pt)))
        used.add(id(s_))
        out.append(s_)
        cur = s_['b'] if _near(s_['a'], cur, 0.005) else s_['a']
        if math.dist(cur, pad_pt) < 0.8 and abs(cur[1] - pad_pt[1]) < 0.36 and cur[0] >= pad_pt[0] - 0.76:
            return out
    raise AssertionError(('stub chain', net, via_pt, pad_pt, [(_pts(o)) for o in out]))


def _place_series_f(ref, value, lcsc, net, far, via_pt, pref, rng=2.6):
    """series resistor on F between the module pad and the line's first via: the via and everything beyond it become `far`;
    pad B -> via is a straight F stub, the module pad -> pad A is a straight or one-bend F track"""
    global _items
    pq = next(q for q in _P['U1']['abs'] if q['n'] == pref)
    P = (pq['wx'], pq['wy'])
    stub = _f_chain(net, via_pt, P)
    sid = {id(o) for o in stub}
    _items = [it for it in _items if id(it) not in sid]
    # the via goes to `far` with its run: rename the via, then flood from the module pad
    for it in _items:
        if _is_via(it, net, *via_pt):
            it['net'] = far
    pads_ = _pad_items()
    nodes = [it for it in _items if it['net'] in (net, far)] + [d for d in pads_ if d['net'] == net]
    src = [d for d in pads_ if d['ref'] == 'U1' and d['n'] == pref]
    seen, todo = {id(src[0])}, list(src)
    while todo:
        cur = todo.pop()
        for o in nodes:
            if id(o) not in seen and (o.get('net') == net) and _conn(cur, o):
                seen.add(id(o))
                todo.append(o)
    moved = []
    for it in _items:
        if it['net'] == net and id(it) not in seen:
            it['net'] = far
    for d in pads_:
        if d['net'] == net and id(d) not in seen:
            _P[d['ref']]['nets'][d['n']] = far
            moved.append(f"{d['ref']}.{d['n']}")
    globals()['_new_pads'] = _pad_items() + _mhp
    G = _Geo()
    best, why = None, {}
    _w = lambda k: why.__setitem__(k, why.get(k, 0) + 1)
    for rot in (0, 90):
        for ix in range(-int(rng / 0.05), int(rng / 0.05) + 1):
            for iy in range(-int(rng / 0.05), int(rng / 0.05) + 1):
                cx, cy = round(via_pt[0] + ix * 0.05, 3), round(via_pt[1] + iy * 0.05, 3)
                dx, dy = (0.48, 0) if rot == 0 else (0, 0.48)
                pb, pa = sorted([(cx - dx, cy - dy), (cx + dx, cy + dy)], key=lambda p_: math.dist(p_, via_pt))
                L0 = math.dist(pb, via_pt) + math.dist(P, pa)
                if best and L0 >= best[0]:
                    continue
                pw, ph = (0.56, 0.62) if rot == 0 else (0.62, 0.56)
                ga = _BOX(pa[0] - pw / 2, pa[1] - ph / 2, pa[0] + pw / 2, pa[1] + ph / 2)
                gb = _BOX(pb[0] - pw / 2, pb[1] - ph / 2, pb[0] + pw / 2, pb[1] + ph / 2)
                bb = (cx - (0.86 if rot == 0 else 0.41), cy - (0.41 if rot == 0 else 0.86), cx + (0.86 if rot == 0 else 0.41), cy + (0.41 if rot == 0 else 0.86))
                if not _bbox_free(bb, 'F'):
                    _w('bbox'); continue
                if not (_clear_poly(ga, 'F.Cu', net, G) and _clear_poly(gb, 'F.Cu', far, G)):
                    _w('padclear'); continue
                if ga.distance(_PT(via_pt)) < 0.2 + _CL + 0.01:
                    _w('pa-via'); continue
                if gb.distance(_PT(via_pt)) < 0.001:
                    _w('via-in-pad'); continue
                sb = _LS([pb, via_pt]).buffer(0.0635)
                if not G.stub_ok(pb, via_pt, 'F.Cu', 0.127, far) or sb.distance(ga) < _CL + 0.01:
                    _w('stubB'); continue
                # module pad -> pad A: straight, or west along the pad row first then straight
                for W in [None] + [(round(P[0] - kx * 0.1, 3), round(P[1] + ky * 0.05, 3)) for kx in range(1, 30) for ky in range(-12, 13)]:
                    pts = [P, pa] if W is None else [P, W, pa]
                    L = math.dist(pb, via_pt) + sum(math.dist(u, v) for u, v in zip(pts, pts[1:]))
                    if best and L >= best[0]:
                        continue
                    ok = True
                    for u, v in zip(pts, pts[1:]):
                        if math.dist(u, v) < 0.005:
                            continue
                        g_ = _LS([u, v]).buffer(0.0635)
                        if not G.stub_ok(u, v, 'F.Cu', 0.127, net) or g_.distance(gb) < _CL + 0.01 or g_.distance(sb) < _CL + 0.01 or g_.distance(_PT(via_pt).buffer(0.2)) < _CL + 0.01:
                            ok = False
                            break
                    if not ok:
                        _w('pathA')
                        if os.environ.get('R7F_DBG') and why['pathA'] % 4000 == 1:
                            print('  pathA', ref, (cx, cy, rot), pts, [G.blockers(u, v, 'F.Cu', 0.127, net)[:3] for u, v in zip(pts, pts[1:])], round(_LS(pts).buffer(0.0635).distance(gb), 3), round(_LS(pts).distance(_PT(via_pt)), 3))
                        continue
                    best = (L, rot, (cx, cy), pa, pb, pts)
    assert best, f'no place for {ref} on {net}: {why}'
    L, rot, (cx, cy), pa, pb, pts = best
    loc = {}
    for n_, (xx, yy) in (('1', (-0.48, 0)), ('2', (0.48, 0))):
        aa = math.radians(rot)
        c_, s_ = round(math.cos(aa), 6), round(math.sin(aa), 6)
        loc[n_] = (round(cx + xx * c_ + yy * s_, 3), round(cy - xx * s_ + yy * c_, 3))
    na = '1' if _near(loc['1'], pa, 0.01) else '2'
    nb = '2' if na == '1' else '1'
    _new_part(ref, value, lcsc, 'R0402', R0402P, cx, cy, rot, {na: net, nb: far}, 'F', BODY['R0402'])
    for u, v in zip(pts, pts[1:]):
        if math.dist(u, v) > 0.005:
            _S(net, 'F.Cu', u, v, 0.127)
    _S(far, 'F.Cu', pb, via_pt, 0.127)
    R7F_LOG.append(f'r7f: {ref} {value} at ({cx}, {cy}) rot {rot} F: U1.{pref} -> {[tuple(round(c, 3) for c in p_) for p_ in pts]} pad {na}; pad {nb} {pb} -> via {via_pt} (now {far}); '
                   f'track {L:.2f} mm; {far} also takes {moved}; old stub {len(stub)} segs removed')


# The SD lines are boxed in at the module edge (LDO_VO4 on F above SD_D0, the via column 0.1 mm from the pads, J7's body on B), so no
# resistor fits between a pad and its first via. Instead: the six resistors sit in a 2 x 3 block on B in the free band between the HPD
# parts and J7 (x -19.4..-15.4, y -5.1..-2.4), every SD copper item is removed, and Freerouting routes the twelve new connections
# (U1 pad -> R pad 1, R pad 2 -> J7 pin and its 51k pull-up). The pull-ups R43-R47 go on the card side. data/r7f_route.ses holds that pass.
SD_NETS = ('SD_CLK', 'SD_CMD', 'SD_D0', 'SD_D1', 'SD_D2', 'SD_D3')
# each line keeps its module-side escape (the F stub from the U1 pad to the first via, and that via): r6's escape search placed them
_SD_ESC = {'SD_D0': ((-16.558, -4.944), '67'), 'SD_D1': ((-16.556, -4.1), '68'), 'SD_D2': ((-16.556, -2.943), '69'),
           'SD_D3': ((-16.988, -0.328), '70'), 'SD_CLK': ((-16.635, -1.335), '71'), 'SD_CMD': ((-16.564, -0.038), '72')}
_keep = set()
for _nn, (_vv, _pn) in _SD_ESC.items():
    _pq = next(q for q in _P['U1']['abs'] if q['n'] == _pn)
    _keep |= {id(o) for o in _f_chain(_nn, _vv, (_pq['wx'], _pq['wy']))}
    _keep |= {id(it) for it in _items if _is_via(it, _nn, *_vv)}
_drop(lambda it: it['net'] in SD_NETS and id(it) not in _keep, 'SD copper beyond the first via of each line (re-routed by Freerouting with the series resistors)')
_drop(lambda it: _is_via(it, 'GND', -19.05, -4.91), 'GND stitching via under the new SD resistor block')
for _r in ('J7', 'R43', 'R44', 'R45', 'R46', 'R47'):
    for _k, _nn in list(_P[_r]['nets'].items()):
        if _nn in SD_NETS:
            _P[_r]['nets'][_k] = _nn + '_C'
# B, rotation 0: pad 1 (module side) east, pad 2 (card side) west
# D0, D1, D2: a row each, west of the line's kept escape via, pad 1 (module side) 0.1 mm from the via and strapped to it.
# CLK, CMD, D3: the three spots left (B east of the via column, B at the west edge, F west of the via column), joined by the router.
_SD = [('R76', 'SD_D0', -17.62, -4.78, 0, 'B'), ('R77', 'SD_D1', -17.62, -3.92, 0, 'B'), ('R78', 'SD_D2', -17.62, -2.65, 0, 'B'),
       ('R74', 'SD_CLK', -15.92, -3.6, 90, 'B'), ('R75', 'SD_CMD', -19.25, -4.5, 90, 'B'), ('R79', 'SD_D3', -17.45, -1.0, 270, 'F')]
for _ref, _net, _x, _y, _rot, _sd in _SD:
    _new_part(_ref, '22 0402', 'C25092', 'R0402', R0402P, _x, _y, _rot, {'1': _net, '2': _net + '_C'}, _sd, BODY['R0402'])
# D3 by hand: R79 on F takes the place of the vertical part of D3's escape (x -17.0, y -1.5..-0.35); pad 1 (north) from the escape,
# pad 2 (south) to the escape via, which becomes the card side. C6's ground via moves 0.5 mm south to make room for pad 1.
_drop(lambda it: _is_seg(it, 'SD_D3', 'F.Cu', (-17.005, -0.346), (-17.005, -1.51)) or _is_seg(it, 'SD_D3', 'F.Cu', (-16.988, -0.328), (-17.005, -0.346)), 'D3 escape vertical (R79 goes there)')
assert _rename(lambda it: _is_via(it, 'SD_D3', -16.988, -0.328), 'SD_D3_C') == 1
# C6.2 keeps its ground through the F.Cu pour (its via had to go for R79, and no other spot within 1 mm is clear on all layers)
_drop(lambda it: _is_seg(it, 'GND', 'F.Cu', (-18.3, -1.88), (-17.53, -1.88)) or _is_via(it, 'GND', -17.53, -1.88), 'C6 ground via (R79 sits there)')
_r79a, _r79b = _pad_xy('R79', 1), _pad_xy('R79', 2)
assert _r79a[1] < _r79b[1], (_r79a, _r79b)
_S('SD_D3', 'F.Cu', (-17.005, -1.51), _r79a, 0.127)
_S('SD_D3_C', 'F.Cu', _r79b, (-16.988, -0.328), 0.127)
for _ref, _net in (('R76', 'SD_D0'), ('R77', 'SD_D1'), ('R78', 'SD_D2')):
    _v = _SD_ESC[_net][0]
    _p1 = _pad_xy(_ref, 1)
    assert _p1[0] > _x - 1 and abs(_p1[0] - _v[0]) < 0.62, (_ref, _p1, _v)
    _S(_net, 'B.Cu', _v, _p1, 0.127)
# R77 pad 2 is boxed in by R76/R78 and R75: R78 sits 0.3 mm lower (its courtyard meets J7's, pads and bodies stay clear) so a via fits
# between R77.2 and R78.2 and the router can leave the block through it
_S('SD_D1_C', 'B.Cu', _pad_xy('R77', 2), (-18.1, -3.285), 0.127)
_V('SD_D1_C', -18.1, -3.285)
R7F_LOG.append('r7f: SD series 22 ohm R74-R79: ' + ', '.join(f'{r} {n} ({x}, {y}) rot {ro} {sd}' for r, n, x, y, ro, sd in _SD))
R7F_ROUTED = set(SD_NETS) | {n + '_C' for n in SD_NETS}

# ============ 4. LCD series 33 ohm (placement in tools/r7f_lcd.py, decided with the user) ============
_lcd_file = os.path.join(HERE, 'tools', 'r7f_lcd.py')
if os.path.exists(_lcd_file) and not os.environ.get('R7F_NO_LCD'):
    exec(open(_lcd_file, encoding='utf-8').read())
else:
    R7F_LOG.append('r7f: LCD series resistors NOT placed (tools/r7f_lcd.py missing or R7F_NO_LCD set)')

# router copper for the r7f connections (R7F_ROUTE unset: data/r7f_route.ses; set but empty: none, to write the DSN for a new pass)
_R7F_DEF = os.path.join(HERE, 'data', 'r7f_route.ses')
# nets whose Freerouting copper is not taken (they are routed in data/r7f_hand.json instead)
R7F_SKIP = set(filter(None, os.environ.get('R7F_ROUTE_SKIP', '').split(',')))
for _rses in filter(None, os.environ.get('R7F_ROUTE', _R7F_DEF if os.path.exists(_R7F_DEF) else '').split(',')):
    _have = {(it['net'], it['ly'], tuple(round(v, 3) for p_ in _pts(it) for v in p_)) for it in _items}
    _have |= {(it['net'], it['ly'], tuple(round(v, 3) for p_ in _pts(it)[::-1] for v in p_)) for it in _items}
    _add = 0
    for t in ses_items(_rses, skip_unknown=True):
        it = _item(t)
        if it['net'] not in R7F_ROUTED or it['net'] in R7F_SKIP:
            continue
        if (it['net'], it['ly'], tuple(round(v, 3) for p_ in _pts(it) for v in p_)) not in _have:
            _items.append(it)
            _add += 1
    R7F_LOG.append(f'r7f: {_add} router items added from {_rses}')
# connections Freerouting left open, routed by tools/r7f_astar.py on the board above and stored in data/r7f_hand.json
_HAND = os.path.join(HERE, 'data', 'r7f_hand.json')
if os.path.exists(_HAND) and not os.environ.get('R7F_NO_HAND'):
    for _h in json.load(open(_HAND, encoding='utf-8')):
        for _sg in _h['segs']:
            _S(_h['net'], _sg[0], tuple(_sg[1]), tuple(_sg[2]), _h['w'])
        for _vv in _h['vias']:
            _V(_h['net'], _vv[0], _vv[1])
        R7F_LOG.append(f"r7f: hand route {_h['net']}: {len(_h['segs'])} segments, {len(_h['vias'])} vias, {_h['len']:.2f} mm ({_h['note']})")
# C6.2 (LDO_VO4 decoupling ground) lost its via to R79; with every other copper in place, look for a new one (r7e _escape search)
_new_pads = _pad_items() + _mhp
_c62 = next(d for d in _new_pads if d['ref'] == 'C6' and d['net'] == 'GND')
if not _reaches_via(_c62):
    G = _Geo()
    _pv, _how = _escape(_c62, w=0.15, reach=2.0, radii=tuple(round(0.5 + 0.05 * k, 2) for k in range(40)))
    R7F_LOG.append(f'r7f: C6.2 GND -> {_how} {_pv}' if _pv else 'r7f NO ESCAPE for C6.2')
# vias that reach copper on one layer only (the router took SD_CMD out on F, so its old escape via is a stub) and the 5V track end that the
# J5 link used to feed (now fed by the via at (14.75, 6.3)) are removed
_lyset = lambda v: {it['ly'] for it in _items if it['k'] == 's' and it['net'] == v['net'] and _geom(it).distance(_PT(v['a'])) < v['w'] / 2 - 0.01}
_dead = [v for v in _items if v['k'] == 'v' and v['net'].startswith(('SD_', 'LCD_')) and len(_lyset(v)) == 1]
_items[:] = [it for it in _items if not any(it is v for v in _dead)]
R7F_LOG.append(f"r7f: {len(_dead)} single-layer via(s) removed: {[(v['net'], v['a']) for v in _dead]}")
for it in _items:
    if _is_seg(it, '5V', 'B.Cu', (14.75, 5.75), (14.75, 6.85)):
        it['a'], it['b'] = (14.75, 6.3), (14.75, 6.85)
        R7F_LOG.append('r7f: 5V B track now starts at the eFuse via (14.75, 6.3)')
# J6.8's old 3V3 via also carried C63.1's B strap (r7b): its end follows to J6.8's new via
tracks[:] = [_text(it) for it in _items]
for _l in R7F_LOG:
    R7C_LOG.append(_l)
