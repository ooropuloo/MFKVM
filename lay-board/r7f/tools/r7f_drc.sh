#!/bin/sh
# r7f development: ERC + DRC on out/ as it stands (gen already run). Same commands as tools/check.sh after the generator.
M=$(cd "$(dirname "$0")/.." && pwd)
C=${KICAD_CLI:-kicad-cli}
H=${KICAD_TOOL_HOME:-$HOME/.kicad-tool-home}
export KICAD_DOCUMENTS_HOME="$H/doc" KICAD_CONFIG_HOME="$H/cfg" KICAD_CACHE_HOME="$H/cache" PYTHONIOENCODING=utf-8
cd "$M/out" || exit 1
"$C" sch erc --format json --severity-all -o erc.json p4_kvm_mini.kicad_sch > erc.log 2>&1
python -I "$M/tools/erc_check.py" . --no-run > erc_check.log 2>&1; echo "erc_check exit $?"; tail -1 erc_check.log
"$C" pcb drc --refill-zones --save-board --schematic-parity --format json --severity-all -o drc.json p4_kvm_mini.kicad_pcb > drc.log 2>&1
python -I "$M/tools/summ.py" .
