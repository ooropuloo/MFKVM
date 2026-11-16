#!/bin/sh
# r7d: every check, in order, on the board regenerated from out/final.ses. Logs go to out/ and fab_r7d/.
M=$(cd "$(dirname "$0")/.." && pwd)
CASE_PY=${CASE_PY:-python}
cd "$M" || exit 1
sh tools/check.sh out/final.ses > out/check.log 2>&1; echo "check.sh done"; grep -v "^  (" out/check.log | tail -6
python -I tools/hotplug.py --design out/design.json --out out/hotplug.out > /dev/null 2>&1; echo "hotplug exit $?"; tail -1 out/hotplug.out
python -I tools/verify.py out data/antmicro/a.net > out/verify.out 2>&1; echo "verify exit $?"; tail -1 out/verify.out
rm -rf fab_r7d
python -I tools/fab_pack.py out fab_r7d > out/pack.log 2>&1; echo "fab_pack exit $?"; tail -1 out/pack.log
cp out/erc_check.out fab_r7d/erc_check_report.txt
cp out/hotplug.out fab_r7d/hotplug_report.txt
python -I tools/r7/cpl_table.py out fab_r7d/CPL_JLC.csv fab_r7d/CPL_pin1_check.md
python -I tools/r7/impedance_r7.py out/p4_kvm_mini.kicad_pcb > fab_r7d/impedance_r7d.txt 2>&1; echo "impedance exit $?"
python -I tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7d/pairs_r7d.txt 2>&1 || PYTHONPATH=tools/r6 python tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7d/pairs_r7d.txt 2>&1; echo "pairs exit $?"
"$CASE_PY" case/check_case.py case/stl --design out/design.json --pcb out/p4_kvm_mini.kicad_pcb --report fab_r7d/case_check.txt --title "r7d board 40 x 45" > /dev/null 2>&1; echo "case exit $?"; tail -1 fab_r7d/case_check.txt
for f in p4_kvm_mini.kicad_sch mini.kicad_sym p4_kvm_mini.kicad_pro p4_kvm_mini.kicad_pcb p4_kvm_mini.kicad_dru erc.json drc.json; do cp out/$f kicad/$f; done
python -I tools/mutate.py out --report MUTATION_REPORT.txt > out/mutate.log 2>&1; echo "mutate exit $?"; tail -2 MUTATION_REPORT.txt
python -I tools/r7d_csi_ref.py out/p4_kvm_mini.kicad_pcb > fab_r7d/csi_reference_r7d.txt 2>&1; echo "csi ref exit $?"; tail -1 fab_r7d/csi_reference_r7d.txt
python -I tools/bodycheck.py out --report fab_r7d/bodycheck_r7d.txt > /dev/null 2>&1; echo "body exit $?"
