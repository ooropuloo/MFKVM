#!/bin/sh
# r7e: the interpreter for case/check_case.py (needs cadquery), kept inside this folder so the release no longer depends on another
# session's temporary directory. Versions are the ones the r7c/r7d case checks ran with.
# usage: sh tools/setup_case_env.sh      -> creates .venv-case/ ; tools/r7e_release.sh and tools/mutate.py use .venv-case/Scripts/python.exe
cd "$(dirname "$0")/.." || exit 1
[ -x .venv-case/Scripts/python.exe ] && .venv-case/Scripts/python.exe -c "import cadquery" 2>/dev/null && { echo "case env ok"; exit 0; }
uv venv --python 3.11 .venv-case || exit 1
uv pip install --python .venv-case/Scripts/python.exe cadquery==2.8.0 cadquery-ocp==7.9.3.1.1 numpy==2.4.6 shapely==2.2.0 trimesh==5.2.0 || exit 1
.venv-case/Scripts/python.exe -c "import cadquery, numpy, shapely; print('case env ok, cadquery', cadquery.__version__)"
