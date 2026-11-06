# MF KVM v3 and v2 firmware: build record

> **In this repo:** `logs/` holds only the `dependencies.lock` copies. Build logs, build directories, images and the `espkvm` clone are not committed; where this record mentions them, they are the record of the original build. `v2` means `lay-board/` and `v3` means `off-the-shelf/`. Paths under `D:/tools` are where this build was made, not requirements: see `MFKVM_IDF_PATH`, `MFKVM_IDF_TOOLS_PATH`, `MFKVM_PYTHON_DIR` in `off-the-shelf/firmware/scripts/idf_env.ps1`.

2026-11-06. **Compile-only. Nothing was flashed or run on hardware.** A successful compile shows the options, code and sizes fit together. It does not show that any panel, pin, capture, USB, Wi-Fi or SD function works.

## Result

| Phase | Build dir | Exit | `espkvm.bin` | Free in 4 MB slot | sha256 (first 16) |
|---|---|---|---|---|---|
| A: FireBeetle baseline, upstream | `build.firebeetle` | 0 | 2,535,472 (0x26b030) | 40% | `6bc840f9425dd9fe` |
| B: v3 overlay, upstream | `build.v3` | 0 | 2,535,472 (0x26b030) | 40% | `c8961f2658a95ea4` |
| C: v3 with ST7789 | `build.v3_st7789` | 0 | 2,533,472 | 40% | `e7d530a6b04cd830` |
| C: v3 with GC9A01 | `build.v3_gc9a01` | 0 | 2,535,472 | 40% | `7d52988fdb15e417` |
| C: patch, FireBeetle only, round-path check | `build.fb_patched` | 0 | 2,535,536 | 40% | `f2d4d5e9b0a46eec` |
| D: v2 rev3, upstream | `build.v2_rev3` | 0 | 2,543,936 (0x26d140) | 39% | `39816cb683157d82` |
| D: v2 pre-3.0, upstream | `build.v2_pre3` | 0 | 2,540,416 (0x26c380) | 39% | `d91b6c9c9530273b` |
| E: v3 with ST7789, ATX fixes | `build.v3r2_st7789` | 0 | 2,534,112 (0x26aae0) | 40% | `16da101a47ea0321` |
| E: v3 with GC9A01, ATX fixes | `build.v3r2_gc9a01` | 0 | 2,536,112 (0x26b2b0) | 40% | `55e55d1357f0a02f` |

- Build directories are under `espkvm/`, about 390 MB each. Logs and exit codes are in `logs/build_<name>.log` and `.exit`. Final configs are in `sdkconfig_evidence/`.
- The app slot is 0x400000 in `partitions_16mb.csv`. The bootloader is 0x5b80, 5% free.
- A and B have the same size but different hashes, because only pin values changed.
- The three v3 rows were rebuilt on 2026-11-06 after the ATX pins moved from 49/50/52 to 28/29/30, because the ATX board now plugs straight into header P1. `v3_st7789` and `v3_gc9a01` were built from the committed branch and rebuilt clean with the empty update URL (0 occurrences of the official URL in either image). `v3` was built from `0893eef` before the URL change, so its image and `sdkconfig_evidence/sdkconfig.v3` still hold the official URL.
- Phase E is the current v3 pair: `patches/0001` and `patches/0002`, commit `5b4262e`. The patch in this repo differs from that commit in two test fixture strings only (the Wi-Fi name and IP shown by the layout test), so applying it gives another commit hash, and `render/contact_sheet.png` was re-rendered from it. Full hashes: ST7789 `16da101a47ea0321486dee1f9cf6ab0abba4002c4741eb142c841dbecb883b57`, GC9A01 `55e55d1357f0a02fe21c2f6594eda436f4563fa71b01be3f1dc2ced482600584`. The official manifest address appears 0 times in both. `check_sdkconfig.py` reports 80 of 83 assignments landed in each and exits 1, for the same three upstream items listed below.
- Phases A to D embed the version `v.0.77.0-dirty`, because the build rewrites `dependencies.lock` (see Limits). Phase E embeds `v.0.77.0-2-g5b4262e`. Hashes are not reproducible builds, so use them only to identify these files.

