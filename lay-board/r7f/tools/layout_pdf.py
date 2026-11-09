# -*- coding: utf-8 -*-
# Board drawings a person can read: real traces, real placement, and the pin number on every pad.
# Everything is drawn from the .kicad_pcb, nothing by hand. Vector output, so it can be zoomed.
# Usage: python tools/layout_pdf.py kicad/p4_kvm_mini.kicad_pcb fab_r6/p4_kvm_mini_gerber.zip out/design.json out.pdf
import datetime, hashlib, json, math, re, sys

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PCB, GERBER, DESIGN, OUT = sys.argv[1:5]
pdfmetrics.registerFont(TTFont("JH", "C:/Windows/Fonts/msjh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("JHB", "C:/Windows/Fonts/msjhbd.ttc", subfontIndex=0))
s = open(PCB, encoding="utf-8").read()
GHASH = hashlib.sha256(open(GERBER, "rb").read()).hexdigest()[:8]
# the Gerber the drawing belongs to: GERBER_SHA8 (first 8 hex of its sha256) must match when given; r6 pinned 525fb981 here
import os
assert GHASH == os.environ.get("GERBER_SHA8", GHASH), GHASH
REV = os.environ.get("BOARD_REV", "r6")
BBOX = {p["ref"]: p["bbox"] for p in json.load(open(DESIGN, encoding="utf-8"))["parts"]}
VALUE = {p["ref"]: p["value"] for p in json.load(open(DESIGN, encoding="utf-8"))["parts"]}
BUILD = datetime.datetime.now().strftime("%Y%m%d-%H%M")


def block(text, start):
    depth, i, q = 0, start, False
    while i < len(text):
        ch = text[i]
        if ch == '"' and text[i - 1] != "\\":
            q = not q
        elif not q:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return text[start:]


SEGS = [(float(a), float(b), float(c_), float(d), float(w), l, n) for a, b, c_, d, w, l, n in re.findall(
    r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([-\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]*)"\)', s)]
VIAS = [(float(x), float(y), float(z), float(dr), n) for x, y, z, dr, n in re.findall(
    r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)\s+\(drill ([\d.]+)\).*?\(net "([^"]*)"\)', s, flags=re.S)]
EDGE = [(float(a), float(b), float(c_), float(d)) for a, b, c_, d in re.findall(
    r'\(gr_line\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(stroke.*?\)\s*\)\s+\(layer "Edge.Cuts"\)', s, flags=re.S)]
# r6 pinned its own counts (1249 segments, 283 vias); since r7d the drawing must have read every segment and via the board text holds
assert len(SEGS) == len(re.findall(r'\(segment\b', s)) and len(VIAS) == len(re.findall(r'\(via\b', s)) and len(EDGE) >= 8, (len(SEGS), len(VIAS), len(EDGE))
assert {q[5] for q in SEGS} <= {"F.Cu", "B.Cu", "In2.Cu"}, {q[5] for q in SEGS}
POURS = []
for m in re.finditer(r"\(zone\s", s):
    z = block(s, m.start())
    if "(keepout" in z:  # the J8 rule area has no net and no fill
        continue
    net = re.search(r'\(net "([^"]*)"\)', z).group(1)
    for f in re.finditer(r'\(filled_polygon\s+\(layer "([^"]+)"\)\s+\(pts(.*?)\)\s*\)', z, flags=re.S):
        pts = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", f.group(2))]
        POURS.append((f.group(1), net, pts))
FPS = []
idx = [m.start() for m in re.finditer(r"\(footprint\s", s)]
for st in idx:
    b = block(s, st)
    ref = re.search(r'\(property "Reference" "([^"]+)"', b)
    if not ref:
        continue
    t = re.search(r"translate ([-\d.]+) ([-\d.]+)", b)
    ox, oy = float(t.group(1)), float(t.group(2))
    side = re.search(r'\(layer "([FB])\.Cu"\)', b).group(1)
    pads = []
    for pm in re.finditer(r'\(pad "([^"]*)" (\w+) (\w+)\s+\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s+\(size ([\d.]+) ([\d.]+)\)', b):
        pb = block(b, pm.start())
        n = re.search(r'\(net "([^"]*)"\)', pb)
        pads.append(dict(n=pm.group(1), kind=pm.group(2), shape=pm.group(3), x=ox + float(pm.group(4)), y=oy + float(pm.group(5)),
                         r=float(pm.group(6) or 0), w=float(pm.group(7)), h=float(pm.group(8)), net=n.group(1) if n else "",
                         drill=re.search(r"\(drill (?:oval )?([\d.]+)", pb).group(1) if "(drill" in pb else None))
    FPS.append(dict(ref=ref.group(1), x=ox, y=oy, side=side, pads=pads))
assert sum(len(f["pads"]) for f in FPS) > 450

W, H = landscape(A3)
c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle(f"MF KVM v2 {REV} PCB 佈局與腳位")
PAGE = [0]
HDMI = re.compile(r"^(D\d|CK)_[PN]$")


def color(net):
    if net == "GND":
        return (0.42, 0.45, 0.48)
    if net in ("3V3", "5V", "V1V2", "V2V5", "AVDD25", "AVDD12", "VDD_MIPI", "VDDC", "SD1_VDD", "OSC_VDD", "HOST_VBUS", "SD_SRC", "SW"):
        return (0.82, 0.13, 0.13)
    if HDMI.match(net):
        return (0.50, 0.18, 0.72)
    if net.startswith("CSI"):
        return (0.90, 0.45, 0.03)
    if net.startswith("USB"):
        return (0.05, 0.42, 0.82)
    if net.startswith("SD_"):
        return (0.02, 0.56, 0.42)
    return (0.16, 0.20, 0.26)


def view(title, note, layer, x0, x1, y0, y1, mirror=False):
    """Draw one copper layer. layer F.Cu / B.Cu / In2.Cu; x and y are board mm."""
    PAGE[0] += 1
    TOP, BOT, L, R = H - 66, 34, 28, W - 28
    k = min((R - L) / (x1 - x0), (TOP - BOT) / (y1 - y0))
    px0 = L + ((R - L) - k * (x1 - x0)) / 2
    py0 = BOT + ((TOP - BOT) - k * (y1 - y0)) / 2

    def T(x, y):
        return (px0 + (x1 - x) * k if mirror else px0 + (x - x0) * k, py0 + (y1 - y) * k)

    c.setFont("JHB", 16); c.setFillColorRGB(0.1, 0.12, 0.16); c.drawString(28, H - 32, title)
    c.setFont("JH", 9.5); c.setFillColorRGB(0.3, 0.33, 0.38); c.drawString(28, H - 50, note)
    c.setFont("JH", 8.5); c.setFillColorRGB(0.4, 0.42, 0.46)
    c.drawString(28, 16, f"MF KVM v2 {REV}  ·  Gerber {GHASH}  ·  build {BUILD}  ·  直接取自 KiCad 板檔，比例 {k / 2.835:.1f}:1（A3）")
    c.drawRightString(W - 28, 16, f"第 {PAGE[0]} 頁")
    for i, (lab, col) in enumerate((("HDMI", (0.50, 0.18, 0.72)), ("CSI", (0.90, 0.45, 0.03)), ("USB", (0.05, 0.42, 0.82)), ("SD", (0.02, 0.56, 0.42)), ("電源", (0.82, 0.13, 0.13)), ("GND", (0.42, 0.45, 0.48)), ("其他", (0.16, 0.20, 0.26)))):
        xx = W - 28 - (7 - i) * 62
        c.setStrokeColorRGB(*col); c.setLineWidth(2.5); c.line(xx, H - 28, xx + 18, H - 28)
        c.setFont("JH", 8.5); c.setFillColorRGB(0.2, 0.22, 0.26); c.drawString(xx + 22, H - 31, lab)
    c.setFont("JH", 8.5); c.setFillColorRGB(0.3, 0.33, 0.38)
    c.drawRightString(W - 28, H - 46, "粉紅圈＝第 1 腳  ·  ○＝過孔  ·  淡綠底＝這層的銅皮")

    # clip to drawing area
    c.saveState()
    a = c.beginPath(); a.rect(L, BOT, R - L, TOP - BOT); c.clipPath(a, stroke=0, fill=0)
    c.setFillColorRGB(0.985, 0.985, 0.975); c.rect(L, BOT, R - L, TOP - BOT, stroke=0, fill=1)
    for lay, net, pts in POURS:
        if lay != layer:
            continue
        p = c.beginPath(); p.moveTo(*T(*pts[0]))
        for q in pts[1:]:
            p.lineTo(*T(*q))
        p.close()
        c.setFillColorRGB(*((0.99, 0.90, 0.90) if net == "3V3" else (0.84, 0.92, 0.84)))
        c.drawPath(p, stroke=0, fill=1, fillMode=0)
    c.setStrokeColorRGB(0.1, 0.1, 0.1); c.setLineWidth(1.4)
    for a_, b_, c_, d_ in EDGE:
        c.line(*T(a_, b_), *T(c_, d_))

    c.setLineCap(1)
    drawn = 0
    for q in SEGS:
        if q[5] != layer:
            continue
        c.setStrokeColorRGB(*color(q[6])); c.setLineWidth(max(q[4] * k, 0.5))
        c.line(*T(q[0], q[1]), *T(q[2], q[3]))
        drawn += 1
    c.setLineCap(0)

    in_view = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1
    for x, y, z, dr, net in VIAS:
        cx, cy = T(x, y)
        c.setFillColorRGB(*color(net)); c.setStrokeColorRGB(1, 1, 1); c.setLineWidth(0.2)
        c.circle(cx, cy, z / 2 * k, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1); c.circle(cx, cy, dr / 2 * k, stroke=0, fill=1)

    # footprints on this side
    want = {"F.Cu": "F", "B.Cu": "B"}.get(layer)
    fsz_net = min(0.42 * k, 7.5)
    for f in FPS:
        mine = want == f["side"]
        for pd in f["pads"]:
            hole = pd["kind"] != "smd"
            if not (mine or (hole and layer in ("F.Cu", "B.Cu"))):
                continue
            cx, cy = T(pd["x"], pd["y"])
            w, h = pd["w"] * k, pd["h"] * k
            rot = pd["r"]
            if hole and pd["kind"] == "np_thru_hole":
                c.setFillColorRGB(1, 1, 1); c.setStrokeColorRGB(0, 0, 0); c.setLineWidth(0.7)
                c.circle(cx, cy, w / 2, stroke=1, fill=1)
                continue
            c.saveState(); c.translate(cx, cy); c.rotate(rot if mirror else -rot)
            if not mine:
                c.setFillColorRGB(0.82, 0.78, 0.66)
            else:
                c.setFillColorRGB(0.93, 0.77, 0.33)
            c.setStrokeColorRGB(0.45, 0.32, 0.05); c.setLineWidth(0.35)
            if pd["shape"] == "circle":
                c.circle(0, 0, w / 2, stroke=1, fill=1)
            elif pd["shape"] == "oval":
                c.roundRect(-w / 2, -h / 2, w, h, min(w, h) / 2, stroke=1, fill=1)
            else:
                c.rect(-w / 2, -h / 2, w, h, stroke=1, fill=1)
            c.restoreState()
            if pd["drill"]:
                c.setFillColorRGB(1, 1, 1); c.circle(cx, cy, float(pd["drill"]) / 2 * k, stroke=0, fill=1)
            if mine and pd["n"]:
                fs = max(min(min(w, h) * 0.72, 8.5), 2.2)
                if len(pd["n"]) > 2:
                    fs = min(fs, max(w, h) / (len(pd["n"]) * 0.62))
                c.setFont("JHB", fs); c.setFillColorRGB(0.05, 0.05, 0.05)
                c.drawCentredString(cx, cy - fs * 0.35, pd["n"])
                if pd["n"] in ("1", "A1") and f["ref"][0] in "UJQY":
                    c.setStrokeColorRGB(0.92, 0.10, 0.62); c.setLineWidth(1.1)
                    c.circle(cx, cy, min(w, h) / 2 + 1.0, stroke=1, fill=0)
    # body outlines and refs
    for f in FPS:
        if want != f["side"] or f["ref"].startswith("TP"):
            continue
        bb = BBOX.get(f["ref"])
        if not bb:
            continue
        ax, ay = T(bb[0] + 100, bb[1] + 100)
        bx, by = T(bb[2] + 100, bb[3] + 100)
        xa, xb, ya, yb = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
        big = f["ref"][0] in "UJQYL"
        c.setStrokeColorRGB(*((0.05, 0.25, 0.60) if big else (0.35, 0.40, 0.48))); c.setLineWidth(0.9 if big else 0.4)
        c.setDash(3, 2) if f["ref"] == "U1" else c.setDash()
        c.rect(xa, ya, xb - xa, yb - ya, stroke=1, fill=0)
        c.setDash()

    def draw_refs():
        for f in FPS:
            if want != f["side"] or f["ref"].startswith("TP"):
                continue
            bb = BBOX.get(f["ref"])
            if not bb:
                continue
            big = f["ref"][0] in "UJQYL"
            cx, cy = T(f["x"], f["y"])
            if f["ref"] == "U1":
                cx, cy = T((bb[0] + bb[2]) / 2 + 100, (bb[1] + bb[3]) / 2 + 100)
            fs = max(min(0.95 * k, 15) if big else min(0.52 * k, 7.5), 4)
            if not big:
                # above the part, so the pads and their pin numbers stay visible
                top = max(T(bb[0] + 100, bb[1] + 100)[1], T(bb[2] + 100, bb[3] + 100)[1])
                cy = top + fs * 0.45
            c.setFont("JHB", fs); tw = pdfmetrics.stringWidth(f["ref"], "JHB", fs)
            c.setFillColorRGB(1, 1, 1); c.setFillAlpha(0.85)
            c.roundRect(cx - tw / 2 - 1, cy - fs * 0.42, tw + 2, fs * 1.05, 1, stroke=0, fill=1)
            c.setFillAlpha(1)
            c.setFillColorRGB(*((0.03, 0.2, 0.55) if big else (0.1, 0.1, 0.1)))
            c.drawCentredString(cx, cy - fs * 0.25, f["ref"])
            if big and k > 25:
                v = VALUE.get(f["ref"], "").split(" 3.3V")[0][:26]
                c.setFont("JH", 6.5); tw = pdfmetrics.stringWidth(v, "JH", 6.5)
                c.setFillColorRGB(1, 1, 1); c.rect(cx - tw / 2 - 1, cy - fs * 0.42 - 8.5, tw + 2, 8, stroke=0, fill=1)
                c.setFillColorRGB(0.2, 0.25, 0.35); c.drawCentredString(cx, cy - fs * 0.42 - 7, v)

    # net name beside each pad on zoomed pages
    if k >= 22:
        for f in FPS:
            if want != f["side"]:
                continue
            for pd in f["pads"]:
                if not pd["net"] or pd["net"].startswith("unconnected") or pd["net"] == "GND" or not in_view(pd["x"], pd["y"]):
                    continue
                cx, cy = T(pd["x"], pd["y"])
                fx, fy = T(f["x"], f["y"])
                dx, dy = cx - fx, cy - fy
                w, h = pd["w"] * k, pd["h"] * k
                c.setFont("JH", fsz_net)
                tw = pdfmetrics.stringWidth(pd["net"], "JH", fsz_net)
                if abs(dx) >= abs(dy):
                    px = cx + (w / 2 + 1.5 if dx >= 0 else -w / 2 - 1.5 - tw)
                    py = cy - fsz_net * 0.3
                    c.setFillColorRGB(1, 1, 1); c.setFillAlpha(0.72); c.rect(px - 0.5, py - 1, tw + 1, fsz_net + 1, stroke=0, fill=1); c.setFillAlpha(1)
                    c.setFillColorRGB(*color(pd["net"])); c.drawString(px, py, pd["net"])
                else:
                    c.saveState(); c.translate(cx + fsz_net * 0.3, cy + (h / 2 + 1.5 if dy >= 0 else -h / 2 - 1.5 - tw)); c.rotate(90)
                    c.setFillColorRGB(1, 1, 1); c.setFillAlpha(0.72); c.rect(-0.5, -1, tw + 1, fsz_net + 1, stroke=0, fill=1); c.setFillAlpha(1)
                    c.setFillColorRGB(*color(pd["net"])); c.drawString(0, 0, pd["net"])
                    c.restoreState()

    # net name along the longest piece of each routed net
    best = {}
    for q in SEGS:
        if q[5] != layer or q[6] in ("GND", ""):
            continue
        mx, my = (q[0] + q[2]) / 2, (q[1] + q[3]) / 2
        if not in_view(mx, my):
            continue
        L_ = math.hypot(q[2] - q[0], q[3] - q[1])
        if q[6] not in best or L_ > best[q[6]][0]:
            best[q[6]] = (L_, q)
    fs = min(0.42 * k, 7)
    for net, (L_, q) in best.items():
        (ax, ay), (bx, by) = T(q[0], q[1]), T(q[2], q[3])
        ang = math.degrees(math.atan2(by - ay, bx - ax))
        if ang > 90 or ang < -90:
            ang += 180
        c.saveState(); c.translate((ax + bx) / 2, (ay + by) / 2); c.rotate(ang)
        c.setFont("JHB", fs); tw = pdfmetrics.stringWidth(net, "JHB", fs)
        if L_ * k > tw * 0.8:
            c.setFillColorRGB(1, 1, 1); c.setFillAlpha(0.8); c.rect(-tw / 2 - 0.5, -fs * 0.35, tw + 1, fs * 1.05, stroke=0, fill=1); c.setFillAlpha(1)
            c.setFillColorRGB(*color(net)); c.drawCentredString(0, -fs * 0.2, net)
        c.restoreState()
    draw_refs()
    c.restoreState()
    c.showPage()
    return drawn


FULL = (79.2, 120.8, 78.5, 121)
counts = 0
counts += view("正面（Top）元件與走線，從正面看", "U1 的虛線框是模組外形，模組蓋在這些焊盤上。焊盤上的數字是腳位。放大看更清楚（向量圖）。", "F.Cu", *FULL)
counts += view("背面（Bottom）元件與走線，從背面看（左右鏡像，和 JLC 預覽同方向）", "HDMI 差分走線都在這一面。焊盤上的數字是腳位；J2 開口朝上。", "B.Cu", *FULL, mirror=True)
counts += view("內層 In2 走線，從正面看", "只有這一層有內層走線。上下是 In1 GND、In3 3V3 平面。圓點是過孔，連到正反面。", "In2.Cu", *FULL)
assert counts == len(SEGS), (counts, len(SEGS))
view("背面放大：HDMI 接頭 → ESD → U7（你圈的區域）", "J2 到 U7 的 4 組 TMDS，U8、U9 是 ESD。每個焊盤旁是網路名。從背面看。", "B.Cu", 88, 113, 84, 102.5, mirror=True)
view("背面放大：電源區 U2、L1、U4、U5、Q1、光耦", "5V → U2 降壓 → 3V3；U4、U5 → 2.5V、1.2V；U10–U12 光耦、J4 ATX。從背面看。", "B.Cu", 92, 120.5, 100, 120.5, mirror=True)
view("背面放大：microSD J7、U6", "J7 卡座，1–8 腳靠板邊；U6 是 DDC 準位轉換。從背面看。", "B.Cu", 79.5, 98, 88, 118, mirror=True)
view("正面放大：J3、U14、CC 電阻", "J3 接被控主機，U14 是 USB2 的 ESD，U1 右側焊盤。從正面看。", "F.Cu", 100, 120.5, 79, 100)
view("正面放大：J5、J6", "J5 供電和燒錄，J6 接圓形 LCD，U1 右下焊盤。從正面看。", "F.Cu", 100, 120.5, 97, 120.5)
view("正面放大：U1 左側與電容、電阻", "U1 左邊的焊盤和週邊被動元件。從正面看。", "F.Cu", 79.5, 101, 96, 120.5)
c.save()
print("pages", PAGE[0], "segments drawn", counts, "vias", len(VIAS), "footprints", len(FPS), "build", BUILD)
