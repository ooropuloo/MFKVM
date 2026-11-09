#!/bin/sh
# r7e: every check, in order, on the board regenerated from out/final.ses (plus the r7d/r7e stages). Logs go to out/ and fab_r7e/.
# Gates (r7e): any of these failing makes the script exit 1 at the end: check.sh (ERC/DRC), drc_accept, verify, hotplug, fab_pack,
# refplane, pairgap, cpl_pin1, impedance, s3_solver_test (non-round dimensions), case, bodycheck, mutate. coldstart.py is an analysis (no gate).
M=$(cd "$(dirname "$0")/.." && pwd)
CASE_PY=${CASE_PY:-$M/.venv-case/Scripts/python.exe}   # r7e: local interpreter (tools/setup_case_env.sh), not another session's temp dir
cd "$M" || exit 1
FAILS=""
gate() { if [ "$2" != "0" ]; then FAILS="$FAILS $1"; fi; echo "$1 exit $2"; }
[ -x "$CASE_PY" ] || { sh tools/setup_case_env.sh > out/case_env.log 2>&1; }
sh tools/check.sh out/final.ses > out/check.log 2>&1; echo "check.sh done"; grep -v "^  (" out/check.log | tail -6
grep -q "DRC errors 0 " out/check.log && grep -q "unconnected 0 parity 0" out/check.log && grep -q "ERC_CHECK PASS" out/check.log; gate check $?
python -I tools/drc_accept.py out/drc.json > out/drc_accept.out 2>&1; gate drc_accept $?; tail -1 out/drc_accept.out
python -I tools/hotplug.py --design out/design.json --out out/hotplug.out > /dev/null 2>&1; gate hotplug $?; tail -1 out/hotplug.out
python -I tools/verify.py out data/antmicro/a.net > out/verify.out 2>&1; gate verify $?; tail -1 out/verify.out
python -I tools/refplane.py out/p4_kvm_mini.kicad_pcb > out/refplane.out 2>&1; gate refplane $?; tail -2 out/refplane.out | head -1
python -I tools/pairgap.py out/p4_kvm_mini.kicad_pcb > out/pairgap.out 2>&1; gate pairgap $?; tail -1 out/pairgap.out
rm -rf fab_r7e
python -I tools/fab_pack.py out fab_r7e > out/pack.log 2>&1; gate fab_pack $?; tail -1 out/pack.log
cp out/erc_check.out fab_r7e/erc_check_report.txt
cp out/hotplug.out fab_r7e/hotplug_report.txt
cp out/refplane.out fab_r7e/refplane_r7e.txt
python -I tools/pairgap.py out/p4_kvm_mini.kicad_pcb --report fab_r7e/pairgap_r7e.md > /dev/null 2>&1
python -I tools/drc_accept.py out/drc.json > fab_r7e/drc_instances_r7e.txt 2>&1
python -I tools/r7/cpl_table.py out fab_r7e/CPL_JLC.csv fab_r7e/CPL_pin1_check.md
python -I tools/cpl_pin1.py out fab_r7e/CPL_JLC.csv --report fab_r7e/CPL_polarity_pin1_r7e.md > out/cpl_pin1.out 2>&1; gate cpl_pin1 $?; tail -1 out/cpl_pin1.out
python -I tools/r7/impedance_r7.py out/p4_kvm_mini.kicad_pcb > fab_r7e/impedance_r7e.txt 2>&1; gate impedance $?
python -I tools/r6/test_s3_solver.py tools/r6 > fab_r7e/s3_solver_test_r7e.txt 2>&1; gate s3_solver_test $?; tail -1 fab_r7e/s3_solver_test_r7e.txt
python -I tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7e/pairs_r7e.txt 2>&1 || PYTHONPATH=tools/r6 python tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7e/pairs_r7e.txt 2>&1; echo "pairs exit $?"
"$CASE_PY" case/check_case.py case/stl --design out/design.json --pcb out/p4_kvm_mini.kicad_pcb --report fab_r7e/case_check.txt --title "r7e board 40 x 45" > /dev/null 2>&1; gate case $?; tail -1 fab_r7e/case_check.txt
python -I tools/bodycheck.py out --report fab_r7e/bodycheck_r7e.txt > /dev/null 2>&1; gate body $?
G8=$(sha256sum fab_r7e/p4_kvm_mini_gerber.zip | cut -c1-8)
GERBER_SHA8=$G8 BOARD_REV=r7e python -I tools/layout_pdf.py out/p4_kvm_mini.kicad_pcb fab_r7e/p4_kvm_mini_gerber.zip out/design.json fab_r7e/p4_kvm_mini_layout.pdf > out/layout_pdf.log 2>&1; echo "layout pdf exit $?"; tail -1 out/layout_pdf.log
python -I tools/coldstart.py --plot report_r7e/coldstart.png --report fab_r7e/coldstart_r7e.txt > /dev/null 2>&1; echo "coldstart (analysis) exit $?"
for f in p4_kvm_mini.kicad_sch mini.kicad_sym p4_kvm_mini.kicad_pro p4_kvm_mini.kicad_pcb p4_kvm_mini.kicad_dru erc.json drc.json; do cp out/$f kicad/$f; done
python -I tools/mutate.py out --report MUTATION_REPORT.txt > out/mutate.log 2>&1; gate mutate $?; tail -2 MUTATION_REPORT.txt
(cd fab_r7e && sha256sum p4_kvm_mini_layout.pdf coldstart_r7e.txt CPL_polarity_pin1_r7e.md refplane_r7e.txt pairgap_r7e.md drc_instances_r7e.txt bodycheck_r7e.txt s3_solver_test_r7e.txt > SHA256_extra.txt)
if [ -n "$FAILS" ]; then echo "RELEASE FAILED:$FAILS"; exit 1; fi
echo "RELEASE ALL GATES PASS"
