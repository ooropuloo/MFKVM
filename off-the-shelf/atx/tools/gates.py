# -*- coding: utf-8 -*-
"""One line summary of ERC and DRC. usage: gates.py <out_dir> [--show]"""
import collections
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = sys.argv[1]
e = json.load(open(f'{d}/erc.json', encoding='utf-8'))
r = json.load(open(f'{d}/drc.json', encoding='utf-8'))
erc = [v for s in e.get('sheets', []) for v in s.get('violations', [])]
v = r.get('violations', [])
err = [x for x in v if x['severity'] == 'error']
print(f"errors {len(err)} unconnected {len(r.get('unconnected_items', []))} parity {len(r.get('schematic_parity', []))} erc {len(erc)} warnings {len(v) - len(err)}")
if len(sys.argv) > 2:
    print(collections.Counter(x['type'] for x in v).most_common(12))
    print(collections.Counter(x['type'] for x in erc).most_common(12))
    for x in err[:20]:
        print(' ', x['type'], '|', ' || '.join(i['description'][:60] for i in x['items'][:2]))
