# -*- coding: utf-8 -*-
"""Mutation tests for the verification suite: inject known faults into a copy of the design and require each check to FAIL.

A check that still passes with the fault in place is broken. Each family first runs once on the unmodified copy (control),
which must pass; otherwise a failing mutation would prove nothing.

A fault is put into the board file AND design.json together, so it is a real design fault and not a mismatch between the
two files (that mismatch has its own mutation). Every mutation names the failure it must produce (regex on the FAIL text):
failing for some other reason does not count as caught.

usage: mutate.py <out_dir> [--only family,family] [--report file] [--keep]
families: verify erc drc mask hole body hotplug imp fabpack r7e case r7f
exit 0 when every control passes and every mutation is caught.
"""
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schgen

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
NAME = 'p4_kvm_mini'
KC = 'D:/tools/kicad-nightly/app/bin/kicad-cli.exe'
H = 'D:/tools/kicad-nightly/home'
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=f'{H}/doc', KICAD_CONFIG_HOME=f'{H}/cfg', KICAD_CACHE_HOME=f'{H}/cache', PYTHONIOENCODING='utf-8')
PY = sys.executable
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
OUT = ARGS[0]
ONLY = None
REPORT = None
for i, a in enumerate(sys.argv):
    if a == '--only':
        ONLY = set(sys.argv[i + 1].split(','))
    if a == '--report':
        REPORT = sys.argv[i + 1]
ARGS = [a for a in ARGS if a not in (','.join(ONLY or []), REPORT)]
COPY = ['p4_kvm_mini.kicad_pcb', 'design.json', 'stock.json', 'p4_kvm_mini.kicad_pro', 'p4_kvm_mini.kicad_dru', 'sym-lib-table', 'fp-lib-table', 'mini.kicad_sym', 'p4_kvm_mini.kicad_sch']
WORK = tempfile.mkdtemp(prefix='mutate_')
results = []


# ---------- editing helpers
def fp_span(pcb, ref):
    m = re.search(r'\(property "Reference" "%s"' % re.escape(ref), pcb)
    a = pcb.rfind('\n\t(footprint ', 0, m.start())
    b = pcb.find('\n\t(footprint ', m.end())
    b = len(pcb) if b < 0 else b
    if b > 0:
        nxt = re.search(r'\n\t\((segment|via|zone|gr_|arc|embedded)', pcb[m.end():b])
        if nxt:
            b = m.end() + nxt.start()
    return a, b


def set_pad_net(pcb, ref, pad, new):
    a, b = fp_span(pcb, ref)
    blk = pcb[a:b]
    m = re.search(r'\(pad "%s"\s.*?\(net "([^"]*)"\)' % re.escape(pad), blk, re.S)
    assert m, (ref, pad)
    blk = blk[:m.start(1)] + new + blk[m.end(1):]
    return pcb[:a] + blk + pcb[b:]


def move_fp(pcb, ref, dx, dy):
    a, b = fp_span(pcb, ref)
    blk = pcb[a:b]
    m = re.search(r'\(translate ([-\d.]+) ([-\d.]+)\)', blk)
    blk = blk[:m.start()] + f'(translate {float(m[1]) + dx:.4f} {float(m[2]) + dy:.4f})' + blk[m.end():]
    return pcb[:a] + blk + pcb[b:]


def P(d, ref):
    return next(p for p in d['parts'] if p['ref'] == ref)


def seg_of(pcb, net, layer=None, minlen=0.8):
    for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', pcb):
        if m[7] == net and (layer is None or m[6] == layer) and math.dist((float(m[1]), float(m[2])), (float(m[3]), float(m[4]))) > minlen:
            return [float(m[i]) for i in range(1, 6)] + [m[6]]
    raise KeyError(net)


def add_segment(pcb, a, b, w, layer, net):
    t = f'\t(segment\n\t\t(start {a[0]:.4f} {a[1]:.4f})\n\t\t(end {b[0]:.4f} {b[1]:.4f})\n\t\t(width {w})\n\t\t(layer "{layer}")\n\t\t(net "{net}")\n\t\t(uuid "{schgen.uid()}")\n\t)\n'
    i = pcb.find('\t(segment')
    return pcb[:i] + t + pcb[i:]


def add_via(pcb, x, y, net, size=0.4, drill=0.2):
    t = f'\t(via\n\t\t(at {x:.4f} {y:.4f})\n\t\t(size {size})\n\t\t(drill {drill})\n\t\t(layers "F.Cu" "B.Cu")\n\t\t(net "{net}")\n\t\t(uuid "{schgen.uid()}")\n\t)\n'
    i = pcb.find('\t(segment')
    return pcb[:i] + t + pcb[i:]


def side_point(seg, off, frac=0.5):
    x0, y0, x1, y1 = seg[:4]
    L = math.dist((x0, y0), (x1, y1))
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    mx, my = x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac
    return mx - uy * off, my + ux * off, ux, uy


class Case:
    def __init__(self):
        self.pcb = open(f'{WORK}/base/{NAME}.kicad_pcb', encoding='utf-8').read()
        self.d = json.load(open(f'{WORK}/base/design.json', encoding='utf-8'))
        self.stock = json.load(open(f'{WORK}/base/stock.json', encoding='utf-8'))

    def net(self, ref, pin, new):
        """Same fault in the board and in design.json."""
        self.pcb = set_pad_net(self.pcb, ref, pin, new)
        P(self.d, ref)['nets'][pin] = new

    def part(self, ref, **kw):
        P(self.d, ref).update(kw)

    def swap_nets(self, a, b):
        ra, pa = a.split('.', 1)
        rb, pb = b.split('.', 1)
        na, nb = P(self.d, ra)['nets'][pa], P(self.d, rb)['nets'][pb]
        self.net(ra, pa, nb)
        self.net(rb, pb, na)

    def swap_values(self, a, b):
        A, B = P(self.d, a), P(self.d, b)
        A['value'], B['value'] = B['value'], A['value']
        A['lcsc'], B['lcsc'] = B['lcsc'], A['lcsc']

    def write(self, dst):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(f'{WORK}/base', dst)
        open(f'{dst}/{NAME}.kicad_pcb', 'w', encoding='utf-8', newline='\n').write(self.pcb)
        json.dump(self.d, open(f'{dst}/design.json', 'w', encoding='utf-8'), indent=0)
        json.dump(self.stock, open(f'{dst}/stock.json', 'w', encoding='utf-8'))
        if getattr(self, 'cpl', None):
            json.dump(self.cpl, open(f'{dst}/cpl_override.json', 'w'))
        return dst


