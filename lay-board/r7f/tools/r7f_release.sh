#!/bin/sh
# r7f: every check, in order, on the board regenerated from out/final.ses (plus the r7d/r7e/r7f stages; the r7f stage reads
# data/r7f_route.ses and data/r7f_hand.json). Logs go to out/ and fab_r7f/.
# Gates: any of these failing makes the script exit 1 at the end: check.sh (ERC/DRC), drc_accept, verify, hotplug (r7f: the eFuse input),
# fab_pack, refplane, pairgap, cpl_pin1, impedance, s3_solver_test, case (regenerated from design.json first), bodycheck, maskcheck,
# holecheck (inside verify), mutate (r7f family added). coldstart.py is an analysis (no gate).
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
python -I tools/csi_via.py out/p4_kvm_mini.kicad_pcb > out/csi_via.out 2>&1; gate csi_via $?; tail -2 out/csi_via.out | head -1
python -I tools/hand_solder_gap.py out/p4_kvm_mini.kicad_pcb > out/hand_solder_gap.out 2>&1; gate hand_solder_gap $?; tail -2 out/hand_solder_gap.out | head -1
rm -rf fab_r7f
python -I tools/fab_pack.py out fab_r7f > out/pack.log 2>&1; gate fab_pack $?; tail -1 out/pack.log
cp out/erc_check.out fab_r7f/erc_check_report.txt
cp out/hotplug.out fab_r7f/hotplug_report.txt
cp out/refplane.out fab_r7f/refplane_r7f.txt
cp out/csi_via.out fab_r7f/csi_via_r7f.txt
cp out/hand_solder_gap.out fab_r7f/hand_solder_gap_r7f.txt
python -I tools/pairgap.py out/p4_kvm_mini.kicad_pcb --report fab_r7f/pairgap_r7f.md > /dev/null 2>&1
python -I tools/drc_accept.py out/drc.json > fab_r7f/drc_instances_r7f.txt 2>&1
python -I tools/r7/cpl_table.py out fab_r7f/CPL_JLC.csv fab_r7f/CPL_pin1_check.md
python -I tools/cpl_pin1.py out fab_r7f/CPL_JLC.csv --report fab_r7f/CPL_polarity_pin1_r7f.md > out/cpl_pin1.out 2>&1; gate cpl_pin1 $?; tail -1 out/cpl_pin1.out
python -I tools/r7/impedance_r7.py out/p4_kvm_mini.kicad_pcb > fab_r7f/impedance_r7f.txt 2>&1; gate impedance $?
python -I tools/r6/test_s3_solver.py tools/r6 > fab_r7f/s3_solver_test_r7f.txt 2>&1; gate s3_solver_test $?; tail -1 fab_r7f/s3_solver_test_r7f.txt
python -I tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7f/pairs_r7f.txt 2>&1 || PYTHONPATH=tools/r6 python tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb > fab_r7f/pairs_r7f.txt 2>&1; echo "pairs exit $?"
"$CASE_PY" case/gen_case.py out/design.json case/stl > case/case.log 2>&1; gate gen_case $?
"$CASE_PY" case/check_case.py case/stl --design out/design.json --pcb out/p4_kvm_mini.kicad_pcb --report fab_r7f/case_check.txt --title "r7f board 40 x 45" > /dev/null 2>&1; gate case $?; tail -1 fab_r7f/case_check.txt
python -I tools/bodycheck.py out --report fab_r7f/bodycheck_r7f.txt > /dev/null 2>&1; gate body $?
G8=$(sha256sum fab_r7f/p4_kvm_mini_gerber.zip | cut -c1-8)
GERBER_SHA8=$G8 BOARD_REV=r7f python -I tools/layout_pdf.py out/p4_kvm_mini.kicad_pcb fab_r7f/p4_kvm_mini_gerber.zip out/design.json fab_r7f/p4_kvm_mini_layout.pdf > out/layout_pdf.log 2>&1; echo "layout pdf exit $?"; tail -1 out/layout_pdf.log
python -I tools/coldstart.py --plot report_r7f/coldstart.png --report fab_r7f/coldstart_r7f.txt > /dev/null 2>&1; echo "coldstart (analysis) exit $?"
cp case/stl/case_spec.json fab_r7f/case_spec_r7f.json
for f in p4_kvm_mini.kicad_sch mini.kicad_sym p4_kvm_mini.kicad_pro p4_kvm_mini.kicad_pcb p4_kvm_mini.kicad_dru erc.json drc.json; do cp out/$f kicad/$f; done
# r7f (REVIEW_r7f minor-4): the delivered KiCad project gets the full footprint library, and its own ERC must be as clean as out/'s
rm -rf kicad/mini.pretty; cp -r out/mini.pretty kicad/mini.pretty; cp out/fp-lib-table out/sym-lib-table kicad/
(cd kicad && KICAD_DOCUMENTS_HOME=${KICAD_TOOL_HOME:-$HOME/.kicad-tool-home}/doc KICAD_CONFIG_HOME=${KICAD_TOOL_HOME:-$HOME/.kicad-tool-home}/cfg KICAD_CACHE_HOME=${KICAD_TOOL_HOME:-$HOME/.kicad-tool-home}/cache ${KICAD_CLI:-kicad-cli} sch erc --format json --severity-all -o erc_kicad.json p4_kvm_mini.kicad_sch > /dev/null 2>&1)
python -I -c "import json,sys; a=json.load(open('kicad/erc_kicad.json',encoding='utf-8')); v=[x['type'] for s in a['sheets'] for x in s['violations']]; print('kicad/ ERC violations', len(v), v[:6]); sys.exit(1 if v else 0)"; gate kicad_erc $?
python -I tools/mutate.py out --report MUTATION_REPORT.txt > out/mutate.log 2>&1; gate mutate $?; tail -2 MUTATION_REPORT.txt
(cd fab_r7f && sha256sum p4_kvm_mini_layout.pdf coldstart_r7f.txt case_spec_r7f.json hand_solder_gap_r7f.txt csi_via_r7f.txt CPL_polarity_pin1_r7f.md refplane_r7f.txt pairgap_r7f.md drc_instances_r7f.txt bodycheck_r7f.txt s3_solver_test_r7f.txt > SHA256_extra.txt)
if [ -n "$FAILS" ]; then echo "RELEASE FAILED:$FAILS"; exit 1; fi
echo "RELEASE ALL GATES PASS"
