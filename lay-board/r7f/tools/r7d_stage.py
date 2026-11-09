# -*- coding: utf-8 -*-
# r7d stage of gen_mini.py (exec'd from it, after the r7c stage, with its globals). R7D_REPORT.md has the reasons and the numbers.
#
# CSI option B: the TC358743 (U7) moves R7D_DX in x, away from the module's CSI pads, so CK and D1 can be lengthened to D0 with coupled
# meanders (Espressif ESP32-P4 HW Design Guidelines p28: inter-pair skew <= 30 mil, intra-pair <= 10 mil).
#   rigid: U7 and the parts on its north and east side move with it, so their copper and their distance to U7 do not change.
#   stay: C14, C16 (moved 0.8 mm further out), C19, C20 sit west of U7; U7 comes closer to them.
#   re-placed: C13, C15, C21 (the new U7 body covers their old places) and C17 (its old place is under the CSI meanders).
# Copper:
#   1. copper of the rigid parts' nets with every point inside the rigid area moves with them: hand fan-out, rails, plane escapes.
#      For GND and 3V3 only what is under U7 or hangs off a rigid part's pad moves (other parts' escapes in the area stay).
#   2. TMDS reaches U7 in straight horizontal runs; the run that crosses into the area keeps its outside end and slides its inside end.
#   3. every CSI item is replaced by data/r7d_csi.json (tools/r7d_csi_gen.py, checked by tools/r7c_csi_plan.py).
#   4. routed copper (not plane, not high speed) in the zone around the old and new footprint is removed; Freerouting routes it again
#      (R7D_DSN=1 writes the DSN with everything else protected; R7D_ROUTE=<ses> brings the router's new copper back).
#   5. copper that stays but now touches moved copper or a moved pad is removed (plane escapes are made again, signals re-routed).
#   6. plane pads that lost their escape, and the re-placed parts' plane pads, get a new stub and via clear of everything.
import json as _json
import os as _os

from shapely.geometry import LineString as _LS, Point as _PT, box as _BOX
from shapely.ops import unary_union as _UU
from shapely.strtree import STRtree as _TREE

R7D_DX = -2.5
R7D_RIGID = ['U7', 'C18', 'C22', 'C23', 'C24', 'C25', 'C26', 'C27', 'R20']   # C31 (not fitted) stays: moved, it would sit on R60
# (x, y, rotation, side B) for parts that get a new place
# rotations put the supply pad (pad 1) on the U7 side (bottom side: rotation 0 puts pad 1 east)
R7D_PLACE = {'C13': (-1.2, -0.6, 0), 'C15': (-1.0, -1.7, 0), 'C16': (-2.6, -0.9, 90), 'C21': (1.65, -7.95, 90), 'C17': (6.9, -5.4, 180)}
_names = {v: k for k, v in netid.items()}
_CL = 0.1


def _item(t):
    m = SEG_RE.match(t)
    if m:
        return dict(k='s', a=(float(m[1]) - OX, float(m[2]) - OY), b=(float(m[3]) - OX, float(m[4]) - OY), w=float(m[5]), ly=m[6], net=_names[int(m[7])])
    m = VIA_RE.match(t)
    return dict(k='v', a=(float(m[1]) - OX, float(m[2]) - OY), w=float(m[3]), ly='*', net=_names[int(m[4])])


def _text(it):
    if it['k'] == 's':
        return _seg(it['net'], it['ly'], it['a'], it['b'], round(it['w'], 4))
    return f'(via (at {it["a"][0] + OX:.4f} {it["a"][1] + OY:.4f}) (size {it["w"]}) (drill {0.25 if it["w"] >= 0.5 else 0.2}) (layers "F.Cu" "B.Cu") (net {netid[it["net"]]}) (uuid "{uid()}"))'


def _pts(it):
    return [it['a'], it['b']] if it['k'] == 's' else [it['a']]


def _geom(it):
    return _LS([it['a'], it['b']]).buffer(it['w'] / 2) if it['k'] == 's' else _PT(it['a']).buffer(it['w'] / 2)