# ---------- runners: each returns (passed, failure text)
def r_verify(dst):
    p = subprocess.run([PY, '-I', f'{HERE}/verify.py', dst, 'x', '--fast'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    bad = '\n'.join(l for l in p.stdout.splitlines() if l.lstrip().startswith('FAIL'))
    if 'Traceback' in p.stderr or 'Error' in p.stderr or p.returncode not in (0, 1):   # a crash (r7f: also a SyntaxError, which prints no Traceback) is not a FAIL
        return None, 'CRASH ' + p.stderr[-600:]
    return p.returncode == 0, bad


def r_erc(dst, writer=None):
    import erc_check
    d = json.load(open(f'{dst}/design.json', encoding='utf-8'))
    (writer or schgen.write)(d['parts'], dst, NAME)
    r = erc_check.run(dst, True)
    return r['ok'], '\n'.join(r['fails'])


def r_drc(dst):
    p = subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--format', 'json', '--severity-all', '-o', f'{dst}/drc.json', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True, text=True, errors='replace')
    r = json.load(open(f'{dst}/drc.json', encoding='utf-8'))
    import drc_accept   # r7e: warnings accepted per instance (data/drc_accepted.json), errors and opens never
    bad, _ = drc_accept.check(r)
    return not bad, '\n'.join(bad)


def gerbers(dst, drill=False):
    g = f'{dst}/g'
    os.makedirs(g, exist_ok=True)
    subprocess.run([KC, 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Mask,B.Mask', '--no-protel-ext', '-o', g + '/', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True)
    if drill:
        subprocess.run([KC, 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute', '--excellon-separate-th', '-o', g + '/', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True)
    return g


def r_mask(dst):
    import maskcheck
    r = maskcheck.check(gerbers(dst))
    return r['ok'], maskcheck.summary(r)


def r_hole(dst):
    import holecheck
    r = holecheck.check(gerbers(dst, True))
    return r['ok'], holecheck.summary(r) + ' ' + ' '.join(f"{x['hole']}->{x['other']} {x['gap']:.3f}" for x in r['fails'][:4])


def r_body(dst):
    import bodycheck
    r = bodycheck.check(dst)
    return r['ok'], bodycheck.summary(r) + ' ' + ' '.join(bodycheck.line(x) for x in r['fails'][:3])


def r_imp(dst):
    p = subprocess.run([PY, '-I', f'{HERE}/r7/impedance_r7.py', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    return p.returncode == 0, (p.stderr or p.stdout)[-300:]


def r_fabpack(dst):
    tgt = f'{dst}/fab_target'
    p = subprocess.run([PY, '-I', f'{HERE}/fab_pack.py', dst, tgt], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    return p.returncode == 0, '\n'.join(l for l in p.stdout.splitlines() if l.startswith(('FAIL', 'REFUSED')))


def r_case(dst):
    case = os.path.join(HERE, '..', 'case')
    # check_case needs cadquery; the system python has none. r7e: the interpreter is this folder's .venv-case (tools/setup_case_env.sh);
    # r7d used another session's temporary directory (REVIEW_r7d tool table). CASE_PY still overrides.
    py = os.environ.get('CASE_PY', os.path.join(HERE, '..', '.venv-case', 'Scripts', 'python.exe'))
    p = subprocess.run([py, f'{case}/check_case.py', f'{case}/stl', '--design', f'{dst}/design.json', '--pcb', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    return p.returncode == 0, '\n'.join(l for l in p.stdout.splitlines() if 'FAIL' in l)[-800:]


def r_verify_full(dst):
    """verify.py with the Gerber-based checks (mask, hole, body, component hole spacing)."""
    p = subprocess.run([PY, '-I', f'{HERE}/verify.py', dst, 'x'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    if 'Traceback' in p.stderr:
        return None, 'CRASH ' + p.stderr[-600:]
    return p.returncode == 0, '\n'.join(l for l in p.stdout.splitlines() if l.lstrip().startswith('FAIL'))


def r_verify_refill(dst):
    """r7e: zones refilled and the board saved first (kicad-cli DRC), so an injected via cuts the planes the way a real one would"""
    subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json', '-o', f'{dst}/drc_refill.json', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True)
    return r_verify(dst)


def r_cpl(dst):
    """r7e: the CPL as fab_pack.py writes it (angles from data/jlc_offsets.json), then a mutation's cpl_override.json, then tools/cpl_pin1.py"""
    import csv
    d = json.load(open(f'{dst}/design.json', encoding='utf-8'))
    off = json.load(open(os.path.join(HERE, '..', 'data', 'jlc_offsets.json'), encoding='utf-8'))
    offs = {r: v['offset'] for r, v in {**off['verified'], **off['unverified_assumption']}.items()}
    over = json.load(open(f'{dst}/cpl_override.json')) if os.path.exists(f'{dst}/cpl_override.json') else {}
    with open(f'{dst}/CPL.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for p in d['parts']:
            if p['dnp'] or p['consign'] or not p['lcsc']:
                continue
            rot = over.get(p['ref'], (p['r'] + offs.get(p['ref'], 0)) % 360)
            w.writerow([p['ref'], f"{p['x'] + 100:.3f}mm", f"{-(p['y'] + 100):.3f}mm", 'Top' if p['side'] == 'F' else 'Bottom', f'{rot:g}'])
    pr = subprocess.run([PY, '-I', f'{HERE}/cpl_pin1.py', dst, f'{dst}/CPL.csv'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    if 'Traceback' in pr.stderr:
        return None, 'CRASH ' + pr.stderr[-600:]
    return pr.returncode == 0, chr(10).join(l for l in pr.stdout.splitlines() if l.startswith('FAIL'))


def r_hotplug(dst):
    p = subprocess.run([PY, '-I', f'{HERE}/hotplug.py', '--design', f'{dst}/design.json'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
    return p.returncode == 0, p.stdout[-400:]


J5_SLOT_VIA = (12.5, -2.45)   # 0.23 mm hole to hole from the J5 shell slot: legal for via to via (0.2), not for a pad hole (0.45)


def run(family, name, runner, mutate, expect):
    c = Case()
    if mutate:
        mutate(c)
    dst = c.write(f'{WORK}/{family}_{len(results):02d}')
    try:
        ok, txt = runner(dst)
    except Exception as e:  # a crash is not a catch
        ok, txt = None, f'CRASH {type(e).__name__}: {e}'
    if mutate is None:
        good = ok is True
        verdict = 'control passes' if good else 'CONTROL FAILED'
    else:
        good = ok is False and re.search(expect, txt) is not None
        verdict = 'caught' if good else ('MISSED (check passed)' if ok else f'failed, but not by the expected check /{expect}/')
    results.append((family, name, verdict, good, txt.strip().splitlines()[:2] if txt else []))
    print(f"{'ok  ' if good else 'BAD '} {family:8s} {name:55s} {verdict}")
    if not good:
        print('     ', (txt or '')[:600].replace('\n', '\n      '))
    if '--keep' not in sys.argv:
        shutil.rmtree(dst, ignore_errors=True)


def all_passive(parts, out, name):
    orig = schgen.pin_type
    schgen.pin_type = lambda p, n, T: ('passive', n, 'r7b writer')
    try:
        return schgen.write(parts, out, name)
    finally:
        schgen.pin_type = orig


def want(f):
    return ONLY is None or f in ONLY


os.makedirs(f'{WORK}/base')
for f in COPY:
    shutil.copy(f'{OUT}/{f}', f'{WORK}/base/{f}')
shutil.copytree(f'{OUT}/mini.pretty', f'{WORK}/base/mini.pretty')
print('work dir', WORK)

if want('verify'):
    V = r_verify
    run('verify', 'control', V, None, '')
    run('verify', 'U6.5 TCA9517A EN back on 3V3 (the r6 bug)', V, lambda c: c.net('U6', '5', '3V3'), r'U6\.5')
    run('verify', 'R50 and R51 swapped (3V3 divider)', V, lambda c: c.swap_values('R50', 'R51'), r'U7\.B1|U1\.8[456]')
    run('verify', 'R51 33.2k -> 30k (3V3 rises to 3.7 V)', V, lambda c: c.part('R51', value='30k 0402'), r'U7\.B1')
    run('verify', 'R62 and R63 swapped (1.2 V divider)', V, lambda c: c.swap_values('R62', 'R63'), r'U7\.(B2|C3|D3)')
    def tol5(c):
        for r in c.stock:
            if r[0] == 'C728559':
                r[1] = '0402WGJ3302TCE'
            if r[0] == 'C319512':
                r[1] = '0402WGJ5600TCE'
    run('verify', 'R61-R63 at 5% instead of 0.1%', V, tol5, r'U7\.(B2|D3)')
    run('verify', 'HPDO tied to CSI clock+ (two outputs on one net)', V, lambda c: c.net('U7', 'H1', 'CSI_CK_P'), r'two push-pull')
    run('verify', 'Y1 load cap C30 47 pF fitted', V, lambda c: c.part('C30', dnp=False), r'Y1\.3')
    run('verify', 'HPDI straight onto HDMI +5V', V, lambda c: c.net('U7', 'H2', 'HDMI_5V'), r'series resistor')
    run('verify', 'VDDIO2 on its own unpowered net', V, lambda c: c.net('U7', 'H7', 'VDDIO2_X'), r'U7\.H7')
    run('verify', 'TEST ball tied to 3V3', V, lambda c: c.net('U7', 'E5', '3V3'), r'U7\.E5')
    run('verify', 'REXT 2.2k instead of 2k', V, lambda c: c.part('R20', value='2.2k 0402', lcsc='C25879'), r'U7\.A1')
    run('verify', 'VBUS divider R10 100k (GPIO3 below VIH)', V, lambda c: c.part('R10', value='100k 0402', lcsc='C25741'), r'U1\.18')
    run('verify', 'HDMI D0+ and D0- swapped at the bridge', V, lambda c: c.swap_nets('U7.D1', 'U7.D2'), r'HDMI connector to TC358743')
    run('verify', 'CSI D0+ and D1+ swapped at the bridge', V, lambda c: c.swap_nets('U7.E8', 'U7.D8'), r'CSI-2')
    def vbus(c):
        c.net('J3', 'A4B9', '5V')
        c.net('J3', 'B4A9', '5V')
    run('verify', 'host VBUS joined to box 5V', V, vbus, r'host VBUS')
    run('verify', 'R67 not fitted (HPDI floating)', V, lambda c: c.part('R67', dnp=True), r'U7\.H2')
    run('verify', 'U2 EN tied to GND', V, lambda c: c.net('U2', '1', 'GND'), r'U2\.1')
    run('verify', 'U4 TLV73325 replaced by TLV73312 (C2871228)', V, lambda c: c.part('U4', lcsc='C2871228', value='TLV73312PDBVR 1.2V'), r'known part|U7\.B5')
    run('verify', 'I2C SDA moved from GPIO7 to GPIO6', V, lambda c: c.swap_nets('U1.22', 'U1.21'), r'firmware')
    run('verify', 'LCD DIN and CLK swapped at J6', V, lambda c: c.swap_nets('J6.3', 'J6.4'), r'firmware')
    run('verify', 'R41 fitted as well as R42 (3V3 onto VO4)', V, lambda c: c.part('R41', dnp=False), r'SD switch source')
    run('verify', 'Q1 gate pull-down R40 not fitted', V, lambda c: c.part('R40', dnp=True), r'Q1\.1')
    run('verify', 'DDC B-side pull-up R27 to 3V3 instead of 5V', V, lambda c: c.net('R27', '2', '3V3'), r'U6\.7')
    def usbswap(c):
        c.swap_nets('J3.A6', 'J3.A7')
        c.swap_nets('J3.B6', 'J3.B7')
    run('verify', 'USB D+ and D- swapped at the host connector', V, usbswap, r'USB-C')
    run('verify', 'CC pull-down R1 10k instead of 5.1k', V, lambda c: c.part('R1', value='10k 0402', lcsc='C25744'), r'USB-C')
    def esd(c):
        c.net('U8', '1', 'unconnected-(U8-Pad1)')
        c.net('U8', '10', 'unconnected-(U8-Pad10)')
    run('verify', 'ESD channel taken off D1-', V, esd, r'TPD4E05U06 channel')
    run('verify', 'TC358743 VSS ball A2 left open', V, lambda c: c.net('U7', 'A2', 'unconnected-(U7-PadA2)'), r'ground pin')
    run('verify', 'VDDC bead FB5 not fitted', V, lambda c: c.part('FB5', dnp=True), r'U7\.(C3|F5|G2)')
    run('verify', 'ATX PWR opto cathode lifted off GND', V, lambda c: c.net('U10', '2', 'PWR_LED'), r'firmware')

    def stale(c):
        c.pcb = set_pad_net(c.pcb, 'R11', '1', 'GND')   # board only
    run('verify', 'board changed, design.json not regenerated', V, stale, r'agree pin for pin')

    def stub(c):
        s = seg_of(c.pcb, 'CK_P')
        x, y, ux, uy = side_point(s, 0.0, 1.0)
        c.pcb = add_segment(c.pcb, (s[2], s[3]), (s[2] + 0.0, s[3] + 5.0), s[4], s[5], 'CK_P')
    run('verify', '5 mm stub added to CK_P (skew budget)', V, stub, r'length difference')

    def wide(c):
        c.pcb = c.pcb.replace('(width 0.127)\n\t\t(layer "B.Cu")\n\t\t(net "D1_P")', '(width 0.2)\n\t\t(layer "B.Cu")\n\t\t(net "D1_P")', 1)
        assert '(width 0.2)\n\t\t(layer "B.Cu")\n\t\t(net "D1_P")' in c.pcb
    run('verify', 'one D1_P segment widened 0.127 -> 0.2 mm', V, wide, r'controlled-impedance')

    def csi_stub(c):
        s = seg_of(c.pcb, 'CSI_CK_P', minlen=0.1)
        c.pcb = add_segment(c.pcb, (s[2], s[3]), (s[2] + 0.3, s[3]), s[4], s[5], 'CSI_CK_P')
    run('verify', 'CSI_CK_P 0.3 mm longer than CSI_CK_N (Espressif 10 mil)', V, csi_stub, r'CSI within each pair')

    def csi_pair(c):   # r7d: both lines of D0 0.9 mm longer, so the pair stays matched and only the inter-pair spread breaks
        for n_ in ('CSI_D0_P', 'CSI_D0_N'):
            s = seg_of(c.pcb, n_, minlen=0.1)
            c.pcb = add_segment(c.pcb, (s[2], s[3]), (s[2] + 0.9, s[3]), s[4], s[5], n_)
    run('verify', 'CSI D0 pair 0.9 mm longer than the others (Espressif 30 mil)', V, csi_pair, r'CSI between pairs')

    def csi_ref(c):    # r7d: the In1 ground fill removed, so the F.Cu CSI lines have no reference plane
        n0 = len(c.pcb)
        c.pcb = re.sub(r'\(filled_polygon\s+\(layer "In1\.Cu"\).*?\n\t\t\)', '', c.pcb, flags=re.S)
        assert len(c.pcb) < n0
    run('verify', 'In1 ground fill missing under the CSI lines', V, csi_ref, r'CSI lines have GND under them|filled GND on In1')
    run('verify', 'TC358743 IR (B4) tied to 3V3 instead of GND', V, lambda c: c.net('U7', 'B4', '3V3'), r'U7\.B4')

if want('erc'):
    E = r_erc
    run('erc', 'control', E, None, '')
    run('erc', 'HPDO output tied to CSI clock+ output', E, lambda c: c.net('U7', 'H1', 'CSI_CK_P'), r'pin_to_pin')
    run('erc', 'VDDIO2 on its own unpowered net', E, lambda c: c.net('U7', 'H7', 'VDDIO2_X'), r'power_pin_not_driven')
    run('erc', 'U4 LDO output onto the 3V3 buck rail', E, lambda c: c.net('U4', '5', '3V3'), r'pin_to_pin|power_pin_not_driven')
    run('erc', 'L1 not fitted (3V3 has no source)', E, lambda c: c.part('L1', dnp=True), r'power_pin_not_driven')
    run('erc', 'TC358743 GND ball on a floating net', E, lambda c: c.net('U7', 'A2', 'GND_X'), r'power_pin_not_driven')
    run('erc', 'REFCLK input left open', E, lambda c: c.net('U7', 'H5', 'unconnected-(U7-PadH5)'), r'open and pin_types')
    run('erc', 'Y1 OE input left open', E, lambda c: c.net('Y1', '1', 'unconnected-(Y1-Pad1)'), r'open and pin_types')
    run('erc', 'schematic written the r7b way (every pin passive)', lambda dst: r_erc(dst, all_passive), lambda c: None, r'pin types differ')
    run('erc', 'TC358743 IR (B4) left open again', E, lambda c: c.net('U7', 'B4', 'unconnected-(U7-PadB4)'), r'B4.*open and pin_types')

if want('drc'):
    D = r_drc
    run('drc', 'control', D, None, '')

    # r7e: warnings are accepted per instance (data/drc_accepted.json). A new instance of an accepted type must fail.
    def cy_new(c):   # C33's courtyard (a footprint edit) grown 0.4 mm toward C32: courtyards_overlap is an accepted TYPE, C32 + C33 is not an accepted instance
        a_, b_ = fp_span(c.pcb, 'C33')
        blk = c.pcb[a_:b_]
        m = re.search(r'\(fp_rect\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)', blk)
        new = m[0].replace(f'(start {m[1]} {m[2]})', f'(start {m[1]} {float(m[2]) - 0.4:.3f})').replace(f'(end {m[3]} {m[4]})', f'(end {m[3]} {float(m[4]) + 0.4:.3f})')
        c.pcb = c.pcb[:a_] + blk.replace(m[0], new, 1) + c.pcb[b_:]
    run('drc', 'new courtyard overlap C32 + C33 (accepted type, new instance)', D, cy_new, r'warning courtyards_overlap C32 \+ C33')

    def r_drc_extra_starved(dst):
        # A starved thermal could not be made on demand by copper edits (pours here keep >= 2 spokes or none), so this one adds a starved
        # thermal at C10.2 to the DRC result itself, the same item format KiCad wrote for the accepted C14.2.
        subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--format', 'json', '--severity-all', '-o', f'{dst}/drc.json', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True)
        r = json.load(open(f'{dst}/drc.json', encoding='utf-8'))
        v = next(x for x in r['violations'] if x['type'] == 'starved_thermal' and any(' C14 ' in i['description'] for i in x['items']))
        v = json.loads(json.dumps(v).replace(' C14 B.Cu', ' C10 B.Cu'))
        r['violations'].append(v)
        import drc_accept
        bad, _ = drc_accept.check(r)
        return not bad, chr(10).join(bad)
    run('drc', 'new starved thermal at C10.2 (accepted type, new instance; injected into the DRC result)', r_drc_extra_starved, lambda c: None, r'starved_thermal C10\.2')

    def short(c):
        s = seg_of(c.pcb, 'D2_P')
        x, y, ux, uy = side_point(s, 0.0)
        c.pcb = add_segment(c.pcb, (x + uy * 0.4, y - ux * 0.4), (x - uy * 0.4, y + ux * 0.4), 0.1, s[5], 'LCD_DIN')
    run('drc', 'LCD_DIN track across D2_P', D, short, r'shorting_items|tracks_crossing|clearance')

    def near(c):
        s = seg_of(c.pcb, 'D2_P')
        x, y, ux, uy = side_point(s, s[4] / 2 + 0.095 + 0.05)
        c.pcb = add_segment(c.pcb, (x - ux * 0.3, y - uy * 0.3), (x + ux * 0.3, y + uy * 0.3), 0.1, s[5], 'LCD_DIN')
    run('drc', 'track 0.095 mm from D2_P (netclass clearance 0.1)', D, near, r'clearance')

    def h2h(c):
        m = re.search(r'\(via\s+\(at ([-\d.]+) ([-\d.]+)\)', c.pcb)
        nn = re.search(r'\(net "([^"]+)"\)', c.pcb[m.end():m.end() + 600])[1]
        x, y = float(m[1]), float(m[2])
        c.pcb = add_via(c.pcb, x + 0.35, y, nn)
    run('drc', 'second via, holes 0.15 mm apart', D, h2h, r'hole_to_hole')

    def edge(c):
        c.pcb = add_segment(c.pcb, (100.0, 80.1), (101.0, 80.1), 0.1, 'B.Cu', 'GND')
    run('drc', 'track 0.05 mm from the board edge', D, edge, r'edge')

    def cut(c):
        m = list(re.finditer(r'\t\(segment\n(?:\t\t[^\n]*\n){4}\t\t\(net "LCD_CS"\)\n\t\t\(uuid "[^"]*"\)\n\t\)\n', c.pcb))
        def ln(x):
            a = re.findall(r'\((?:start|end) ([-\d.]+) ([-\d.]+)\)', x[0])
            return math.dist(*[(float(u), float(v)) for u, v in a])
        x = max(m, key=ln)   # the longest one: a short stub may lie on top of a pad and leave the net connected
        c.pcb = c.pcb[:x.start()] + c.pcb[x.end():]
    run('drc', 'one LCD_CS segment deleted (open net)', D, cut, r'unconnected')
    run('drc', 'GND via 0.23 mm (hole to hole) from the J5 shell slot', D,
        lambda c: setattr(c, 'pcb', add_via(c.pcb, J5_SLOT_VIA[0] + 100, J5_SLOT_VIA[1] + 100, 'GND')), r'hole_to_hole')

if want('mask'):
    run('mask', 'control', r_mask, None, '')
    run('mask', 'mask expansion 0.05 mm on every pad', r_mask, lambda c: setattr(c, 'pcb', c.pcb.replace('(pad_to_mask_clearance 0)', '(pad_to_mask_clearance 0.05)')), r'FAIL|bridge|fail')

if want('hole'):
    run('hole', 'control', r_hole, None, '')

    def vh(c):
        s = seg_of(c.pcb, 'D2_P')
        x, y, ux, uy = side_point(s, s[4] / 2 + 0.15 + 0.1)
        c.pcb = add_via(c.pcb, x, y, 'GND', 0.25, 0.2)
    run('hole', 'GND via drilled 0.15 mm from a D2_P track', r_hole, vh, r'[1-9]\d* under limit')
    run('hole', 'GND via 0.23 mm (hole to hole) from the J5 shell slot, verify.py', r_verify_full,
        lambda c: setattr(c, 'pcb', add_via(c.pcb, J5_SLOT_VIA[0] + 100, J5_SLOT_VIA[1] + 100, 'GND')), r'component hole to any hole')

if want('body'):
    run('body', 'control', r_body, None, '')

    def mv(c):
        a, b = P(c.d, 'U6'), P(c.d, 'R28')
        dx, dy = b['x'] - a['x'], b['y'] - a['y']
        L = math.hypot(dx, dy)
        dx, dy = dx / L * 0.35, dy / L * 0.35
        c.pcb = move_fp(c.pcb, 'U6', dx, dy)
        a['x'] += dx
        a['y'] += dy
    run('body', 'U6 moved 0.35 mm toward R28', r_body, mv, r'U6')
    # check_case.py reads part envelopes from design.json; a board moved by hand without regenerating design.json must be stopped here
    run('body', 'J6 moved 0.8 mm on the board only (design.json stale)', r_body, lambda c: setattr(c, 'pcb', move_fp(c.pcb, 'J6', 0.8, 0.0)), r'disagree|J6')

    def c20back(c):   # undo half of r7c's C20 move: worst gap 0.050 -> 0.025, under the 0.05 mm margin
        c.pcb = move_fp(c.pcb, 'C20', 0.0, 0.025)
        P(c.d, 'C20')['y'] += 0.025
    run('body', 'C20 moved 0.025 mm back toward C19 (margin 0.05)', r_body, c20back, r'C19/C20')

if want('hotplug'):
    # r7f: J5 now rings into VBUS_IN ahead of the eFuse (U16); the R68/C69 damping on 5V no longer decides the hot-plug peak, so the
    # r7c/r7e R68 mutations are replaced by faults on the eFuse input: the UVLO divider that keeps EN under its 7 V absolute maximum
    run('hotplug', 'control', r_hotplug, None, '')
    run('hotplug', 'R72 (EN divider bottom) not fitted: EN sees the VBUS_IN ring', r_hotplug, lambda c: c.part('R72', dnp=True), r'OVER LIMIT')
    run('hotplug', 'R71 and R72 swapped (EN at 68 % of VBUS_IN)', r_hotplug, lambda c: c.swap_values('R71', 'R72'), r'OVER LIMIT')

if want('imp'):
    run('imp', 'control', r_imp, None, '')
    run('imp', 'outer prepreg 0.0994 -> 0.12 mm in the board stackup', r_imp, lambda c: setattr(c, 'pcb', c.pcb.replace('(thickness 0.0994)', '(thickness 0.12)', 1)), r'differ|Assertion')

if want('fabpack'):
    def ready(c):
        pass

    def withreports(dst, verify_text, erc_ok=True):
        open(f'{dst}/verify.out', 'w', encoding='utf-8').write(verify_text)
        shutil.copy(f'{OUT}/drc.json', f'{dst}/drc.json')
        import hashlib
        sha = hashlib.sha256(open(f'{dst}/{NAME}.kicad_sch', 'rb').read()).hexdigest()
        open(f'{dst}/erc_check.out', 'w', encoding='utf-8').write(f'SCHEMATIC sha256 {sha}\nERC_CHECK ' + ('PASS' if erc_ok else '1 FAILED') + '\n')

    def fp_verify_fail(dst):
        withreports(dst, 'FAIL something\nRESULT 1 FAILED\n')
        return r_fabpack(dst)

    def fp_erc_fail(dst):
        import hashlib
        sha = hashlib.sha256(open(f'{dst}/{NAME}.kicad_pcb', 'rb').read()).hexdigest()
        withreports(dst, f'PASS MASKCHECK\nPASS HOLECHECK\nPASS BODYCHECK\nBOARD sha256 {sha}\nRESULT ALL PASS\n', erc_ok=False)
        return r_fabpack(dst)

    def fp_erc_stale(dst):
        import hashlib
        sha = hashlib.sha256(open(f'{dst}/{NAME}.kicad_pcb', 'rb').read()).hexdigest()
        withreports(dst, f'PASS MASKCHECK\nPASS HOLECHECK\nPASS BODYCHECK\nBOARD sha256 {sha}\nRESULT ALL PASS\n')
        open(f'{dst}/{NAME}.kicad_sch', 'a', encoding='utf-8').write('\n')
        return r_fabpack(dst)
    run('fabpack', 'verify.out reports a failure', fp_verify_fail, ready, r'REFUSED')
    run('fabpack', 'erc_check.out reports a failure', fp_erc_fail, ready, r'ERC check \(typed pins\)')
    run('fabpack', 'schematic edited after erc_check ran', fp_erc_stale, ready, r'exact schematic')

    def fp_hotplug(dst):
        import hashlib
        sha = hashlib.sha256(open(f'{dst}/{NAME}.kicad_pcb', 'rb').read()).hexdigest()
        withreports(dst, f'PASS MASKCHECK\nPASS HOLECHECK\nPASS BODYCHECK\nBOARD sha256 {sha}\nRESULT ALL PASS\n')
        dsha = hashlib.sha256(open(f'{dst}/design.json', 'rb').read()).hexdigest()
        open(f'{dst}/hotplug.out', 'w', encoding='utf-8').write(f'design x sha256 {dsha}\nHOTPLUG WORST 9.826 V OVER 5.8 V\n')
        return r_fabpack(dst)
    run('fabpack', 'hotplug.out reports a peak over 5.8 V', fp_hotplug, ready, r'5V hot-plug')

    def fp_hotplug_ef(dst):   # r7f: the eFuse form of the line, over its limit
        fp_hotplug(dst)
        dsha = __import__('hashlib').sha256(open(f'{dst}/design.json', 'rb').read()).hexdigest()
        open(f'{dst}/hotplug.out', 'w', encoding='utf-8').write(f'design x sha256 {dsha}' + chr(10) + 'HOTPLUG WORST 10.335 V at VBUS_IN, 10.335 V at EN, U2 VIN <= 5.70 V OVER LIMIT' + chr(10))
        return r_fabpack(dst)
    run('fabpack', 'hotplug.out (eFuse form) reports EN over its limit', fp_hotplug_ef, ready, r'5V hot-plug')

# ---------- r7e (REVIEW_r7d): checks added in r7e, each with the fault it must catch
if want('r7e'):
    VR = r_verify_refill
    run('r7e', 'control (verify after a zone refill)', VR, None, '')

    def via_beside(c, net, layer, dist, vnet):
        """a via of vnet dist mm from the centre of a segment of net, on the side away from the pair's other line"""
        # the longest segment of the line that keeps 1.5 mm from every pad of other nets' parts' (so the via lands on bare board)
        segs_ = [(float(m[1]), float(m[2]), float(m[3]), float(m[4]), float(m[5]), m[6]) for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)', c.pcb) if m[7] == net and m[6] == layer]
        pads_ = [(v[0] + 100, v[1] + 100) for k, v in c.d['padpos'].items()]
        s_ = max(segs_, key=lambda q: min(math.dist(((q[0] + q[2]) / 2, (q[1] + q[3]) / 2), pp_) for pp_ in pads_) + 0.01 * math.dist(q[:2], q[2:4]))
        # the side away from every other copper segment (the partner line is 0.325 mm away on one side; KiCad gives a via that lands on a
        # track that track's net when it saves the board, which would turn the fault into a harmless via of the pair)
        from shapely.geometry import LineString as LS_, Point as PT_
        allseg = [LS_([(float(m[1]), float(m[2])), (float(m[3]), float(m[4]))]) for m in re.finditer(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width [\d.]+\)\s+\(layer "' + layer + r'"\)\s+\(net "([^"]+)"\)', c.pcb) if m[5] != net]
        cands = [side_point(s_, sg * dist) for sg in (1, -1)]
        x, y, _, _ = max(cands, key=lambda q: min(l.distance(PT_(q[:2])) for l in allseg))
        c.pcb = add_via(c.pcb, x, y, vnet)
    run('r7e', '3V3 via 0.4 mm beside HDMI CK_N (TMDS plane gap, REVIEW injection 6)', VR, lambda c: via_beside(c, 'CK_N', 'B.Cu', 0.4, '3V3'), r'TMDS and USB lines have GND under them')
    run('r7e', '3V3 via 0.4 mm beside CSI_CK_N on F.Cu (CSI plane gap, injection 5)', VR, lambda c: via_beside(c, 'CSI_CK_N', 'F.Cu', 0.4, '3V3'), r'TMDS and USB lines have GND under them')

    def r_csi_ref_cli(dst):   # r7e item 3: the command-line tool the release gates on must exit non-zero on a gap
        subprocess.run([KC, 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json', '-o', f'{dst}/drc_refill.json', f'{dst}/{NAME}.kicad_pcb'], env=ENV, capture_output=True)
        pr = subprocess.run([PY, '-I', f'{HERE}/r7d_csi_ref.py', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        return pr.returncode == 0, f'exit {pr.returncode} ' + chr(10).join(l for l in pr.stdout.splitlines() if l.startswith(('FAIL', 'RESULT')))
    run('r7e', 'control (r7d_csi_ref.py exit code)', r_csi_ref_cli, None, '')
    run('r7e', 'r7d_csi_ref.py on the CSI plane-gap via: must exit non-zero', r_csi_ref_cli, lambda c: via_beside(c, 'CSI_CK_N', 'F.Cu', 0.4, '3V3'), r'exit 1 FAIL CSI_CK_N')

    def r_pairgap(dst):
        pr = subprocess.run([PY, '-I', f'{HERE}/pairgap.py', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        if 'Traceback' in pr.stderr:
            return None, 'CRASH ' + pr.stderr[-600:]
        return pr.returncode == 0, chr(10).join(l for l in pr.stdout.splitlines() if l.startswith('FAIL'))
    run('r7e', 'control (pairgap)', r_pairgap, None, '')

    def squeeze(c, net, layer, d=0.12):   # a coupled segment of the line copied d mm closer to its partner
        from shapely.geometry import LineString as LS_
        from shapely.ops import nearest_points
        rx = r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width ([\d.]+)\)\s+\(layer "([^"]+)"\)\s+\(net "([^"]+)"\)'
        other = net[:-1] + ('P' if net.endswith('N') else 'N')
        S_ = [(float(m[1]), float(m[2]), float(m[3]), float(m[4]), float(m[5]), m[6], m[7]) for m in re.finditer(rx, c.pcb) if m[6] == layer and m[7] in (net, other)]
        mine = [q for q in S_ if q[6] == net and math.dist(q[:2], q[2:4]) > 0.6]
        oth = [LS_([q[:2], q[2:4]]) for q in S_ if q[6] == other]
        def gap_(q):
            mid = LS_([q[:2], q[2:4]]).interpolate(0.5, normalized=True)
            return min(l.distance(mid) for l in oth), mid
        q = min(mine, key=lambda q: abs(gap_(q)[0] - (0.325 if net.startswith(('CK', 'D')) else 0.5)))
        mid = gap_(q)[1]
        near = min(oth, key=lambda l: l.distance(mid))
        a_, b_ = nearest_points(mid, near)
        L = a_.distance(b_)
        dx, dy = (b_.x - a_.x) / L * d, (b_.y - a_.y) / L * d
        c.pcb = add_segment(c.pcb, (q[0] + dx, q[1] + dy), (q[2] + dx, q[3] + dy), q[4], q[5], net)
    run('r7e', 'TMDS D2_N segment 0.12 mm closer to D2_P (gap 0.198 -> 0.078)', r_pairgap, lambda c: squeeze(c, 'D2_N', 'B.Cu'), r'D2_N: impedance outside 100 ohm')
    run('r7e', 'USB_DN segment 0.2 mm closer to USB_DP (gap 0.32 -> 0.12, 78 ohm)', r_pairgap, lambda c: squeeze(c, 'USB_DN', 'B.Cu', 0.2), r'USB_DN: impedance outside 90 ohm')

    def vip(c):
        x, y = P(c.d, 'C21')['x'], P(c.d, 'C21')['y']
        k = next(k for k, v in c.d['padpos'].items() if k.startswith('C21.') and P(c.d, 'C21')['nets'][k.split('.')[1]] == 'GND')
        px, py = c.d['padpos'][k]
        c.pcb = add_via(c.pcb, px + 100, py + 100, 'GND')
    run('r7e', 'GND via put back in the middle of C21.2 (via in pad, REVIEW m2)', r_verify, vip, r'no via drill inside a pasted pad')
    run('r7e', 'C69 reversed: + on GND, - on 5V_DAMP (REVIEW injection 3), verify', r_verify, lambda c: c.swap_nets('C69.1', 'C69.2'), r'polarized capacitors')

    run('r7e', 'control (CPL written as fab_pack does, cpl_pin1)', r_cpl, None, '')
    run('r7e', 'C69 reversed, cpl_pin1', r_cpl, lambda c: c.swap_nets('C69.1', 'C69.2'), r'C69: polarized capacitor')

    def cpl_rot(c):
        c.cpl = {'U2': 90}   # verified offset 270 on KiCad 0: 180 degrees off
    run('r7e', 'U2 CPL angle 180 degrees off (SY8089 on the bottom)', r_cpl, cpl_rot, r'U2: FAIL: CPL')

    def pin1_moved(c):   # the SOT-23-5 land with pins 1 and 3 swapped (a footprint edit): pin 1 no longer where the preview saw it
        a, b = c.d['padpos']['U4.1'], c.d['padpos']['U4.3']
        c.d['padpos']['U4.1'], c.d['padpos']['U4.3'] = b, a
    run('r7e', 'U4 footprint pin 1 moved (pads 1 and 3 swapped)', r_cpl, pin1_moved, r'U4: FAIL: pin 1 in the footprint frame')

if want('case'):
    run('case', 'control', r_case, None, '')

    def j6(c):   # r7f: toward the J6-corner screw in x and y, so the envelope comes within 0.2 mm of the shank (the check is 2-D since r7f)
        dx, dy = 0.8, 3.6
        c.pcb = move_fp(c.pcb, 'J6', dx, dy)
        j = P(c.d, 'J6')
        j['x'] += dx
        j['y'] += dy
        j['bbox'] = [j['bbox'][0] + dx, j['bbox'][1] + dy, j['bbox'][2] + dx, j['bbox'][3] + dy]   # as gen_mini would write it
        for k in list(c.d['padpos']):
            if k.startswith('J6.'):
                c.d['padpos'][k] = [c.d['padpos'][k][0] + dx, c.d['padpos'][k][1] + dy]
    run('case', 'J6 moved 0.8 mm / 3.6 mm toward the M2 screw', r_case, j6, r'M2 shank')

# ---------- r7f: the six approved changes, each with a fault its check must catch
def r_case_mod(mod):
    def runner(dst):
        src = os.path.join(HERE, '..', 'case', 'stl')
        tgt = f'{dst}/stl'
        shutil.copytree(src, tgt)
        mod(tgt)
        case = os.path.join(HERE, '..', 'case')
        py = os.environ.get('CASE_PY', os.path.join(HERE, '..', '.venv-case', 'Scripts', 'python.exe'))
        p = subprocess.run([py, f'{case}/check_case.py', tgt, '--design', f'{dst}/design.json', '--pcb', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        return p.returncode == 0, '\n'.join(l for l in p.stdout.splitlines() if 'FAIL' in l)[-800:]
    return runner


if want('r7f'):
    V = r_verify
    run('r7f', 'control (verify)', V, None, '')

    def j5_bypass(c):   # J5 VBUS straight onto 5V (the eFuse bypassed)
        c.net('J5', 'A4B9', '5V')
        c.net('J5', 'B4A9', '5V')
    run('r7f', 'J5 VBUS wired straight to 5V (eFuse bypassed)', V, j5_bypass, r'only through the eFuse')
    run('r7f', 'D1 (CEC ESD) not fitted', V, lambda c: c.part('D1', dnp=True), r'CEC .* clamp')
    run('r7f', 'R80 (LCD DIN series) 330 ohm instead of 33', V, lambda c: c.part('R80', value='330 0201'), r'DISP_MOSI')
    run('r7f', 'R76 (SD D0 series) 220 ohm instead of 22', V, lambda c: c.part('R76', value='220 0402'), r'SD_D0_GPIO')

    # REVIEW_r7f major-3: the eFuse's support parts and its bypass, each must FAIL by name (no crash)
    def byp(order):
        def f(c):   # C70 re-used as a 0 ohm across the eFuse
            a_, b_ = ('5V', 'VBUS_IN') if order else ('VBUS_IN', '5V')
            c.net('C70', '1', a_)
            c.net('C70', '2', b_)
            c.part('C70', value='0R 0402', lcsc='C17168')
        return f
    run('r7f', '0 ohm 5V(pin 1) -> VBUS_IN(pin 2) across the eFuse', V, byp(True), r'nothing bypasses the eFuse')
    run('r7f', '0 ohm VBUS_IN(pin 1) -> 5V(pin 2) across the eFuse', V, byp(False), r'nothing bypasses the eFuse')
    run('r7f', 'R73 (ILIM) 10k instead of 1k', V, lambda c: c.part('R73', value='10k 0402', lcsc='C25744'), r'ILM .* one resistor')
    run('r7f', 'R73 (ILIM) not fitted', V, lambda c: c.part('R73', dnp=True), r'ILM .* one resistor')
    # DELTA_r7f: the reviewer's four faults that passed every gate in the r7f delta review
    run('r7f', 'R73 (ILIM) 2.2k (C25879, ILIM about 0.95 A, below the full load)', V, lambda c: c.part('R73', value='2.2k 0402', lcsc='C25879'), r'ILIM at its low end')
    run('r7f', 'C71 (dVdt) 2.2 uF (C385032, ramp about 260 ms)', V, lambda c: c.part('C71', value='2.2uF 0402', lcsc='C385032'), r'dVdt ramp to 5 V')

    def ep_nopaste(c):   # the two B.Paste windows on U16's EP removed
        i_ = c.pcb.find('(property "Reference" "U16"')
        j_, k_ = c.pcb.rfind('(footprint ', 0, i_), c.pcb.find('\n\t)', i_)
        blk = re.sub(r'\n\t\t\(fp_rect\s*\(start [-\d.]+ [-\d.]+\)\s*\(end [-\d.]+ [-\d.]+\)(?:(?!\(fp_|\(pad ).)*?\(layer "B\.Paste"\).*?\n\t\t\)', '', c.pcb[j_:k_], flags=re.S)
        assert blk != c.pcb[j_:k_]
        c.pcb = c.pcb[:j_] + blk + c.pcb[k_:]
    run('r7f', 'U16 EP paste windows removed', V, ep_nopaste, r'EP paste')

    def ring31(c):   # H1 copper back to 3.1 mm (0.218 mm to the corner chamfer)
        i_ = c.pcb.find('(property "Reference" "H1"')
        k_ = c.pcb.find('\n\t)', i_)
        blk = c.pcb[i_:k_]
        assert blk.count('(size 2.9 2.9)') == 1
        c.pcb = c.pcb[:i_] + blk.replace('(size 2.9 2.9)', '(size 3.1 3.1)') + c.pcb[k_:]
    run('r7f', 'H1 copper ring back to 3.1 mm (0.218 mm to the board edge)', V, ring31, r'mounting hole copper ring')

    def swap_dv_ilm(c):   # C71 and R73 placed in each other's spot: dVdt sees 1k, ILM sees 100 nF
        c.net('C71', '2', 'EF_ILM')
        c.net('R73', '1', 'EF_DVDT')
    run('r7f', 'C71 and R73 swapped (dVdt on 1k, ILM on 100 nF)', V, swap_dv_ilm, r'dVdt .* capacitor|ILM .* one resistor')
    run('r7f', 'R71 (EN top) not fitted', V, lambda c: c.part('R71', dnp=True), r'EN/UVLO divider')
    run('r7f', 'C71 (dVdt) not fitted', V, lambda c: c.part('C71', dnp=True), r'dVdt .* capacitor')

    def in_out(c):
        c.net('U16', '3', '5V')
        c.net('U16', '4', '5V')
        c.net('U16', '5', 'VBUS_IN')
    run('r7f', 'U16 IN and OUT swapped (must FAIL by name, not crash)', V, in_out, r'only through the eFuse')

    def mh_float(c):
        c.pcb = set_pad_net(c.pcb, 'H1', '1', '')
    run('r7f', 'H1 mounting hole pad off GND', V, mh_float, r'mounting hole')

    def r_csi_via(dst):
        p = subprocess.run([PY, '-I', f'{HERE}/csi_via.py', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        if p.returncode not in (0, 1) or 'Error' in p.stderr:
            return None, 'CRASH ' + p.stderr[-400:]
        return p.returncode == 0, chr(10).join(l for l in p.stdout.splitlines() if l.startswith(('FAIL', 'RESULT')))
    run('r7f', 'control (csi_via)', r_csi_via, None, '')

    def via_near_csi(c):   # a 3V3 via 0.5 mm from a CSI_D1_P segment centre (rule 0.62)
        sg = seg_of(c.pcb, 'CSI_D1_P', minlen=0.8)
        best = None
        for off in (0.5, -0.5):
            x, y, _, _ = side_point(sg, off)
            dmin = min(math.dist((x, y), (v[0] + 100, v[1] + 100)) for v in c.d['padpos'].values())
            if best is None or dmin > best[0]:
                best = (dmin, x, y)
        c.pcb = add_via(c.pcb, best[1], best[2], '3V3')
    run('r7f', '3V3 via 0.5 mm from CSI_D1_P', r_csi_via, via_near_csi, r'FAIL via \(.3V3')

    def vddmipi_back(c):   # the r7d place of the VDD_MIPI via, 0.585 mm from CSI_CK_P (no allowlist any more)
        c.pcb = c.pcb.replace('(at 108.25 98.314)', '(at 108.18 98.314)', 1) if '(at 108.25 98.314)' in c.pcb else add_via(c.pcb, 108.18, 98.314, 'VDD_MIPI')
    run('r7f', 'VDD_MIPI via back at its r7d place (0.585 mm from CSI_CK_P)', r_csi_via, vddmipi_back, r'FAIL via \(.VDD_MIPI')

    def r_hand(dst):
        p = subprocess.run([PY, '-I', f'{HERE}/hand_solder_gap.py', f'{dst}/{NAME}.kicad_pcb'], capture_output=True, text=True, encoding='utf-8', errors='replace', env=ENV)
        if p.returncode not in (0, 1) or 'Error' in p.stderr:
            return None, 'CRASH ' + p.stderr[-400:]
        return p.returncode == 0, chr(10).join(l for l in p.stdout.splitlines() if l.startswith(('FAIL', 'RESULT')))
    run('r7f', 'control (hand_solder_gap)', r_hand, None, '')
    run('r7f', 'R80 0.25 mm toward U1 (pad 0.137 mm from U1.24)', r_hand, lambda c: setattr(c, 'pcb', move_fp(c.pcb, 'R80', -0.25, 0.0)), r'R80\.\d is 0\.1')
    run('r7f', 'R81 0.08 mm toward R80 (pads 0.08 mm apart)', r_hand, lambda c: setattr(c, 'pcb', move_fp(c.pcb, 'R81', 0.0, 0.08)), r'R80 to R81')
    run('r7f', 'R79 (SD_D3, 0402) 0.75 mm toward U1.70/71 (0.14 mm)', r_hand, lambda c: setattr(c, 'pcb', move_fp(c.pcb, 'R79', 0.75, 0.0)), r'R79\.\d is 0\.1')
    run('r7f', 'C3 0.5 mm toward U1.79/80 (0.14 mm)', r_hand, lambda c: setattr(c, 'pcb', move_fp(c.pcb, 'C3', 0.5, 0.0)), r'C3\.\d is 0\.1')

    C0 = r_case_mod(lambda d: None)
    run('r7f', 'control (case with plate, vents, gap filler)', C0, None, '')

    def no_plate(d):
        os.remove(f'{d}/mf_kvm_plate.step')
    run('r7f', 'spreader plate file missing', r_case_mod(no_plate), lambda c: None, r'plate')

    def pla(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        sp['materials']['tray'] = 'PLA'
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'))
    run('r7f', 'tray material PLA', r_case_mod(pla), lambda c: None, r'heat resistant')

    def lid_plastic(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        sp['materials']['lid'] = 'PETG, printed'
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'))
    run('r7f', 'lid material plastic', r_case_mod(lid_plastic), lambda c: None, r'aluminium')
    def no_mask(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        sp['masked'].pop('post_end')
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'))
    run('r7f', 'post end faces not masked (anodized: no ground contact)', r_case_mod(no_mask), lambda c: None, r'masked from the anodize')

    def no_accept(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        sp['acceptance'] = []
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'))
    run('r7f', 'ground resistance acceptance test dropped', r_case_mod(no_accept), lambda c: None, r'acceptance tests')

    def fan_on_board(d):
        sp = json.load(open(f'{d}/case_spec.json', encoding='utf-8'))
        sp['fan']['fan'] = '30 x 30 mm 5 V fan powered from the board 5V'
        json.dump(sp, open(f'{d}/case_spec.json', 'w', encoding='utf-8'))
    run('r7f', 'fan spec says powered from the board', r_case_mod(fan_on_board), lambda c: None, r'own USB supply')
    run('r7f', 'fan duct file missing', r_case_mod(lambda d: os.remove(f'{d}/mf_kvm_fanduct.step')), lambda c: None, r'fan duct files')

    run('r7f', 'H2 mounting hole pad off GND (case grounding check)', r_case_mod(lambda d: None), lambda c: setattr(c, 'pcb', set_pad_net(c.pcb, 'H2', '1', '')), r'plated and on GND')

bad = [r for r in results if not r[3]]
lines = [f"{'ok ' if r[3] else 'BAD'} | {r[0]:8s} | {r[1]} | {r[2]} | {' / '.join(r[4])[:160]}" for r in results]
txt = f'mutation run on {os.path.abspath(OUT)}\n' + '\n'.join(lines) + f'\n\n{len(results)} runs, {len(bad)} bad\nMUTATION ' + ('ALL CAUGHT' if not bad else f'{len(bad)} BAD') + '\n'
if REPORT:
    open(REPORT, 'w', encoding='utf-8', newline='\n').write(txt)
print(txt)
if '--keep' not in sys.argv:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if bad else 0)
