# -*- coding: utf-8 -*-
# Conventional wired schematic, because the KiCad schematic has 0 wires and 415 net labels.
# Builds one netlistsvg netlist per functional sheet straight from design.json. Stops if any connected pin is on no sheet.
# Usage: python tools/wired_schematic.py out/design.json <netlistsvg dir> <work dir> out.pdf
import datetime, json, os, re, subprocess, sys

DESIGN, NLS, WORK, OUT = sys.argv[1:5]
os.makedirs(WORK, exist_ok=True)
PARTS = {p["ref"]: p for p in json.load(open(DESIGN, encoding="utf-8"))["parts"]}
GND = "GND"
RAILS = {"3V3", "5V", "V2V5", "V1V2", "AVDD25", "AVDD12", "VDD_MIPI", "VDDC", "OSC_VDD", "SD1_VDD"}
TWO = re.compile(r"^(R|C|FB)\d+$")
ALL = ".*"
# sheet: title, note, {ref: regex of nets to show}; passives take all their pins
SHEETS = [
    ("電源", "J5 的 5V 進來，U2 降到 3.3V，U4 再降到 2.5V，U5 再降到 1.2V，磁珠分給 U7 各組電源。",
     {"J5": r"^(5V|GND|PWR_CC\d)$", "U2": ALL, "L1": ALL, "U4": ALL, "U5": ALL, "C60": ALL, "C64": ALL, "C61": ALL, "C62": ALL, "C63": ALL, "R50": ALL, "R51": ALL,
      "R3": ALL, "R4": ALL, "C10": ALL, "C11": ALL, "C12": ALL, "FB2": ALL, "FB3": ALL, "FB4": ALL, "FB5": ALL, "FB6": ALL, "C13": ALL, "C14": ALL, "C15": ALL, "C16": ALL,
      "C17": ALL, "C18": ALL, "C19": ALL, "C20": ALL, "C21": ALL, "C29": ALL}),
    ("HDMI 輸入", "J2 到 U7 的 4 對 TMDS，U8、U9 是 ESD（同一條線的兩腳內部相連），U6 轉 DDC 準位。",
     {"J2": ALL, "U8": ALL, "U9": ALL, "U6": ALL, "U7": r"^((D\d|CK)_[PN]|DDC3_S..|HDMI_5V|HDMI_CEC|TC_HPDO)$", "R25": ALL, "R26": ALL, "R27": ALL, "R28": ALL,
      "R30": ALL, "R31": ALL, "R32": ALL, "C32": ALL, "C33": ALL}),
    ("U7 影像橋接：CSI、時脈、控制", "U7 把 HDMI 轉成 CSI 送到 U1；Y1 是 27 MHz 時脈；I2C 和重置由 U1 控制。",
     {"U7": r"^(CSI_.*|I2C_S..|TC_RST|TC_REFCLK|TC_REXT|TC_PFIL|TC_BIASDA|TC_PCKIN|3V3|GND|AVDD25|AVDD12|VDD_MIPI|VDDC)$", "U1": r"^(CSI_.*|I2C_S..|TC_RST)$",
      "Y1": ALL, "R20": ALL, "R21": ALL, "R22": ALL, "R23": ALL, "R24": ALL, "C22": ALL, "C23": ALL, "C24": ALL, "C25": ALL, "C26": ALL, "C27": ALL, "C30": ALL, "C31": ALL}),
    ("USB", "J3 接被控主機，J5 燒錄和 console，U3、U14 是 ESD。主機 VBUS 只經 R9、R10 分壓給 U1 偵測，不供電。",
     {"J3": ALL, "J5": r"^USB2_D.$", "U3": ALL, "U14": ALL, "R60": ALL, "U1": r"^(USB.*|HOST_VBUS_DIV)$", "R1": ALL, "R2": ALL, "R9": ALL, "R10": ALL, "C50": ALL}),
    ("microSD", "Q1 開關 SD 電源，來源是 3V3 經 R42；R41 不焊。R43–R47 上拉到 U1 的 LDO_VO4，韌體要把 VO4 設成 3.3 V。",
     {"J7": ALL, "Q1": ALL, "U1": r"^(SD_.*|LDO_VO4)$", "R40": ALL, "R41": ALL, "R42": ALL, "R43": ALL, "R44": ALL, "R45": ALL, "R46": ALL, "R47": ALL, "C40": ALL, "C41": ALL, "C6": ALL}),
    ("LCD 與 ATX 前面板", "J6 接圓形 LCD。J8 是天線 U.FL，接 U1.2 LNA_OUT。U10、U11 隔離按主機電源、重置鍵；U12 讀主機 LED。",
     {"J6": ALL, "J8": ALL, "J4": ALL, "U10": ALL, "U11": ALL, "U12": ALL, "U1": r"^(LCD_.*|ATX_.*|LNA_OUT)$", "R52": ALL, "R53": ALL, "R54": ALL, "R55": ALL}),
    ("U1 主控：電源、開機、測試點", "U1 其他腳：3V3、接地、EN、開機腳和測試點。C6 在 microSD 那張。",
     {"U1": r"^(3V3|GND|ESP_EN|BOOT|GPIO36|C6_.*|U0_.*)$", "C1": ALL, "C2": ALL, "C3": ALL, "C4": ALL, "C5": ALL, "R11": ALL, "R12": ALL, "R13": ALL,
      "TP1": ALL, "TP2": ALL, "TP3": ALL, "TP4": ALL, "TP5": ALL, "TP6": ALL, "TP7": ALL, "TP8": ALL}),
]
# nets that leave a part on its right-hand side, per sheet; every other pin goes on the left. This is the signal flow.
FLOW_OUT = [
    {"J5": ALL, "U2": r"^SW$", "U4": r"^V2V5$", "U5": r"^V1V2$"},
    {"J2": ALL, "U6": r"^DDC3"},
    {"U7": r"^(CSI_|I2C_|TC_RST)", "Y1": r"^OSC_OUT$"},
    {"J3": ALL, "J5": ALL},
    {"U1": ALL, "Q1": r"^SD1_VDD$"},
    {"U1": ALL, "U10": r"^PWR_[CE]$", "U11": r"^RST_[CE]$", "U12": r"^LED_"},
    {"U1": ALL},
]
# rails drawn as real wires on this sheet instead of a symbol at each pin
WIRED = [{"5V", "V2V5", "V1V2", "AVDD25", "AVDD12", "VDD_MIPI", "VDDC", "OSC_VDD", "3V3"}, set(), set(), set(), {"SD1_VDD"}, set(), set()]
FLOW_ESD = {"U3", "U14", "U8", "U9"}
RIGHT_PADS = {"10", "9", "7", "6"}  # same net as 1, 2, 4, 5 inside the package, so the wire runs straight through
covered = set()
os.makedirs(WORK, exist_ok=True)
pages = []
for si, (title, note, members) in enumerate(SHEETS):
    used = {}
    for ref, pat in members.items():
        for pad, net in PARTS[ref]["nets"].items():
            if net and not net.startswith("unconnected") and re.search(pat, net):
                used[(ref, pad)] = net
                covered.add((ref, pad))
    # which sheet nets also live elsewhere
    here = {}
    for (ref, pad), net in used.items():
        here.setdefault(net, []).append((ref, pad))
    everywhere = {}
    for r, p in PARTS.items():
        for pad, net in p["nets"].items():
            if net:
                everywhere.setdefault(net, []).append((r, pad))
    bit = [10]

    def newbit():
        bit[0] += 1
        return bit[0]

    netbit = {}
    cells, ports = {}, {}

    wired = WIRED[si]
    has_esd = {n for (r, _), n in used.items() if r in FLOW_ESD and n != GND}

    def endpoint(net, stage="R"):
        """Bit for a net at this pin. Rails and ground get their own symbol per use, as a hand-drawn schematic would."""
        if net == GND:
            b = newbit()
            cells[f"G{b}"] = {"type": "gnd", "port_directions": {"A": "input"}, "connections": {"A": [b]}, "attributes": {"name": "GND"}}
            return b
        if net in RAILS and net not in wired:
            b = newbit()
            cells[f"V{b}"] = {"type": "vcc", "port_directions": {"A": "output"}, "connections": {"A": [b]}, "attributes": {"name": net}}
            return b
        key = (net, stage if net in has_esd else "R")
        if key not in netbit:
            netbit[key] = newbit()
        return netbit[key]

    for ref in members:
        pins = [(pad, used[(ref, pad)]) for pad in PARTS[ref]["nets"] if (ref, pad) in used]
        if not pins:
            continue
        val = PARTS[ref]["value"]
        if TWO.match(ref):
            nets = dict(pins)
            pa, pb = sorted(nets)[:2]
            na, nb = nets[pa], nets.get(pb, "")
            # keep rail on the input side and ground on the output side so the layout reads left to right
            if (nb in RAILS and nb not in wired) or na == GND:
                na, nb = nb, na
            kind = "c_h" if ref[0] == "C" else "l_h" if ref.startswith("FB") else "r_h"
            short = val.replace(" 0402", "").replace(" 0603", "").replace(" 0805", "").replace(" 500mA", "")
            cells[ref] = {"type": kind, "port_directions": {"A": "input", "B": "output"},
                          "connections": {"A": [endpoint(na)], "B": [endpoint(nb)]},
                          "attributes": {"ref": ref, "value": short + (" DNP" if PARTS[ref]["dnp"] else "")}}
            continue
        if ref == "L1":
            nets = dict(pins)
            cells[ref] = {"type": "l_h", "port_directions": {"A": "input", "B": "output"},
                          "connections": {"A": [endpoint(nets["1"])], "B": [endpoint(nets["2"])]},
                          "attributes": {"ref": "L1", "value": "2.2uH"}}
            continue
        pd, cn = {}, {}
        pat = FLOW_OUT[si].get(ref)
        for pad, net in pins:
            name = f"{pad} {net}" if not ref.startswith("TP") else f"{net}"
            stage = "R"
            if ref in FLOW_ESD and net != GND:
                d = "output" if pad in RIGHT_PADS else "input"
                stage = "R" if pad in RIGHT_PADS else "L"
            else:
                d = "output" if pat and re.search(pat, net) else "input"
                if ref in ("J2", "J3", "J5") and net in has_esd:
                    stage = "L"
            pd[name] = d
            cn[name] = [endpoint(net, stage)]
        short = re.sub(r"\s*\(.*?consigned\)", "", val).replace("(EL,NOK", "")
        label = f"{ref} {short}" if not ref.startswith("TP") else ref
        cells[ref] = {"type": label, "port_directions": pd, "connections": cn, "attributes": {}}
    # nets continuing on another sheet become labelled off-sheet ports
    for net, here_pins in here.items():
        if net == GND or (net in RAILS and net not in wired):
            continue
        if set(everywhere[net]) - set(here_pins):
            b = netbit.get((net, "R")) or endpoint(net)
            ports[net] = {"direction": "input", "bits": [b]}
    pages.append((title, note, {"modules": {"sheet": {"ports": ports, "cells": cells, "attributes": {"top": 1}}}}))