def _layers(it):
    return ('F.Cu', 'In2.Cu', 'B.Cu') if it['ly'] == '*' else (it['ly'],)


def _pad_items():
    out = []
    for p in parts:
        for q in p['abs']:
            g = _PT(q['wx'], q['wy']).buffer(q['ww'] / 2) if q['shape'] == 'circle' else _BOX(q['wx'] - q['ww'] / 2, q['wy'] - q['wh'] / 2, q['wx'] + q['ww'] / 2, q['wy'] + q['wh'] / 2)
            lys = ('F.Cu', 'In2.Cu', 'B.Cu') if q['kind'] == 'thru_hole' else (p['side'] + '.Cu',)
            out.append(dict(ref=p['ref'], n=q['n'], net=p['nets'][q['n']], g=g, lys=lys, q=q, side=p['side']))
    return out


def _on_pad(pt, ly, net, pads_):
    return any(d['net'] == net and ly in d['lys'] and d['g'].buffer(0.01).contains(_PT(pt)) for d in pads_)


_rp = {r: _P[r] for r in R7D_RIGID}
_area = _UU([_BOX(*bbox(_rp[r])).buffer(0.35) for r in R7D_RIGID])
_u7box = _BOX(*bbox(_P['U7'])).buffer(0.35)
_cnets = {n for r in R7D_RIGID for n in _P[r]['nets'].values() if not n.startswith('unconnected')}
_old_pads = _pad_items()
_rigid_pads = [d for d in _old_pads if d['ref'] in R7D_RIGID]
_old_place = {r: (_P[r]['x'], _P[r]['y']) for r in R7D_PLACE}
_old_boxes = [_BOX(*bbox(_P[r])) for r in R7D_PLACE]
# plane pads that have an escape now; any of them without one at the end gets a new one
_items = [_item(t) for t in tracks if t]


def _touches_pad(d, items):
    return any(it['net'] == d['net'] and any(ly in d['lys'] for ly in _layers(it)) and _geom(it).intersects(d['g']) for it in items)


_plane_pads_before = {(d['ref'], d['n']) for d in _old_pads if d['net'] in PLANE and d['q']['kind'] != 'thru_hole'}

# ---- 1-3: classify
_moved, _stay, _dropped = [], [], []
_rigid_plane_vias = set()
for it in _items:
    if it['net'] in PLANE and it['k'] == 's':
        ends = _pts(it)
        on_rigid = [e for e in ends if any(d['net'] == it['net'] and it['ly'] in d['lys'] and d['g'].buffer(0.01).contains(_PT(e)) for d in _rigid_pads)]
        if on_rigid and all(_area.contains(_PT(e)) for e in ends):
            _rigid_plane_vias |= {(round(e[0], 3), round(e[1], 3)) for e in ends}
for it in _items:
    P_ = _pts(it)
    inside = [_area.contains(_PT(p)) for p in P_]
    if it['net'].startswith('CSI_') or it['net'] == 'TC_REFCLK':
        _dropped.append(it)
        continue
    if it['net'] in PLANE:
        if all(_u7box.contains(_PT(p)) for p in P_) or (all(inside) and any((round(p[0], 3), round(p[1], 3)) in _rigid_plane_vias for p in P_)):
            _moved.append(dict(it, a=(it['a'][0] + R7D_DX, it['a'][1]), b=(it['b'][0] + R7D_DX, it['b'][1]) if it['k'] == 's' else None))
        else:
            _stay.append(it)
        continue
    if it['net'] in _cnets and all(inside):
        _moved.append(dict(it, a=(it['a'][0] + R7D_DX, it['a'][1]), b=(it['b'][0] + R7D_DX, it['b'][1]) if it['k'] == 's' else None))
        continue
    if it['net'] in _cnets and any(inside) and it['k'] == 's' and abs(it['a'][1] - it['b'][1]) < 1e-3 and it['net'] in HS_NETS:
        a, b = (it['a'], it['b']) if inside[1] else (it['b'], it['a'])   # a outside, b inside
        nb = (b[0] + R7D_DX, b[1])
        if (nb[0] - a[0]) * (b[0] - a[0]) > 0 and abs(nb[0] - a[0]) > 0.05:
            _moved.append(dict(it, a=a, b=nb))
            continue
    if it['net'] in _cnets and any(inside):
        _dropped.append(it)
        continue
    _stay.append(it)