The first B attempt failed with exit 2 (`ccache: error: Filename too long`). That was my own broken `CCACHE_DIR` in the build script, not the overlay. I fixed it and rebuilt from clean.

## Versions

| Item | Value |
|---|---|
| ESP-KVM | `0893eef16c1cb16ff24cc4607f4d75f002ffa129` (tag `v.0.77.0`), full clone with submodules |
| Submodules | `third_party/microlink` `d40909c`, `web` `eca5399` |
| Patches | branch `mf-v3-st7789`, commit `5b4262e`; `patches/0001-*.patch` then `patches/0002-*.patch` apply cleanly on `0893eef` |
| ESP-IDF | v6.1, `fff9895c82d744c7237be8847347bdd1b07c6643`, at `D:/tools/esp-idf-v6.1` |
| Tools | `D:/tools/espressif` via `IDF_TOOLS_PATH`; riscv32-esp-elf esp-15.2.0_20251204 |
| Python | 3.11.13. IDF 6.1 needs 3.10 or newer and the machine default is 3.9, so the build script sets `PATH` for its own process only |

No global PATH, Node or system setting changed. The machine-wide `IDF_TOOLS_PATH` pointed at another project; `scripts/idf_env.ps1` overrides it in-process.

## Reproduce

```powershell
# Once: install
git clone -b v6.1 --depth 1 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git D:\tools\esp-idf-v6.1
$env:IDF_TOOLS_PATH='D:\tools\espressif'; $env:PATH="$env:APPDATA\uv\python\cpython-3.11.13-windows-x86_64-none;$env:PATH"
D:\tools\esp-idf-v6.1\install.ps1 esp32p4

# Once: source. Full clone, as the source tarball can miss the wireguard_lwip path (issue #63)
git clone --recurse-submodules https://github.com/espkvm/espkvm <repo>\off-the-shelf\firmware\espkvm
```

Use `scripts/idf_build.ps1 -Name <name> -Defaults "<list>"`. It runs `idf.py -B build.<name> -D SDKCONFIG=build.<name>/sdkconfig -D SDKCONFIG_DEFAULTS=<list> build`.

| Name | Tree | `-Defaults` |
|---|---|---|
| `firebeetle` | `0893eef` | `sdkconfig.defaults;boards/firebeetle2_p4.defaults` |
| `v3` | `0893eef` | the above`;../boards/mf_kvm_v3.defaults` |
| `v3_st7789` | `mf-v3-st7789` | the above`;../boards/mf_kvm_v3_st7789.defaults` |
| `v3_gc9a01` | `mf-v3-st7789` | `v3` list`;../boards/mf_kvm_v3_gc9a01.defaults` |
| `fb_patched` | `c5a0ef7` | same as `firebeetle` |
| `v3r2_st7789` | `mf-v3-st7789` | same as `v3_st7789` |
| `v3r2_gc9a01` | `mf-v3-st7789` | same as `v3_gc9a01` |
| `v2_rev3` | `0893eef` | `sdkconfig.defaults;boards/moduledevkit_p4.defaults;boards/moduledevkit_p4_rev3.defaults;boards/p4_kvm_mini.defaults` |
| `v2_pre3` | `0893eef` | same without `_rev3` |

For the v2 builds, first copy `lay-board/firmware/p4_kvm_mini.defaults` to `espkvm/boards/`. I removed that copy afterwards.

Other checks:

```sh
python scripts/check_sdkconfig.py <sdkconfig> <defaults...>   # what landed, and repeated GPIOs
sh espkvm/components/kvm_display/test/run.sh <out dir>        # layout test, needs gcc on PATH
python scripts/ppm2png.py <out dir> 2                         # PNGs and contact sheet
python scripts/compare_round.py <objcopy> <objdump> <base build> <patched build>
```

## Options: what really landed

**Delete the build directory after changing a defaults file.** An existing `sdkconfig` wins over the defaults, with no warning. A rebuild with `CONFIG_KVM_UPDATE_URL=""` in an old directory exited 0 and kept the official URL; the check below caught it.

`scripts/check_sdkconfig.py` compares every assignment in the defaults with the final `sdkconfig`, because defaults files silently ignore unknown names.

