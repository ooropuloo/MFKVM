# -*- coding: utf-8 -*-
"""r7e: kept for the r7d command line; the check is tools/refplane.py (CSI, TMDS and USB, own-pair vias only excluded, exit 1 on a gap).
r7d's version printed gaps but always exited 0 and excluded every CSI via (REVIEW_r7d tool table, injection 5).
usage: r7d_csi_ref.py <saved .kicad_pcb>      -> refplane.py <pcb> csi
"""
import os
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, '-I', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'refplane.py'), sys.argv[1], 'csi']))