# placement
for r in R7D_RIGID:
    _P[r]['x'] += R7D_DX
    bake(_P[r])
for r, (x, y, rot) in R7D_PLACE.items():
    _P[r]['x'], _P[r]['y'], _P[r]['r'] = x, y, rot
    bake(_P[r])
_new_pads = _pad_items()

# 4: routed copper in the zone goes back to the router
_zone = _UU([_area, _shift_area := _UU([_BOX(*bbox(_rp[r])).buffer(0.35) for r in R7D_RIGID])] + [_BOX(*bbox(_P[r])).buffer(0.6) for r in R7D_PLACE] + [b.buffer(0.6) for b in _old_boxes]).buffer(0.3)
_keep = []
for it in _stay:
    if it['net'] not in PLANE and it['net'] not in HS_NETS and any(_zone.contains(_PT(p)) for p in _pts(it)) | _zone.intersects(_geom(it)):
        _dropped.append(it)
    else:
        _keep.append(it)
_stay = _keep
# copper of the re-placed parts' own pads (stubs whose end sat on an old pad of theirs), plane or not
_old_rp = [d for d in _old_pads if d['ref'] in R7D_PLACE]
_keep = []
for it in _stay:
    if any(d['net'] == it['net'] and any(ly in d['lys'] for ly in _layers(it)) and any(d['g'].buffer(0.01).contains(_PT(p)) for p in _pts(it)) for d in _old_rp):
        _dropped.append(it)
    else:
        _keep.append(it)
_stay = _keep

# 3: CSI plan
_plan = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(sys.argv[0])), 'data', 'r7d_csi.json'), encoding='utf-8'))
_csi = []
for net, lst in _plan['tracks'].items():
    for ly, pts in lst:
        for a, b in zip(pts, pts[1:]):
            _csi.append(dict(k='s', a=tuple(a), b=tuple(b), w=W_DIFF, ly=ly, net=net))
for net, x, y in _plan['vias']:
    _csi.append(dict(k='v', a=(x, y), w=0.4, ly='*', net=net))
_moved += _csi
# reference clock, hand routed: H5 south, then along y -7.0 (under the body edge, below the H-row dogbones) to C31.1 and R24.2, as r6 had it
_h5 = (round(ball('H5')[0] + R7D_DX, 4), ball('H5')[1])
_rc = [_h5, (_h5[0], -6.6), (_h5[0] + 0.4, -7.0), (5.68, -7.0), (6.08, -7.4), (6.08, -7.8), (6.92, -8.2)]
_hand = _csi + [dict(k='s', a=a, b=b, w=W_DIFF, ly='B.Cu', net='TC_REFCLK') for a, b in zip(_rc, _rc[1:])]
_moved += _hand[len(_csi):]


# 5: what stays and now touches moved copper or a moved pad
def _conflicts(fixed, mobile, mobile_pads):
    geo = [(_geom(it), it) for it in mobile] + [(d['g'], dict(net=d['net'], ly='+'.join(d['lys']), lys=d['lys'])) for d in mobile_pads]
    tree = _TREE([g for g, _ in geo])
    bad = []
    for it in fixed:
        g = _geom(it)
        for j in tree.query(g.buffer(_CL - 0.001)):
            mg, mo = geo[j]
            if mo['net'] == it['net']:
                continue
            mlys = mo.get('lys') or _layers(mo)
            if not set(_layers(it)) & set(mlys):
                continue
            if g.distance(mg) < _CL - 0.001:
                bad.append((it, mo))
                break
    return bad


_mpads = [d for d in _new_pads if d['ref'] in R7D_RIGID or d['ref'] in R7D_PLACE]
_bad = _conflicts(_stay, _moved, _mpads)
_hs_conf = []
for it, mo in _bad:
    if it['net'] in HS_NETS:
        _hs_conf.append((it['net'], it['ly'], _pts(it), mo['net']))
        continue
    _stay.remove(it)
    _dropped.append(it)
