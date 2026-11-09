# CPL rotation and pin 1 of polarized parts (tools/cpl_pin1.py)

CPL rotation and pin 1 of every polarized part (r7e, REVIEW_r7d M1).

For each polarized part on the CPL (ICs, connectors, the crystal oscillator, polarized capacitors; plain R/C/L/FB/TP are not polarized):
  - pin 1 (A1 for the BGA, A1B12 for USB-C) from design.json, as an offset from the part centre in the JLC top preview (x right, y down,
    = KiCad screen) and in the JLC bottom preview (x mirrored);
  - pin 1 in the footprint's own frame (rotation and bottom mirror undone; the convention is checked: every part of one footprint gives the
    same vector whatever its angle and side);
  - the JLC angle offset (CPL = KiCad + offset) from data/jlc_offsets.json. Only parts a person verified in JLC's preview have one; for every
    other part the offset is UNKNOWN (not 0) and the row says CHECK IN PREVIEW.
FAIL when: a verified part's CPL angle is not KiCad + offset; its pin 1 (footprint frame) is not where it was when verified (footprint
changed); a polarized part is missing from the CPL; a polarized capacitor has pin 1 on GND or pin 2 off GND, or its + pin does not reach a
positive supply through at most one resistor (C69: + on 5V_DAMP, R68 to 5V, REVIEW_r7d M1).

| Ref | LCSC | Land | Side | KiCad deg | CPL deg | JLC offset | Pin 1 | Net | Pin 1 in JLC top view (mm) | Pin 1 in JLC bottom view | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C69 | C347552 | CP_7343 | Bottom | 0 | 0 | UNKNOWN | 1 | 5V_DAMP | right (+3.10, +0.00) | left (-3.10, +0.00) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| D1 | C48260 | X1SON-2_0.6x1 | Top | 0 | 0 | UNKNOWN | 1 | HDMI_CEC | left (-0.35, +0.00) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J2 | C720616 | HDMI-001S | Bottom | 180 | 180 | UNKNOWN | 1 | D2_P | down-right (+4.50, +3.36) | down-left (-4.50, +3.36) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J3 | C41427493 | USB-C_HX_16P | Top | 180 | 180 | UNKNOWN | A1B12 | GND | down-right (+3.20, +2.55) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J4 | C160405 | JST_SM06B | Bottom | 0 | 0 | UNKNOWN | 1 | PWR_C | up-right (+2.50, -2.00) | up-left (-2.50, -2.00) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J5 | C41427493 | USB-C_HX_16P | Top | 90 | 90 | UNKNOWN | A1B12 | GND | down-left (-2.55, +3.20) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J6 | C160407 | JST_SM08B | Top | 90 | 90 | UNKNOWN | 1 | 3V3 | down-left (-2.00, +3.50) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| J7 | C585350 | microSD_Molex_104031-0811 | Bottom | 270 | 90 | 180 | 1 | SD_D2_C | up-left (-5.45, -3.10) | up-right (+5.45, -3.10) | OK (offset verified in JLC preview 2026-11-07) |
| J8 | C88373 | U.FL-R-SMT-1 | Bottom | 0 | 0 | UNKNOWN | 1 | LNA_OUT | down (+0.00, +1.52) | down (-0.00, +1.52) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| Q1 | C15127 | SOT-23 | Bottom | 0 | 270 | 270 | 1 | SD_PWR_N | down-right (+0.95, +0.94) | down-left (-0.95, +0.94) | OK (offset verified in JLC preview 2026-11-07) |
| U10 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270 | 270 | 1 | PWR_LED | up-right (+3.17, -0.63) | up-left (-3.17, -0.63) | OK (offset verified in JLC preview 2026-11-07) |
| U11 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270 | 270 | 1 | RST_LED | up-right (+3.17, -0.63) | up-left (-3.17, -0.63) | OK (offset verified in JLC preview 2026-11-07) |
| U12 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270 | 270 | 1 | LED_IN | up-right (+3.18, -0.64) | up-left (-3.18, -0.64) | OK (offset verified in JLC preview 2026-11-07) |
| U14 | C138714 | USON-10 | Top | 0 | 0 | UNKNOWN | 1 | USB2_DP | down-left (-1.00, +0.41) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U15 | C78988 | SOT-23-5 | Top | 90 | 0 | UNKNOWN | 1 | 3V3 | down-right (+1.14, +0.95) | - | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U16 | C2155674 | WSON-8_2x2_EP | Bottom | 90 | 90 | UNKNOWN | 1 | EF_DVDT | down-right (+0.75, +0.95) | down-left (-0.75, +0.95) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U2 | C78988 | SOT-23-5 | Bottom | 0 | 270 | 270 | 1 | 5V | down-right (+0.95, +1.14) | down-left (-0.95, +1.14) | OK (offset verified in JLC preview 2026-11-07) |
| U3 | C138714 | USON-10 | Bottom | 90 | 90 | UNKNOWN | 1 | USB_DN | down-left (-0.41, +1.00) | down-right (+0.41, +1.00) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U4 | C882825 | SOT-23-5 | Bottom | 0 | 270 | 270 | 1 | 3V3 | down-right (+0.95, +1.14) | down-left (-0.95, +1.14) | OK (offset verified in JLC preview 2026-11-07) |
| U6 | C201698 | MSOP-8 | Bottom | 90 | 90 | UNKNOWN | 1 | 3V3 | down-left (-2.11, +0.98) | down-right (+2.11, +0.98) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U7 | C3008606 | BGA-64_6x6 | Bottom | 180 | 180 | UNKNOWN | A1 | TC_REXT | down-left (-2.27, +2.27) | down-right (+2.27, +2.27) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U8 | C138714 | USON-10 | Bottom | 180 | 180 | UNKNOWN | 1 | D1_N | up-left (-1.00, -0.41) | up-right (+1.00, -0.41) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| U9 | C138714 | USON-10 | Bottom | 180 | 180 | UNKNOWN | 1 | CK_N | up-left (-1.00, -0.41) | up-right (+1.00, -0.41) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| Y1 | C725995 | OSC3225 | Bottom | 0 | 0 | UNKNOWN | 1 | OSC_VDD | down-right (+1.05, +0.83) | down-left (-1.05, +0.83) | CHECK IN PREVIEW: JLC offset not verified, pin 1 must appear where the two view columns say |
| C69 | C347552 | CP_7343 |  |  |  |  | +/- | + 5V_DAMP, - GND |  |  | polarity OK |

RESULT PASS: 24 polarized parts, 7 with a verified JLC offset, 17 UNKNOWN (check in JLC preview)
