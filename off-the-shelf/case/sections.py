# -*- coding: utf-8 -*-
"""Cuts the whole assembly through chosen planes and draws them to sections/*.png, so a person can see the fit."""
import os

import numpy as np
import trimesh
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = [('stl/mf_kvm_tray.stl', '#555b63'), ('stl/mf_kvm_lid.stl', '#8a7fb0'), ('stl/mf_kvm_bridge.stl', '#c08a2e'), ('stl/mf_kvm_former.stl', '#b0a080'), ('asm/core_board.stl', '#111111'), ('asm/core_parts.stl', '#888888'), ('asm/c790.stl', '#1f8a5f'), ('asm/lcd.stl', '#2a6db0'), ('asm/atx.stl', '#2fa04f'), ('asm/fpc.stl', '#e0611a')]
meshes = [(trimesh.load(os.path.join(HERE, f)), c) for f, c in PARTS]
K = 14


def section(name, origin, normal, u, v, ur, vr):
    W, H = int((ur[1] - ur[0]) * K) + 40, int((vr[1] - vr[0]) * K) + 40
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    P = lambda p: (20 + (np.dot(p, u) - ur[0]) * K, H - 20 - (np.dot(p, v) - vr[0]) * K)
    for m, c in meshes:
        sec = m.section(plane_origin=origin, plane_normal=normal)
        if sec is None:
            continue
        for ent in sec.discrete:
            pts = [P(p) for p in ent]
            d.line(pts, fill=c, width=2)
    d.text((6, 4), name, fill='black')
    im.save(os.path.join(HERE, 'sections', name + '.png'))


E = np.eye(3)
section('y14.9_riser_roll', (0, 14.9, 0), E[1], E[0], E[2], (-26, 16), (-7, 23))
section('x-6.55_hdmi_c790', (-6.55, 0, 0), E[0], E[1], E[2], (-3, 76), (-7, 23))
section('y45.5_otg_tf', (0, 45.5, 0), E[1], E[0], E[2], (-26, 16), (-7, 23))
section('y68_hdmi_alcove', (0, 68, 0), E[1], E[0], E[2], (-26, 16), (-7, 23))
section('x-11.43_atx_pin_row', (-11.43, 0, 0), E[0], E[1], E[2], (24, 66), (-7, 8))
section('y35.69_atx_pin', (0, 35.687, 0), E[1], E[0], E[2], (-24, -2), (-7, 8))
section('y53.3_boot_rst', (0, 53.34, 0), E[1], E[0], E[2], (-26, 16), (-7, 8))
section('z9.5_lower_run', (0, 0, 9.5), E[2], E[0], E[1], (-26, 16), (-3, 76))