_spads = [d for d in _new_pads if d['ref'] not in R7D_RIGID and d['ref'] not in R7D_PLACE]

_all = _moved + _stay
tracks[:] = [_text(it) for it in _all]
_n0 = len(tracks)


def _key(it):
    return (it['net'], it['k'], it['ly'], tuple(round(v, 3) for p in _pts(it) for v in p))


# escapes that moved (pad stub plus its via) are kept even when their onward route was handed back to the router: prune() would
# take the via (one layer) and then the stub, and the router cannot reach a ball inside the BGA by itself
_esc = set()
for it in _moved:
    if it['k'] == 's' and any(_on_pad(p, it['ly'], it['net'], _new_pads) for p in _pts(it)):
        vs = [o for o in _moved if o['k'] == 'v' and o['net'] == it['net'] and any(math.dist(o['a'], p) < 0.02 for p in _pts(it))]
        if vs:   # a pad-to-via stub: the dogbone pattern
            _esc |= {_key(it)} | {_key(o) for o in vs}


def _prune(ts):
    out = prune(ts)
    have = set(out)
    return out + [t for t in ts if t not in have and _key(_item(t)) in _esc]


tracks[:] = _prune(tracks)
R7C_LOG.append(f'r7d: {len(R7D_RIGID)} parts moved {R7D_DX:+.2f} mm, {len(R7D_PLACE)} re-placed; {len(_moved) - len(_csi)} items moved, {len(_csi)} CSI items from the plan, '
               f'{len(_dropped)} removed, {_n0 - len(tracks)} pruned as dead ends')
# moved plane copper that now touches a pad or copper that stays is removed; its pad gets a new escape below
_items = [_item(t) for t in tracks]
_mkeys = {(it['net'], it['k'], tuple(round(v, 3) for p in _pts(it) for v in p)) for it in _moved if not any(it is h for h in _hand)}   # hand copper counts as fixed here
_mv = [it for it in _items if (it['net'], it['k'], tuple(round(v, 3) for p in _pts(it) for v in p)) in _mkeys]
_st = [it for it in _items if it not in _mv]
_hs_conf = [c for c in _hs_conf if c[0] not in PLANE]
for it, mo in _conflicts(_mv, _st, _spads + [d for d in _new_pads if d['ref'] in R7D_PLACE]):
    if it['net'] not in PLANE and it['net'] not in HS_NETS:
        if it in _items:
            _items.remove(it)
        R7C_LOG.append(f'r7d: moved {it["net"]} {it["k"]} at {[tuple(round(v, 3) for v in p) for p in _pts(it)]} touches {mo["net"]}; removed, the router makes it again')
        continue
    if it['net'] in PLANE:
        # the whole escape goes: the item, and the plane items of its net that share one of its points
        grp = [it] + [o for o in _items if o is not it and o['net'] == it['net'] and any(math.dist(p, r) < 0.02 for p in _pts(it) for r in _pts(o))]
        for o in grp:
            if o in _items:
                _items.remove(o)
        R7C_LOG.append(f'r7d: moved {it["net"]} {it["k"]} at {[tuple(round(v, 3) for v in p) for p in _pts(it)]} touches {mo["net"]}; {len(grp)} items removed')
    else:
        _hs_conf.append((it['net'], it['ly'], _pts(it), mo['net']))
tracks[:] = _prune([_text(it) for it in _items])
for c in _hs_conf:
    R7C_LOG.append(f'r7d CONFLICT (high speed or moved copper, fix by hand): {c}')

