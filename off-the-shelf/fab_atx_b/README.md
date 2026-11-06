# MF KVM v3 ATX board, rev B: fab package

**Status: NOT ORDERED. Not built, not tested on any motherboard.** Passing the checks below means the files are consistent, nothing more.

Plugs straight into the FireBeetle's P1 header with 5 pins. No wires between the two boards.

| | |
|---|---|
| Size | 11.05 x 35.40 mm, L shape with a tongue and a notch, 2 layers, 1.0 mm, 1 oz, green mask |
| Upload | `mf_kvm_atx_gerber.zip`, sha256 `f67933de962fa971` |
| Assembly | Top side only. `BOM_JLC.csv`, `CPL_JLC.csv` |
| Parts cost | about US$ 1.11 per board at JLC's single price |
| Pins, not in the BOM | 5 pieces of 0.64 mm round solid tinned copper wire (AWG 22), about 10 mm each, cut after soldering. **Not a 0.64 mm square header pin:** its diagonal is 0.905 mm against a 0.9 mm hole. A header housing does not fit either, the gap is only 1.2 mm |

**At order time:**
1. Check the rotation of U1, U2, U3 and J1 in JLC's preview. Pin 1 of each opto is on the +x side.
2. The narrow tongue is close to JLC's SMT minimum. If the order page asks for it, add edge rails.
3. Green mask only. On black or white the 0.13 mm rule applies, see `mask_report.txt`.

## Connections

| Hole | Net | FireBeetle P1 pin | y on the core (mm) | | J1 pin | Front panel |
|---|---|---|---|---|---|---|
| H1 | 3V3 | pin 2, 3V3 | 45.85 | | 1 | PWR switch + (C) |
| H2 | GND | pin 4, GND | 40.77 | | 2 | PWR switch - (E) |
| H3 | ATX_PWR | pin 6, GPIO28 | 35.69 | | 3 | RST switch + (C) |
| H4 | ATX_RST | pin 7, GPIO29 | 33.15 | | 4 | RST switch - (E) |
| H5 | ATX_LED | pin 8, GPIO30 | 30.61 | | 5 | Power LED - (K) |
| | | | | | 6 | Power LED + (A) |

P1 pins 1 (RST), 3 and 5 (NC) have no hole on this board. Silk on the bottom side names each hole. The bottom side faces the tray floor, the top side faces the core. `case/pinmap_check.py` proves the holes against the STEP.

Circuit and values are the same as `lay-board/`: 470 ohm into each drive opto, 270 ohm into the LED sense opto, 10k pull-down on ATX_LED. Footprints are the official KiCad SO-4_4.4x3.6mm_P2.54mm and JST_SH_SM06B-SRSS-TB. The JST mount tabs connect to nothing.

## Rebuild
```
sh build_atx.sh                 # generate, route, ERC, DRC
<v3cad python> fab_atx.py out ../fab_atx_b
```
