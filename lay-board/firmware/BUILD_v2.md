# MF KVM v2 firmware: build record

> **In this repo:** `logs/` holds only the `dependencies.lock` copies. Build logs, build directories, images and the `espkvm` clone are not committed; where this record mentions them, they are the record of the original build. `v2` means `lay-board/` and `v3` means `off-the-shelf/`. Paths under `D:/tools` are where this build was made, not requirements: see `MFKVM_IDF_PATH`, `MFKVM_IDF_TOOLS_PATH`, `MFKVM_PYTHON_DIR` in `off-the-shelf/firmware/scripts/idf_env.ps1`.

2026-11-06. **Compile-only. Nothing was flashed or run on hardware.** A successful compile shows the options, code and sizes fit together. It does not show that the panel, QR, ATX, capture, USB, Wi-Fi or SD work on this board. What follows about first boot comes from reading the source.

## Result

Both built from clean, in new build directories.

| Variant | Build dir (under `off-the-shelf/firmware/espkvm/`) | Exit | `espkvm.bin` | Free in 4 MB slot | Bootloader | sha256 |
|---|---|---|---|---|---|---|
| rev 3.x | `build.v2r6_rev3` | 0 | 2,544,496 (0x26d370) | 39% | 0x5e10, 2% free | `95083ff2a3cc3351387faba312df64ad10fbdd8cf5ca0cb2d730fc6c1bba1341` |
| pre-3.0 | `build.v2r6_pre3` | 0 | 2,540,944 (0x26c590) | 39% | 0x5b00, 5% free | `542fcf6357d83b02c45c449f2eee98a3d167351c06c2659f3ce668659d45851f` |

These include the ATX reset fixes in `patches/0002`. The earlier `v2r5` images, without those fixes, remain in their build directories and logs: rev 3.x `0ddd3701...`, pre-3.0 `c7127782...`.

- Logs and exit codes: `logs/build_v2r6_*.log`, `.exit`. Final configs: `sdkconfig_evidence/`. Lock file from the run: `logs/dependencies.lock.v2r6`.
- All 20 overlay options are in both final `sdkconfig` files, including `# CONFIG_KVM_ETH_ENABLE is not set` and the three defaults from the patch. `check_v2_build.py` checks this and exits 1 if one is missing.
- `fw.espkvm.io` appears 0 times in both images. The strings that remain are not an address to update from:
  - `manifest.json`: the help text of the `upd_url` setting.
  - `p4-module-devkit` (`-rev3` on rev 3.x): the board id from `board_header.c`.
  - `https://espkvm.github.io/espkvm/`: the old prefix `migrate_update_url` looks for.
- The web console inside the image is gzip, so a search of the image cannot see into it. Unpacked, it names `fw.espkvm.io` once, in a set of hosts that the once-a-day device count applies to, and has no manifest address. It also holds the GitHub releases address that `fw_fetch` uses.
- Images embed `v.0.77.0-2-gbc371a7`. Hashes identify these files; these are not reproducible builds.

Not overlay problems, same as every build on this tree (see `off-the-shelf/firmware/BUILD.md`): `CONFIG_MBEDTLS_DYNAMIC_BUFFER` and `CONFIG_MBEDTLS_POLY1305_C` from upstream's `sdkconfig.defaults` are absent from the final config. `ESPTOOLPY_FLASHSIZE_32MB` is replaced by 16MB on purpose, and on rev 3.x so are `ESP32P4_REV_MIN_100` and `SPIRAM_SPEED_200M`.

## Versions

| Item | Value |
|---|---|
| ESP-KVM | `0893eef` (tag `v.0.77.0`) plus `patches/0001` and `patches/0002`, commit `bc371a7` on branch `mf-v2-defaults` of the clone at `off-the-shelf/firmware/espkvm` |
| Submodules | `third_party/microlink` `d40909c`, `web` `eca5399` |
| ESP-IDF | v6.1, `D:/tools/esp-idf-v6.1`, tools in `D:/tools/espressif` |

## Reproduce

