# -*- coding: utf-8 -*-
"""r7f: lists tracks and vias (design mm) of given nets inside a window. usage: r7f_dump.py <board> <net,net|*> x0,y0,x1,y1"""
import re
import sys

s = open(sys.argv[1], encoding='utf-8').read()
nets = set(sys.argv[2].split(','))
x0, y0, x1, y1 = map(float, sys.argv[3].split(','))
names = dict((int(a), b) for a, b in re.findall(r'\(net (\d+) "([^"]*)"\)', s))
inw = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1
for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net (\d+|"[^"]*")\)', s):
    n = m[7].strip('"')
    n = names.get(int(n), n) if n.isdigit() else n
    a = (float(m[1]) - 100, float(m[2]) - 100)
    b = (float(m[3]) - 100, float(m[4]) - 100)
    if ('*' in nets or n in nets) and (inw(*a) or inw(*b)):
        print(f'seg {n:12s} {m[6]:7s} w{m[5]:5s} ({a[0]:.3f}, {a[1]:.3f}) -> ({b[0]:.3f}, {b[1]:.3f})')
for m in re.finditer(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)\s+\(size ([\d.]+)\)\s+\(drill ([\d.]+)\)(?:(?!\(via|\(segment).)*?\(net (\d+|"[^"]*")\)', s, re.S):
    n = m[5].strip('"')
    n = names.get(int(n), n) if n.isdigit() else n
    a = (float(m[1]) - 100, float(m[2]) - 100)
    if ('*' in nets or n in nets) and inw(*a):
        print(f'via {n:12s} size {m[3]} ({a[0]:.3f}, {a[1]:.3f})')
