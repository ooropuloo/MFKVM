# v2 (P4 KVM Mini) overlay: proposed fixes

Checked file: `lay-board/firmware/p4_kvm_mini.defaults`, sha256 starts `4e9346a2f7b3a4b0`, against ESP-KVM `0893eef` and ESP-IDF v6.1. `v2/` was not edited.

**Result:** the overlay builds in both variants, and all of its options landed. No names are wrong and no values were dropped. What needs fixing is what the overlay leaves unset. Compile-only: nothing ran on hardware.

## Evidence

| Variant | Exit | Image | Free in 4 MB slot | Rev / PSRAM |
|---|---|---|---|---|
| rev3 (the overlay header's command) | 0 | 2,543,936 B (0x26d140) | 39% | `REV_MIN_FULL=300`, 250 MHz |
| pre-3.0 (same, without `_rev3`) | 0 | 2,540,416 B (0x26c380) | 39% | `REV_MIN_FULL=100`, 200 MHz |

I added `-B` and `-D SDKCONFIG` so each variant has its own build directory. The resolved option layers are the same as the header's.

All overlay options are in both `sdkconfig` files (`sdkconfig_evidence/sdkconfig.v2_*`), including `# CONFIG_KVM_ETH_ENABLE is not set`, which is the form most likely to be ignored.

Assignments that did not land, none from the overlay:

| Option | Source | Why |
|---|---|---|
| `MBEDTLS_DYNAMIC_BUFFER`, `MBEDTLS_POLY1305_C` | upstream `sdkconfig.defaults` | Not in the final config. Same in every build here, including the FireBeetle baseline |
| `ESPTOOLPY_FLASHSIZE_32MB` | upstream `sdkconfig.defaults` | Replaced by 16MB, as intended |
| `ESP32P4_REV_MIN_100`, `SPIRAM_SPEED_200M` | upstream `sdkconfig.defaults` | Replaced by the rev3 overlay, rev3 only, as intended |

## Flash and PSRAM

**They match.** Waveshare's product page gives ESP32-P4-Module-U as "16MB Nor Flash" and "32MB PSRAM in the chip's package". The build has `CONFIG_ESPTOOLPY_FLASHSIZE="16MB"`, `partitions_16mb.csv` and `CONFIG_SPIRAM_MODE_HEX=y`.

The PSRAM size is not set in the config. I did not confirm how the firmware detects it, so that remains a runtime check.

## Proposed fixes, most important first

### 1. The LCD and ATX stay off at first boot

`CONFIG_KVM_ENABLE_DISPLAY=y` only compiles the feature in. At runtime `disp_enable` and `atx_enable` default to 0, and `disp_type` defaults to 0, which is SSD1306 and not the round panel. The overlay comment "Round GC9A01 LCD on J6" therefore does not make the panel light up. The panel cannot show the hotspot join QR until someone sets it from the web console.

Upstream has no Kconfig option for these. Two ways to fix it:

- Build v2 with `patches/0001` too and add:
  ```
  CONFIG_KVM_DISP_ENABLE_DEFAULT=1
  CONFIG_KVM_DISP_TYPE_DEFAULT=2
  ```
  This is the recommended one. The default panel choice stays GC9A01. The patch does not cover `atx_enable`.
- Keep upstream and document that the first setup is done from the console over the hotspot, with no QR on the panel.

### 2. The console is not primary on J5, unlike the README

`v2/README.md:48` says J5 is the flash and console port (USB-Serial-JTAG). The overlay inherits the DEV-KIT's UART console, because the DEV-KIT has a CH343:

```
CONFIG_ESP_CONSOLE_UART_DEFAULT=y
CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y
```

J5 is only the secondary console, and the primary is UART0 on TP pads. To match the README, as `firebeetle2_p4.defaults` does:

```
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y
```

This also stops `board_reserved.c` listing GPIO 37/38 as "Console UART".

### 3. The update URL points at the DEV-KIT's official image

`CONFIG_KVM_UPDATE_URL` is `.../p4-module-devkit-rev3/manifest.json` (or `p4-module-devkit` on pre-3.0). Taking an update from the console would install the DEV-KIT build. That build has Ethernet enabled, leaves the capture chip's reset unassigned, and drops the mini's pin defaults. The overlay's own comment says Ethernet left on means no console at first boot.

Point it at your own manifest. I did not check what an empty value does. Until then, do not use the console's update on these units.

### 4. The console names the wrong board

`CONFIG_KVM_BOARD_WAVESHARE_MODULE_DEVKIT=y` stays set, so the console shows the DEV-KIT's name and its 2x20 header in the Pins tab, which the mini does not have. This is cosmetic. A real fix needs a new board entry in `board_header.c` and Kconfig, which is an upstream code change.

### 5. Choose the variant and correct the comment

- `boards/moduledevkit_p4.defaults` says Waveshare's shop has listed the module as NRW32X (rev 3.x) since 2026-09. I did not verify this; Waveshare's product page does not state a revision. **Read the chip revision with esptool on arrival before choosing an image.** Per the upstream docs the two families are mutually exclusive.
- Change the overlay's line 3, "NOT BUILT, NOT TESTED", to "Compile checked on ESP-KVM 0893eef, not run on hardware".
