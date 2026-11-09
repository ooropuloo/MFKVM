# MF KVM（P4 KVM Mini）

40 × 40 mm、6 層單片板的 KVM over IP，目標外殼 44 × 44 × 20 mm。主控是 ESP32-P4-Module 基本款（SKU 28101，內建 ESP32-C6，2.4 GHz，天線訊號從第 2 腳經模組上的 R99 出來，再到板上的 J8 U.FL），影像用 TC358743，韌體是 ESP-KVM。

**狀態：打板包 `fab_r7b/` 只能送 CAM 預審，還不能算放行。** r7b 是 r7 依獨立審查（`REVIEW_independent.md`）修正的版本，改了什麼見 `R7B_REPORT.md`。 ERC、DRC、`verify.py`（含新的電氣規則表）、阻焊幾何、孔到銅、零件外形、阻抗都過了，但這些是檔案層級的檢查，**沒有打過板、沒有焊過、沒有實機驗證**。r7 新加的 1.2 V 降壓（U15）和它的遠端回授線沒有上過電。裸板和雙面組裝都要等 CAM 預審結果與 CPL 旋轉角確認後才放行。

## 打板包（JLCPCB）
送審用 `fab_r7b/p4_kvm_mini_gerber.zip`（雜湊見 `fab_r7b/SHA256.txt`），BOM 和座標用 `fab_r7b/BOM_JLC.csv`、`fab_r7b/CPL_JLC.csv`，下單預覽逐顆對照 `fab_r7b/CPL_pin1_check.md`。r7 的改動見 `R7_REPORT.md`，r7b 的見 `R7B_REPORT.md`。

**不要用 `fab_r7/`。** 1.2 V 分壓是 1% 電阻（AVDD12 最差只剩約 1 mV）、遠端回授線斷開會讓 1.2 V 升到 3.3 V、HDMI +5V 直接接 HPDI、U1 沒有絲印外框、J6 離 U1 焊墊 0.225 mm、TC358743 RESETN 是上拉、不焊零件和客供 U1 的說明不一致。

**不要用 `fab_r6/`。** 它的 U6（PCA9517）EN 接 3V3，低於 EN 的 VIH（0.7 × VCCB = 3.5 V），DDC 中繼不保證會開；Y1 的輸出掛了 2 顆 47 pF，超過振盪器 15 pF 的負載；1.2 V 用 TLV73325 → TLV73312 兩級 LDO，U4 最差負載 98%、U5 在 SOT-23 裡發熱、AVDD12 最差會低於 1.15 V；有 4 組零件在 ±0.1 mm 貼裝誤差下會碰到；KiCad 疊構和下單疊構不一致；CSI_D0 有 4 個 90 度彎，CSI_D0、CSI_CK 線內長度差 2.08、1.47 mm。

更舊的版本（`fab_r5/` 以前）的問題見 `../v2_r6/README.md`，這裡不重複。

| 項目 | 設定 |
|---|---|
| 層數、厚度 | 6 層，1.2 mm 板厚，1 oz 外層 |
| 疊構 | F｜GND｜訊號｜3V3｜GND｜B。**JLC06121H-3313**：外層介質 3313 0.0994 mm、core 0.35 mm、內層 2116 0.1088 mm，銅 0.035／0.0152 mm，銅加介質 1.1384 mm。r7 起 KiCad 板檔的疊構就是這組數字，Gerber job 檔跟著一致。介電常數（3313 4.1、2116 4.16、core 4.6）是解算器用的值，不是這個資料夾裡的 JLC 文件 |
| 阻抗 | 場解算（`tools/r6/s3_solver.py`，含阻焊）：TMDS、CSI 0.127/0.198 mm **99.1 Ω**；USB 0.18/0.32 mm **89.1 Ω**；LNA_OUT 0.15 mm、同層鋪銅間隙 0.25 mm **50.5 Ω**。都在 ±10% 內，線寬沒改。另用 Kirschning-Jansen 公式交叉驗證，薄銅條件下差 2%。表在 `fab_r7/impedance_r7.txt`。**沒有跑 JLC 的線上計算器** |
| 最小線寬、線距 | 0.09 mm |
| 最小過孔 | 0.4/0.2 mm，V1V2 有 3 顆 0.5/0.25。選 Epoxy Filled & Capped（JLC 6 層預設）。**不要選阻焊塞孔**：JLC 要求塞孔離開窗 0.35 mm 以上，這塊板不符合 |
| 阻焊 | **綠色**，expansion 0（焊盤與開窗 1:1）。**最小 bridge 0.1088 mm**（J5.1 對 C64.2，同網路），開窗到其他網路銅最小 0.101 mm，明細見 `fab_r7b/mask_report.txt`。（r6 README 寫的「最小 bridge 0.15 mm」是 r5 以前的數字，r6 加了 C64 之後就已經是 0.1088） |
| 孔到銅 | 依 JLC 公開規格：過孔孔 0.20，NPTH 0.20，PTH 外層 0.28、內層 0.30。實測最小：過孔 0.2000（外層）、0.2005（內層），NPTH 0.3005，PTH 0.3017（外層）、0.3025（內層），明細見 `fab_r7/hole_report.txt` |
| 組裝 | 雙面、Standard PCBA。BGA 需要 X-ray |
| 拼板 | 40 mm 太小，依 JLC 要求加工藝邊或拼板 |

