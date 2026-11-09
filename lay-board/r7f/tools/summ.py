# -*- coding: utf-8 -*-
import collections
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = sys.argv[1]
e = json.load(open(f'{d}/erc.json', encoding='utf-8'))
print('ERC', collections.Counter(v['type'] for s in e.get('sheets', []) for v in s.get('violations', [])).most_common(6))
r = json.load(open(f'{d}/drc.json', encoding='utf-8'))
v = r.get('violations', [])
print('DRC errors', sum(x['severity'] == 'error' for x in v), 'warnings', sum(x['severity'] == 'warning' for x in v), collections.Counter(x['type'] for x in v).most_common(14))
print('unconnected', len(r.get('unconnected_items', [])), 'parity', len(r.get('schematic_parity', [])))
print('unconnected nets', collections.Counter(i['description'].split('[')[-1].split(']')[0] for u in r.get('unconnected_items', []) for i in u['items'][:1]).most_common(25))
for x in [x for x in v if x['severity'] == 'error'][:int(sys.argv[2]) if len(sys.argv) > 2 else 14]:
    print(' ', x['type'], '|', ' || '.join(i['description'][:62] + f" @{i['pos']['x']-100:.2f},{i['pos']['y']-100:.2f}" for i in x['items'][:2]))
