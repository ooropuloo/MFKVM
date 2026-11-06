import re, json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
PCB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'kicad', 'p4_kvm_mini.kicad_pcb')
TOK = re.compile(r'\s+|\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def sexp(s):
    st = [[]]
    for m in TOK.finditer(s):
        t = m.group()
        if t.isspace():
            continue
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop()
            st[-1].append(x)
        else:
            st[-1].append(t[1:-1] if t[0] == '"' else t)
    return st[0][0]


def get(n, k):
    for c in n:
        if isinstance(c, list) and c and c[0] == k:
            return c


def load():
    t = sexp(open(PCB, encoding='utf-8').read())
    fps = {}
    for c in t:
        if isinstance(c, list) and c and c[0] == 'footprint':
            tf = get(c, 'transform')
            layer = get(c, 'layer')[1]
            tr = get(tf, 'translate')
            x, y = float(tr[1]), float(tr[2])
            rot = float(get(tf, 'rotate')[1])
            assert rot == 0 and get(tf, 'scale')[1:] == ['1', '1']
            ref = None
            attr = get(c, 'attr')
            pads = []
            crt = None
            for d in c:
                if not isinstance(d, list):
                    continue
                if d[0] == 'property' and d[1] == 'Reference':
                    ref = d[2]
                if d[0] == 'fp_rect' and get(d, 'layer')[1].endswith('CrtYd'):
                    crt = (float(get(d, 'start')[1]) + x, float(get(d, 'start')[2]) + y, float(get(d, 'end')[1]) + x, float(get(d, 'end')[2]) + y)
                if d[0] == 'pad':
                    pa = get(d, 'at')
                    sz = get(d, 'size')
                    net = get(d, 'net')
                    if len(pa) > 3 and float(pa[3]) % 180 != 0:
                        raise SystemExit('rotated pad ' + str(ref))
                    pads.append(dict(n=d[1], kind=d[2], shape=d[3], x=x + float(pa[1]), y=y + float(pa[2]), w=float(sz[1]), h=float(sz[2]), net=net[1] if net else '', layers=get(d, 'layers')[1:]))
            fps[ref] = dict(ref=ref, lib=c[1], x=x, y=y, rot=rot, layer=layer, attr=attr[1:] if attr else [], pads=pads, crt=crt)
    return fps, t


if __name__ == '__main__':
    f, t = load()
    print(len(f))
    for r in 'U11 J4 U10 U12 C11 U5 C19 Y1 C40 J7 R52 R42 R53 C41 C17 R22 R23 U4 C10 J5'.split():
        p = f[r]
        print(r, p['lib'], 'at', round(p['x'] - 100, 3), round(p['y'] - 100, 3), 'rot', p['rot'], p['layer'], p['attr'], 'crt', p['crt'])
        if r != 'J5':
            print('    ', [(q['n'], round(q['x'] - 100, 3), round(q['y'] - 100, 3), q['w'], q['h'], q['net']) for q in p['pads']])
    print('B side:', sorted(r for r in f if f[r]['layer'] == 'B.Cu'))
    print('F side:', sorted(r for r in f if f[r]['layer'] == 'F.Cu'))