# U7.H8 (GND) has no room for a via: module pads 46 and 47 are south-east of it, the D1 meander is above it on F, REFCLK below it on B.
# It joins C17's ground pad on B instead (east along the H row, then up into the pad), which also gives C17 a short return to U7.
_h8, _c17g = ball('H8'), next((q['wx'], q['wy']) for q in _P['C17']['abs'] if _P['C17']['nets'][q['n']] == 'GND')
_h8 = (round(_h8[0] + R7D_DX, 4), _h8[1])
_g = [_h8, (_c17g[0] - 0.48, _h8[1]), (_c17g[0], _h8[1] + 0.48), _c17g]
tracks += [_seg('GND', 'B.Cu', a, b, 0.15) for a, b in zip(_g, _g[1:])]
# C17.1 (VDD_MIPI) to the F6 dogbone via on B, between the F and G ball rows (0.325 from each row's centres)
_c17v = next((q['wx'], q['wy']) for q in _P['C17']['abs'] if _P['C17']['nets'][q['n']] == 'VDD_MIPI')
_f6 = (round(ball('F6')[0] + R7D_DX - 0.325, 4), round(ball('F6')[1] - 0.325, 4))
_g = [_c17v, (_c17v[0] - 0.1, _f6[1]), _f6]
tracks += [_seg('VDD_MIPI', 'B.Cu', a, b, 0.127) for a, b in zip(_g, _g[1:])]
# HDMI_CEC (G1): its r6 escape via went west of the ball field, where C19 now sits; a via just west of G1 lets the router leave on In2
_g1 = (round(ball('G1')[0] + R7D_DX, 4), ball('G1')[1])
tracks += [_seg('HDMI_CEC', 'B.Cu', _g1, (_g1[0] - 0.825, _g1[1]), 0.15), _via('HDMI_CEC', _g1[0] - 0.825, _g1[1])]
# C15.1 (AVDD12) joins the AVDD12 In2 line the router laid at y -1.35 through a via east of its pad
_c15 = next((q['wx'], q['wy']) for q in _P['C15']['abs'] if _P['C15']['nets'][q['n']] == 'AVDD12')
tracks += [_seg('AVDD12', 'B.Cu', _c15, (_c15[0] + 0.67, _c15[1] + 0.35), 0.15), _via('AVDD12', _c15[0] + 0.67, _c15[1] + 0.35)]
# North of the ball field the r6 plane search strapped C22.2 and C23.2 (GND) straight to balls A2 and A3. After the move those two straps
# close the only B.Cu way out for A1 (TC_REXT) and A4 (TC_BIASDA), so they go; A2/A3 keep the GND via at their dogbone, C22/C23 get escapes below.
_u7p = {q['n']: (q['wx'], q['wy']) for q in _P['U7']['abs']}
_cp = [(q['wx'], q['wy']) for r in ('C22', 'C23') for q in _P[r]['abs'] if _P[r]['nets'][q['n']] == 'GND']
_drop = []
for t in tracks:
    it = _item(t) if SEG_RE.match(t) else None
    if it and it['net'] == 'GND' and it['ly'] == 'B.Cu':
        ends = _pts(it)
        if any(math.dist(e, c) < 0.02 for e in ends for c in _cp) and any(math.dist(e, _u7p[b]) < 0.02 for e in ends for b in ('A2', 'A3')):
            _drop.append(t)
tracks[:] = [t for t in tracks if t not in _drop]
R7C_LOG.append(f'r7d: {len(_drop)} GND straps C22/C23 to A2/A3 removed')
# 6: plane escapes
_items = [_item(t) for t in tracks]


def _clear_via(x, y, net, items, pads_):
    g = _PT(x, y).buffer(0.2)
    # a via that is not GND cuts an antipad (0.2 + 0.12 zone clearance, slivers under 0.13 dropped) into In1/In4: it must stay clear of the
    # CSI lines' reference strip (line + 0.1 mm each side), checked by verify.py
    if net != 'GND' and any(it['net'].startswith('CSI_') and it['k'] == 's' and _LS([it['a'], it['b']]).distance(_PT(x, y)) < 0.62 for it in items):
        return False
    for it in items:
        if it['net'] != net and _geom(it).distance(g) < _CL + 0.005:
            return False
        if it['k'] == 'v' and math.hypot(it['a'][0] - x, it['a'][1] - y) < 0.45:
            return False
    for d in pads_:
        if d['net'] != net and d['g'].distance(g) < _CL + 0.005:
            return False
        if d['net'] == net and d['q']['kind'] == 'thru_hole' and d['g'].distance(g) < 0.3:
            return False
        if d['net'] == net and d['g'].intersects(g):   # never a via in a pad
            return False
    return True


