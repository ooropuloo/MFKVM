# -*- coding: utf-8 -*-
# r7f item 4 (exec'd from tools/r7f_stage.py with its globals): 33 ohm in series with LCD_DIN and LCD_CLK, at the module pins.
# U1.24/25 and J6.3/4 were 0.43 mm apart (pad edge to pad edge), so no resistor fitted. Option A, as offered to the user:
#   J6 moves 0.65 mm east (+x), with its plane escapes; check_case's 'M2 shank clears the J6 envelope' falls from 0.88 to 0.23 mm (needs > 0.2).
#   Two 0201 33 ohm (UNI-ROYAL RC-01W33R0FT, LCSC C320843) sit in line between the module pad and the J6 pad, 0.1 mm from each.
# 0201 land: 0.30 x 0.30 pads, centres 0.54 apart (IPC-7351 RESC0603X26 least-material style; the KiCad 0402-sized default would
# not fit). The board vendor's 0201 rules are not checked here beyond DRC, maskcheck and holecheck: see R7F_REPORT.
J6_DX = 0.65
R0201P = [pad(1, -0.27, 0, 0.30, 0.30), pad(2, 0.27, 0, 0.30, 0.30)]
BODY['R0201'] = (-0.33, -0.18, 0.33, 0.18)    # UNI-ROYAL 0201: 0.60+-0.03 x 0.30+-0.03

# 1. J6 and everything of its nets that sits on its pads (track ends, the 3V3/GND escape vias and their stubs) moves +x
_j6 = _P['J6']
_old = [dict(q) for q in _j6['abs']]
_j6['x'] += J6_DX
bake(_j6)


def _on_old_j6(pt, net, ly):
    return any(_j6['nets'][q['n']] == net and abs(pt[0] - q['wx']) <= q['ww'] / 2 + 1e-6 and abs(pt[1] - q['wy']) <= q['wh'] / 2 + 1e-6
               and (q['kind'] == 'thru_hole' or ly in ('F.Cu', '*')) for q in _old)


_nm = 0
for it in _items:
    if it['k'] != 's':
        continue
    pts = _pts(it)
    new = [((p_[0] + J6_DX, p_[1]) if _on_old_j6(p_, it['net'], it['ly']) else p_) for p_ in pts]
    if new != pts:
        it['a'], it['b'] = new[0], new[1]
        _nm += 1
# plane escape vias now under a moved J6 pad, or too close to one, go with their stubs; the pads get new escapes (r7e _escape search)
_j6g = [(_BOX(q['wx'] - q['ww'] / 2, q['wy'] - q['wh'] / 2, q['wx'] + q['ww'] / 2, q['wy'] + q['wh'] / 2), _j6['nets'][q['n']]) for q in _j6['abs']]
_gone = [it for it in _items if it['k'] == 'v' and any(g.distance(_PT(it['a'])) < 0.2 + _CL + 0.01 for g, n in _j6g)]
_gp = {(round(v['a'][0], 3), round(v['a'][1], 3), v['net']) for v in _gone}
_items[:] = [it for it in _items if not any(it is g for g in _gone) and not (it['k'] == 's' and any((round(p_[0], 3), round(p_[1], 3), it['net']) in _gp for p_ in _pts(it))
                                                                        and any(g.distance(_LS(_pts(it))) < 0.01 for g, n in _j6g if n == it['net']))]
R7F_LOG.append(f'r7f: J6 moved +{J6_DX} mm in x; {_nm} track ends moved with its pads; {len(_gone)} escape vias under the new pads removed: {sorted(_gp)}')
_new_pads = _pad_items() + _mhp
for d in [d for d in _new_pads if d['ref'] == 'J6' and d['net'] in ('3V3', 'GND')]:
    if _reaches_via(d):
        continue
    G = _Geo()
    p_, how = _escape(d, w=0.2, reach=1.2)
    R7F_LOG.append(f'r7f: J6.{d["n"]} {d["net"]} -> {how} {p_}' if p_ else f'r7f NO ESCAPE for J6.{d["n"]}')
    _new_pads = _pad_items() + _mhp