**要先處理：**
1. **P4 模組：** BOM 不含 U1，**JLC 不貼，由客戶組裝後手焊**；U1 的 88 個焊盤保留錫膏。買 Waveshare `ESP32-P4-Module` 基本款（SKU 28101）。正面絲印有模組外框、第 1 腳那一角切角和圓點，對準再焊。焊完量 U1.23（I2C_SCL）對 GND、對 3V3 沒有短路（它和 J6.2 GND 相隔 0.425 mm）。**模組上的 R99（0R）要留著**，R75 不要焊。U.FL 天線另外買，接 J8。確認晶片版本，韌體分 rev 3 和舊版。
2. **CPL 旋轉角：** 下單預覽要逐顆確認方向，特別是背面零件。2026-11-07 對過的：U2、U4、Q1、U10、U11、U12 是 270 度，J7 是 90 度（`fab_pack.py` 的 `JLC_ROT`）。**r7 新增或換料、沒有在 JLC 預覽對過的：** U15（SY8089，**正面**；同料號的 U2 在背面是 270 度，正面的 0 度沒對過）、L2、C65–C68、R61–R63、R65、U6（換成 C201698，封裝相同）、R28（移位）。r6 留下的 J8、C64、R60 也還沒對過。U5 拿掉了，它的 0 度（C2871228，JLC 3D 預覽確認過）不再用到。在預覽裡手動旋轉不會存檔，要改 CPL 重傳。
3. **不要焊：** R31、R41、C30、C31（r7b 起這些焊盤沒有錫膏）。**不要同時焊 R41 和 R42**（3V3 對 VO4 短路）。**R65（0R）和 R66（100 Ω）兩顆都要焊**：R65 是遠端回授，R66 是遠端線斷開時的本地備援。見 `fab_r7b/CONSIGNED_AND_NOT_FITTED.csv`。
4. **低庫存：** TC358743 在 JLC 剩 225 顆（`stock.py`，2026-11-08）。
5. **新的擴充料：** U6 TCA9517ADGKR（C201698）；r7b 的 R61、R63 33k 0.1%（C728559）、R62 560 Ω 0.1%（C319512，庫存 7,835）、R51 33.2k（C122548）。R67 51k、R66 100 Ω 是基本庫。U15、L2 和 U2、L1 同料號，不用多一個料站。

## 供電要求
- **用能供 1.5 A 以上的 Type-C 電源接 J5。** 板子的 CC 只有 5.1 kΩ 下拉，照規範只能當預設電流。
- **電腦的 USB 2.0 埠只保證 500 mA。** r7 電流預算：5V 典型約 384 mA、最差約 1019 mA（r6 是 460／1134），見 `R7_REPORT.md` 第 3 項。
- **從電腦燒錄或看 console 時，關掉 Wi-Fi 或降低發射功率。**

## 1.2 V（r7）
U5（TLV73312）拿掉，1.2 V 改由 U15（SY8089AAAC，和 U2 同料）從 3V3 降壓，放在正面 J2 上方原本只有絲印的空位。L2 2.2 µH（和 L1 同料）、C65 輸入 22 µF、C66/C67 輸出 2 × 22 µF。U4 只剩 AVDD25（最差 19 mA）。
- **遠端回授：** 回授分壓（R61 33k + R62 560 Ω 對 R63 33k，r7b 起都是 0.1%；C68 22 pF）在 U15 旁邊，分壓上端經 V1V2_SNS 一路接到磁珠入口旁的 R65（0R），所以 U15 到磁珠之間約 76 mΩ 的走線壓降被補償。最差情況 AVDD12 在球上 **1.1617–1.2373 V**（規格 1.15–1.25 V），上下各約 12 mV 餘量（r7 用 1% 電阻時只有約 1 mV）。
- **V1V2_SNS 很長（約 51 mm）**，大部分在 In2（上下是 GND 和 3V3 平面），最後約 13 mm 在背面經過 FB5 和 J5 旁邊。回授的穩定度和雜訊沒有量過。
- **斷線保護（r7b）：** R66 100 Ω 把回授節點也接到 U15 本地的 V1V2。兩端都通時只偏 0.09 mV；遠端線或 R65 斷開時，U15 改成在本地取樣，AVDD12 最差掉到約 1.139 V（低於規格但不會過壓）。R61 或 R62 本身開路則沒有保護，1.2 V 會升到 3V3。
- **只用本地取樣（備案）：** 拿掉 R65。AVDD12 最差約 1.139 V。
- **第一片要量：** AVDD12 球上的電壓與雜訊（規格 40 mVpp）、U15 負載瞬變和穩定度、輕載時的漣波。

