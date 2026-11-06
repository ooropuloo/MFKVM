"""Compare what the defaults files asked for with what landed in the final sdkconfig.
   python check_sdkconfig.py <sdkconfig> <defaults1> [defaults2 ...]
Later files win, as in ESP-IDF. A choice member set to y in an earlier file and replaced by a later choice member shows
as MISMATCH only if the final value differs from the last assignment. Exit 1 if anything is dropped or changed."""
import collections
import pathlib
import re
import sys

SET = re.compile(r"^CONFIG_(\w+)=(.*)$")
UNSET = re.compile(r"^# CONFIG_(\w+) is not set")


def parse(path):
    out = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = SET.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m = UNSET.match(line.strip())
        if m:
            out[m.group(1)] = "n"
    return out


def main():
    final = parse(sys.argv[1])
    wanted, origin = {}, {}
    for d in sys.argv[2:]:
        for k, v in parse(d).items():
            wanted[k] = v
            origin[k] = pathlib.Path(d).name
    ok, bad = 0, []
    for k, v in wanted.items():
        got = final.get(k)
        if got == v:
            ok += 1
        elif got is None:
            bad.append(("ABSENT (name unknown, or dependency off)", k, v, "-", origin[k]))
        else:
            bad.append(("CHANGED", k, v, got, origin[k]))
    print(f"{ok}/{len(wanted)} assignments landed")
    for kind, k, v, got, src in bad:
        print(f"  {kind}: CONFIG_{k} wanted {v} got {got}  [{src}]")

    pins = collections.defaultdict(list)
    for k, v in final.items():
        if "GPIO" in k and re.fullmatch(r"\d+", v) and "RANGE" not in k:
            pins[int(v)].append(k)
    print("GPIO values used more than once in sdkconfig:")
    for pin, names in sorted(pins.items()):
        if len(names) > 1:
            print(f"  {pin}: {', '.join(names)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
