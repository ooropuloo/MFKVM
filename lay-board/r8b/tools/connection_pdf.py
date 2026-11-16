# -*- coding: utf-8 -*-
# Readable connection document. The schematic has 0 wires and 415 net labels, so it can't be followed by eye.
# Page 1 draws real lines; every line is asserted against the netlist, so a wrong drawing stops the build.
# Usage: python tools/connection_pdf.py out/design.json kicad/p4_kvm_mini.kicad_pcb fab_r6/p4_kvm_mini_gerber.zip out.pdf
import collections, datetime, hashlib, json, re, sys

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

DESIGN, PCB, GERBER, OUT = sys.argv[1:5]
pdfmetrics.registerFont(TTFont("JH", "C:/Windows/Fonts/msjh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("JHB", "C:/Windows/Fonts/msjhbd.ttc", subfontIndex=0))

d = json.load(open(DESIGN, encoding="utf-8"))
PARTS = {p["ref"]: p for p in d["parts"]}
NET = collections.defaultdict(list)
for p in d["parts"]:
    for pad, n in p["nets"].items():
        if n:
            NET[n].append((p["ref"], pad))


def crosscheck():
    """Every pad's net in design.json must match the routed board."""
    s = open(PCB, encoding="utf-8").read()
    idx = [m.start() for m in re.finditer(r"\(footprint\s", s)] + [len(s)]
    seen = bad = 0
    for a, b in zip(idx, idx[1:]):
        block = s[a:b]
        r = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not r or r.group(1) not in PARTS:
            continue
        for m in re.finditer(r'\(pad "([^"]*)"', block):
            n = re.search(r'\(net "([^"]*)"\)', block[m.end():m.end() + 300])
            want = PARTS[r.group(1)]["nets"].get(m.group(1))
            if m.group(1) == "" or want is None:
                continue
            seen += 1
            if (n.group(1) if n else "") != want:
                bad += 1
                print("MISMATCH", r.group(1), m.group(1), want, n.group(1) if n else "")
    assert seen > 300 and bad == 0, (seen, bad)
    return seen


CHECKED = crosscheck()
GHASH = hashlib.sha256(open(GERBER, "rb").read()).hexdigest()[:8]
# the Gerber the drawing belongs to: GERBER_SHA8 (first 8 hex of its sha256) must match when given; r6 pinned 525fb981 here
import os
assert GHASH == os.environ.get("GERBER_SHA8", GHASH), GHASH
REV = os.environ.get("BOARD_REV", "r6")
BUILD = datetime.datetime.now().strftime("%Y%m%d-%H%M")
EDGES_CHECKED = [0]


def on(net, *refs):
    """Assert that each ref has a pad on net."""
    assert net in NET, net
    members = {r for r, _ in NET[net]}
    for r in refs:
        assert r in members, (net, r, sorted(members))
    EDGES_CHECKED[0] += 1


W, H = landscape(A3)
c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle(f"MF KVM v2 {REV} 接線圖")
INK = (0.13, 0.15, 0.18)
COL = {"hdmi": (0.48, 0.18, 0.68), "csi": (0.86, 0.42, 0.05), "usb": (0.07, 0.40, 0.75), "pwr": (0.80, 0.12, 0.12),
       "ctl": (0.30, 0.34, 0.40), "sd": (0.05, 0.53, 0.42), "gnd": (0.45, 0.45, 0.45)}
PAGE = [0]


def text(x, y, s, size=9, font="JH", color=INK, anchor="l"):
    c.setFont(font, size)
    c.setFillColorRGB(*color)
    {"l": c.drawString, "c": c.drawCentredString, "r": c.drawRightString}[anchor](x, y, s)


def box(x, y, w, h, title, sub=(), fill=(0.96, 0.97, 0.99), edge=INK):
    c.setFillColorRGB(*fill)
    c.setStrokeColorRGB(*edge)
    c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    text(x + w / 2, y + h - 15, title, 11, "JHB", anchor="c")
    for i, s in enumerate(sub):
        text(x + w / 2, y + h - 29 - i * 12, s, 8.5, anchor="c", color=(0.3, 0.33, 0.38))


def line(pts, kind, width=1.6, arrow=True):
    c.setStrokeColorRGB(*COL[kind])
    c.setFillColorRGB(*COL[kind])
    c.setLineWidth(width)
    p = c.beginPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    c.drawPath(p, stroke=1, fill=0)
    if arrow:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        dx, dy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
        a = c.beginPath()
        a.moveTo(x1, y1)
        a.lineTo(x1 - 7 * dx - 3.5 * dy, y1 - 7 * dy - 3.5 * dx)
        a.lineTo(x1 - 7 * dx + 3.5 * dy, y1 - 7 * dy + 3.5 * dx)
        a.close()
        c.drawPath(a, stroke=0, fill=1)


def footer(title):
    PAGE[0] += 1
    text(30, H - 34, title, 16, "JHB")
    text(30, 16, f"MF KVM v2 {REV}  ·  Gerber {GHASH}  ·  build {BUILD}  ·  與 PCB 板檔逐腳比對 {CHECKED} 腳、0 不符", 8.5, color=(0.4, 0.42, 0.46))
    text(W - 30, 16, f"第 {PAGE[0]} 頁", 9, anchor="r", color=(0.4, 0.42, 0.46))


# ---------------------------------------------------------------- page 1
footer(f"MF KVM v2 {REV} 系統接線圖")
text(30, H - 52, "線上的字是網路名稱，每條線都和網路表核對過。後面幾頁有每一支腳接到哪裡。", 10, color=(0.3, 0.33, 0.38))
for i, (k, s) in enumerate((("hdmi", "HDMI TMDS"), ("csi", "CSI 影像"), ("usb", "USB"), ("sd", "microSD"), ("ctl", "控制"), ("pwr", "電源"))):
    line([(640 + i * 90, H - 40), (665 + i * 90, H - 40)], k, 2.4, arrow=False)
    text(669 + i * 90, H - 44, s, 9)

UX, UY, UW, UH = 720, 190, 150, 520
box(UX, UY, UW, UH, "U1 主控", ("ESP32-P4-Module（基本款 28101）", "R99 要留著", "客供，不在 BOM", "正面"), fill=(0.93, 0.96, 1))
TX, TY, TW, TH = 450, 280, 150, 175
box(TX, TY, TW, TH, "U7 影像橋接", ("TC358743 BGA", "HDMI 轉 CSI", "背面"), fill=(0.97, 0.94, 1))

# USB host
for n in ("USB_DP", "USB_DN"):
    on(n, "J3", "U3", "U1")
box(30, 625, 125, 70, "J3 USB-C", ("接被控主機", "鍵鼠、虛擬媒體"))
line([(155, 665), (UX, 665)], "usb")
text(330, 670, "USB_DP / USB_DN（U1.49 / U1.48）", 9, color=COL["usb"])
box(250, 695, 95, 34, "U3 ESD", (), fill=(1, 0.98, 0.9))
line([(297, 695), (297, 665)], "usb", 1, arrow=False)
on("HOST_VBUS", "J3", "R9")
on("HOST_VBUS_DIV", "R9", "R10", "U1")
line([(155, 640), (UX, 640)], "ctl", 1.2)
text(330, 628, "HOST_VBUS → R9/R10 分壓 → U1.18（偵測主機 VBUS，不供電；韌體尚未使用）", 8.5, color=COL["ctl"])

# USB power and console
for n in ("USB2_DP", "USB2_DN"):
    on(n, "J5", "U14", "U1")
box(30, 520, 125, 70, "J5 USB-C", ("5V 供電", "燒錄、console"))
line([(155, 560), (UX, 560)], "usb")
text(330, 565, "USB2_DP / USB2_DN（U1.51 / U1.50）", 9, color=COL["usb"])
box(250, 590, 95, 34, "U14 ESD", (), fill=(1, 0.98, 0.9))
line([(297, 590), (297, 560)], "usb", 1, arrow=False)

# HDMI
for n in ("D0_P", "D0_N", "D1_P", "D1_N", "D2_P", "D2_N", "CK_P", "CK_N"):
    on(n, "J2", "U7")
for n in ("D1_P", "D1_N", "D2_P", "D2_N"):
    on(n, "U8")
for n in ("D0_P", "D0_N", "CK_P", "CK_N"):
    on(n, "U9")
box(30, 280, 125, 175, "J2 HDMI", ("接被控主機", "影像輸入"))
line([(155, 415), (TX, 415)], "hdmi", 2.4)
text(165, 402, "TMDS 4 對：D0、D1、D2、CK", 9, color=COL["hdmi"])
box(235, 458, 80, 34, "U8 ESD", (), fill=(1, 0.98, 0.9))
box(330, 458, 80, 34, "U9 ESD", (), fill=(1, 0.98, 0.9))
line([(275, 458), (275, 415)], "hdmi", 1, arrow=False)
line([(370, 458), (370, 415)], "hdmi", 1, arrow=False)
text(275, 500, "ESD 並在線上，接地，訊號不穿過", 8.5, color=(0.45, 0.4, 0.2), anchor="l")

on("DDC_SCL", "J2", "U6"); on("DDC_SDA", "J2", "U6"); on("DDC3_SCL", "U6", "U7"); on("DDC3_SDA", "U6", "U7")
box(255, 345, 95, 45, "U6", ("PCA9517 準位轉換",))
line([(155, 367), (255, 367)], "ctl", 1.4)
line([(350, 367), (TX, 367)], "ctl", 1.4)
text(160, 372, "DDC_SCL/SDA", 8.5, color=COL["ctl"])
text(355, 372, "DDC3_SCL/SDA", 8.5, color=COL["ctl"])
on("HDMI_5V", "J2", "U7"); on("HDMI_CEC", "J2", "U7"); on("TC_HPDO", "U7", "R30"); on("HDMI_HPD", "R30", "J2")
line([(155, 325), (TX, 325)], "ctl", 1.2)
text(165, 330, "HDMI_5V（主機 5V 偵測）、HDMI_CEC", 8.5, color=COL["ctl"])
line([(TX, 298), (155, 298)], "ctl", 1.2)
text(165, 303, "TC_HPDO → R30 1k → HDMI_HPD（告訴主機有螢幕）", 8.5, color=COL["ctl"])

# U7 to U1
for n in ("CSI_D0_P", "CSI_D0_N", "CSI_D1_P", "CSI_D1_N", "CSI_CK_P", "CSI_CK_N"):
    on(n, "U7", "U1")
line([(TX + TW, 415), (UX, 415)], "csi", 2.4)
text(TX + TW + 8, 420, "CSI 3 對：D0、D1、CK", 9, color=COL["csi"])
on("I2C_SDA", "U1", "U7"); on("I2C_SCL", "U1", "U7"); on("TC_RST", "U1", "U7")
line([(UX, 345), (TX + TW, 345)], "ctl", 1.4)
text(TX + TW + 8, 350, "I2C_SDA / I2C_SCL、TC_RST", 8.5, color=COL["ctl"])

# clock
on("OSC_OUT", "Y1", "R24"); on("TC_REFCLK", "R24", "U7")
box(TX + 25, 180, 100, 42, "Y1 27 MHz", ("振盪器",))
line([(TX + 75, 222), (TX + 75, TY)], "ctl", 1.4)
text(TX + 82, 248, "OSC_OUT → R24 22Ω → TC_REFCLK", 8.5, color=COL["ctl"])

# right side
RX = 985
on("LNA_OUT", "U1", "J8")
box(RX, 582, 175, 42, "J8 U.FL 天線", ("背面，接 FPC 天線",))
line([(UX + UW, 603), (RX, 603)], "ctl", 1.4)
text(UX + UW + 6, 608, "LNA_OUT（U1.2，50 Ω）", 8.5, color=COL["ctl"])
for n in ("LCD_DIN", "LCD_CLK", "LCD_CS", "LCD_DC", "LCD_RST"):
    on(n, "U1", "J6")
box(RX, 630, 175, 70, "J6 圓形 LCD", ("SM08B，正面", "線材接 1.28 吋螢幕"))
line([(UX + UW, 665), (RX, 665)], "ctl")
text(UX + UW + 6, 670, "LCD 5 條", 8.5, color=COL["ctl"])
for n in ("SD_CMD", "SD_D0", "SD_D1", "SD_D2", "SD_D3", "SD_CLK"):
    on(n, "U1", "J7")
on("SD_PWR_N", "U1", "Q1"); on("SD1_VDD", "Q1", "J7"); on("SD_SRC", "Q1", "R42"); on("3V3", "R42"); on("LDO_VO4", "U1", "R43")
box(RX, 505, 175, 70, "J7 microSD", ("背面", "電源由 Q1 開關"))
box(RX - 0, 435, 175, 44, "Q1 AO3401A", ("電源來自 3V3，經 R42；上拉接 LDO_VO4",))
line([(UX + UW, 545), (RX, 545)], "sd")
text(UX + UW + 6, 550, "SD 資料 6 條", 8.5, color=COL["sd"])
line([(UX + UW, 457), (RX, 457)], "ctl", 1.2)
text(UX + UW + 6, 462, "SD_PWR_N", 8.5, color=COL["ctl"])
line([(RX + 87, 479), (RX + 87, 505)], "pwr", 1.4)
text(RX + 93, 488, "SD1_VDD", 8.5, color=COL["pwr"])
on("ATX_PWR", "U1", "R52"); on("PWR_LED", "R52", "U10"); on("PWR_C", "U10", "J4"); on("PWR_E", "U10", "J4")
on("ATX_RST", "U1", "R53"); on("RST_LED", "R53", "U11"); on("RST_C", "U11", "J4"); on("RST_E", "U11", "J4")
on("ATX_LED", "U1", "U12"); on("LED_IN", "U12", "R54"); on("LED_A", "R54", "J4"); on("LED_K", "U12", "J4")
box(RX, 355, 80, 40, "U10 光耦", ())
box(RX, 305, 80, 40, "U11 光耦", ())
box(RX, 255, 80, 40, "U12 光耦", ())
box(RX + 115, 255, 60, 140, "J4", ("ATX", "前面板"))
for y, s, t, rev in ((375, "ATX_PWR", "R52 470Ω", 0), (325, "ATX_RST", "R53 470Ω", 0), (275, "ATX_LED", "讀 LED", 1)):
    if rev:
        line([(RX, y), (UX + UW, y)], "ctl", 1.2)
    else:
        line([(UX + UW, y), (RX, y)], "ctl", 1.2)
    text(UX + UW + 6, y + 5, f"{s}  {t}", 8.5, color=COL["ctl"])
for y, s in ((375, "PWR_C/E"), (325, "RST_C/E"), (275, "LED_A/K")):
    line([(RX + 80, y), (RX + 115, y)], "ctl", 1.2, arrow=False)
    text(RX + 81, y + 5, s, 6.5, color=COL["ctl"])

# power rail row
on("5V", "J5", "C64", "C60", "U2"); on("SW", "U2", "L1"); on("3V3", "L1", "U1", "U4", "U6"); on("V2V5", "U4", "U5", "FB2")
on("V1V2", "U5", "FB3", "FB4", "FB5"); on("AVDD25", "FB2", "U7"); on("AVDD12", "FB3", "U7"); on("VDD_MIPI", "FB4", "U7"); on("VDDC", "FB5", "U7"); on("OSC_VDD", "FB6", "Y1")
Y = 60
box(150, Y, 125, 58, "U2 + L1", ("SY8089 降壓", "5V → 3.3V 2A"), fill=(1, 0.95, 0.95))
box(380, Y, 95, 58, "U4", ("TLV73325", "3.3V → 2.5V"), fill=(1, 0.95, 0.95))
box(560, Y, 95, 58, "U5", ("TLV73312", "2.5V → 1.2V"), fill=(1, 0.95, 0.95))
box(735, Y, 230, 58, "FB2–FB5 磁珠 → U7 四組電源", ("AVDD25、AVDD12、VDD_MIPI、VDDC",), fill=(1, 0.95, 0.95))
line([(30, 560), (15, 560), (15, 89), (150, 89)], "pwr", 2.2)
text(22, 95, "5V", 9, "JHB", COL["pwr"])
line([(275, 89), (380, 89)], "pwr", 2.2)
text(290, 95, "3V3", 9, "JHB", COL["pwr"])
line([(475, 89), (560, 89)], "pwr", 2.2)
text(490, 95, "V2V5", 9, "JHB", COL["pwr"])
line([(655, 89), (735, 89)], "pwr", 2.2)
text(668, 95, "V1V2", 9, "JHB", COL["pwr"])
line([(327, 89), (327, 150), (UX + 40, 150), (UX + 40, UY)], "pwr", 1.8)
on("3V3", "U1", "U6", "U7", "FB6")
text(335, 155, "3V3 也供 U1、U6、U7，以及經 FB6 供 Y1", 8.5, color=COL["pwr"])
assert EDGES_CHECKED[0] > 50
c.showPage()

# ---------------------------------------------------------------- pin cards
SHORT = {"GND", "3V3", "5V"}


def describe(ref, pad, net):
    others = [(r, p) for r, p in NET[net] if not (r == ref and p == pad)]
    if net in SHORT:
        return f"（{net} 共 {len(NET[net])} 腳）"
    return "  ".join(f"{r}.{p}" for r, p in others)


def card_rows(ref):
    p = PARTS[ref]
    rows, un = [], []
    rails = collections.defaultdict(list)
    for pad, net in p["nets"].items():
        if not net or net.startswith("unconnected"):
            un.append(pad)
        elif net in SHORT:
            rails[net].append(pad)
        else:
            rows.append((pad, net, describe(ref, pad, net)))
    rows.sort(key=lambda r: (r[1]))
    for net in ("5V", "3V3", "GND"):
        if rails[net]:
            rows.append((",".join(rails[net]), net, f"（這顆有 {len(rails[net])} 腳接 {net}：" + " ".join(rails[net]) + "）"))
    return rows, un


CARDS = [("U1", "主控"), ("U7", "HDMI 轉 CSI"), ("J2", "HDMI"), ("J3", "接主機"), ("J5", "供電、燒錄"), ("J7", "microSD"), ("J6", "LCD"), ("J8", "天線"),
         ("J4", "ATX 前面板"), ("U2", "3.3V 降壓"), ("U4", "2.5V LDO"), ("U5", "1.2V LDO"), ("U6", "DDC 準位轉換"), ("Q1", "SD 電源開關"),
         ("Y1", "27 MHz"), ("L1", "降壓電感"), ("U3", "USB ESD"), ("U14", "USB2 ESD"), ("U8", "TMDS ESD"), ("U9", "TMDS ESD"), ("U10", "ATX 電源鍵"),
         ("U11", "ATX 重置鍵"), ("U12", "ATX LED")]
footer("每顆主要零件的接線")
COLW = (W - 80) / 2
x, y = 30, H - 62
RH = 13.5
for ref, what in CARDS:
    rows, un = card_rows(ref)
    i = 0
    first = True
    while i < len(rows) or first:
        room = int((y - 50 - 34 - (14 if un else 0)) // RH)
        if room < 3:
            if x > 40:
                c.showPage()
                footer("每顆主要零件的接線")
                x, y = 30, H - 62
            else:
                x, y = 30 + COLW + 20, H - 62
            continue
        chunk = rows[i:i + room]
        p = PARTS[ref]
        c.setFillColorRGB(0.16, 0.2, 0.28)
        c.rect(x, y - 16, COLW, 17, stroke=0, fill=1)
        text(x + 6, y - 11, f"{ref}  {what}  ·  {p['value']}  ·  {'正面' if p['side'] == 'F' else '背面'}" + ("" if first else "（續）"), 9.5, "JHB", (1, 1, 1))
        y -= 18
        for pad, net, oth in chunk:
            kind = "pwr" if net in ("3V3", "5V", "V1V2", "V2V5", "AVDD25", "AVDD12", "VDD_MIPI", "VDDC", "SD1_VDD", "OSC_VDD", "HOST_VBUS") else "gnd" if net == "GND" else "hdmi" if re.match(r"(D\d|CK)_", net) else "csi" if net.startswith("CSI") else "usb" if net.startswith("USB") else "sd" if net.startswith("SD") else "ctl"
            text(x + 4, y - 10, pad if len(pad) < 11 else pad[:10] + "…", 8.5, "JHB")
            c.setStrokeColorRGB(*COL[kind]); c.setLineWidth(1.3)
            c.line(x + 62, y - 7, x + 82, y - 7)
            text(x + 86, y - 10, net, 8.5, "JHB", COL[kind])
            text(x + 178, y - 10, oth[:88], 8, color=(0.25, 0.28, 0.33))
            y -= RH
        i += len(chunk)
        if i >= len(rows) and un:
            s = "未接：" + " ".join(un)
            text(x + 4, y - 10, s[:112], 7.5, color=(0.5, 0.5, 0.5))
            y -= 13
        y -= 8
        first = False
c.showPage()

# ---------------------------------------------------------------- passives
footer("電阻、電容、磁珠：兩端各接到哪裡")
x, y = 30, H - 62
cols = 3
CW = (W - 60 - 15 * (cols - 1)) / cols
refs = [r for r in PARTS if re.match(r"(R|C|FB)\d", r)]
refs.sort(key=lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0))))
for r in refs:
    p = PARTS[r]
    if y < 44:
        if x + CW + 15 < W - CW:
            x += CW + 15
        else:
            c.showPage()
            footer("電阻、電容、磁珠：兩端各接到哪裡")
            x = 30
        y = H - 62
    a = [p["nets"].get(k, "") for k in sorted(p["nets"])]
    val = p["value"].replace(" 0402", "").replace(" 0603", "").replace(" 0805", "")
    text(x, y - 10, r, 8.5, "JHB")
    text(x + 34, y - 10, val.replace(" 500mA", "")[:14], 8, color=(0.3, 0.33, 0.38))
    text(x + 108, y - 10, "  —  ".join(a) + ("  【不焊】" if p["dnp"] else ""), 8)
    y -= 13
c.showPage()
c.save()
print("pages", PAGE[0], "edges checked", EDGES_CHECKED[0], "pads checked", CHECKED, "build", BUILD)
