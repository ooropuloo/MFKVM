# -*- coding: utf-8 -*-
"""Real-part geometry for MF KVM v2 courtyard review. Board coordinates, mm, X-ray view from F side (KiCad view).
Every dimension says where it came from: DS = manufacturer drawing, STD = package standard (labelled worst case), ASSUME = my assumption."""
import sys
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
import parse

OX, OY = 100.0, 100.0
PLACE = 0.10  # ASSUME: per-part placement error after reflow. JLC publishes no number. Used on both parts of a pair.


def rect(cx, cy, w, h):
    return box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


class Part:
    def __init__(self, ref, src, height, body, body_max, leads=None, leads_max=None):
        self.ref, self.src, self.height = ref, src, height
        self.body, self.body_max = body, body_max
        self.leads, self.leads_max = leads or [], leads_max or []

    @property
    def metal(self):
        return unary_union([self.body] + self.leads)

    @property
    def metal_max(self):
        return unary_union([self.body_max] + self.leads_max)


def chip(ref, fp, L, W, H, dL, dW, src):
    """2-pad chip, long axis from the pads."""
    a, b = fp['pads'][:2]
    cx, cy = fp['x'], fp['y']
    horiz = abs(a['x'] - b['x']) > abs(a['y'] - b['y'])
    if horiz:
        return Part(ref, src, H, rect(cx, cy, L, W), rect(cx, cy, L + 2 * dL, W + 2 * dW))
    return Part(ref, src, H, rect(cx, cy, W, L), rect(cx, cy, W + 2 * dW, L + 2 * dL))


def sot235(ref, fp):
    """TI DBV0005A p35 of TLV733 SBVS235: body L 2.75-3.05 (x here), W 1.45-1.75, span 2.6-3.0, lead W 0.3-0.5, height 1.45 max.
    Note 4: mold flash up to 0.25 per side is NOT in the body dimension."""
    cx, cy = fp['x'], fp['y']
    xs = [-0.95, 0, 0.95]
    leads, lmax = [], []
    for x in xs:
        leads.append(box(cx + x - 0.2, cy + 0.8, cx + x + 0.2, cy + 1.4))
        lmax.append(box(cx + x - 0.25, cy + 0.875, cx + x + 0.25, cy + 1.5))
    for x in (-0.95, 0.95):
        leads.append(box(cx + x - 0.2, cy - 1.4, cx + x + 0.2, cy - 0.8))
        lmax.append(box(cx + x - 0.25, cy - 1.5, cx + x + 0.25, cy - 0.875))
    return Part(ref, 'DS TI DBV0005A', 1.45, rect(cx, cy, 2.9, 1.6), rect(cx, cy, 3.05 + 0.5, 1.75 + 0.0), leads, lmax)


def opto(ref, fp):
    """LITE-ON LTV-357T rev Aug 2013 p2 of 12: 4.40+-0.2 along the leads, 3.85+-0.3 along the pin pitch, shoulder 5.30+-0.3,
    tip span 7.00 +0.2/-0.7, lead W 0.40+-0.1, pitch 2.54+-0.25, H 2.00+-0.2."""
    cx, cy = fp['x'], fp['y']
    leads, lmax = [], []
    for sx in (-1, 1):
        for sy in (-1, 1):
            a, b = sorted((cx + sx * 2.2, cx + sx * 3.5))
            leads.append(box(a, cy + sy * 1.27 - 0.2, b, cy + sy * 1.27 + 0.2))
            a, b = sorted((cx + sx * 2.2, cx + sx * 3.6))
            lmax.append(box(a, cy + sy * 1.395 - 0.25, b, cy + sy * 1.395 + 0.25))
    return Part(ref, 'DS LITE-ON p2', 2.2, rect(cx, cy, 4.4, 3.85), rect(cx, cy, 4.8, 4.45 - 0.3), leads, lmax)


