# -*- coding: utf-8 -*-
"""DRC warnings accepted per instance (r7e). r7c/r7d accepted whole warning types, so a new starved thermal or courtyard overlap passed
silently (REVIEW_r7d tool table: data/drc_accepted.json listed one starved thermal, five went through).

An instance is its type plus the sorted labels of its items: 'U1.52' for a pad, 'C14' for a footprint, 'zone GND F.Cu' for a pour;
anything else by its position to 0.01 mm. data/drc_accepted.json lists every accepted instance with its reason. Any DRC error, any
unconnected item and any warning instance not listed fails.
usage: drc_accept.py <drc.json>      prints the instances, exit 1 if any is not accepted
"""
import json
import os
import re
import sys

ACCEPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'drc_accepted.json')


def label(item):
    d = item['description']
    m = re.match(r'^(\S+) .*?\[([^\]]*)\].*?\b([A-Z]+\d+)\s+[FB]\.Cu$', d)
    if m:                                    # a pad: "<number> ... [<net>] ... <REF> F.Cu"
        return f'{m[3]}.{m[1]}'
    m = re.search(r'\b([A-Z]+\d+)$', d)      # a footprint: "... <REF>"
    if m:
        return m[1]
    m = re.search(r'\[([^\]]*)\].*?([FB]\.Cu|In\d\.Cu)', d)
    if m and len(d) < 80 and not re.search(r'\d+\.\d+ mm', d):   # a pour: "... [GND] ... F.Cu ..."
        return f'zone {m[1]} {m[2]}'
    return f'@{item["pos"]["x"] - 100:.2f},{item["pos"]["y"] - 100:.2f}'


def key(v):
    return v['type'] + ' ' + ' + '.join(sorted(label(i) for i in v['items']))


def check(drc):
    acc = json.load(open(ACCEPT, encoding='utf-8'))['accepted']
    bad = [f"error {key(v)}" for v in drc['violations'] if v['severity'] == 'error']
    bad += [f"unconnected {key(dict(type='', items=u['items']))}" for u in drc.get('unconnected_items', [])]
    bad += [f"warning {key(v)} (not in data/drc_accepted.json)" for v in drc['violations'] if v['severity'] == 'warning' and key(v) not in acc]
    seen = {key(v) for v in drc['violations'] if v['severity'] == 'warning'}
    stale = [k for k in acc if k not in seen]
    return bad, stale


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    r = json.load(open(sys.argv[1], encoding='utf-8'))
    for v in r['violations']:
        print(f"{v['severity']:8s} {key(v)}")
    bad, stale = check(r)
    for b in bad:
        print('NOT ACCEPTED', b)
    for k in stale:
        print('accepted but not present (stale entry):', k)
    print('DRC ACCEPT ' + ('FAIL' if bad else 'PASS'))
    sys.exit(1 if bad else 0)
