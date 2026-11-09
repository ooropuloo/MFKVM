# -*- coding: utf-8 -*-
"""ERC that means something: runs KiCad ERC on the schematic and adds what KiCad cannot judge.

1. The schematic's pin types are read back from the .kicad_sch and compared with data/pin_types.json, pin by pin.
   A symbol whose pins were written some other way (for example all passive, as up to r7b) fails here.
2. KiCad ERC, all severities. Every violation must match an entry in data/erc_waivers.json (type, text, reason with a
   datasheet reference); anything else fails. A waiver that no longer matches anything also fails, so waivers cannot pile up.
3. Pins left open: an open pin of type input, bidirectional, tri_state or power_in fails unless data/pin_types.json
   open_ok lists it with a reason. Entries marked WARN are printed as warnings: they are open questions, not passes.
4. PWR_FLAG: each flag placed by tools/schgen.py is listed with the source path it was given.

usage: erc_check.py <out_dir> [--no-run]      writes <out_dir>/erc_check.out; exit 0 pass, 1 fail
"""
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schgen

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
NAME = 'p4_kvm_mini'
KC = 'D:/tools/kicad-nightly/app/bin/kicad-cli.exe'
H = 'D:/tools/kicad-nightly/home'
ENV = dict(os.environ, KICAD_DOCUMENTS_HOME=f'{H}/doc', KICAD_CONFIG_HOME=f'{H}/cfg', KICAD_CACHE_HOME=f'{H}/cache')
WAIVERS = os.path.join(HERE, '..', 'data', 'erc_waivers.json')
OPEN_NEEDS_REASON = ('input', 'bidirectional', 'tri_state', 'power_in')


def run(out, do_erc=True, T=None):
    T = T or schgen.load_types()
    lines, fails, warns = [], [], []

    def say(s):
        lines.append(s)

    sch_path = f'{out}/{NAME}.kicad_sch'
    sch = open(sch_path, encoding='utf-8').read()
    d = json.load(open(f'{out}/design.json', encoding='utf-8'))
    parts = d['parts']
    P = {p['ref']: p for p in parts}

    # 1. pin types in the file against the data
    types = {}
    for m in re.finditer(r'\(symbol "mini:S_([^"]+)" .*?\n    \)', sch, re.S):
        for q in re.finditer(r'\(pin (\w+) line \(at [^)]*\) \(length [\d.]+\) \(name "([^"]*)"', m[0]):
            types[(m[1], q[2])] = q[1]
    bad = []
    count = 0
    for p in parts:
        for n in p['nets']:
            want = schgen.pin_type(p, n, T)[0]
            got = types.get((p['ref'], n))
            count += 1
            if got != want:
                bad.append(f"{p['ref']}.{n} file {got} data {want}")
    by_type = {}
    for t in types.values():
        by_type[t] = by_type.get(t, 0) + 1
    say(f'pin types read back from the schematic: {len(types)} pins {dict(sorted(by_type.items()))}')
    if bad or len(types) != count:
        fails.append(f'schematic pin types differ from data/pin_types.json ({len(types)} in file, {count} expected): {bad[:8]}')

    # 2. KiCad ERC
    if do_erc:
        p = subprocess.run([KC, 'sch', 'erc', '--format', 'json', '--severity-all', '-o', f'{out}/erc.json', sch_path], env=ENV, capture_output=True, text=True, errors='replace')
        if p.returncode not in (0, 5) and not os.path.exists(f'{out}/erc.json'):
            fails.append(f'kicad-cli erc failed: {p.stderr[-300:]}')
    e = json.load(open(f'{out}/erc.json', encoding='utf-8'))
    viol = [v for s in e.get('sheets', []) for v in s.get('violations', [])]
    say(f"KiCad {e.get('kicad_version')} ERC: {len(viol)} violations; checks ignored by the project: {[c['key'] for c in e.get('ignored_checks', [])]}")
    waivers = json.load(open(WAIVERS, encoding='utf-8'))['waivers'] if os.path.exists(WAIVERS) else []
    used = [0] * len(waivers)
    for v in viol:
        text = ' || '.join(i['description'] for i in v['items'])
        hit = [i for i, w in enumerate(waivers) if w['type'] == v['type'] and re.search(w['match'], text)]
        if hit:
            used[hit[0]] += 1
            say(f"  waived {v['severity']} {v['type']}: {text}  [{waivers[hit[0]]['reason']}]")
        else:
            fails.append(f"ERC {v['severity']} {v['type']}: {text}")
    for w, u in zip(waivers, used):
        if not u:
            fails.append(f"stale waiver, matches nothing: {w['type']} {w['match']}")

    # 3. open pins that would need a reason
    n_open = 0
    for p in parts:
        k = schgen.kind_of(p, T)
        for n, net in p['nets'].items():
            if not net.startswith('unconnected'):
                continue
            n_open += 1
            t, nm, _ = schgen.pin_type(p, n, T)
            if t not in OPEN_NEEDS_REASON:
                continue
            ok = T['open_ok'].get(f'{k}.{n}')
            if ok is None and k == 'ESP32-P4-Module' and t == 'bidirectional' and re.match(r'(GPIO|C6_IO)\d+$', nm):
                ok = T['open_ok']['ESP32-P4-Module.GPIO']
            if ok is None:
                fails.append(f"{p['ref']}.{n} ({nm}, {t}) is open and pin_types.json open_ok gives no reason")
            elif ok['level'] == 'WARN':
                warns.append(f"{p['ref']}.{n} ({nm}, {t}) open: {ok['why']}")
    say(f'open pins: {n_open}')

    # 4. power flags
    flags = schgen.flags_needed(parts, T)
    for net, path in flags.items():
        if path:
            say(f"  PWR_FLAG {net}: {' / '.join(path)}")
        else:
            say(f'  {net}: power_in pins, no source behind a link or connector (needs a power_out pin on the net itself)')

    sha = hashlib.sha256(open(sch_path, 'rb').read()).hexdigest()
    for w in warns:
        say('WARN ' + w)
    for f in fails:
        say('FAIL ' + f)
    say(f'SCHEMATIC sha256 {sha}')
    say('ERC_CHECK ' + ('PASS' if not fails else f'{len(fails)} FAILED') + f', {len(warns)} warnings')
    return dict(ok=not fails, fails=fails, warns=warns, lines=lines, viol=viol)


if __name__ == '__main__':
    out = sys.argv[1]
    r = run(out, '--no-run' not in sys.argv)
    txt = '\n'.join(r['lines']) + '\n'
    print(txt, end='')
    open(f'{out}/erc_check.out', 'w', encoding='utf-8', newline='\n').write(txt)
    sys.exit(0 if r['ok'] else 1)