**Dropped from every build, all upstream, none from our overlays:**

- `CONFIG_MBEDTLS_DYNAMIC_BUFFER=n` and `CONFIG_MBEDTLS_POLY1305_C=y` from `sdkconfig.defaults`. They are absent from the final config, so upstream's setting has no effect here. I did not investigate what that means for TLS at runtime.

**Replaced as intended (the tool reports them, but they are correct):** `ESPTOOLPY_FLASHSIZE_32MB` by 16MB. On rev3 only, `ESP32P4_REV_MIN_100` and `SPIRAM_SPEED_200M`.

The `NOTE: unknown kconfig symbol` lines for `ESP_HOSTED_*` and `EH_HOST_*` in the logs come from the first pass, before the managed component is downloaded. These options did land.

Evidence for v3 (`sdkconfig.v3_st7789`):

```
CONFIG_KVM_DISP_SCLK_GPIO=20   MOSI=21  CS=22  DC=23  RST=51   CONFIG_KVM_DISP_BL_GPIO=33
CONFIG_KVM_ATX_PWR_GPIO=28     RST=29   LED=30
CONFIG_KVM_SPI_PANEL_ST7789_170X320=y   CONFIG_KVM_DISP_ENABLE_DEFAULT=1   CONFIG_KVM_DISP_TYPE_DEFAULT=2
CONFIG_ESPTOOLPY_FLASHSIZE="16MB"       CONFIG_ESP32P4_REV_MIN_FULL=100    CONFIG_SPIRAM_SPEED=200
CONFIG_KVM_BOARD_FIREBEETLE2_P4=y       # CONFIG_KVM_ETH_ENABLE is not set
CONFIG_KVM_UPDATE_URL=""
```

**Pin conflicts for v3: none.** None of the v3 pins is in `board_reserved.c` or repeated in `sdkconfig`, and all are header IOs in `board_header.c` under `CONFIG_KVM_BOARD_FIREBEETLE2_P4`. Pin settings that are not Kconfig-driven all default to -1.

ATX on 28/29/30 takes the pins `research/firebeetle_firmware.md` suggested for future I2S audio. Audio is off by default, so nothing conflicts today, but enabling it needs other pins.

v2 evidence and proposed fixes: `v2_overlay_fixes.md`.

## Phase C: what changed

- **Selection:** `CONFIG_KVM_SPI_PANEL` is a Kconfig choice, GC9A01 by default. `disp_type` index 2 means "the SPI colour panel" in either build, so the NVS index, the console and the pin settings need no change. The console's `SettingsPanel.vue` hard-codes index 2 for the SPI pins and works unchanged.
- **Driver:** `drivers/st7789/st7789.c` handles panel I/O through IDF's `esp_lcd_new_panel_st7789`. `st7789_ui.c` is the layout, pixels only.
- **`kvm_panel_t`:** `w`/`h` widened to `uint16_t`, because 320 does not fit `uint8_t`.
- **New Kconfig:** `KVM_DISP_ENABLE_DEFAULT`, `KVM_DISP_TYPE_DEFAULT`, `KVM_DISP_BL_GPIO`, all defaulting to the old values.
- **Panel values:** gap X 0, Y 35, inversion on, RGB, from `research/c790_lcd.md` (vendor example code). The result is MADCTL 0x60, confirmed against esp_lcd's source. The vendor writes 0x70; the extra ML bit changes only the refresh direction.

**Round path check.** `build.fb_patched` against the baseline, with debug info removed, comparing code and data:

| Object | Result |
|---|---|
| `gc9a01.c.obj`, `kvm_display.c.obj`, `kvm_settings_table.c.obj` | **Identical** |
| `kvm_panels.c.obj` | Differs: the table is wider, with the same panel values in the part I inspected |
| `mono_oled.c.obj` | Differs: reads `w`/`h` as 16-bit, and branch offsets shift. This is the I2C OLED path, not the round one |

The `sdkconfig` diff is only the four new options. So the round panel's code is unchanged. The whole image is not byte-identical: it is 64 bytes larger. I reasoned that `mono_oled` behaves the same, but did not test it.

**Layout render.** `render/contact_sheet.png` and 14 PNGs. Each scene passes an automated check that no ink enters the strip inside the frame. I also looked at the sheet.

