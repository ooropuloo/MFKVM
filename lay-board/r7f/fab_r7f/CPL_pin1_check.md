# CPL rotation and pin-1 check table (r7d)

r7b M2: one row per placed part: CPL angle, KiCad angle, and where pin 1 must appear in JLC's placement preview.

Pin 1 is read from the saved board (pad "1", or A1 for the BGA, or the first pad of the connectors), as an offset from the part centre in
board coordinates seen from the top (x right, y toward the back wall = down in KiCad and in JLC's top preview). For bottom-side parts the
same offset is also given as seen in JLC's bottom preview, which shows the board flipped about the vertical axis (x mirrored).
The JLC angle convention is per LCSC part (r6/r7 history: C2871228 at 0 and C78988 at 270 on the same SOT-23-5 land), so nothing here
predicts JLC's angle; the table only says what the preview must show. "verified" means checked by a person in JLC's preview (2026-11-07).

| Ref | LCSC | Land | Side | KiCad deg | CPL deg | CPL-KiCad | Pin | Pin 1 from centre, top view (mm) | Same pin in JLC bottom view | Status |
|---|---|---|---|---:|---:|---:|---|---|---|---|
| C69 | C347552 | CP_7343 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+3.10, +0.00) | left (-3.10, +0.00) | CHECK in preview; new in r7c: polarized (pin 1 = +, silk + beside it) |
| D1 | C48260 | X1SON-2_0.6x1 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.35, +0.00) |  | CHECK in preview |
| J2 | C720616 | HDMI-001S | Bottom | 180 | 180.0 | 0.0 | 1 | down-right (+4.50, +3.36) | down-left (-4.50, +3.36) | CHECK in preview |
| J3 | C41427493 | USB-C_HX_16P | Top | 180 | 180.0 | 0.0 | A1B12 | down-right (+3.20, +2.55) |  | CHECK in preview |
| J4 | C160405 | JST_SM06B | Bottom | 0 | 0.0 | 0.0 | 1 | up-right (+2.50, -2.00) | up-left (-2.50, -2.00) | CHECK in preview |
| J5 | C41427493 | USB-C_HX_16P | Top | 90 | 90.0 | 0.0 | A1B12 | down-left (-2.55, +3.20) |  | CHECK in preview |
| J6 | C160407 | JST_SM08B | Top | 90 | 90.0 | 0.0 | 1 | down-left (-2.00, +3.50) |  | CHECK in preview |
| J7 | C585350 | microSD_Molex_104031-0811 | Bottom | 270 | 90.0 | 180.0 | 1 | up-left (-5.45, -3.10) | up-right (+5.45, -3.10) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| J8 | C88373 | U.FL-R-SMT-1 | Bottom | 0 | 0.0 | 0.0 | 1 | down (+0.00, +1.52) | down (-0.00, +1.52) | CHECK in preview |
| Q1 | C15127 | SOT-23 | Bottom | 0 | 270.0 | 270.0 | 1 | down-right (+0.95, +0.94) | down-left (-0.95, +0.94) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| U10 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270.0 | 270.0 | 1 | up-right (+3.17, -0.63) | up-left (-3.17, -0.63) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| U11 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270.0 | 270.0 | 1 | up-right (+3.17, -0.63) | up-left (-3.17, -0.63) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| U12 | C92243 | SSOP-4_1.27 | Bottom | 0 | 270.0 | 270.0 | 1 | up-right (+3.18, -0.64) | up-left (-3.18, -0.64) | CHECK in preview (seen right on 2026-11-07; re-check, review M2); moved 0.08 mm in r7c |
| U14 | C138714 | USON-10 | Top | 0 | 0.0 | 0.0 | 1 | down-left (-1.00, +0.41) |  | CHECK in preview |
| U15 | C78988 | SOT-23-5 | Top | 90 | 0.0 | 270.0 | 1 | down-right (+1.14, +0.95) |  | CHECK in preview |
| U16 | C2155674 | WSON-8_2x2_EP | Bottom | 90 | 90.0 | 0.0 | 1 | down-right (+0.75, +0.95) | down-left (-0.75, +0.95) | CHECK in preview |
| U2 | C78988 | SOT-23-5 | Bottom | 0 | 270.0 | 270.0 | 1 | down-right (+0.95, +1.14) | down-left (-0.95, +1.14) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| U3 | C138714 | USON-10 | Bottom | 90 | 90.0 | 0.0 | 1 | down-left (-0.41, +1.00) | down-right (+0.41, +1.00) | CHECK in preview |
| U4 | C882825 | SOT-23-5 | Bottom | 0 | 270.0 | 270.0 | 1 | down-right (+0.95, +1.14) | down-left (-0.95, +1.14) | CHECK in preview (seen right on 2026-11-07; re-check, review M2) |
| U6 | C201698 | MSOP-8 | Bottom | 90 | 90.0 | 0.0 | 1 | down-left (-2.11, +0.98) | down-right (+2.11, +0.98) | CHECK in preview |
| U7 | C3008606 | BGA-64_6x6 | Bottom | 180 | 180.0 | 0.0 | A1 | down-left (-2.27, +2.27) | down-right (+2.27, +2.27) | CHECK in preview; moved -2.5 mm in x in r7d |
| U8 | C138714 | USON-10 | Bottom | 180 | 180.0 | 0.0 | 1 | up-left (-1.00, -0.41) | up-right (+1.00, -0.41) | CHECK in preview |
| U9 | C138714 | USON-10 | Bottom | 180 | 180.0 | 0.0 | 1 | up-left (-1.00, -0.41) | up-right (+1.00, -0.41) | CHECK in preview |
| Y1 | C725995 | OSC3225 | Bottom | 0 | 0.0 | 0.0 | 1 | down-right (+1.05, +0.83) | down-left (-1.05, +0.83) | CHECK in preview |
| C1 | C19702 | C0603 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.78) |  | non-polar, either way works |
| C10 | C19702 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works |
| C11 | C19702 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works |
| C12 | C19702 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works |
| C13 | C1537 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; new place and rotation in r7d |
| C14 | C19666 | C0603 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.78) | down (-0.00, +0.78) | non-polar, either way works |
| C15 | C1537 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; new place and rotation in r7d |
| C16 | C19666 | C0603 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.78) | down (-0.00, +0.78) | non-polar, either way works; new place and rotation in r7d |
| C17 | C1537 | R0402 | Bottom | 180 | 180.0 | 0.0 | 1 | left (-0.48, +0.00) | right (+0.48, +0.00) | non-polar, either way works; new place and rotation in r7d |
| C18 | C19666 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C19 | C1537 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| C2 | C19702 | C0603 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.78) |  | non-polar, either way works |
| C20 | C19666 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works; moved 0.05 mm in r7c |
| C21 | C1525 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works; new place and rotation in r7d |
| C22 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C23 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C24 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved 0.05 mm in r7c; moved -2.5 mm in x in r7d |
| C25 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C26 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C27 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| C29 | C1525 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| C3 | C1525 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| C32 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| C33 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| C4 | C1525 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| C40 | C19702 | C0603 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.78, +0.00) | left (-0.78, +0.00) | non-polar, either way works |
| C41 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| C5 | C52923 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| C50 | C1525 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| C6 | C1525 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| C60 | C45783 | C0805 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.95) | down (-0.00, +0.95) | non-polar, either way works |
| C61 | C45783 | C0805 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.95) | down (-0.00, +0.95) | non-polar, either way works |
| C62 | C45783 | C0805 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.95) | down (-0.00, +0.95) | non-polar, either way works |
| C63 | C1555 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| C64 | C52923 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| C65 | C45783 | C0805 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.95, +0.00) |  | non-polar, either way works |
| C66 | C45783 | C0805 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.95) |  | non-polar, either way works |
| C67 | C45783 | C0805 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.95) |  | non-polar, either way works |
| C68 | C1555 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| C70 | C385032 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| C71 | C1525 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| FB2 | C98485 | C0805 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.95, +0.00) | left (-0.95, +0.00) | non-polar, either way works |
| FB3 | C85840 | C0805 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.95, +0.00) | left (-0.95, +0.00) | non-polar, either way works |
| FB4 | C98485 | C0805 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.95, +0.00) | left (-0.95, +0.00) | non-polar, either way works |
| FB5 | C85840 | C0805 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.95, +0.00) | left (-0.95, +0.00) | non-polar, either way works |
| FB6 | C19330 | C0603 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.78) | down (-0.00, +0.78) | non-polar, either way works |
| L1 | C83423 | IND4020 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+1.50, +0.00) | left (-1.50, +0.00) | non-polar, either way works |
| L2 | C83423 | IND4020 | Top | 0 | 0.0 | 0.0 | 1 | left (-1.50, +0.00) |  | non-polar, either way works |
| R1 | C25905 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R10 | C25755 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R11 | C25744 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| R12 | C25744 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| R13 | C25744 | R0402 | Top | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) |  | non-polar, either way works |
| R2 | C25905 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R20 | C4109 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved -2.5 mm in x in r7d |
| R21 | C25744 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R22 | C25879 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R23 | C25879 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R24 | C25092 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R25 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R26 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R27 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R28 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works; moved 0.08 mm in r7c |
| R3 | C25905 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R30 | C11702 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R32 | C25741 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R4 | C25905 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R40 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R42 | C17168 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R43 | C25794 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R44 | C25794 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R45 | C25794 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R46 | C25794 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R47 | C25794 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R50 | C25755 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R51 | C122548 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R52 | C25117 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R53 | C25117 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R54 | C25099 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R55 | C25744 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R60 | C26083 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R61 | C728559 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R62 | C319512 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R63 | C728559 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R65 | C17168 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R66 | C25076 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R67 | C25794 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
| R68 | C247444 | C0805 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.95, +0.00) | left (-0.95, +0.00) | non-polar, either way works; new in r7c |
| R71 | C25741 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R72 | C25792 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R73 | C11702 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R74 | C25092 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R75 | C25092 | R0402 | Bottom | 90 | 90.0 | 0.0 | 1 | down (+0.00, +0.48) | down (-0.00, +0.48) | non-polar, either way works |
| R76 | C25092 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R77 | C25092 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R78 | C25092 | R0402 | Bottom | 0 | 0.0 | 0.0 | 1 | right (+0.48, +0.00) | left (-0.48, +0.00) | non-polar, either way works |
| R79 | C25092 | R0402 | Top | 270 | 270.0 | 0.0 | 1 | up (+0.00, -0.48) |  | non-polar, either way works |
| R80 | C320843 | R0201 | Top | 270 | 270.0 | 0.0 | 1 | up (+0.00, -0.27) |  | non-polar, either way works |
| R81 | C320843 | R0201 | Top | 270 | 270.0 | 0.0 | 1 | up (+0.00, -0.27) |  | non-polar, either way works |
| R9 | C25741 | R0402 | Top | 0 | 0.0 | 0.0 | 1 | left (-0.48, +0.00) |  | non-polar, either way works |