def _clear_stub(a, b, ly, w, net, items, pads_):
    g = _LS([a, b]).buffer(w / 2)
    for it in items:
        if it['net'] != net and ly in _layers(it) and _geom(it).distance(g) < _CL + 0.005:
            return False
    for d in pads_:
        if d['net'] != net and ly in d['lys'] and d['g'].distance(g) < _CL + 0.005:
            return False
    return True


_n_esc = 0
for d in _new_pads:
    if d['net'] not in PLANE or d['q']['kind'] == 'thru_hole':
        continue
    if (d['ref'], d['n']) not in _plane_pads_before and d['ref'] not in R7D_PLACE:
        continue
    if _touches_pad(d, _items):
        continue
    q = d['q']
    ly = d['side'] + '.Cu'
    best = None
    bga = d['ref'] == 'U7'
    # an existing via of the net within reach comes first (one stub, no new hole)
    for it in sorted((it for it in _items if it['k'] == 'v' and it['net'] == d['net']), key=lambda it: math.dist(it['a'], (q['wx'], q['wy']))):
        if math.dist(it['a'], (q['wx'], q['wy'])) > (1.6 if d['ref'] == 'U1' else 1.0):
            break
        if _clear_stub((q['wx'], q['wy']), it['a'], ly, 0.15, d['net'], _items, _new_pads):
            best = it['a']
            break
    if best:
        new = [dict(k='s', a=(q['wx'], q['wy']), b=best, w=0.15, ly=ly, net=d['net'])]
        _items += new
        tracks += [_text(it) for it in new]
        R7C_LOG.append(f'r7d escape {d["ref"]}.{d["n"]} {d["net"]} -> existing via {best}')
        continue
    for r in ((0.46,) if bga else ()) + (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.65, 1.8):
        for k in range(4 if r == 0.46 else 72):
            ang = math.pi / 4 + k * math.pi / 2 if r == 0.46 else 2 * math.pi * k / 72   # BGA: the dogbone diagonals first
            x, y = round(q['wx'] + r * math.cos(ang), 3), round(q['wy'] + r * math.sin(ang), 3)
            if _clear_via(x, y, d['net'], _items, _new_pads) and _clear_stub((q['wx'], q['wy']), (x, y), ly, 0.15, d['net'], _items, _new_pads):
                best = (x, y)
                break
        if best:
            break
    if not best:
        R7C_LOG.append(f'r7d NO ESCAPE for {d["ref"]}.{d["n"]} {d["net"]}')
        if _os.environ.get('R7D_DEBUG'):
            x, y = map(float, _os.environ['R7D_DEBUG'].split(','))
            R7C_LOG.append(f'   debug {d["ref"]}.{d["n"]} pad {q["wx"], q["wy"]} {q["ww"]}x{q["wh"]} clear_via {_clear_via(x, y, d["net"], _items, _new_pads)} clear_stub {_clear_stub((q["wx"], q["wy"]), (x, y), ly, 0.15, d["net"], _items, _new_pads)}')
            g = _PT(x, y).buffer(0.2)
            for it in _items:
                if (it['net'] != d['net'] and _geom(it).distance(g) < 0.105) or (it['k'] == 'v' and math.hypot(it['a'][0] - x, it['a'][1] - y) < 0.45):
                    R7C_LOG.append(f'   blocks via: {it["net"]} {it["k"]} {it["ly"]} {_pts(it)}')
            for o in _new_pads:
                if o['net'] != d['net'] and o['g'].distance(g) < 0.105:
                    R7C_LOG.append(f'   blocks via: pad {o["ref"]}.{o["n"]} {o["net"]}')
            st = _LS([(q['wx'], q['wy']), (x, y)]).buffer(0.075)
            for it in _items:
                if it['net'] != d['net'] and ly in _layers(it) and _geom(it).distance(st) < 0.105:
                    R7C_LOG.append(f'   blocks stub: {it["net"]} {it["k"]} {it["ly"]} {_pts(it)}')
            for o in _new_pads:
                if o['net'] != d['net'] and ly in o['lys'] and o['g'].distance(st) < 0.105:
                    R7C_LOG.append(f'   blocks stub: pad {o["ref"]}.{o["n"]} {o["net"]}')
        continue
    new = [dict(k='s', a=(q['wx'], q['wy']), b=best, w=0.15, ly=ly, net=d['net']), dict(k='v', a=best, w=0.4, ly='*', net=d['net'])]
    _items += new
    tracks += [_text(it) for it in new]
    _n_esc += 1
    R7C_LOG.append(f'r7d escape {d["ref"]}.{d["n"]} {d["net"]} -> via {best}')

