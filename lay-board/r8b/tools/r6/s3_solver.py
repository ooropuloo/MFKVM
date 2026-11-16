# -*- coding: utf-8 -*-
# Q3: quasi-static 2D field solver (finite volume Laplace on a graded rectilinear grid), written for this review.
# Conductors are rectangles of real thickness. Validated against Cohn's exact stripline and coupled stripline results below.
# C and L per length: L from the same geometry with all dielectrics removed (L = 1/(c^2) C0^-1).
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl, math, json, sys
from scipy.special import ellipk
c0 = 299792458.0
e0 = 8.8541878128e-12


def graded(lines, fine, coarse, lo, hi, ratio=1.25):
    pts = sorted(set(round(x, 6) for x in list(lines) + [lo, hi]))
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        L = b - a
        # grade from both ends
        xs = [a]
        ds = fine
        left = a
        right = b
        lft = [a]
        rgt = [b]
        while right - left > 2.0 * ds:
            left += ds
            right -= ds
            lft.append(left)
            rgt.append(right)
            ds = min(ds * ratio, coarse)
        seg = lft + sorted(rgt)
        out += seg[1:]
    return np.array(sorted(set(round(x, 7) for x in out)))


class Xsec:
    def __init__(self, halfw=4.0):
        self.rects = []   # conductors: (x0,y0,x1,y1,id)  id>=0 signal, -1 ground-like, -2.. named planes
        self.diel = []    # (x0,y0,x1,y1,er) later wins
        self.xl = set()
        self.yl = set()
        self.halfw = halfw
        self.ymin = 0.0
        self.ymax = 1.0

    def cond(self, x0, y0, x1, y1, i):
        self.rects.append((x0, y0, x1, y1, i))
        self.xl.update((x0, x1))
        self.yl.update((y0, y1))

    def die(self, x0, y0, x1, y1, er):
        self.diel.append((x0, y0, x1, y1, er))
        self.xl.update((max(x0, -self.halfw), min(x1, self.halfw)))
        self.yl.update((y0, y1))

    def grid(self, fine=0.004, coarse=0.12):
        x = graded(self.xl, fine, coarse, -self.halfw, self.halfw)
        y = graded(self.yl, fine, coarse, self.ymin, self.ymax)
        return x, y

    def assemble(self, fine, air=False):
        x, y = self.grid(fine)
        nx, ny = len(x), len(y)
        dx, dy = np.diff(x), np.diff(y)
        xc, yc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:])
        eps = np.ones((nx - 1, ny - 1))
        if not air:
            for x0, y0, x1, y1, er in self.diel:
                ix = (xc >= x0) & (xc <= x1)
                iy = (yc >= y0) & (yc <= y1)
                eps[np.ix_(ix, iy)] = er
        idx = lambda i, j: i * ny + j
        N = nx * ny
        I, J, V = [], [], []
        # horizontal edges (i,j)-(i+1,j)
        for j in range(ny):
            el = eps[:, j - 1] * dy[j - 1] / 2 if j > 0 else 0
            er = eps[:, j] * dy[j] / 2 if j < ny - 1 else 0
            g = (el + er) / dx
            a = np.arange(nx - 1) * ny + j
            b = a + ny
            I += [a, b, a, b]
            J += [a, b, b, a]
            V += [g, g, -g, -g]
        for i in range(nx):
            el = eps[i - 1, :] * dx[i - 1] / 2 if i > 0 else 0
            er = eps[i, :] * dx[i] / 2 if i < nx - 1 else 0
            g = (el + er) / dy
            a = i * ny + np.arange(ny - 1)
            b = a + 1
            I += [a, b, a, b]
            J += [a, b, b, a]
            V += [g, g, -g, -g]
        K = sp.coo_matrix((np.concatenate(V), (np.concatenate(I), np.concatenate(J))), shape=(N, N)).tocsr()
        mark = -999 * np.ones(N, dtype=int)
        for x0, y0, x1, y1, cid in self.rects:
            ix = np.where((x >= x0 - 2e-6) & (x <= x1 + 2e-6))[0]
            iy = np.where((y >= y0 - 2e-6) & (y <= y1 + 2e-6))[0]
            for i in ix:
                mark[i * ny + iy] = cid
        return K, mark, N

    def solve(self, K, mark, N, ids):
        """returns C matrix [F/m] between conductors ids (other marked nodes grounded), plus charges on named planes."""
        free = np.where(mark == -999)[0]
        Kff = K[free][:, free].tocsc()
        lu = spl.splu(Kff)
        n = len(ids)
        Cm = np.zeros((n, n))
        planes = sorted(set(m for m in mark if m != -999 and m not in ids))
        Qp = np.zeros((n, len(planes)))
        for a, cid in enumerate(ids):
            V = np.zeros(N)
            V[mark == cid] = 1.0
            rhs = -K[free].dot(V)
            V[free] = lu.solve(rhs)
            Q = K.dot(V)
            for b, did in enumerate(ids):
                Cm[b, a] = Q[mark == did].sum() * e0
            for b, p in enumerate(planes):
                Qp[a, b] = Q[mark == p].sum() * e0
        return Cm, planes, Qp

    def matrices(self, ids, fine=0.004):
        K, mark, N = self.assemble(fine)
        C, planes, Qp = self.solve(K, mark, N, ids)
        K0, mark0, N0 = self.assemble(fine, air=True)
        C0, _, _ = self.solve(K0, mark0, N0, ids)
        L = np.linalg.inv(C0) / c0 ** 2
        return C, L, C0, planes, Qp