## CAM 預審要確認
1. 接受 1:1 阻焊開窗、不另外加 expansion。若廠內加大，要重新對照 `fab_r7/mask_report.txt`。
2. U7（0.65 mm BGA，0.3 mm 焊盤）在 1:1 開窗下的對位公差可以接受。
3. 過孔用 Epoxy Filled & Capped。
4. 疊構和阻抗：實際介質型號，TMDS、CSI、USB 線寬線距對得到目標阻抗。
5. 0.09/0.09 mm 線寬線距在這個疊構可做，J2、J3、J5 的機構孔和槽孔判讀正確。
6. **逐顆確認 CPL 旋轉角與面別**（雙面組裝），U1 客供流程，以及工藝邊或拼板。
7. 組裝間隙：`fab_r7/body_report.txt` 依規格書外形檢查所有同面零件組合。**r7 起 `bodycheck.py` 把「最差值 < 0」當成錯誤**（最差值 = 最大尺寸再扣每顆 ±0.1 mm 貼裝誤差，**0.1 mm 是假設**，JLC 沒有公開數字）。現在沒有任何組合低於 0，最緊的是 C19/C20 0.000、FB2/C24 0.005、U6/R28 0.006、L1/U12 0.010 mm。TI DBV 外形的毛邊（每邊 0.25 mm）算進去時 U4/Q1 是 +0.055 mm。**Q1 的外形不是原廠圖**（AOS 沒有外形頁，暫用 TI DBZ0003A）。
8. 孔位餘量：過孔孔到走線最小 0.2000 mm，剛好等於限值。`holecheck.py` 沒有檢查孔到孔。
9. J5 A1B12 的 GND 散熱連接只有 1 條（DRC 警告 starved_thermal），可焊性要確認。
10. 絲印：MF KVM 和 R7B（1.0 mm）直排在 J2 和 J3 之間（R67 占了下半段）；U1 外框、切角、第 1 腳圓點（r7b）；JLC 公開規格是字高 1.0 mm、線寬 0.15 mm 以上，P4 MINI R7 剛好在下限。測試點標籤（0.5 mm）低於規格，可能印不清楚。

## Courtyard 警告
DRC 有 18 個 courtyard 重疊警告，全部是外框加 0.1 mm 邊界造成的，零件本體沒有重疊（`body_report.txt`）。最緊的幾組（最大尺寸／最差，mm）：C19/C20 0.200／0.000、U6/R28 0.206／0.006、L1/U2 0.280／0.080、C10/Q1 0.375／0.094、Q1/R43–R45 0.300／0.100、C20/U8 0.300／0.100、C64/U2 0.350／0.150。TP6/J4 是測試點外框邊界，TP 沒有本體。C30/U3 的 C30 不焊。

## 新光耦（需要實機測試）
沒有改動，見 `../v2_r6/README.md` 同名一節：ATX 開機和重置要實機測試過才算數。

## 接線
| 接頭 | 用途 |
|---|---|
| J2 HDMI、J3 USB-C | 接主機，在 I/O 面。J3 是 P4 的 USB OTG-HS，主機看到的鍵盤、滑鼠和虛擬媒體都走這裡；不供電給板子，也不是燒錄或 console |
| J5 USB-C | 5V 供電，也是燒錄口（USB-Serial-JTAG，GPIO24/25）和**次要** console（只有應用程式 log） |
| J7 microSD | 站在接線面外看從右牆插入，推拉式 |
| J6 SM08B | 圓形螢幕：1 3V3、2 GND、3 DIN、4 CLK、5 CS、6 DC、7 RST、8 BL（BL 接 3V3，背光常亮）。r7b 往 +x 移 0.2 mm，焊盤離 U1 焊盤 0.425 mm。見下 |
| J4 SM06B | 前面板：PWR C/E、RST C/E、LED K/A，在背面 |
| J8 U.FL | 天線，在背面靠接線面的對角，接 FPC 天線 |
| TP1–TP8 | 底面：BOOT、EN、UART0 TX/RX、C6 RX/TX/BOOT、GND。**主要 console 是這裡的 UART0（GPIO37/38，115200）** |