missing = [(r, pad, n) for r, p in PARTS.items() for pad, n in p["nets"].items() if n and not n.startswith("unconnected") and (r, pad) not in covered]
assert not missing, missing
print("all", len(covered), "connected pins are on a sheet")

skin = open(os.path.join(NLS, "lib", "analog.svg"), encoding="utf-8").read()
skin = skin.replace('org.eclipse.elk.direction="DOWN"', 'org.eclipse.elk.direction="RIGHT"')
skin = skin.replace('nodeNodeBetweenLayers="5"', 'nodeNodeBetweenLayers="30"').replace('org.eclipse.elk.spacing.nodeNode= "35"', 'org.eclipse.elk.spacing.nodeNode= "24"')
skinp = os.path.join(WORK, "skin.svg")
open(skinp, "w", encoding="utf-8").write(skin)
parts_html = []
css = []
BUILD = datetime.datetime.now().strftime("%Y%m%d-%H%M")
for i, (title, note, nl) in enumerate(pages):
    jp, sp = os.path.join(WORK, f"s{i + 1}.json"), os.path.join(WORK, f"s{i + 1}.svg")
    json.dump(nl, open(jp, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["node", os.path.join(NLS, "bin", "netlistsvg.js"), jp, "-o", sp, "--skin", skinp], check=True, capture_output=True, text=True, encoding="utf-8")
    svg = open(sp, encoding="utf-8").read()
    svg = re.sub(r"^<\?xml.*?\?>", "", svg).strip()
    m = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    w, h = float(m.group(1)), float(m.group(2))
    svg = re.sub(r'(<svg[^>]*?) width="[\d.]+"', r"\1", svg, count=1)
    svg = re.sub(r'(<svg[^>]*?) height="[\d.]+"', r"\1", svg, count=1)
    svg = svg.replace("<svg ", f'<svg viewBox="0 0 {w:.0f} {h:.0f}" ', 1)
    MM = 0.30  # mm per drawing unit: comfortable text on screen, and the page grows with the sheet
    pw, ph = max(420, w * MM + 24), max(297, h * MM + 40)
    print(title, "drawing", round(w), round(h), "page mm", round(pw), round(ph), "cells", len(nl["modules"]["sheet"]["cells"]))
    css.append(f"@page p{i}{{size:{pw:.0f}mm {ph:.0f}mm;margin:0}} .p{i}{{page:p{i};width:{pw:.0f}mm;height:{ph:.0f}mm}} .p{i} svg{{width:{w * MM:.0f}mm;height:{h * MM:.0f}mm}}")
    parts_html.append(f'<section class="p{i}"><h1>{i + 1}. {title}</h1><p>{note} 標 DNP 的零件不焊，那條線實際不通。</p><div class="sheet">{svg}</div><footer>MF KVM v2 r5 電路圖 · build {BUILD} · 線路由網路表自動產生，415 支接線腳都在圖上 · 第 {i + 1} / {len(pages)} 張</footer></section>')
html = """<!doctype html><meta charset="utf-8"><style>
body{margin:0;font-family:"Microsoft JhengHei",sans-serif;color:#111}
section{box-sizing:border-box;padding:9mm 10mm 6mm;page-break-after:always;display:flex;flex-direction:column;overflow:hidden}
h1{font-size:20px;margin:0 0 2px}p{margin:0 0 4px;font-size:12.5px;color:#333}
.sheet{flex:1;min-height:0}
.sheet svg{overflow:visible}
.sheet text{font-size:11px}
footer{font-size:10.5px;color:#666}
""" + "".join(css) + "</style>" + "".join(parts_html)
hp = os.path.join(WORK, "schematic.html")
open(hp, "w", encoding="utf-8").write(html)
CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={os.path.join(WORK, 'chrome')}",
                "--disable-features=OptimizationGuideModelDownloading", f"--print-to-pdf={os.path.abspath(OUT)}", "file:///" + os.path.abspath(hp).replace("\\", "/")],
               check=True, capture_output=True, timeout=120)
print("wrote", OUT, os.path.getsize(OUT), "build", BUILD)