def modal(C, L, v):
    """Impedance and velocity for an excitation vector v (+1,-1 for diff, others 0) with others held at zero; Z=V/I with V across v-normalised."""
    v = np.asarray(v, float)
    Cv = v @ C @ v
    Liv = v @ np.linalg.inv(L) @ v
    # per unit: capacitance seen by mode scaled to 1V amplitude on v
    Z = math.sqrt((1 / Liv) / Cv)
    td = math.sqrt(Cv / Liv)
    return Z, td * 1e12 / 1e3  # ps/mm


def Zdiff(C, L, i=0, j=1):
    n = C.shape[0]
    v = np.zeros(n)
    v[i], v[j] = 1, -1
    Z, td = modal(C, L, v)
    return 4 * Z / 2 * 2 / 2, td  # placeholder corrected below


def zd(C, L, i=0, j=1):
    # Differential voltage Vd = V(+1) - V(-1) = 2 when v = (+1,-1); I = charge rate. Z_d = Vd / I.
    n = C.shape[0]
    v = np.zeros(n)
    v[i], v[j] = 1.0, -1.0
    Cv = v @ C @ v          # = Q_total_energy*2 / 1V^2 with V=(1,-1), Q on + = C11 - C12 etc
    Liv = v @ np.linalg.inv(L) @ v
    # Using Vd basis: Cd = Cv/4, Ld = 4/Liv
    Cd = Cv / 4
    Ld = 4 / Liv
    return math.sqrt(Ld / Cd), math.sqrt(Ld * Cd) * 1e9  # ohm, ps/mm (s/m -> ps/mm = 1e12/1e3)


def ze(C, L, i=0):
    Ci = C[i, i]
    Li = L[i, i]
    return math.sqrt(Li / Ci), math.sqrt(Li * Ci) * 1e9


# ---- stack
T_OUT, T_IN = 0.035, 0.0152
H_PP = 0.0994
H_CORE = 0.35
H_MID = 0.1164
ER_PP, ER_CORE, ER_MID = 4.1, 4.6, 4.16
ER_MASK = 3.8
M_SUB, M_TOP = 0.020, 0.012


def microstrip(traces, h=H_PP, t=T_OUT, er=ER_PP, mask=True, pours=(), halfw=4.0, m_sub=M_SUB, m_top=M_TOP, air_h=1.5):
    """traces: list of (xc,w,id). pours: (x0,x1). plane at y<=0 (id -1). Trace bottom at y=h."""
    X = Xsec(halfw)
    X.ymin = -0.02
    X.ymax = h + t + air_h
    X.cond(-halfw, -0.02, halfw, 0.0, -1)
    X.die(-halfw, 0, halfw, h, er)
    if mask:
        X.die(-halfw, h, halfw, h + m_sub, ER_MASK)
        for xc, w, i in traces:
            X.die(xc - w / 2 - m_top, h, xc + w / 2 + m_top, h + t + m_top, ER_MASK)
        for x0, x1 in pours:
            X.die(x0, h, x1, h + t + m_top, ER_MASK)
    for xc, w, i in traces:
        X.cond(xc - w / 2, h, xc + w / 2, h + t, i)
    for x0, x1 in pours:
        X.cond(x0, h, x1, h + t, -1)
    return X


