"""Turn the host test's PPM scenes into PNGs plus a labelled-by-order contact sheet. Standard library only.
   python ppm2png.py <dir with .ppm files> [integer zoom]"""
import pathlib
import struct
import sys
import zlib


def read_ppm(path):
    data = path.read_bytes()
    fields, pos = [], 0
    while len(fields) < 4:
        end = pos
        while data[end] not in b" \n":
            end += 1
        fields.append(data[pos:end])
        pos = end + 1
    assert fields[0] == b"P6"
    return int(fields[1]), int(fields[2]), data[pos:]


def write_png(path, w, h, rgb):
    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    rows = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


def main():
    folder = pathlib.Path(sys.argv[1])
    zoom = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    scenes = sorted(folder.glob("*.ppm"))
    assert scenes, "no scenes"
    w, h, _ = read_ppm(scenes[0])
    cols, gap = 3, 8
    rows = (len(scenes) + cols - 1) // cols
    sw, sh = cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap
    sheet = bytearray(b"\x60" * (sw * sh * 3))
    for i, scene in enumerate(scenes):
        _, _, px = read_ppm(scene)
        big = bytearray()
        for y in range(h):
            row = b"".join(px[(y * w + x) * 3:(y * w + x) * 3 + 3] * zoom for x in range(w))
            big += row * zoom
        write_png(scene.with_suffix(".png"), w * zoom, h * zoom, bytes(big))
        ox, oy = gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)
        for y in range(h):
            start = (oy + y) * sw * 3 + ox * 3
            sheet[start:start + w * 3] = px[y * w * 3:(y + 1) * w * 3]
    write_png(folder / "contact_sheet.png", sw, sh, bytes(sheet))
    print(f"{len(scenes)} scenes, contact sheet {sw}x{sh}")


if __name__ == "__main__":
    main()
