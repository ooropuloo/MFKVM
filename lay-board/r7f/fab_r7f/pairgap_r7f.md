# Differential pair gap and coupling (tools/pairgap.py)

Differential-pair gap and coupling (r7e, REVIEW_r7d: verify.py never checked pair spacing).

Each line of a pair is sampled every 0.05 mm; at each sample the edge-to-edge gap to the partner line ON THE SAME LAYER is measured and
turned into a differential impedance with the field solver's table below (tools/r7/impedance_r7.py's solver, this stackup, solder mask,
2026-11-09). This board's pairs are weakly coupled (outer dielectric 0.0994 mm), so an uncoupled stretch is only ~10% above target while a
tight one drops fast.
  FAIL  any sample whose impedance is outside target +-10% (CSI/TMDS 100 ohm: gap under 0.12 mm; USB HS 90 ohm: gap under 0.14 mm),
        or a line with no partner segment on its layer for more than half its length.
  report  coupled length (gap within +-0.03 mm of the solved gap) and uncoupled length (fan-outs at balls, pads, vias, matching bumps).

| group | line | partner | solved gap | length mm | coupled mm | uncoupled mm | no partner on layer mm | Zdiff min-max ohm | out of +-10% |
|---|---|---|---|---|---|---|---|---|---|
| csi | CSI_D0_P | CSI_D0_N | 0.198 | 10.10 | 4.54 | 5.56 | 0.00 | 99.0-109.5 | 0  |
| csi | CSI_D0_N | CSI_D0_P | 0.198 | 10.10 | 4.90 | 5.20 | 0.00 | 99.0-109.0 | 0  |
| csi | CSI_D1_P | CSI_D1_N | 0.198 | 10.06 | 7.51 | 2.55 | 0.00 | 99.0-108.4 | 0  |
| csi | CSI_D1_N | CSI_D1_P | 0.198 | 10.15 | 7.73 | 2.41 | 0.00 | 99.0-108.0 | 0  |
| csi | CSI_CK_P | CSI_CK_N | 0.198 | 10.16 | 7.42 | 2.73 | 0.00 | 99.0-109.5 | 0  |
| csi | CSI_CK_N | CSI_CK_P | 0.198 | 10.25 | 6.94 | 3.31 | 0.00 | 99.0-109.2 | 0  |
| tmds | D0_P | D0_N | 0.198 | 13.37 | 7.59 | 5.78 | 0.00 | 99.0-109.5 | 0  |
| tmds | D0_N | D0_P | 0.198 | 13.37 | 8.05 | 5.32 | 0.00 | 99.0-109.0 | 0  |
| tmds | D1_P | D1_N | 0.198 | 10.75 | 5.59 | 5.16 | 0.00 | 99.0-108.7 | 0  |
| tmds | D1_N | D1_P | 0.198 | 11.08 | 6.05 | 5.03 | 0.00 | 99.0-109.0 | 0  |
| tmds | D2_P | D2_N | 0.198 | 8.94 | 3.75 | 5.19 | 0.00 | 99.0-108.7 | 0  |
| tmds | D2_N | D2_P | 0.198 | 8.93 | 4.40 | 4.53 | 0.00 | 99.0-109.0 | 0  |
| tmds | CK_P | CK_N | 0.198 | 15.43 | 9.09 | 6.34 | 0.00 | 99.0-109.5 | 0  |
| tmds | CK_N | CK_P | 0.198 | 15.52 | 9.55 | 5.97 | 0.00 | 99.0-109.0 | 0  |
| usb | USB_DP | USB_DN | 0.32 | 9.67 | 5.55 | 4.12 | 0.00 | 86.8-93.0 | 0  |
| usb | USB_DN | USB_DP | 0.32 | 9.50 | 5.85 | 3.65 | 0.00 | 86.8-92.4 | 0  |
RESULT PASS