# router copper from an earlier R7D_DSN pass: only what is not already on the board
# R7D_ROUTE unset: the two routing passes the release uses (data/r7d_route.ses: the full pass on the handed-back connections;
# data/r7d_route2.ses: a second pass on that board, which closed TC_PCKIN). Set but empty: none (to write the DSN for a new pass).
_R7D_DEF = ','.join(_os.path.join(HERE, 'data', f) for f in ('r7d_route.ses', 'r7d_route2.ses'))
for _rses in filter(None, _os.environ.get('R7D_ROUTE', _R7D_DEF).split(',')):
    _have = {(it['net'], it['ly'], tuple(round(v, 3) for p in _pts(it) for v in p)) for it in _items}
    _have |= {(it['net'], it['ly'], tuple(round(v, 3) for p in _pts(it)[::-1] for v in p)) for it in _items}
    _add = []
    for t in ses_items(_rses, skip_unknown=True):
        it = _item(t)
        if it['net'] in PLANE or it['net'] in HS_NETS:
            continue
        key = (it['net'], it['ly'], tuple(round(v, 3) for p in _pts(it) for v in p))
        if key not in _have:
            _add.append(t)
    tracks += _add
    _n1 = len(tracks)
    tracks[:] = prune([t for t in tracks if not (SEG_RE.match(t) and math.dist(*_pts(_item(t))) < 0.005)])
    R7C_LOG.append(f'r7d: {len(_add)} router items added from {_rses}, {_n1 - len(tracks)} pruned')
    _items = [_item(t) for t in tracks]
# return vias: a GND via within 0.7 mm of every CSI layer change (Espressif p28 asks for ground vias next to signal vias that change layer)
_items = [_item(t) for t in tracks]
for _cv in [it for it in _items if it['k'] == 'v' and it['net'].startswith('CSI_')]:
    if min(math.dist(_cv['a'], it['a']) for it in _items if it['k'] == 'v' and it['net'] == 'GND') <= 0.7:
        continue
    _best = None
    for r in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9):
        for k in range(72):
            x, y = round(_cv['a'][0] + r * math.cos(2 * math.pi * k / 72), 3), round(_cv['a'][1] + r * math.sin(2 * math.pi * k / 72), 3)
            if _clear_via(x, y, 'GND', _items, _new_pads):
                _best = (x, y)
                break
        if _best:
            break
    if _best:
        _items.append(dict(k='v', a=_best, w=0.4, ly='*', net='GND'))
        tracks.append(_via('GND', *_best))
        R7C_LOG.append(f'r7d: return via for {_cv["net"]} at {_cv["a"]}: GND via {_best}')
    else:
        R7C_LOG.append(f'r7d: NO return via within 0.9 mm for {_cv["net"]} at {_cv["a"]}')
# a 3V3 via with no 3V3 track or pad on it is an escape whose stub the move removed: it would only cut holes in In1/In4
_items = [_item(t) for t in tracks]
_orph = [it for it in _items if it['k'] == 'v' and it['net'] == '3V3' and not any(o is not it and o['net'] == '3V3' and o['k'] == 's' and _geom(o).distance(_PT(it['a'])) < 0.03 for o in _items)
         and not any(d['net'] == '3V3' and d['g'].distance(_PT(it['a'])) < 0.2 for d in _new_pads)]
tracks[:] = [t for t, it in zip(tracks, _items) if not any(it is o for o in _orph)]
R7C_LOG.append(f'r7d: {len(_orph)} orphan 3V3 vias removed {[tuple(round(v, 2) for v in o["a"]) for o in _orph]}')
R7D_ON = True
