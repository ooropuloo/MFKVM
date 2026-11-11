# -*- coding: utf-8 -*-
"""Builds the part thumbnails for the v3 and v2 pages.

  python -I off-the-shelf/parts_img/make_parts_img.py <folder holding the original vendor downloads>

Writes <v>/parts_img/src (kept sources), thumb (WebP or SVG that build_page.py embeds), manifest.json and SOURCES.md.
If a vendor file in the folder is missing, the copy already in src is reused, so the script works without the downloads.
"""
import base64
import json
import math
import os
import struct
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIRS = {'v2': 'lay-board', 'v3': 'off-the-shelf'}
DL = sys.argv[1] if len(sys.argv) > 1 else ''
DATE = '2026-11-06'
LONG = 480
MAX_BYTES = 25000
FONT = "'Noto Sans TC','Microsoft JhengHei',sans-serif"


# ---------- own renders: an orthographic z-buffer rasteriser over the real STL ----------

def load_stl(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[80:84])[0]
    assert 84 + 50 * n == len(b), path
    rec = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])
    return np.frombuffer(b, dtype=rec, count=n, offset=84)['v'].reshape(-1, 3, 3).astype(np.float64)


def render_stl(path, size=1440, az=-35.0, el=35.0):
    tris = load_stl(path)
    a, e = math.radians(az), math.radians(el)
    rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    basis = np.array([[1, 0, 0], [0, math.sin(e), math.cos(e)], [0, -math.cos(e), math.sin(e)]])
    v = tris @ (basis @ rz).T
    lo, hi = v.reshape(-1, 3).min(0), v.reshape(-1, 3).max(0)
    span = hi - lo
    s = (size * 0.92) / max(span[0], span[1])
    w, h = int(span[0] * s + size * 0.08), int(span[1] * s + size * 0.08)
    x = (v[..., 0] - lo[0]) * s + size * 0.04
    y = (hi[1] - v[..., 1]) * s + size * 0.04
    zb = np.full((h, w), -1e18)
    nb = np.zeros((h, w, 3))
    nrm = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    keep = ln > 0
    nrm[keep] /= ln[keep][:, None]
    for i in np.nonzero(keep & (nrm[:, 2] > 0))[0]:
        x0, y0, x1, y1 = x[i, 0], y[i, 0], x[i, 1], y[i, 1]
        x2, y2 = x[i, 2], y[i, 2]
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9:
            continue
        cx0, cx1 = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, w - 1)
        cy0, cy1 = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, h - 1)
        if cx1 < cx0 or cy1 < cy0:
            continue
        gx, gy = np.meshgrid(np.arange(cx0, cx1 + 1) + 0.5, np.arange(cy0, cy1 + 1) + 0.5)
        l0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / d
        l1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / d
        l2 = 1 - l0 - l1
        ins = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not ins.any():
            continue
        z = l0 * v[i, 0, 2] + l1 * v[i, 1, 2] + l2 * v[i, 2, 2]
        sub = zb[cy0:cy1 + 1, cx0:cx1 + 1]
        up = ins & (z > sub)
        sub[up] = z[up]
        nb[cy0:cy1 + 1, cx0:cx1 + 1][up] = nrm[i]
    mask = zb > -1e17
    l1 = np.array([-0.45, 0.55, 0.70])
    l1 /= np.linalg.norm(l1)
    l2 = np.array([0.6, 0.1, 0.8])
    l2 /= np.linalg.norm(l2)
    shade = 0.36 + 0.52 * np.clip(nb @ l1, 0, 1) + 0.20 * np.clip(nb @ l2, 0, 1)
    img = np.ones((h, w, 3))
    base = np.array([0.60, 0.66, 0.71])
    img[mask] = np.clip(base * shade[mask][:, None], 0, 1)
    # creases and silhouettes make the shape readable at thumbnail size
    edge = np.zeros((h, w), bool)
    pad = np.where(mask, zb, lo[2] - 1e3)
    for ax in (0, 1):
        dz = np.abs(np.diff(pad, axis=ax)) * s
        dn = np.linalg.norm(np.diff(nb, axis=ax), axis=2)
        e1 = (dz > 3.0) | (dn > 0.45)
        if ax == 0:
            edge[:-1, :] |= e1
            edge[1:, :] |= e1
        else:
            edge[:, :-1] |= e1
            edge[:, 1:] |= e1
    img[edge] = np.array([0.20, 0.24, 0.27])
    out = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    return out.resize((max(w // 2, 1), max(h // 2, 1)), Image.LANCZOS), (hi - lo)


# ---------- photos and board images ----------

def trim_white(im, pad=0.05, thr=244):
    a = np.asarray(im.convert('RGB')).astype(int)
    m = (a.min(axis=2) < thr)
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    p = int(max(x1 - x0, y1 - y0) * pad)
    return im.crop((max(x0 - p, 0), max(y0 - p, 0), min(x1 + p, im.width), min(y1 + p, im.height)))


def board_crop(path):
    """The fab renders carry a soft grey shadow or a pale backdrop: blank whatever pale area touches the image edge, then crop."""
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg.convert('RGB')
    a = np.asarray(im).astype(int)
    pale = ((a.max(axis=2) - a.min(axis=2)) < 62) & (a.min(axis=2) > 118) | ((a[..., 2] >= a[..., 0]) & (a[..., 2] >= a[..., 1]) & (a.min(axis=2) > 60))
    h, w = pale.shape
    seen = np.zeros_like(pale)
    stack = [(y, x) for y in range(h) for x in (0, w - 1) if pale[y, x]] + [(y, x) for x in range(w) for y in (0, h - 1) if pale[y, x]]
    while stack:
        y, x = stack.pop()
        if seen[y, x]:
            continue
        seen[y, x] = True
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and pale[yy, xx] and not seen[yy, xx]:
                stack.append((yy, xx))
    b = np.asarray(im).copy()
    b[seen] = 255
    return trim_white(Image.fromarray(b), pad=0.03)


# ---------- illustrations (SVG, drawn here; dimensions come from the part names only) ----------

def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/><g font-family="{FONT}" fill="#20282c">{body}</g></svg>')


def text(x, y, s, size=16, anchor='start', weight=400, fill='#20282c'):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{s}</text>'


def usb_a_svg():
    # View: looking at the contact side, insertion end pointing up. Spacing 2.54 mm, outer two contacts wider and longer,
    # as in KiCad's USB_A_PCB_traces_small footprint: pad 1 (+) to pad 4 (-) reads left to right in this view.
    b = '<rect x="44" y="18" width="132" height="122" rx="4" fill="#dfe3e5" stroke="#6c777d" stroke-width="3"/>'
    b += '<rect x="52" y="26" width="116" height="110" rx="2" fill="#f7f7f4" stroke="#b9c0c3"/>'
    for i, cx in enumerate((68, 96, 124, 152)):
        outer = i in (0, 3)
        wd, top = (16, 34) if outer else (12, 42)
        b += f'<rect x="{cx - wd / 2}" y="{top}" width="{wd}" height="{130 - top}" rx="2" fill="#d8ab3f" stroke="#8d6d1e"/>'
    b += '<rect x="55" y="28" width="26" height="106" rx="3" fill="#e08a1e" fill-opacity=".82" stroke="#a65a06" stroke-width="2"/>'
    b += '<path d="M36 140h148l-14 52H50z" fill="#39424a"/><rect x="98" y="192" width="24" height="52" fill="#39424a"/>'
    for cx, n in zip((68, 96, 124, 152), '1234'):
        b += text(cx, 168, n, 22, 'middle', 700, '#ffb44d' if n == '1' else '#fff')
    b += '<path d="M110 14V3M104 9l6-7 6 7" fill="none" stroke="#6c777d" stroke-width="2"/>'
    b += text(186, 40, '插入端朝上', 16) + text(186, 60, '看接點那一面', 16)
    b += text(186, 104, '左起第 1 腳', 17, weight=700) + text(186, 126, '= VBUS', 17, weight=700, fill='#a65a06')
    b += text(186, 160, '橘色：Kapton', 16, fill='#a65a06') + text(186, 182, '只蓋第 1 腳', 16)
    b += text(186, 216, '貼完用電表量', 16) + text(186, 236, 'A 到 C 的 VBUS 不通', 15)
    return svg(340, 250, b)


def adapter(x, y):
    b = f'<rect x="{x + 16}" y="{y - 2}" width="6" height="16" fill="#8a9398"/><rect x="{x + 42}" y="{y - 2}" width="6" height="16" fill="#8a9398"/>'
    b += f'<rect x="{x}" y="{y + 12}" width="64" height="70" rx="9" fill="#39424a"/>'
    return b + text(x + 32, y + 54, '5 V', 17, 'middle', 700, '#fff')


def usbc_plug(x, y):
    return f'<rect x="{x}" y="{y - 12}" width="30" height="24" rx="4" fill="#39424a"/><rect x="{x + 30}" y="{y - 7}" width="18" height="14" rx="6" fill="#c9cfd2" stroke="#6c777d" stroke-width="1.5"/>'


def power_svg():
    b = adapter(26, 26)
    b += '<path d="M90 80C150 80 110 150 170 110S190 80 214 80" fill="none" stroke="#39424a" stroke-width="5"/>'
    b += usbc_plug(214, 80)
    b += text(238, 118, 'USB-C', 15, 'middle')
    b += text(26, 150, '插頭寬 13、高 6.6 mm 以內', 15)
    return svg(280, 164, b)


def power3_svg():
    b = adapter(14, 14)
    b += '<path d="M78 66C118 66 110 48 140 48" fill="none" stroke="#39424a" stroke-width="5"/>' + usbc_plug(140, 48)
    b += text(200, 54, 'USB-C 電源', 15)
    b += '<path d="M78 116H140" stroke="#39424a" stroke-width="6"/><path d="M140 104h22v-4h24l-4 28h-20v-4h-22z" fill="#39424a"/>'
    b += '<path d="M162 106h19l-2 16h-17z" fill="#d8ab3f"/>' + text(200, 122, 'HDMI 線', 15)
    b += '<path d="M78 170H140" stroke="#39424a" stroke-width="5"/>' + usbc_plug(140, 170) + text(200, 176, 'USB-C 線', 15)
    return svg(310, 194, b)


def wire_svg():
    b = ''
    for i in range(5):
        y = 40 + i * 18
        b += f'<rect x="46" y="{y}" width="150" height="9" rx="2.5" fill="#b9c0c3" stroke="#6c777d"/><rect x="48" y="{y + 2}" width="146" height="2" fill="#f1f3f4"/>'
    b += '<path d="M46 26h150M46 21v10M196 21v10" stroke="#20282c" stroke-width="1.5" fill="none"/>' + text(121, 17, '約 10 mm', 14, 'middle')
    b += text(208, 74, 'Ø0.64', 18, weight=700) + text(208, 96, '鍍錫單芯', 15)
    return svg(290, 140, b)


def screw_v(cx, top, d, L, s, label, n=''):
    hw, hh = d * 1.0 * s, d * 0.75 * s
    r = d * s / 2
    b = f'<rect x="{cx - hw}" y="{top}" width="{2 * hw}" height="{hh}" rx="{hh * 0.45}" fill="#6c777d"/>'
    y0, y1 = top + hh, top + hh + L * s
    b += f'<path d="M{cx - r} {y0}H{cx + r}V{y1 - r}L{cx} {y1}L{cx - r} {y1 - r}Z" fill="#aab2b6"/>'
    p = d * 0.5 * s
    y = y0 + p * 0.5
    while y < y1 - r:
        b += f'<path d="M{cx - r - 1.5} {y + p * 0.35}L{cx + r + 1.5} {y}" stroke="#596369" stroke-width="1.6"/>'
        y += p
    return b + text(cx, 172, label, 13, 'middle') + (text(cx, 190, n, 13, 'middle', 700) if n else '')


def screws_svg():
    s = 11
    b = screw_v(36, 22, 1.6, 5, s, 'M1.6×5', '2 支')
    b += screw_v(100, 22, 2.0, 8, s, 'M2×8', '2 支')
    b += screw_v(164, 22, 2.5, 6, s, 'M2.5×6')
    b += screw_v(228, 22, 2.5, 8, s, 'M2.5×8')
    b += screw_v(292, 22, 2.5, 10, s, 'M2.5×10')
    return svg(330, 200, b)


def m2_svg():
    s = 13
    x0, y = 46, 52
    L, d = 16 * s, 2 * s
    b = f'<rect x="{x0 - 20}" y="{y - 26}" width="20" height="52" rx="7" fill="#6c777d"/>'
    b += f'<path d="M{x0} {y - d / 2}H{x0 + L - 8}L{x0 + L} {y}L{x0 + L - 8} {y + d / 2}H{x0}Z" fill="#aab2b6"/>'
    px = x0 + 6
    while px < x0 + L - 8:
        b += f'<path d="M{px} {y - d / 2 - 1.5}L{px + 3} {y + d / 2 + 1.5}" stroke="#596369" stroke-width="1.6"/>'
        px += 6.5
    b += f'<path d="M{x0} 92H{x0 + L}M{x0} 86v12M{x0 + L} 86v12" stroke="#20282c" stroke-width="1.5" fill="none"/>'
    b += text(x0 + L / 2, 114, '16 mm', 15, 'middle') + text(x0 + L + 16, y + 6, 'M2', 18, weight=700)
    return svg(320, 128, b)


def antenna_svg():
    b = '<rect x="22" y="26" width="150" height="62" rx="7" fill="#d9942e" stroke="#94600f" stroke-width="2"/>'
    b += '<path d="M36 72V42h20v30h20V42h20v30h20V42h26" fill="none" stroke="#fbe7b2" stroke-width="5"/>'
    b += '<path d="M172 58C220 58 200 112 248 112" fill="none" stroke="#2c3338" stroke-width="4"/>'
    b += '<circle cx="258" cy="112" r="11" fill="#c9cfd2" stroke="#6c777d" stroke-width="2"/><circle cx="258" cy="112" r="4" fill="#6c777d"/>'
    b += text(22, 116, '2.4 GHz FPC 天線', 15) + text(258, 146, 'IPEX 接頭', 14, 'middle')
    return svg(320, 156, b)


def ffc_svg(same):
    x0, x1, y0, y1 = 18, 302, 34, 92
    b = f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="#f1f1ec" stroke="#8a9398"/>'
    for i in range(15):
        y = y0 + 3 + i * (y1 - y0 - 6) / 14.0
        b += f'<path d="M{x0} {y}H{x1}" stroke="#c9cdc8" stroke-width="1.6"/>'
    def zone(xa, contact):
        if contact:
            r = ''
            for i in range(15):
                y = y0 + 3 + i * (y1 - y0 - 6) / 14.0
                r += f'<rect x="{xa}" y="{y - 1.3}" width="36" height="2.6" fill="#c08e27"/>'
            return r
        return f'<rect x="{xa}" y="{y0}" width="36" height="{y1 - y0}" fill="#8fa3b2" stroke="#5f7482"/>'
    b += zone(x0, True) + zone(x1 - 36, same)
    b += f'<path d="M{x0} 20H{x1}M{x0} 14v12M{x1} 14v12" stroke="#20282c" stroke-width="1.4" fill="none"/>' + text(160, 15, '50 mm · 15 芯 · 間距 1.0', 14, 'middle')
    # side section: contacts in gold, stiffener on the opposite face
    ym = 128
    b += text(18, 112, '側視（金色是接點）', 14)
    b += f'<rect x="{x0}" y="{ym - 2}" width="{x1 - x0}" height="4" fill="#d8d8d0" stroke="#8a9398" stroke-width=".8"/>'
    b += f'<rect x="{x0}" y="{ym - 6}" width="36" height="4" fill="#c08e27"/><rect x="{x0}" y="{ym + 2}" width="36" height="7" fill="#8fa3b2"/>'
    if same:
        b += f'<rect x="{x1 - 36}" y="{ym - 6}" width="36" height="4" fill="#c08e27"/><rect x="{x1 - 36}" y="{ym + 2}" width="36" height="7" fill="#8fa3b2"/>'
    else:
        b += f'<rect x="{x1 - 36}" y="{ym + 2}" width="36" height="4" fill="#c08e27"/><rect x="{x1 - 36}" y="{ym - 9}" width="36" height="7" fill="#8fa3b2"/>'
    b += text(160, 164, '兩端接點同一面' if same else '兩端接點不同面', 17, 'middle', 700)
    return svg(320, 176, b)


def jst_svg(n):
    cell = 26
    w = n * cell + 20
    x0, y0 = (320 - w) / 2, 24
    b = f'<rect x="{x0}" y="{y0}" width="{w}" height="56" rx="4" fill="#efe6cf" stroke="#8d7f58" stroke-width="2"/>'
    for i in range(n):
        cx = x0 + 10 + i * cell + cell / 2
        b += f'<rect x="{cx - 7}" y="{y0 + 12}" width="14" height="22" rx="1.5" fill="#cbbf9d" stroke="#8d7f58"/>'
        b += f'<path d="M{cx} {y0 + 56}V{y0 + 104}" stroke="#39424a" stroke-width="4"/>'
    b += text(160, 152, f'SH 1.0 {n}P 外殼加壓接線', 16, 'middle')
    return svg(320, 164, b)


def photo_note(b, w, h, lines):
    """Vendor photos are not redistributed: an own drawing plus where to see the real part."""
    y = h - 14 - 20 * (len(lines) - 1)
    for i, s in enumerate(lines):
        b += text(16, y + 20 * i, s, 14, fill='#4a555b')
    return svg(w, h, b)


def p4_svg():
    b = '<rect x="70" y="16" width="180" height="150" rx="4" fill="#1f5c3a" stroke="#14402a" stroke-width="2"/>'
    for i in range(14):
        b += f'<circle cx="{82 + i * 12}" cy="166" r="3.2" fill="#d8ab3f"/><circle cx="{82 + i * 12}" cy="16" r="3.2" fill="#d8ab3f"/>'
    b += '<rect x="96" y="40" width="128" height="104" rx="3" fill="#c9cfd2" stroke="#6c777d" stroke-width="2"/>'
    b += text(160, 88, 'ESP32-P4', 18, 'middle', 700) + text(160, 112, '屏蔽罩', 14, 'middle')
    b += '<circle cx="84" cy="32" r="7" fill="#e3c26a" stroke="#8d6d1e" stroke-width="2"/>' + text(30, 36, 'IPEX', 13)
    return photo_note(b, 320, 236, ['Waveshare ESP32-P4-Module 16MB -U', '示意圖；實物照片見 SOURCES.md 的商品頁'])


def lcd128_svg():
    b = '<rect x="92" y="14" width="136" height="148" rx="10" fill="#1d2a3a" stroke="#0f1620" stroke-width="2"/>'
    b += '<circle cx="160" cy="84" r="62" fill="#16233a" stroke="#6c777d" stroke-width="3"/><circle cx="160" cy="84" r="54" fill="#244d7a"/>'
    b += text(160, 82, '1.28 吋', 16, 'middle', 700, '#fff') + text(160, 102, '240 × 240', 13, 'middle', 400, '#dde6ef')
    b += '<rect x="138" y="162" width="44" height="10" fill="#efe6cf" stroke="#8d7f58"/>'
    return photo_note(b, 320, 236, ['微雪 1.28 吋圓形 LCD（SKU 19192）', '示意圖；實物照片見 SOURCES.md 的商品頁'])


def fb_svg():
    b = '<rect x="20" y="30" width="280" height="110" rx="8" fill="#2a2f6b" stroke="#181b45" stroke-width="2"/>'
    for i in range(20):
        b += f'<circle cx="{40 + i * 12.6}" cy="40" r="3" fill="#d8ab3f"/><circle cx="{40 + i * 12.6}" cy="130" r="3" fill="#d8ab3f"/>'
    b += '<rect x="8" y="70" width="26" height="30" rx="4" fill="#c9cfd2" stroke="#6c777d" stroke-width="2"/>' + text(46, 90, 'USB-C', 13, fill='#fff')
    b += '<rect x="140" y="58" width="56" height="56" rx="3" fill="#39424a"/>' + text(168, 91, 'P4', 15, 'middle', 700, '#fff')
    b += text(296, 116, 'FireBeetle 2', 14, 'end', 700, '#fff')
    return photo_note(b, 320, 200, ['DFRobot FireBeetle 2 ESP32-P4（DFR1172）', '示意圖；實物照片見 SOURCES.md 的商品頁'])


def c790_svg():
    b = '<rect x="20" y="24" width="220" height="80" rx="6" fill="#1f5c3a" stroke="#14402a" stroke-width="2"/>'
    b += '<path d="M8 44h40v40H8z" fill="#c9cfd2" stroke="#6c777d" stroke-width="2"/>' + text(28, 120, 'HDMI', 13, 'middle')
    b += '<rect x="120" y="44" width="40" height="40" rx="2" fill="#39424a"/>' + text(140, 69, 'TC358743', 9, 'middle', 400, '#fff')
    b += '<rect x="232" y="46" width="12" height="36" fill="#efe6cf" stroke="#8d7f58"/>'
    b += '<path d="M244 52h44M244 76h44" stroke="#c08e27" stroke-width="2"/><rect x="244" y="52" width="50" height="24" fill="#f1f1ec" stroke="#8a9398"/>' + text(268, 98, '15P FFC', 12, 'middle')
    return photo_note(b, 320, 176, ['Geekworm C790 HDMI 轉 CSI，附排線', '示意圖；實物照片見 SOURCES.md 的商品頁'])


def lcd19_svg():
    b = '<rect x="30" y="20" width="250" height="118" rx="6" fill="#1d2a3a" stroke="#0f1620" stroke-width="2"/>'
    b += '<rect x="44" y="34" width="222" height="90" rx="3" fill="#244d7a" stroke="#6c777d" stroke-width="2"/>'
    b += text(155, 76, '1.9 吋', 17, 'middle', 700, '#fff') + text(155, 98, '320 × 170', 13, 'middle', 400, '#dde6ef')
    b += '<rect x="280" y="62" width="10" height="34" fill="#efe6cf" stroke="#8d7f58"/>'
    return photo_note(b, 320, 196, ['微雪 1.9 吋 LCD（SKU 23822）', '示意圖；實物照片見 SOURCES.md 的商品頁'])


# ---------- the two sets ----------

ILL = '示意'
VENDOR = '廠商照片'
RENDER = '實際 STL 渲染'
BOARD = 'KiCad 板圖'

ITEMS = {
    'v3': [
        ('fb', 'svg', fb_svg(), 'FireBeetle 2 ESP32-P4 核心板（DFR1172）示意圖', ILL, '實物照片見原廠商品頁：https://www.dfrobot.com/product-2915.html'),
        ('c790', 'svg', c790_svg(), 'Geekworm C790 HDMI 轉 CSI 板，附排線，示意圖', ILL, '實物照片見原廠商品頁：https://geekworm.com/products/c790'),
        ('ffc_opp', 'svg', ffc_svg(False), 'Würth 686715050001 排線示意圖，兩端接點不同面', ILL, 'DigiKey、Würth、RS 都回 403，改畫示意。接點面依 DigiKey 列表「Top on One Side, Bottom on Other」'),
        ('ffc_same', 'svg', ffc_svg(True), 'Würth 686615050001 排線示意圖，兩端接點同一面', ILL, 'DigiKey、Würth、RS 都回 403，改畫示意。接點面依 DigiKey 列表「Top on Both Sides」'),
        ('power', 'svg', power_svg(), '5 V USB-C 電源示意圖', ILL, '通用料，沒有指定產品'),
        ('usb_a', 'svg', usb_a_svg(), 'USB-A 頭示意圖：插入端朝上看接點面，左起第 1 腳是 VBUS，貼 Kapton 只蓋這一腳', ILL, '腳位：accesscomms.com.au/usb-pinouts-wiring（看接點時 plug 由左到右 1-2-3-4）與 KiCad USB_A_PCB_traces_small 足印，兩者一致'),
        ('lcd19', 'svg', lcd19_svg(), '微雪 1.9 吋 LCD 模組（SKU 23822）示意圖', ILL, '實物照片見經銷商商品頁：https://www.pishop.us/product/1-9inch-lcd-display-module-170-320-resolution-spi-interface-ips-262k-colors/'),
        ('wire', 'svg', wire_svg(), 'Ø0.64 mm 鍍錫單芯線，五段各約 10 mm，示意圖', ILL, '通用料，沒有指定產品'),
        ('jst6', 'svg', jst_svg(6), 'JST SH 1.0 六腳外殼示意圖', ILL, 'DigiKey 回 403、Future Electronics 連線被重設，改畫示意'),
        ('screws', 'svg', screws_svg(), '七支自攻螺絲示意圖：M1.6×5 兩支、M2×8 兩支、M2.5×6、×8、×10 各一支，長度等比例', ILL, '通用料；長度和直徑依表內規格等比例，頭型是示意'),
    ],
    'v2': [
        ('p4', 'svg', p4_svg(), 'Waveshare ESP32-P4-Module 16MB -U 版示意圖，左上角是 IPEX 座', ILL, '實物照片見經銷商商品頁：https://openelab.io/products/waveshare-esp32-p4-module-core-board-wifi-bluetooth'),
        ('ant', 'svg', antenna_svg(), '2.4 GHz IPEX FPC 天線示意圖', ILL, '通用料，沒有指定產品'),
        ('lcd128', 'svg', lcd128_svg(), '微雪 1.28 吋圓形 LCD 模組（SKU 19192）示意圖', ILL, '實物照片見經銷商商品頁：https://pishop.ca/product/240x240-general-1-28inch-round-lcd-display-module-65k-rgb'),
        ('jst8', 'svg', jst_svg(8), 'JST SH 1.0 八腳外殼示意圖', ILL, 'DigiKey 回 403、Future Electronics 連線被重設，改畫示意'),
        ('jst6', 'svg', jst_svg(6), 'JST SH 1.0 六腳外殼示意圖', ILL, 'DigiKey 回 403、Future Electronics 連線被重設，改畫示意'),
        ('m2', 'svg', m2_svg(), 'M2 × 16 螺絲示意圖', ILL, '通用料；長度和直徑依規格等比例，頭型是示意'),
        ('power3', 'svg', power3_svg(), '5 V USB-C 電源、HDMI 線、USB-C 線示意圖', ILL, '通用料，沒有指定產品'),
    ],
}
STLS = {
    'v3': [('tray', '底殼'), ('lid', '上蓋'), ('bridge', 'C790 橋架'), ('former', '排線捲線棒'), ('atx_shim', '焊 ATX 針用的墊片')],
    'v2': [('tray', '底殼'), ('lid', '上蓋')],
}
BOARDS = {
    'v3': ('atx', 'fab_atx_b/board_top.png', 'ATX 小板 rev B 正面'),
    'v2': ('main', 'fab_r5/board_top.png', 'P4 主板 r5 正面'),
}


def save_webp(im, path):
    im = im.convert('RGB')
    r = LONG / max(im.size)
    if r < 1:
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    for q in (78, 70, 60, 50, 40):
        im.save(path, 'WEBP', quality=q, method=6)
        if os.path.getsize(path) <= MAX_BYTES:
            break
    return im.size


def main():
    for ver, items in ITEMS.items():
        base = os.path.join(ROOT, DIRS[ver], 'parts_img')
        src, thumb = os.path.join(base, 'src'), os.path.join(base, 'thumb')
        os.makedirs(src, exist_ok=True)
        os.makedirs(thumb, exist_ok=True)
        man, rows = {}, []
        for key, how, what, alt, kind, note in items:
            if how == 'dl':
                sp = os.path.join(src, key + '.jpg')
                dp = os.path.join(DL, what) if DL else ''
                if dp and os.path.exists(dp):
                    im = trim_white(Image.open(dp).convert('RGB'))
                    im.thumbnail((800, 800), Image.LANCZOS)
                    im.save(sp, 'JPEG', quality=86)
                sz = save_webp(Image.open(sp), os.path.join(thumb, key + '.webp'))
                man[key] = dict(file=key + '.webp', w=sz[0], h=sz[1], alt=alt, kind=kind)
                rows.append((key + '.jpg', kind, note))
            else:
                data = what.encode('utf-8')
                for d in (src, thumb):
                    open(os.path.join(d, key + '.svg'), 'wb').write(data)
                head = what[:120]
                w, h = int(head.split('width="')[1].split('"')[0]), int(head.split('height="')[1].split('"')[0])
                man[key] = dict(file=key + '.svg', w=w, h=h, alt=alt, kind=kind, cap='示意')
                rows.append((key + '.svg', '自繪示意', note))
        for name, label in STLS[ver]:
            p = os.path.join(ROOT, DIRS[ver], 'case', 'stl', f'mf_kvm_{name}.stl')
            im, _ = render_stl(p)
            t = load_stl(p).reshape(-1, 3)
            dims = t.max(0) - t.min(0)
            im.save(os.path.join(src, name + '.png'))
            sz = save_webp(im, os.path.join(thumb, name + '.webp'))
            alt = f'{label}的 3D 模型渲染，實體約 {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm'
            man[name] = dict(file=name + '.webp', w=sz[0], h=sz[1], alt=alt, kind=RENDER)
            rows.append((name + '.png', '自行渲染', f'{DIRS[ver]}/case/stl/mf_kvm_{name}.stl，等角視角，由實際網格算出'))
        key, rel, label = BOARDS[ver]
        im = board_crop(os.path.join(ROOT, DIRS[ver], *rel.split('/')))
        im.thumbnail((800, 800), Image.LANCZOS)
        im.save(os.path.join(src, key + '.png'))
        sz = save_webp(im, os.path.join(thumb, key + '.webp'))
        man[key] = dict(file=key + '.webp', w=sz[0], h=sz[1], alt=label + '的板圖', kind=BOARD)
        rows.append((key + '.png', '自行渲染', f'{DIRS[ver]}/{rel}，裁到板子範圍'))
        json.dump(man, open(os.path.join(base, 'manifest.json'), 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
        with open(os.path.join(base, 'SOURCES.md'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'# 料件圖來源（{DATE} 取得）\n\n全部是自繪示意或由本 repo 的檔案算繪；廠商照片不放進 repo，只留商品頁連結。由 `off-the-shelf/parts_img/make_parts_img.py` 產生。\n\n| 檔案（src/） | 類型 | 來源 |\n|---|---|---|\n')
            for a, b, c in rows:
                f.write(f'| {a} | {b} | {c} |\n')
        total = sum(os.path.getsize(os.path.join(thumb, m['file'])) for m in man.values())
        print(ver, len(man), 'items', total, 'bytes; largest', max((os.path.getsize(os.path.join(thumb, m['file'])), k) for k, m in man.items()))


if __name__ == '__main__':
    main()
