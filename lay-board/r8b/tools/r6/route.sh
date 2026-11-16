#!/bin/sh
# patch, check, compute the widening for VDDC, patch again with it, check
cd "$(dirname "$0")/../.." || exit 1
python tools/ses_patch_r6.py out/final_r5.ses out/final.ses > /dev/null && sh tools/check.sh out/final.ses > out/r6/check.txt 2>&1
(cd tools/r6 && python widen.py ../../out/p4_kvm_mini.kicad_pcb VDDC 0.3 widen_vddc.json > ../../out/r6/widen_vddc.txt)
python tools/ses_patch_r6.py out/final_r5.ses out/final.ses tools/r6/widen_vddc.json && sh tools/check.sh out/final.ses > out/r6/check.txt 2>&1
grep -n "Trace\|finish" out/gen.log | cut -c1-150
python tools/r6/drc_list.py out | sort -u | cut -c1-240 | grep -v courtyards
