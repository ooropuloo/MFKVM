#!/bin/sh
# Generates, routes until clean, then runs ERC and DRC. Keeps the passing route as out/final.ses.
A=$(cd "$(dirname "$0")" && pwd)
C=${KICAD_CLI:-D:/tools/kicad-nightly/app/bin/kicad-cli.exe}
H=${KICAD_TOOL_HOME:-D:/tools/kicad-nightly/home}
export KICAD_DOCUMENTS_HOME="$H/doc" KICAD_CONFIG_HOME="$H/cfg" KICAD_CACHE_HOME="$H/cache" PYTHONIOENCODING=utf-8
cd "$A" || exit 1
i=1
while [ "$i" -le "${1:-5}" ]; do
  python -I gen_atx.py out > out.log 2>&1 || { cat out.log; exit 1; }
  tail -3 out.log
  rm -f out/try.ses
  (cd out && java -jar "${FREEROUTING_JAR:-D:/tools/freerouting/freerouting.jar}" -de mf_kvm_atx.dsn -do try.ses -mp 30 -l en --gui.enabled=false > fr.log 2>&1)
  [ -f out/try.ses ] || { echo "try $i: no SES"; i=$((i + 1)); continue; }
  python -I gen_atx.py out out/try.ses > out.log 2>&1 || { cat out.log; exit 1; }
  (cd out && "$C" sch erc --format json --severity-all -o erc.json mf_kvm_atx.kicad_sch > erc.log 2>&1
   "$C" pcb drc --refill-zones --save-board --schematic-parity --format json --severity-all -o drc.json mf_kvm_atx.kicad_pcb > drc.log 2>&1)
  R=$(python -I tools/gates.py out)
  echo "try $i: $R"
  case "$R" in *"errors 0 unconnected 0 parity 0 erc 0"*) cp out/try.ses out/final.ses; echo CLEAN; exit 0;; esac
  i=$((i + 1))
done
echo "no clean route"
exit 1