# r7b had strapped C63.1 (3V3) on B to J6.8's escape via; the strap now goes to J6.8's new via
_v8 = [it for it in _items if it['k'] == 'v' and it['net'] == '3V3' and any(_near(it['a'], _pts(s_)[k], 0.01) for s_ in _items if s_['k'] == 's' and s_['net'] == '3V3'
       and s_['ly'] == 'F.Cu' for k in range(2) if any(abs(_pts(s_)[1 - k][0] - q['wx']) < q['ww'] / 2 and abs(_pts(s_)[1 - k][1] - q['wy']) < q['wh'] / 2 for q in _j6['abs'] if q['n'] == '8'))]
assert len(_v8) == 1, _v8
_S('3V3', 'B.Cu', _pad_xy('C63', 1), _v8[0]['a'], 0.15)
R7F_LOG.append(f"r7f: C63.1 3V3 strap on B to J6.8's new via {_v8[0]['a']}")

# 2. the two resistors, between U1.24/U1.25 and J6.3/J6.4, turned 90 degrees (pads stacked in y, 0.30 mm wide in x) and centred in x in
#    the 1.075 mm gap, so each pad is ~0.39 mm from the U1 castellation and from the J6 contact. The user solders U1 by hand with an iron
#    after assembly: >= 0.2 mm pad to pad with a solder-mask web in between is required (team lead, 2026-11-09); tools/hand_solder_gap.py
#    gates it. Pad 1 (module side) is the north pad, fed from the U1 pad along its south edge; pad 2 (south) goes to the J6 contact.
for _ref, _net, _un, _jn in (('R80', 'LCD_DIN', '24', '3'), ('R81', 'LCD_CLK', '25', '4')):
    _u = next(q for q in _P['U1']['abs'] if q['n'] == _un)
    _j = next(q for q in _j6['abs'] if q['n'] == _jn)
    assert _j6['nets'][_jn] == _net
    _ue, _je = _u['wx'] + _u['ww'] / 2, _j['wx'] - _j['ww'] / 2
    _x = round((_ue + _je) / 2, 4)
    _y = round((_u['wy'] + _j['wy']) / 2, 3)
    assert (_je - _ue - 0.30) / 2 >= 0.2 + 0.1, (_ref, _je - _ue)
    _drop(lambda it, n=_net: it['net'] == n and it['k'] == 's' and it['ly'] == 'F.Cu' and _u['wx'] - 0.8 <= min(it['a'][0], it['b'][0]) and max(it['a'][0], it['b'][0]) <= _j['wx'] + 0.8
          and abs(it['a'][1] - _y) < 0.4 and abs(it['b'][1] - _y) < 0.4, f'{_net} F track U1.{_un} -> J6.{_jn}')
    _j6['nets'][_jn] = _net + '_J'
    _new_part(_ref, '33 0201', 'C320843', 'R0201', R0201P, _x, _y, 270, {'1': _net, '2': _net + '_J'}, 'F', BODY['R0201'])
    _p1, _p2 = _pad_xy(_ref, 1), _pad_xy(_ref, 2)
    assert _p1[1] < _p2[1] and abs(_p1[0] - _x) < 1e-3, (_p1, _p2)
    assert _u['wy'] - _u['wh'] / 2 <= _p1[1] <= _u['wy'] + _u['wh'] / 2 and _j['wy'] - _j['wh'] / 2 <= _p2[1] - 0.12 <= _j['wy'] + _j['wh'] / 2
    _S(_net, 'F.Cu', (_u['wx'], _p1[1]), _p1, 0.127)                                   # inside the U1 pad, then straight east to pad 1
    _S(_net + '_J', 'F.Cu', _p2, (_j['wx'] - _j['ww'] / 2 + 0.18, _p2[1] - 0.12), 0.127)  # pad 2 to just inside the J6 contact
    R7F_LOG.append(f'r7f: {_ref} 33 ohm 0201 at ({_x}, {_y}) rot 270 F: pad 1 {_p1} (U1.{_un} edge {_ue:.3f}, gap {_p1[0] - 0.15 - _ue:.3f}); '
                   f'pad 2 {_p2} (J6.{_jn} edge {_je:.3f}, gap {_je - _p2[0] - 0.15:.3f})')
