#!/bin/sh
# Routes repeatedly until KiCad reports no opens and no DRC errors. Keeps the SES that passed as out/final.ses.
M=$(cd "$(dirname "$0")/.." && pwd)
C=${KICAD_CLI:-kicad-cli}
H=${KICAD_TOOL_HOME:-$HOME/.kicad-tool-home}
export KICAD_DOCUMENTS_HOME="$H/doc" KICAD_CONFIG_HOME="$H/cfg" KICAD_CACHE_HOME="$H/cache" PYTHONIOENCODING=utf-8
cd "$M" || exit 1
i=1
while [ "$i" -le "${1:-10}" ]; do
  python -I gen_mini.py out > out/gen.log 2>&1 || { echo "gen failed"; exit 1; }
  rm -f out/try.ses
  (cd out && java -jar ${FREEROUTING_JAR:-freerouting.jar} -de p4_kvm_mini.dsn -do try.ses -mp 40 -l en --gui.enabled=false > fr.log 2>&1)
  if [ ! -f out/try.ses ]; then echo "try $i: no SES"; i=$((i + 1)); continue; fi
  sh tools/check.sh out/try.ses > out/check.log 2>&1
  R=$(python -I -c "
import json
r=json.load(open('out/drc.json',encoding='utf-8'))
print(sum(v['severity']=='error' for v in r['violations']),len(r['unconnected_items']),len(r['schematic_parity']))")
  echo "try $i: errors opens parity = $R"
  if [ "$R" = "0 0 0" ]; then cp out/try.ses out/final.ses; echo CLEAN; exit 0; fi
  i=$((i + 1))
done
echo "no clean route in ${1:-10} tries"
exit 1