**J6 和 Waveshare 1.28inch LCD Module（SKU 19192）：** wiki 的接腳順序是 VCC、GND、DIN、CLK、CS、DC、RST、BL，工作電壓 3.3 V／5 V，模組上是 PH2.0 8P（隨附 PH2.0 8P 20 cm 線）。J6 的 1–8 腳順序和它一樣，所以 **SH1.0 8P 對 PH2.0 8P 一對一、不交叉** 的線可以用：J6 第 1 腳（3V3）接模組 VCC，第 8 腳（BL）接 BL。**wiki 沒寫模組端 PH2.0 的腳號和哪一邊是 VCC**，做線前要看模組絲印確認 VCC 那一腳。背光電流 wiki 沒有寫，電流預算沿用 r6 的假設（30／60 mA）。這次沒改 J6。

腳位：TC358743 I2C 7/8、RESET 23（**r7b 起 R21 是下拉**：韌體要把 GPIO23 拉高才會放開 reset，現行韌體的 `bridge_resetn_pulse()` 會做，見 `firmware/BUILD_v2.md` 最後一節）；HDMI +5V 經 R67 51k 接 HPDI；LCD DIN 9、CLK 10、CS 11、DC 12、RST 13；ATX PWR 4、RST 5、LED 2；TF 39–45；GPIO3 是主機 VBUS 分壓，韌體尚未使用。

## 韌體
r7 沒有改韌體，韌體相關事項（`firmware/p4_kvm_mini.defaults`、ATX 預設關閉、VO4 必須設 3.3 V 才關得掉 Q1、晶片版本等）見 `../v2_r6/README.md` 的「韌體」一節，內容仍然適用。r7 的硬體改動不影響腳位。

## 重新產生
r7b 的布線檔是 `out/final.ses`（同 `out/final_r7b.ses`）。一般重建只要這幾行：
```
sh tools/check.sh out/final.ses             # 由布線產生板子和電路圖，跑 ERC、DRC
python tools/stock.py out                   # JLC 型號與庫存
python tools/verify.py out data/antmicro/a.net > out/verify.out   # 含電氣規則表、maskcheck、holecheck、bodycheck
python tools/fab_pack.py out fab_r7b        # 任何檢查沒過就拒絕出檔；目標已有打板包也拒絕
python tools/r7/cpl_table.py out fab_r7b/CPL_JLC.csv fab_r7b/CPL_pin1_check.md   # 每顆零件的 CPL 角度與預覽中第 1 腳位置
python tools/r7/impedance_r7.py out/p4_kvm_mini.kicad_pcb        # 從板檔讀疊構，算阻抗
python tools/r7/budget_r7.py out/p4_kvm_mini.kicad_pcb           # 1.2 V 和電流預算
python tools/r6/pairs.py out/p4_kvm_mini.kicad_pcb               # 差動對長度、skew、90 度彎
```
r7 布線是怎麼做出來的（不必重做）：`gen_mini.py` 的電源平面逃線搜尋仍在 r6 的零件位置上跑，r7 的改動在搜尋之後手動加。r6 板子上全部已布的銅以 `R7_KEEP=<板檔>` 交給 Freerouting 當成保護線，Freerouting 只補 r7 新的連線（`--router.fanout.enabled=false`）。步驟和每一輪加了什麼銅見 `R7_REPORT.md`「布線」一節，`tools/r7/ses_new.py` 可以列出任何 SES 裡新加的銅。

## 外殼
沿用 r6 的外殼檔（`case/stl/`），**尚未試印**。對 r7b 板子重跑 `case/check_case.py` 的結果見 `fab_r7b/case_check.txt`（J6 往 +x 移後，M2 螺絲到 J6 的間隙 0.68 mm）。新加的 U15、L2（高 2.0 mm）在正面 J2 上方，r6 外殼的這一區沒有其他零件。

## 參考來源
- Antmicro hdmi-mipi-bridge（Apache-2.0）：TC358743 周邊電路。`verify.py` 用的網表和授權聲明在 `data/antmicro/`。
- 規格書：TI TCA9517A（SCPS245E，`datasheets_r7/tca9517a.pdf`）、YXC YSO110TR（`datasheets_r7/dl/C725995_ds.pdf`）、Silergy AN_SY8089/A Rev 0.9A、Toshiba TC358743XBG、TI TLV733P（`../pdf_20261108/規格書/`）。
- Waveshare：ESP32-P4-Module 焊盤圖、STEP、腳位表；1.28inch LCD Module wiki（https://www.waveshare.com/wiki/1.28inch_LCD_Module）。
- KiCad 官方封裝庫：microSD、JST SH、SO-4、SOT、VSSOP、振盪器、電感。