```powershell
git -C <espkvm> checkout -b mf-v2-defaults 0893eef
git -C <espkvm> am <mini>\firmware\patches\0001-*.patch <mini>\firmware\patches\0002-*.patch
copy <mini>\firmware\p4_kvm_mini.defaults <espkvm>\boards\
pwsh -File <mini>\firmware\build_v2.ps1 -Name v2r6_rev3 -Rev3
pwsh -File <mini>\firmware\build_v2.ps1 -Name v2r6_pre3
python <mini>\firmware\check_v2_build.py <espkvm>\build.v2r6_rev3 <mini>\firmware\p4_kvm_mini.defaults
```

`build_v2.ps1` runs `idf.py -B build.<name> -D SDKCONFIG=build.<name>/sdkconfig -D SDKCONFIG_DEFAULTS=<list> build`. The list is `sdkconfig.defaults;boards/moduledevkit_p4.defaults;[boards/moduledevkit_p4_rev3.defaults;]boards/p4_kvm_mini.defaults`. It refuses a build directory that already exists, because **an existing `sdkconfig` beats the defaults with no warning**. It uses the private IDF environment from `off-the-shelf/firmware/scripts/idf_env.ps1`, in its own process only.

Afterwards the copy in `boards/` was removed, `dependencies.lock` restored and the checkout returned to `mf-v3-st7789`, clean. The v3 outputs and overlays were not touched.

## Why a patch

Upstream hard-codes `.def = 0` for `disp_enable`, `disp_type` and `atx_enable`, so no defaults file can set them. `patches/0001` adds `KVM_DISP_ENABLE_DEFAULT`, `KVM_DISP_TYPE_DEFAULT` and `KVM_ATX_ENABLE_DEFAULT`, all defaulting to 0, so other boards are unchanged. The patch applies cleanly on `0893eef`. The first two have the same names as in v3's patch. The v3 patch was not used, because it adds the ST7789 driver, which v2 does not need.

**Without the patch, those options are ignored silently** and the panel and ATX stay off. Check the final `sdkconfig`, not the exit code.

## What a user sees at first boot

By reading the source, with no settings in NVS:

- **Network:** Ethernet is off in the build, so `net_mode` defaults to 2, the device's own hotspot, `ESP-KVM-xxxx`. A password is made up on first use, unless `ap_open` is turned on.
- **Panel:** `disp_enable` 1 and `disp_type` 2 (`GC9A01 240x240`). In hotspot mode the panel's face is the join QR (`gc9a01.c:385`). J6 pin 8 (BL) is tied to 3V3, so `disp_bl` stays -1. SPI cannot detect a panel, so with J6 empty the firmware still drives GPIO 9 to 13 into nothing, and the status reports the display as attached.
- **Console:** `http://192.168.4.1/`, sign in as admin / admin, which asks for a new password first (upstream README).
- **ATX:** on, on GPIO 4, 5 and LED sense on 2.

**ATX on by default: what protects the target, and what does not.** This is from reading the source and the linked image. Nothing here has been measured, and only a scope can show what a pin does across a reset.

What the design relies on:

- `atx_active_high` defaults to 1, which matches R52 and R53 driving the optocoupler LEDs from the GPIO. A press happens only on a command.
- LED sense: U12's emitter is on `ATX_LED` with R55 to GND, so it reads high when the target's LED is on. That matches `atx_led_ah` default 1.
- **What changes for a user:** once J4 is wired to a motherboard, the console can press its power and reset buttons from first boot, with no setting to turn on first. The console's own sign-in is what protects this, so change the password before leaving it on a network.

Fixed by `patches/0002`, in `kvm_atx.c`:

