# -*- coding: utf-8 -*-
"""Development only (not used by the release): reloads the gen_mini state saved just before the r7f stage (R7F_DUMP=<pkl>),
then runs the r7f stage and the rest of gen_mini (board, schematic, design.json, DSN writers). usage: r7f_dev.py <pkl>"""
import sys
import textwrap
import dill

pkl = sys.argv[1]
src = open('D:/git/p4-kvm-box/v2_r7f/gen_mini.py', encoding='utf-8').read()
i = src.index("    exec(open(os.path.join(HERE, 'tools', 'r7f_stage.py'), encoding='utf-8').read())\n")
j = src.index('# r7 item 5: the board')
block = textwrap.dedent(src[i:j])
rest = src[j:]
dill.load_module(pkl)
g = sys.modules["__main__"].__dict__
g['os'].environ.pop('R7F_DUMP', None)
exec(compile(block + rest, 'gen_mini_tail', 'exec'), g)
