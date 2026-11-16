# -*- coding: utf-8 -*-
"""Writes stock.json: JLC's model, stock and price for each LCSC number on the board. Reads only."""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
OUT = sys.argv[1]
d = json.load(open(f'{OUT}/design.json', encoding='utf-8'))
codes = {}
for p in d['parts']:
    if p['lcsc'] and not p['dnp']:
        codes.setdefault(p['lcsc'], []).append(p['ref'])
URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
rows = []
for c, refs in sorted(codes.items()):
    body = json.dumps({'keyword': c, 'currentPage': 1, 'pageSize': 3}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    r = json.load(urllib.request.urlopen(req, timeout=25))
    hit = [x for x in (((r.get('data') or {}).get('componentPageInfo') or {}).get('list') or []) if x.get('componentCode') == c]
    x = hit[0] if hit else {}
    rows.append((c, x.get('componentModelEn'), x.get('stockCount'), x.get('componentLibraryType'), (x.get('componentPrices') or [{}])[0].get('productPrice'), len(refs), refs[0]))
    time.sleep(0.2)
json.dump(rows, open(f'{OUT}/stock.json', 'w', encoding='utf-8'))
print('types', len(rows), 'parts', sum(r[5] for r in rows), 'extended', sum(r[3] == 'expand' for r in rows), 'parts cost per board USD', round(sum((r[4] or 0) * r[5] for r in rows), 2), 'lowest stock', sorted((r[2] or 0, r[1]) for r in rows)[:3])