def stripline(traces, h1=H_MID, h2=H_CORE, t=T_IN, er1=ER_MID, er2=ER_CORE, halfw=4.0):
    """h1 to In3 (below), trace, h2 to In1 (above, measured from the far side of the trace per JLC stack listing)."""
    X = Xsec(halfw)
    X.ymin = -0.02
    X.ymax = h1 + t + h2 + 0.02
    X.cond(-halfw, -0.02, halfw, 0, -2)            # In3 3V3
    X.cond(-halfw, h1 + t + h2, halfw, h1 + t + h2 + 0.02, -3)  # In1 GND
    X.die(-halfw, 0, halfw, h1 + t, er1)
    X.die(-halfw, h1 + t, halfw, h1 + t + h2, er2)
    for xc, w, i in traces:
        X.cond(xc - w / 2, h1, xc + w / 2, h1 + t, i)
    return X


def pair(w, g, xc=0):
    p = w + g
    return [(xc - p / 2, w, 0), (xc + p / 2, w, 1)]


def run_pair(X, fine=0.004):
    C, L, C0, pl, Qp = X.matrices([0, 1], fine)
    return zd(C, L), ze(C, L), (C, L, pl, Qp)


if __name__ == '__main__':
    print('--- Validation')
    # Cohn exact: zero-thickness centered stripline, b = 0.5, w = 0.2, er=1 -> Z = 30pi K(k1)/K(k), k=sech(pi w/2b)
    for w, b in ((0.2, 0.5), (0.127, 0.4)):
        k = 1 / math.cosh(math.pi * w / (2 * b))
        kp = math.sqrt(1 - k * k)
        Zex = 30 * math.pi * ellipk(k * k) / ellipk(kp * kp)  # Z0 = 30pi K(k)/K(k'), k = sech(pi w/2b)
        X = stripline([(0, w, 0)], h1=b / 2 - 0.0002, h2=b / 2 - 0.0002, t=0.0004, er1=1, er2=1, halfw=5)
        C, L, *_ = X.matrices([0], 0.002)
        print(' Cohn stripline w=%.3f b=%.3f exact %.2f, solver %.2f' % (w, b, Zex, ze(C, L)[0]))
    # Cohn coupled stripline: even/odd, k_e = tanh(pi w/2b) tanh(pi (w+s)/2b), k_o = tanh(pi w/2b) coth(pi(w+s)/2b)
    w, s, b = 0.15, 0.2, 0.5
    ke = math.tanh(math.pi * w / (2 * b)) * math.tanh(math.pi * (w + s) / (2 * b))
    ko = math.tanh(math.pi * w / (2 * b)) / math.tanh(math.pi * (w + s) / (2 * b))
    Zo_ex = 30 * math.pi * ellipk(1 - ko * ko) / ellipk(ko * ko)
    X = stripline(pair(w, s), h1=b / 2 - 0.0002, h2=b / 2 - 0.0002, t=0.0004, er1=1, er2=1, halfw=5)
    (Zd, td), _, _ = run_pair(X, 0.002)
    print(' Cohn coupled w=.15 s=.2 b=.5 exact Zdiff %.2f, solver %.2f' % (2 * Zo_ex, Zd))
    # Hammerstad-Jensen / Wheeler microstrip, thin strip, er=4.1, no mask
    w, h = 0.2, 0.1
    u = w / h
    er = 4.1
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    bb = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * bb)
    fu = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    Zhj = 60 / math.sqrt(ee) * math.log(fu / u + math.sqrt(1 + (2 / u) ** 2))
    X = microstrip([(0, w, 0)], h=h, t=0.0005, er=er, mask=False, halfw=5, air_h=3)
    C, L, *_ = X.matrices([0], 0.002)
    print(' H-J microstrip w=.2 h=.1 er4.1 thin: formula %.2f (eeff %.3f); solver %.2f (td %.3f ps/mm, formula %.3f)' % (Zhj, ee, ze(C, L)[0], ze(C, L)[1], math.sqrt(ee) / 0.2998))
    # grid convergence on the real case
    for f in (0.008, 0.004, 0.002):
        (Zd, td), (Zs, ts), _ = run_pair(microstrip(pair(0.127, 0.198)), f)
        print(' convergence fine=%.3f Zd=%.2f td=%.3f Zse=%.2f' % (f, Zd, td, Zs))

    R = {}
    print('\n--- Microstrip F/B, h=%.4f t=%.3f er=%.2f, mask %.3f/%.3f er %.1f' % (H_PP, T_OUT, ER_PP, M_SUB, M_TOP, ER_MASK))
    rows = [('TMDS/CSI 0.127/0.198, no pour', pair(0.127, 0.198), ()),
            ('0.127/0.198, no mask', None, ()),
            ('0.127/0.198, pour 0.12 both sides', pair(0.127, 0.198), ((-4, -0.1625 - 0.0635 - 0.12), (0.1625 + 0.0635 + 0.12, 4))),
            ('0.127/0.373 (ESD flow-through, pitch 0.5)', pair(0.127, 0.373), ()),
            ('0.127/0.373 pour 0.12 both sides', pair(0.127, 0.373), ((-4, -0.25 - 0.0635 - 0.12), (0.25 + 0.0635 + 0.12, 4))),
            ('0.127/0.873 (J2 escape, pitch 1.0)', pair(0.127, 0.873), ()),
            ('0.127/1.4 (CSI_D0 meander peak)', pair(0.127, 1.4), ()),
            ('USB 0.18/0.32', pair(0.18, 0.32), ()),
            ('USB 0.18/0.32 pour 0.12 both sides', pair(0.18, 0.32), ((-4, -0.25 - 0.09 - 0.12), (0.25 + 0.09 + 0.12, 4))),
            ('USB 0.18/0.82 (via fan-out pitch 1.0)', pair(0.18, 0.82), ()),
            ('USB2 F 0.15/0.35 (pitch .5)', pair(0.15, 0.35), ())]
    for name, tr, po in rows:
        if tr is None:
            X = microstrip(pair(0.127, 0.198), mask=False)
        else:
            X = microstrip(tr, pours=po)
        (Zd, td), (Zs, ts), _ = run_pair(X)
        print(' %-48s Zdiff %6.1f  odd td %.2f ps/mm  Zse %5.1f' % (name, Zd, td, Zs))
        R[name] = dict(Zd=Zd, td=td, Zs=Zs)

    print('\n--- Sensitivity around 0.127/0.198 no pour (finish w, h, er, t, gap)')
    base = dict(w=0.127, g=0.198, h=H_PP, er=ER_PP, t=T_OUT)
    for k, vals in dict(w=(0.107, 0.117, 0.137, 0.147), h=(0.0894, 0.0944, 0.1044, 0.1094), er=(3.8, 4.4), t=(0.03, 0.043)).items():
        for v in vals:
            d = dict(base)
            d[k] = v
            gg = d['g'] + (0.127 - d['w'] if k == 'w' else 0)  # etch: pitch constant
            X = microstrip(pair(d['w'], gg), h=d['h'], t=d['t'], er=d['er'])
            (Zd, td), _, _ = run_pair(X)
            print('  %s=%.4f gap=%.3f -> Zdiff %.1f' % (k, v, gg, Zd))
    # trapezoid proxy: mean width 0.127-0.0125 for 1 oz outer with narrower top is the w=0.117 row.
    print('\n--- Bus of 8 traces pitch 0.325 (w .127 gap .198): the pair in the middle, neighbours held quiet at 0 (low-Z proxy)')
    bus = [(-0.325 * 3.5 + 0.325 * i, 0.127, i) for i in range(8)]
    Xb = microstrip(bus)
    C, L, C0, pl, Qp = Xb.matrices(list(range(8)), 0.004)
    for i, j, nm in ((3, 2, 'middle lane N/P - hmm'), (2, 3, 'traces 2,3'), (4, 5, 'traces 4,5')):
        pass
    # Lanes: (0,1) (2,3) (4,5) (6,7)
    for a, b in ((0, 1), (2, 3), (4, 5), (6, 7)):
        print('  lane (%d,%d) Zdiff with neighbours grounded %.1f, td %.2f ps/mm' % (a, b, *zd(C, L, a, b)))
    # neighbours in their own differential mode: mode matrices
    T = np.zeros((4, 8))
    for k in range(4):
        T[k, 2 * k] = 0.5
        T[k, 2 * k + 1] = -0.5     # Vd mode: V+ = Vd/2, V- = -Vd/2; Q_d = (Q+ - Q-)/2
    S = T  # Vd->V map transposed
    Cdd = S @ C @ S.T
    Ldd = np.linalg.inv(S @ np.linalg.inv(L) @ S.T)
    print('  Modal Zdd (other lanes are matched-terminated, diag):', [round(math.sqrt(Ldd[k, k] / Cdd[k, k]), 1) for k in range(4)])
    print('  Cdd (pF/m)\n', np.round(Cdd * 1e12, 2))
    print('  Ldd (nH/m)\n', np.round(Ldd * 1e9, 1))
    print('  note P-N polarity: lane1 N adjacent lane2 P')
    for a, b in ((1, 2), (0, 1), (0, 2)):
        Kc = -Cdd[a, b] / math.sqrt(Cdd[a, a] * Cdd[b, b])
        Kl = Ldd[a, b] / math.sqrt(Ldd[a, a] * Ldd[b, b])
        Kb = 0.25 * (Kc + Kl)
        td = math.sqrt(Ldd[a, a] * Cdd[a, a]) * 1e9
        Kf = 0.5 * (Kc - Kl) * td  # per mm, ps/mm units
        print('  lane %d->%d: k_c %.4f k_l %.4f, NEXT Kb %.4f (%.1f dB) saturated above length tr/(2 td), FEXT coefficient %.3f ps/mm' % (a, b, Kc, Kl, Kb, 20 * math.log10(abs(Kb) + 1e-12), Kf))
    # single-ended neighbours
    print('  SE coupling trace 1->2 gap .198: Kb %.4f' % (0.25 * (-C[1, 2] / math.sqrt(C[1, 1] * C[2, 2]) + L[1, 2] / math.sqrt(L[1, 1] * L[2, 2]))))
    # Bus with pour 0.12 outside
    print('\n--- Same bus + B.Cu pour at 0.12 either side, quiet')
    Xb2 = microstrip(bus, pours=((-4, -0.325 * 3.5 - 0.0635 - 0.12), (0.325 * 3.5 + 0.0635 + 0.12, 4)))
    C2, L2, *_ = Xb2.matrices(list(range(8)), 0.004)
    for a, b in ((0, 1), (2, 3), (4, 5), (6, 7)):
        print('  lane (%d,%d) Zdiff %.1f' % (a, b, zd(C2, L2, a, b)[0]))

    print('\n--- In2 asymmetric stripline: In3 3V3 at %.4f (er %.2f), In1 GND at %.3f (er %.2f)' % (H_MID, ER_MID, H_CORE, ER_CORE))
    for w, g in ((0.127, 0.236), (0.127, 0.297), (0.127, 0.836), (0.127, 1.5), (0.0952, 1.4)):
        X = stripline(pair(w, g))
        C, L, C0, pl, Qp = X.matrices([0, 1], 0.003)
        q3 = abs(Qp[0][pl.index(-2)])
        q1 = abs(Qp[0][pl.index(-3)])
        print('  w=%.4f g=%.3f Zdiff %.1f Zse %.1f td %.2f ps/mm; single-line return split (self-cap to plane) 3V3 %.1f%% GND %.1f%%' % (w, g, zd(C, L)[0], ze(C, L)[0], zd(C, L)[1], 100 * q3 / (q3 + q1), 100 * q1 / (q3 + q1)))
    X = stripline([(0, 0.127, 0)])
    C, L, C0, pl, Qp = X.matrices([0], 0.003)
    q3 = abs(Qp[0][pl.index(-2)])
    q1 = abs(Qp[0][pl.index(-3)])
    print('  isolated w=.127 Zse %.1f td %.2f; charge on 3V3 %.1f%% GND %.1f%%' % (ze(C, L)[0], ze(C, L)[1], 100 * q3 / (q3 + q1), 100 * q1 / (q3 + q1)))

    print('\n--- Wide features over plane (per-mm C, for the localised discontinuities)')
    for w, nm in ((0.127, 'trace'), (0.18, 'USB trace'), (0.25, 'U8 pad width'), (0.3, 'J2 pad / BGA dia'), (0.609, 'U3 pad long side')):
        X = microstrip([(0, w, 0)])
        C, L, *_ = X.matrices([0], 0.004)
        print('  w=%.3f %-18s Zse %.1f C %.1f pF/m L %.1f nH/m td %.2f' % (w, nm, ze(C, L)[0], C[0, 0] * 1e12, L[0, 0] * 1e9, ze(C, L)[1]))
    json.dump(R, open('s3.json', 'w'), indent=1)
