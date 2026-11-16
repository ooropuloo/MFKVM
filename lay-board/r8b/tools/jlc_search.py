# -*- coding: utf-8 -*-
"""r7f: read-only JLC parts search (same public endpoint tools/stock.py uses). usage: jlc_search.py <keyword> [<keyword> ...]
Prints LCSC code, model, package, stock, library type, first price break. Writes nothing."""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
for kw in sys.argv[1:]:
    body = json.dumps({'keyword': kw, 'currentPage': 1, 'pageSize': 25}).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    r = json.load(urllib.request.urlopen(req, timeout=25))
    lst = (((r.get('data') or {}).get('componentPageInfo') or {}).get('list') or [])
    print(f'== {kw}: {len(lst)} hits')
    for x in lst:
        pr = x.get('componentPrices') or [{}]
        print(f"  {x.get('componentCode')}  {x.get('componentModelEn')}  {x.get('componentSpecificationEn')}  stock {x.get('stockCount')}  {x.get('componentLibraryType')}  "
              f"{pr[0].get('startNumber')}+ {pr[0].get('productPrice')} USD  | {(x.get('describe') or '')[:90]}")
    time.sleep(0.3)
