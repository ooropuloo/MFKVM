#!/bin/sh
# Regenerates schematic and board from the routed SES, then runs ERC and DRC with parity.
M=$(cd "$(dirname "$0")/.." && pwd)
C=${KICAD_CLI:-D:/tools/kicad-nightly/app/bin/kicad-cli.exe}
H=${KICAD_TOOL_HOME:-D:/tools/kicad-nightly/home}
export KICAD_DOCUMENTS_HOME="$H/doc" KICAD_CONFIG_HOME="$H/cfg" KICAD_CACHE_HOME="$H/cache" PYTHONIOENCODING=utf-8
cd "$M" || exit 1
python -I gen_mini.py out "$1" > out/gen.log 2>&1
echo "gen exit $?"; tail -3 out/gen.log | cut -c1-120
cd out || exit 1
"$C" sch erc --format json --severity-all -o erc.json p4_kvm_mini.kicad_sch > erc.log 2>&1
echo "erc exit $?"
"$C" pcb drc --refill-zones --save-board --schematic-parity --format json --severity-all -o drc.json p4_kvm_mini.kicad_pcb > drc.log 2>&1
echo "drc exit $?"
python -I "$M/tools/summ.py" .