def j4(fp):
    """JST eSH p1/p3: B=8.0, depth 4.25, tail 0.7 past the rear, front outline 0.2 inside the tab pad's outer edge, height 2.9 (2.95 mated).
    Same numbers as the official KiCad F.Fab (-4,-1.675)-(4,2.575). Housing tolerance not published: +-0.1 ASSUME from JST's land +-0.1.
    Tail width not published: 0.3 ASSUME (inside the 0.6 land)."""
    cx, cy = fp['x'], fp['y']
    body = box(cx - 4, cy - 1.675, cx + 4, cy + 2.575)
    bmax = box(cx - 4.1, cy - 1.775, cx + 4.1, cy + 2.675)
    leads, lmax = [], []
    for q in fp['pads']:
        if q['n'] in '123456':
            leads.append(box(q['x'] - 0.15, cy - 2.375, q['x'] + 0.15, cy - 1.675))
            lmax.append(box(q['x'] - 0.2, cy - 2.475, q['x'] + 0.2, cy - 1.775))
    # reinforcement tabs stay inside their 1.2 x 1.8 lands; outline from the land, labelled ASSUME
    for q in fp['pads']:
        if q['n'] in '78':
            leads.append(rect(q['x'], q['y'], 1.0, 1.6))
            lmax.append(rect(q['x'], q['y'], 1.2, 1.8))
    return Part('J4', 'DS JST eSH p1,p3', 2.95, body, bmax, leads, lmax)


def j7(fp):
    """Molex SD-104031-001 rev B2 sheet 1: 11.95+-0.15 wide, 11.40+-0.15 deep, 1.42+-0.15 high, push-pull, normal type.
    Card 11 wide, 15.4 overall from the rear of the shell so 4.0+-0.2 out of the front. Footprint local (x,y) -> board (y, x) as placed by bake()."""
    cx, cy = fp['x'], fp['y']
    # local y -5.7..5.7 -> board x, local x -5.955..5.995 -> board y
    body = box(cx - 5.7, cy - 5.955, cx + 5.7, cy + 5.995)
    bmax = box(cx - 5.775, cy - 6.03, cx + 5.775, cy + 6.07)
    return Part('J7', 'DS Molex SD-104031-001', 1.57, body, bmax)


def osc(fp):
    """YXC YSO110TR datasheet p3: 3.2+-0.10 x 2.5+-0.10, 1.2 max. OT322527MJBA4SL is the 3.2x2.5 row (LCSC C725995 datasheet)."""
    cx, cy = fp['x'], fp['y']
    return Part('Y1', 'DS YXC YSO110TR p3', 1.2, rect(cx, cy, 3.2, 2.5), rect(cx, cy, 3.3, 2.6))


def ind4020(fp):
    """Sunlord SWPA4020S: 4.0+-0.2 square, 2.0 max. Part code from BOM; see REPORT source table for what was and was not confirmed."""
    cx, cy = fp['x'], fp['y']
    return Part('L1', 'STD SWPA4020 family 4.0x4.0', 2.0, rect(cx, cy, 4.0, 4.0), rect(cx, cy, 4.4, 4.4))


def build():
    fps, tree = parse.load()
    P = {}
    for r, fp in fps.items():
        if not r:
            continue
        lib = fp['lib'].split(':')[1]
        if lib == 'R0402':
            if r[0] == 'R':
                P[r] = chip(r, fp, 1.0, 0.5, 0.35, 0.10, 0.05, 'DS UNI-ROYAL 0402 p4')
            elif r in ('C17', 'C19'):
                P[r] = chip(r, fp, 1.0, 0.5, 0.5, 0.05, 0.05, 'DS FH 0402B471K500NT p5, CA')
            else:
                P[r] = chip(r, fp, 1.0, 0.5, 0.5, 0.05, 0.05, 'DS Samsung CL05 p6')
        elif lib == 'C0603':
            P[r] = chip(r, fp, 1.6, 0.8, 0.8, 0.10, 0.10, 'DS Samsung CL10 p6')
        elif lib == 'C0805':
            P[r] = chip(r, fp, 2.0, 1.25, 1.25, 0.15, 0.15, 'STD EIA 0805')
        elif lib == 'SOT-23-5':
            P[r] = sot235(r, fp)
        elif lib == 'OPTO_SO4':
            P[r] = opto(r, fp)
        elif lib == 'JST_SM06B':
            P[r] = j4(fp)
        elif lib == 'microSD_Molex_104031-0811':
            P[r] = j7(fp)
        elif lib == 'OSC3225':
            P[r] = osc(fp)
        elif lib == 'IND4020':
            P[r] = ind4020(fp)
        elif lib in ('TP_1.0', 'MH_2.2'):
            continue
        else:
            # sweep only: outline from the generated courtyard, shrunk by its 0.1 margin. Labelled, never used as a verdict.
            x0, y0, x1, y1 = fp['crt']
            b = box(x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1)
            P[r] = Part(r, 'courtyard-derived, sweep only', None, b, b)
    return fps, P, tree


def pad_poly(q):
    return rect(q['x'], q['y'], q['w'], q['h'])


def pads_of(fp, layer):
    return [q for q in fp['pads'] if layer in q['layers'] or '*.Cu' in q['layers']]