- **Known limit:** on the hotspot screen, a 32-character SSID or a long passphrase is cut off at the column. The QR still carries the full text, but the text on screen cannot be typed from in that case. Rendering uses the real QR encoder, but no phone scanned it.
- This shows pixels on a host only. It says nothing about the panel's offset, colour order, rotation or SPI timing.

## Phase E: ATX fixes

`patches/0002` is the same change as v2's: a press in flight no longer survives `esp_restart` or a panic, a reset with no warning is released right after `kvm_log_init` in `app_main`, a released button output no longer keeps a pull-up, and the idle level is set before the output is enabled. Reasons, evidence, what stays exposed and the measurement plan are in `lay-board/firmware/BUILD_v2.md`, under "ATX on by default". `atx_enable` is unchanged here: it defaults to 0 and needs the console.

On v3's GPIO 28 and 29, function 0 is plain GPIO, not JTAG (`io_mux_reg.h:324,331`), so the MTDO question from v2 does not apply. Only a scope can show what these pins do across a reset. `kvm_atx` has no test harness in the repo, so this was not run in any test.

## Limits and what remains unverified

**Not verified, needs hardware:**

- ST7789: gap, mirror, colour order, inversion, 40 MHz SPI, whether the QR scans, the backlight on GPIO 33.
- Whether upstream's GC9A01 driver works on v3's pins, and all ATX wiring, including the state of GPIO 28 and 29 from chip reset to `kvm_atx_apply` and across a reset.
- Capture, USB, Wi-Fi and SD on v3 and v2. See `research/firebeetle_firmware.md` for the C6 firmware risk and for P4 revision v1.0 being untested.
- v2 RESETN on GPIO 23, LCD and ATX pins, and which P4 revision the modules carry.

**Tests:**

- The new layout test passes. The pin-conflict test passes.
- `test_profiles` in `kvm_config` could not run: it needs POSIX headers (`sys/wait.h`, `sys/mman.h`) and this host is Windows. So the settings-table default changes are compile-checked only.
- `run.sh` in `kvm_config` stops on MinGW because `strlcpy` is missing, so I ran the pin-conflict test directly. The rest of `tools/test.sh` was not run.

**Behaviour to know about:**

- **v3 upstream overlay:** `mf_kvm_v3.defaults` alone leaves the panel and ATX off at first boot, and cannot set the backlight. The `_st7789` and `_gc9a01` layers fix the panel and backlight.
- **ATX stays off in all variants:** `atx_enable` defaults to 0 and needs the console. The patch does not change this.
- **Official updates:** `mf_kvm_v3.defaults` sets `CONFIG_KVM_UPDATE_URL=""`, so the manifest update path is off. By code reading only: `UpdateWidget.vue:249` treats an empty URL as disabled and does not fetch or show an error, and `fw_latest_version()` returns `ESP_ERR_INVALID_ARG`, which `kvm_mqtt.c:836` treats as no answer. Not run in a browser. The console shows no "updates disabled" message: the check block is just hidden (`UpdateWidget.vue:713`), and the banner offering to turn update checks on still appears (`App.vue:1728-1733`). Changing that needs a rebuilt web bundle, so it is left as is.
- **Still able to install the official image:** turning on `fw_fetch` (off by default) lets the console list GitHub releases and install one (`device.ts:1193`, `fw_install.c:39`), and a `.bin` can be uploaded by hand. Closing the `fw_fetch` path needs a tracked code change. A value already stored in NVS also overrides the new default.
- **Help text:** in an ST7789 build, the pin settings' help still says "GC9A01". Only the Panel choice name changes.

**Build inputs:**

- `dependencies.lock` is rewritten on each build, because the committed lock lacks the Wi-Fi components (`esp_hosted` and others) these boards pull in. Component versions could therefore change on a later rebuild. Copies from this run: `logs/dependencies.lock.firebeetle` and `logs/dependencies.lock.v2`. The tracked file is restored and is not part of the patch.
- The web console is the committed `components/kvm_web/assets/index.html.gz`. I did not run the README's `npm ci && npm run build`, so the bundle was not rebuilt from the `web` submodule.
