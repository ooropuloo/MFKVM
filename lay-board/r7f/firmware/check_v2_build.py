# -*- coding: utf-8 -*-
"""Checks one finished v2 build: every overlay option in the final sdkconfig, official update addresses in the image, size and hash.

usage: python check_v2_build.py <build dir> <overlay defaults>
exit 0 when every option landed and the image holds no official manifest address, 1 otherwise
"""
import hashlib
import os
import re
import sys

build, overlay = sys.argv[1:3]
cfg = open(f'{build}/sdkconfig', encoding='utf-8', errors='replace').read().splitlines()
final = {}
for line in cfg:
    m = re.match(r'CONFIG_(\w+)=(.*)$', line)
    if m:
        final[m[1]] = m[2]
    m = re.match(r'# CONFIG_(\w+) is not set', line)
    if m:
        final[m[1]] = 'n'
bad = 0
for line in open(overlay, encoding='utf-8').read().splitlines():
    m = re.match(r'CONFIG_(\w+)=(.*)$', line)
    want = (m[1], m[2]) if m else None
    m = re.match(r'# CONFIG_(\w+) is not set', line)
    want = (m[1], 'n') if m else want
    if want:
        ok = final.get(want[0]) == want[1]
        bad += not ok
        print(('ok   ' if ok else 'FAIL ') + f'{want[0]}={final.get(want[0])}')
for k in ('ESP_CONSOLE_UART_DEFAULT', 'ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG', 'ESP_CONSOLE_USB_SERIAL_JTAG', 'ESP32P4_REV_MIN_FULL', 'SPIRAM_SPEED', 'KVM_BOARD_WAVESHARE_MODULE_DEVKIT', 'ESPTOOLPY_FLASHSIZE'):
    print(f'info {k}={final.get(k)}')
img = open(f'{build}/espkvm.bin', 'rb').read()
for pat in (b'manifest.json', b'fw.espkvm.io', b'p4-module-devkit', b'espkvm.github.io'):
    print(f'image occurrences of {pat.decode()}: {img.count(pat)}')
n = img.count(b'fw.espkvm.io/firmware')
bad += n != 0
print(f'official manifest address in image: {n}')
print('image', os.path.getsize(f'{build}/espkvm.bin'), 'bytes', hex(os.path.getsize(f'{build}/espkvm.bin')), 'sha256', hashlib.sha256(img).hexdigest())
print('RESULT', 'PASS' if not bad else f'{bad} FAILED')
sys.exit(1 if bad else 0)