| Problem | Evidence | Fix |
|---|---|---|
| A press lasts through a reset. `esp_restart` and a panic reset the CPUs and a list of peripherals, not the GPIO block, so the pin stays at its press level through the ROM and bootloader | `esp_system.c:40`, `system_internal.c` `esp_system_reset_modules_on_exit` and `esp_restart_noos_inner`. Callers include `fw_install.c:387` (OTA) and `http_server.c:1098` (console reboot) | The press in flight is written to RTC no-init memory before the pin moves. A shutdown handler ends it on `esp_restart`, a wrap of `esp_panic_handler` ends it in a panic, and `kvm_atx_release_stuck_press()` ends it right after `kvm_log_init` in `app_main` for a reset with no warning |
| A released button output keeps a pull-up, a steady current into the optocoupler LED | `gpio.c:501-502` in `gpio_reset_pin`. The source shows the pull-up is enabled. The figures, about 45 kΩ and 50 µA, are not from the source | `release_button` disables the pull-up and enables the pull-down on an active-high output. An active-low output keeps the pull-up, which is its idle level. LED and HDD sense pins still use `release_pin` and `configure_led`, so their behaviour is unchanged |
| The output is enabled before the idle level is set | `kvm_atx.c` `configure_output` set the level after `gpio_config`. `gpio_config` at `gpio.c:428` reaches `gpio_output_enable`, which enables the output and then selects the GPIO function (`gpio.c:230-231`) | Set the level, then `gpio_output_disable` (selects the GPIO function with the output off), then `gpio_config`. `gpio_set_level` writes the output latch, whatever function the pad has, so it does take effect first |

On that third row, two separate things:

- **Certain from the source:** on an active-low output the old order pressed the button for the few instructions until the next line. After a warm restart it showed whatever the latch held.
- **Not established:** that MTDO reached GPIO 5 during the old order. Function 0 of GPIO 5 is MTDO (`io_mux_reg.h:214`), and `gpio_config` does touch the pad in that order. But the comment at `gpio.c:231` says that under a peripheral function the output enable is the peripheral's, so the GPIO enable may have had no effect. The new order removes the question. Function 0 of v3's GPIO 28 and 29 is plain GPIO, so this does not apply there.

**Why not write the configured pins at every boot:** with `atx_enable` off they may be wired to something else, and at that moment nothing has checked them. The marker holds the pin that was really pressed and its polarity, so a boot with no press in flight touches no pin. A power-up's random memory would have to match 24 bits, and even then the pin must be a valid output and not in `board_reserved.c`.

**Press and hold are unchanged:** press, `vTaskDelay` for `atx_short_ms` or `atx_long_ms`, idle, 150 ms settle, all under `s_op_mtx`. The hooks take no lock and only read the marker and write the pin, so they cannot deadlock on `s_op_mtx` or wait for a hold. In all four linked images, `panic_handler` calls `__wrap_esp_panic_handler`, `end_press_now` is in IRAM and `s_press` is in LP RAM. The handler table has 5 slots. If it is full, a warning is logged and the boot release still works. **New behaviour: a reset cuts a press short,** so a click during a reboot may not register and a hard-off hold may not finish.

**Still exposed:**

- **ROM and bootloader window, cold or warm, with no press in flight:** the pad state from chip reset until `kvm_atx_apply` runs is not set by this firmware, and GPIO 4 and 5 are JTAG pins at function 0. With `atx_enable` off, firmware never touches the pins at all. Only a scope can settle this.
- **A reset with no warning during a press:** RTC watchdog, a CPU lockup, or the brown-out handler, which resets without running shutdown handlers (`brownout.c:44`). If the pin survives such a reset, it stays pressed through the ROM, bootloader and app start-up, until the boot release. If the image never reaches `app_main`, it stays pressed until something resets the pads.
- **A panic:** the press ends when the panic handler starts, so the core dump no longer extends it. The microseconds before that, and a fault inside the handler itself, are not covered.
- **A very narrow race:** a press that starts on the other core after the shutdown handler ran and before that core is stalled, microseconds later. The boot release ends it.
- **The LED sense pin** keeps `gpio_reset_pin`'s pull-up after a release, as upstream does. It no longer applies to buttons.

