# -*- coding: utf-8 -*-
# r7e stage of gen_mini.py (exec'd right after tools/r7d_stage.py, with its globals). R7E_REPORT.md has the reasons.
# REVIEW_r7d.md m1 and m2:
#   m2  a via whose drill lies inside a solder pad (any net) pulls solder out of the joint (C21.2 sat on R21.1's ground via). Such vias go;
#       the pads that relied on them get a ground via of their own next to the pad.
#   m1  U1.52 (module GND, next to the USB pins) had only a 0.25 mm neck of F.Cu pour. It gets a 0.2 mm track to a ground via.

R7E_LOG = []
_items = [_item(t) for t in tracks]
_new_pads = _pad_items()
_smd = [d for d in _new_pads if d['q']['kind'] != 'thru_hole']


def _drill_in_pad(it):
    h = _PT(it['a']).buffer(0.1)   # 0.2 mm drill
    return [d for d in _smd if any(ly in d['lys'] for ly in ('F.Cu', 'B.Cu')) and d['g'].intersects(h)]


_gone, _need = [], []
for it in [it for it in _items if it['k'] == 'v']:
    hit = _drill_in_pad(it)
    if hit:
        _gone.append(it)
        # pads of the via's net whose copper reached the via (the stub ends there, or the pad holds it)
        _stubs = [o for o in _items if o['k'] == 's' and o['net'] == it['net'] and any(math.dist(p, it['a']) < 0.02 for p in _pts(o))]
        for d in _smd:
            if d['net'] == it['net'] and d['g'].distance(_PT(it['a'])) < 3.0 and (d in hit or any(o['ly'] in d['lys'] and d['g'].buffer(0.01).intersects(_geom(o)) for o in _stubs)):
                _need.append(d)
        _names_hit = [d['ref'] + '.' + d['n'] for d in hit]
        R7E_LOG.append(f'r7e: via {it["net"]} at {tuple(round(v, 3) for v in it["a"])} has its drill in pad {_names_hit}: removed')
_items = [it for it in _items if not any(it is g for g in _gone)]


class _Geo:
    """cached geometry of every copper item and pad, with a spatial index, for fast clearance queries (r7d's checks rebuild buffers per call)"""
    def __init__(self):
        self.g = [(_geom(it), it) for it in _items]
        self.t = _TREE([g for g, _ in self.g])
        self.pg = [d['g'] for d in _new_pads]
        self.pt = _TREE(self.pg)
        self.csi = [_LS([it['a'], it['b']]) for it in _items if it['k'] == 's' and it['net'].startswith('CSI_')]

    def via_ok(self, x, y, net):
        v = _PT(x, y).buffer(0.2)
        if net != 'GND' and any(l.distance(_PT(x, y)) < 0.62 for l in self.csi):
            return False
        for j in self.t.query(v.buffer(0.5)):
            g, it = self.g[j]
            if it['net'] != net and g.distance(v) < _CL + 0.005:
                return False
            if it['k'] == 'v' and math.dist(it['a'], (x, y)) < 0.45:
                return False
        for j in self.pt.query(v.buffer(0.35)):
            d = _new_pads[j]
            if d['net'] != net and d['g'].distance(v) < _CL + 0.005:
                return False
            if d['net'] == net and (d['g'].intersects(v) or (d['q']['kind'] == 'thru_hole' and d['g'].distance(v) < 0.3)):
                return False
        return True

    def blockers(self, a, b, ly, w, net):
        st = _LS([a, b]).buffer(w / 2)
        out = [(it['net'], it['k'], it['ly'], [tuple(round(v, 3) for v in p) for p in _pts(it)]) for g, it in self.g if it['net'] != net and ly in _layers(it) and g.distance(st) < _CL + 0.005]
        out += [(f"pad {d['ref']}.{d['n']}", d['net']) for d in _new_pads if d['net'] != net and ly in d['lys'] and d['g'].distance(st) < _CL + 0.005]
        return out

    def stub_ok(self, a, b, ly, w, net):
        st = _LS([a, b]).buffer(w / 2)
        for j in self.t.query(st.buffer(0.2)):
            g, it = self.g[j]
            if it['net'] != net and ly in _layers(it) and g.distance(st) < _CL + 0.005:
                return False
        for j in self.pt.query(st.buffer(0.2)):
            d = _new_pads[j]
            if d['net'] != net and ly in d['lys'] and d['g'].distance(st) < _CL + 0.005:
                return False
        return True


