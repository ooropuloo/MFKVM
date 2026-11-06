"""Compare the code and data of objects between the upstream baseline and the patched default build.
Debug sections are ignored because they hold build paths.
   python compare_round.py <objcopy> <objdump> <baseline build dir> <patched build dir>"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile

OBJCOPY, OBJDUMP, BASE, PATCHED = sys.argv[1:5]
OBJS = [
    "esp-idf/kvm_display/CMakeFiles/__idf_kvm_display.dir/drivers/gc9a01/gc9a01.c.obj",
    "esp-idf/kvm_display/CMakeFiles/__idf_kvm_display.dir/kvm_display.c.obj",
    "esp-idf/kvm_display/CMakeFiles/__idf_kvm_display.dir/kvm_panels.c.obj",
    "esp-idf/kvm_display/CMakeFiles/__idf_kvm_display.dir/drivers/mono_oled.c.obj",
    "esp-idf/kvm_config/CMakeFiles/__idf_kvm_config.dir/kvm_settings_table.c.obj",
]


def digest(obj):
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "o"
        subprocess.check_call([OBJCOPY, "--strip-debug", "--remove-section=.comment", obj, str(out)])
        dump = subprocess.check_output([OBJDUMP, "-d", "-r", "-s", "--no-show-raw-insn", str(out)], text=True)
    body = "\n".join(dump.splitlines()[2:])
    return hashlib.sha256(body.encode()).hexdigest()[:16], body


status = 0
for rel in OBJS:
    a, ta = digest(f"{BASE}/{rel}")
    b, tb = digest(f"{PATCHED}/{rel}")
    same = a == b
    print(f"{'SAME' if same else 'DIFF'} {a} {b} {rel.rsplit('/', 1)[-1]}")
    if not same:
        status = 1
        la, lb = ta.splitlines(), tb.splitlines()
        diff = [(x, y) for x, y in zip(la, lb) if x != y]
        print(f"     {len(la)} vs {len(lb)} lines, {len(diff)} differ. First lines:")
        for x, y in diff[:6]:
            print(f"       - {x[:100]}\n       + {y[:100]}")
sys.exit(status)