**Measurement plan.** Scope on the optocoupler collector and emitter (C-E on J4), with 10 kΩ and then 20 kΩ to 3.3 V in place of the motherboard's pull-up, single shot at 1 MHz or faster, triggered on a falling edge. Pass means no pulse at all in the "idle" cases, and a press that ends promptly in the others. Use a pre-3.0 chip on v2, and repeat on v3's GPIO 28 and 29.

| Case | Do | Expect |
|---|---|---|
| Cold power-up | Repeat at least 20 times, ATX on | No pulse |
| EN reset | Pull TP EN low, no press | No pulse |
| Console reboot | Reboot from the console, no press | No pulse |
| OTA | Install an image by manual upload | No pulse |
| First apply on GPIO 5 | Trigger on any edge across boot, ATX on, compare with GPIO 4 | No pulse. Look hardest here for MTDO activity |
| `esp_restart` during a press | Reboot during `atx_long_ms` | Pulse ends at the restart, far short of the full hold |
| Panic during a press | Debug build that aborts during a hold | Pulse ends before the panic output finishes |
| Watchdog during a press | Debug build that resets with no warning | Whether the pin survives, and the time to the boot release |
| LED current, ATX off | 1 µA or better meter on the anode side, `atx_enable` 0, both after a cold boot and after turning ATX off in the console | No steady current. Cold boot shows the pad's own default |

A stored value in NVS wins over all of these defaults. A board that already has settings keeps them after a reflash, and a settings reset brings the defaults back.

## Which USB does what

| Port | Peripheral | Does | Does not |
|---|---|---|---|
| **J5** | USB-Serial-JTAG, GPIO 24/25. 5 V input | Power. Flashing through the ROM download mode. **Secondary console: application log output only** | No REPL or input, and non-blocking (ESP-IDF Kconfig help). The bootloader log does not go here (`bootloader_console.c` handles USB only when it is the primary console) |
| **J3** | USB OTG-HS, module pads 48/49 | The target's keyboard, mouse and virtual media | Does not power the board. Not for flashing or console |
| **TP UART0** | UART0, GPIO 37/38, 115200 | **Primary console**: bootloader log, application log, input | |

From `CONFIG_ESP_CONSOLE_UART_DEFAULT=y` and `CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y` in both final configs. These are inherited from the DEV-KIT, which has a CH343 on UART0. I corrected the README and did not change this, so GPIO 37/38 stay listed as reserved for the console. J5's part value in the schematic and BOM still reads "USB-C 5V, flash and console", left as is so that no part data changes in r5.

To get J5 as the primary console, add `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` as `firebeetle2_p4.defaults` does. Not built here.

Flashing over J5 is not tested. If auto reset does not work, use TP BOOT (GPIO 35) low and TP EN.

## Update path

`CONFIG_KVM_UPDATE_URL=""`, because the official DEV-KIT manifest would install an image that drops this board's pin defaults and has Ethernet on.

By reading the source, as for v3, not run in a browser: `upd_check` defaults to off, and an empty URL also counts as disabled (`UpdateWidget.vue:249`). The console shows no "updates disabled" message.

**Still open, all three can install a wrong image:**

1. **`fw_fetch`** (off by default): once turned on, the console lists GitHub releases and installs one. Closing it needs a code change.
2. **Manual upload** of a `.bin` in the console.
3. **NVS:** a stored `upd_url` overrides the empty default.

## Other limits

- The console names the board as the DEV-KIT and draws its 2x20 header in the Pins tab. Cosmetic. A real fix needs a new board entry upstream.
- `sdkconfig.defaults` and the rev layers are upstream's. The web console is the committed `index.html.gz`, not rebuilt.
- Which P4 revision the modules carry is unknown. Read it with esptool on arrival. An image runs on one family only.
- PSRAM size is not set in the config. How the firmware detects it is a runtime check.
- `test_profiles` in `kvm_config` cannot run on this Windows host (see `off-the-shelf/firmware/BUILD.md`), so the changed setting defaults are compile-checked only.
- `kvm_atx` has no test harness in the repo, so the ATX fixes were not run in any test. They are compile-checked, read through and checked in the linked image.
