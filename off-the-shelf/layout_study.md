# MF KVM v3 layout study

All numbers come from `layout_study.py`. Heights use the upper bound of the C790 estimate (total 11 mm). Walls 1.6, floor 1.2, roof 1.0, air gap 0.3. Nothing has been measured on real parts.

## Why 65 x 35 x 24 was wrong

It assumed the C790 could lie along the core. It cannot without a fold, because a ribbon only bends about an axis across its width, so the two connector long axes stay parallel unless the ribbon is folded on a diagonal. J1 runs along the core's 60 mm side and J2 runs along the C790's 30 mm side, so the C790's 45 mm side lies across the core. On top of that the 50 mm ribbon has 42.0 mm of free path to use up (50 minus 4.5 inside J1 and 3.5 inside J2 [G]). There is no shorter catalogue part in the research.

## Results

| | Layout | Outer X x Y x Z mm | Box cm3 | Real cm3 | Pin 1 | Ribbon type | Antenna to C790 / LCD / ribbon mm | Ribbon path vs 42.0 |
|---|---|---|---|---|---|---|---|---|
| A | Stacked crosswise, C790 face down past the core, LCD beside it | 83.8 x 65.3 x 23.5 | 129 | 129 | ok | opposite | 18.9 / 29.7 / 7.1 | sized to fit |
| B | Flat L: C790 face up off the +x edge, LCD on C790, ribbon hump | 95.1 x 65.3 x 16.9 | 105 | 70 | ok | opposite | 24.9 / 26.3 / 7.1 | sized to fit |
| C | Inline, roll upward: C790 high over the core, LCD on top | 38.1 x 75.0 x 29.4 | 84 | 84 | ok | opposite | 25.1 / 22.8 / 7.1 | 36.6 |
| D | Inline, roll downward: C790 just above the USB plug tunnel, LCD on top | 38.1 x 75.0 x 26.7 | 76 | 76 | ok | opposite | 21.7 / 20.4 / 7.1 | 41.7 |
| E | C790 under the core, ribbon wrapped round the +x edge | 52.9 x 65.3 x 23.6 | 82 | 82 | WRONG | same-side | 3.3 / 26.4 / 0.9 | 40.4 |

- **A:** The 50 mm ribbon has to go somewhere, which pushes the C790 edge out to x -20.2. Face-up here gives pin 1 to pin 15 (3V3 onto GND), so it has to be face down.
- **B:** No roll, no tunnel, height 16.9. Bounding box is huge, real volume is the L (70 cm3). OTG and TF sit in the notch of the L.
- **C:** Simplest structure over the USB plug, but it pays the 6 mm roll on top of everything.
- **D:** Picked. See below.
- **E:** Rejected twice: the C790 ground plane sits under the antenna, and pin 1 lands on pin 15.

## Pick: D

**38.1 x 75.0 x 26.7 mm, 76 cm3.** The case in `case/gen_case.py` is built to these numbers.

- **Smallest box that keeps the antenna clear.** C starts the same way and is taller. A and B also clear the antenna but need a far bigger box. E has the C790 under the antenna.
- **Antenna.** C790 starts at y 26.0. C790, LCD, ATX board and screws are all past Espressif's 15 mm. The ribbon comes within 7.1 mm, and the core's own connectors are closer still, where DFRobot put them. Stacking the C790 directly over y 0..30 would be smaller but needs a shorter ribbon than the catalogue has, and puts its ground plane over the antenna.
- **Ribbon.** The free path gets used by the roll, 41.7 mm routed against 42.0 mm available, with no slack loop to store.
- **Cost: a 45 degree roll in a MIPI ribbon.** A fold keeps every conductor the same length, so it adds no skew in theory, but no one has tested this exact ribbon and radius at 972 Mbit/s. A printed former sets R. Check the picture first thing when the parts arrive.
- **Cost: the 5 V plug sits in a 11.6 mm deep alcove** under the HDMI end, because the C790 overhangs the core's USB end. An overmoulded plug must be 13 mm wide and 6.6 mm tall or less.

## Runner up: B

Flat L, bounding box 95 x 65 x 17, real volume 70 cm3, height only 16.9. It has no roll and no alcove, the OTG and TF ports stand in open air, and the antenna is clearest of all. It loses because the footprint is 95 x 65 mm and it is a strange shape to pack. **If the roll fails on the bench, or a flat box suits you better than a small one, B is the fallback.** It uses the same ribbon, the same pin map and the same ATX board.

## Later improvement

A custom L-shaped flex PCB (not a catalogue FFC) removes the fold and about 6 mm of height, about 60 cm3 [G]. It needs 100 ohm impedance control on flex and an extra order, so it is not part of this design.

## Ribbon pin map, derived

The frame is carried from C790 to J1 in code, `transport()`. Conductor 1 lies on t x n, where t is the direction of travel and n is the face away from the C790 contacts.

| Fact | Value | Evidence |
|---|---|---|
| C790 J2 pin 1 | low Y_c, contacts toward the PCB | [P] triangle in the photo, [V] G6 for contact direction |
| J1 pin 1 | high y (toward the P4), white dot | [V] DFRobot pinout figure |
| J1 contact | spring contact on the -x side of the slot, slider on the +x side | [V] section of the official STEP at y 11.9, `case/j1_section.png` (made from the vendor model, not in the repo; see THIRD_PARTY.md). A vendor model, not the part in hand [U] |

For D, C790 face up with its FPC edge toward -y: t = -y, n = +z, so conductor 1 is on -x. The roll takes it to t = +x, n = -z, conductor 1 on +y. The final bend gives t = -z, n = -x, conductor 1 on +y.

- **Pin 1 lands on pin 1**, independent of ribbon type.
- **Opposite-contact ribbon** (Wurth 686715050001): the J1 contact face is +n = -x, which is the side the spring is on. That agrees with the DFRobot wording (contacts toward the contacts, blue backing toward the black slider).
- **If the real J1 has its contact on +x**, the same layout needs a same-side ribbon (Wurth 686615050001). The layout does not change, only the part number. Buy one of each. Look before plugging in.
- **Checked by conductor position too:** on the roll line y - 14.9 = -(x - x_f), pin 1 at x_f - 7 maps to y = 21.9, which is J1 pin 1.
- **What the geometry rejects:** C790 face up off the -x edge gives pin 1 to pin 15 (3V3 to GND). The +x roll variant does too.
