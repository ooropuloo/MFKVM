# -*- coding: utf-8 -*-
"""usage: drc_list.py <out dir> [--all]: prints DRC errors and anything not in the r5 warning set."""
import json
import sys

r = json.load(open(sys.argv[1] + '/drc.json', encoding='utf-8'))
errs = [v for v in r['violations'] if v['severity'] == 'error']
warn = [v for v in r['violations'] if v['severity'] != 'error']
print('errors', len(errs), 'warnings', len(warn), 'unconnected', len(r['unconnected_items']), 'parity', len(r['schematic_parity']))
for v in errs:
    print(' E', v['type'], '|', v.get('description', '')[:60], '|', ' ; '.join(f"{i['description'][:70]} @{i['pos']['x']:.2f},{i['pos']['y']:.2f}" for i in v['items']))
for v in warn:
    if '--all' in sys.argv or v['type'] != 'courtyards_overlap':
        print(' W', v['type'], '|', ' ; '.join(f"{i['description'][:50]} @{i['pos']['x']:.2f},{i['pos']['y']:.2f}" for i in v['items']))
print(' courtyards', sorted({' / '.join(sorted(i['description'].split()[1] for i in v['items'])) for v in warn if v['type'] == 'courtyards_overlap'}))
for u in r['unconnected_items'][:40]:
    print(' U', ' ; '.join(f"{i['description'][:60]} @{i['pos']['x']:.2f},{i['pos']['y']:.2f}" for i in u['items']))
for u in r['schematic_parity'][:20]:
    print(' P', u.get('description'), [i['description'] for i in u.get('items', [])][:3])