def _escape(d, w=0.15, reach=1.0, radii=(0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.65, 1.8)):
    """a stub of width w from pad d to an existing via of its net within reach, else to a new via; returns the via point or None"""
    q = d['q']
    c = (q['wx'], q['wy'])
    ly = d['side'] + '.Cu'
    for it in sorted((it for it in _items if it['k'] == 'v' and it['net'] == d['net']), key=lambda it: math.dist(it['a'], c)):
        if math.dist(it['a'], c) > reach:
            break
        if G.stub_ok(c, it['a'], ly, w, d['net']):
            _items.append(dict(k='s', a=c, b=it['a'], w=w, ly=ly, net=d['net']))
            return it['a'], 'existing via'
    # a through-hole pad of the net (connector shell) within reach is as good as a via
    for o in sorted((o for o in _new_pads if o['net'] == d['net'] and o['q']['kind'] == 'thru_hole'), key=lambda o: o['g'].distance(_PT(c))):
        t = (o['q']['wx'], o['q']['wy'])
        if math.dist(t, c) > reach + 0.6:
            break
        if G.stub_ok(c, t, ly, w, d['net']):
            _items.append(dict(k='s', a=c, b=t, w=w, ly=ly, net=d['net']))
            return t, f"through-hole pad {o['ref']}.{o['n']}"
    for r in radii:
        for k in range(72):
            x, y = round(c[0] + r * math.cos(2 * math.pi * k / 72), 3), round(c[1] + r * math.sin(2 * math.pi * k / 72), 3)
            if G.via_ok(x, y, d['net']) and G.stub_ok(c, (x, y), ly, w, d['net']):
                _items.extend([dict(k='s', a=c, b=(x, y), w=w, ly=ly, net=d['net']), dict(k='v', a=(x, y), w=0.4, ly='*', net=d['net'])])
                return (x, y), 'new via'
    return None, None


def _reaches_via(d):
    seen, todo = set(), [d['g']]
    while todo:
        g = todo.pop()
        for i, it in enumerate(_items):
            if i in seen or it['net'] != d['net']:
                continue
            if _geom(it).distance(g) < 0.01:
                if it['k'] == 'v':
                    return True
                seen.add(i)
                todo.append(_geom(it))
                for o in _new_pads:
                    if o['net'] == d['net'] and o is not d and o['g'].distance(_geom(it)) < 0.01:
                        if o['q']['kind'] == 'thru_hole':
                            return True
                        todo.append(o['g'])
    return False


for d in _need:
    if _reaches_via(d):
        R7E_LOG.append(f'r7e: {d["ref"]}.{d["n"]} still reaches a {d["net"]} via through its copper')
        continue
    G = _Geo()
    p, how = _escape(d)
    R7E_LOG.append(f'r7e: {d["ref"]}.{d["n"]} {d["net"]} -> {how} {p}' if p else f'r7e NO ESCAPE for {d["ref"]}.{d["n"]}')

G = _Geo()
_u152 = next(d for d in _smd if d['ref'] == 'U1' and d['n'] == '52')
p, how = _escape(_u152, w=0.2, reach=2.6, radii=(0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.65, 1.8, 2.0, 2.2))
R7E_LOG.append(f'r7e: U1.52 GND -> 0.2 mm track to {how} {p}' if p else 'r7e NO ESCAPE for U1.52')
if not p and _os.environ.get('R7E_DEBUG'):
    for t in _os.environ['R7E_DEBUG'].split(';'):
        tx, ty = map(float, t.split(','))
        R7E_LOG.append(f'   blockers to {tx, ty}: {G.blockers((_u152["q"]["wx"], _u152["q"]["wy"]), (tx, ty), "F.Cu", 0.2, "GND")}')

tracks[:] = [_text(it) for it in _items]
for _l in R7E_LOG:
    R7C_LOG.append(_l)
