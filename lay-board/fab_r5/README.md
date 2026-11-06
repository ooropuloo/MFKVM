# MF KVM（P4 KVM Mini）

40 × 40 mm、6 層單片板的 KVM over IP，目標外殼 44 × 44 × 20 mm。主控是 ESP32-P4-Module（內建 ESP32-C6，2.4 GHz），影像用 TC358743，韌體是 ESP-KVM。

**狀態：打板包 `fab_r5/` 只能送 CAM 預審，還不能算放行。** ERC、DRC、`verify.py`、阻焊幾何檢查、孔到銅檢查和零件外形檢查都過了，但這些是檔案層級的檢查，**沒有打過板、沒有焊過、沒有實機驗證**。裸板和雙面組裝都要等 CAM 預審結果與 CPL 旋轉角確認後才放行。

## 打板包（JLCPCB）
送審用 `fab_r5/p4_kvm_mini_gerber.zip`（雜湊見 `fab_r5/SHA256.txt`），BOM 和座標用 `fab_r5/BOM_JLC.csv`、`fab_r5/CPL_JLC.csv`。

**不要用 `fab_r4/`。** 它的 4 個 2.2 mm 安裝孔到 GND、3V3 鋪銅只有 0.2005 mm，貼著 JLC 的 NPTH 0.2 mm，沒有餘量。`fab_r5/` 只把這 4 個孔的孔壁到鋪銅放大到 0.3005 mm，每個角每層少約 0.85 mm² 銅，走線、過孔、零件、鑽孔都沒動，比較見 `fab_r5/R5_vs_R4.txt`。

**也不要用 `fab_r3/`。** 依規格書外形，LTV-357T 的 U10、U11 本體重疊 0.25 x 4.40 mm，U12 和 L1 重疊 0.125 x 1.40 mm，U4 和 Q1 重疊 0.21 x 0.45 mm。DRC 看不出來，因為當時的 courtyard 只包焊盤。

`fab_r3/` 之後改了三件事（從 r4 開始，r5 保留）：
- U10、U11、U12 換成 Everlight EL3H7(C)(TA)-G（LCSC C92243），焊盤照規格書 p7，零件中心不動。
- U4 從 (-0.2, 5.2) 移到 (0.5, 5.2)。
- courtyard 改成包含零件本體，新增 `tools/bodycheck.py`。

**也不要用 `fab_r2/`。** 它的 4 個 2.2 mm 安裝孔到 GND、3V3 鋪銅只有 0.1505 mm，低於 JLC 的 NPTH 0.2 mm。

**也不要用 `fab/` 和 `fab_new/`。** `fab/p4_kvm_mini_gerber.zip` 沒有 MF KVM 絲印。兩者的阻焊都有 0.05 mm expansion，37 處 bridge 低於 0.10 mm、547 處開窗到其他網路銅低於 0.09 mm。`fab/MFKVM_v1.7z` 是 `fab/` 的打包，同樣不要用。

| 項目 | 設定 |
|---|---|
| 層數、厚度 | 6 層，1.2 mm，1 oz 外層 |
| 疊構 | F｜GND｜訊號｜3V3｜GND｜B。選介質約 0.1 mm 的 3313 系列，確切型號在下單頁確認 |
| 阻抗 | TMDS、CSI 約 100 Ω（0.127/0.198 mm），USB 約 90 Ω（0.18/0.32 mm）。公式估算，要用 JLC 計算器確認 |
| 最小線寬、線距 | 0.09 mm |
| 最小過孔 | 0.4/0.2 mm。選 Epoxy Filled & Capped（JLC 6 層預設）。**不要選阻焊塞孔**：JLC 要求塞孔離開窗 0.35 mm 以上，這塊板不符合（正面 89 顆、背面 150 顆低於 0.35） |
| 阻焊 | **綠色**，expansion 0（焊盤與開窗 1:1）。最小 bridge 0.15 mm，開窗到其他網路銅 0.10 mm，明細見 `fab_r5/mask_report.txt`。黑、白油的 0.13 mm 也通過，但只有綠色列入預審假設 |
| 孔到銅 | 依 JLC 公開規格：過孔孔 0.20，NPTH 0.20，PTH 外層 0.28、內層 0.30。實測最小：過孔孔 0.2000（外層）、0.2015（內層），NPTH 0.3005（H1–H4 的 pad 上設 0.30 mm local clearance，全板 min_hole_clearance 仍是 0.20，過孔本來就貼 0.2000），PTH 0.3017（外層）、0.3025（內層），明細見 `fab_r5/hole_report.txt`。距離以鑽孔檔的孔徑計算 |
| 組裝 | 雙面、Standard PCBA。BGA 需要 X-ray |
| 拼板 | 40 mm 太小，依 JLC 要求加工藝邊或拼板 |

**要先處理：**
1. **P4 模組：** BOM 不含 U1。買 Waveshare `ESP32-P4-Module-U`（IPEX 版）寄給工廠或自己焊，再接 FPC 天線。確認晶片版本，韌體分 rev 3 和舊版。
2. **CPL 旋轉角：** 下單預覽要逐顆確認方向，特別是背面零件，以及 U7、J2、J7、U3、U6、U8、U9。**U10、U11、U12 是新料**，CPL 的 0 度沒有對過 JLC 的封裝方向（EasyEDA 封裝 API 回 403），下單預覽要確認 1 腳：板上位置見 `fab_r5/README.md` 的「新光耦」一節。
3. **不要焊：** R31、R42。見 `fab_r5/CONSIGNED_AND_NOT_FITTED.csv`。
4. **低庫存：** U5 TLV73312PDBVT 在 JLC 只剩 36 顆，TC358743 剩 230 顆。

## CAM 預審要確認
1. 接受 1:1 阻焊開窗、不另外加 expansion。若廠內加大，要重新對照 `fab_r5/mask_report.txt`，特別是 U6、U3、U8、U9、U14 和 J2、J3、J5 的細間距排。
2. U7（0.65 mm BGA，0.3 mm 焊盤）在 1:1 開窗下的對位公差可以接受。
3. 過孔用 Epoxy Filled & Capped，0.4/0.2 與 0.5 mm 過孔都在製程範圍內，訂單頁確實是這個選項。
4. 疊構和阻抗：實際介質型號，TMDS、CSI、USB 線寬線距對得到目標阻抗。
5. 0.09/0.09 mm 線寬線距在這個疊構可做，J2、J3、J5 的機構孔和槽孔判讀正確。
6. **逐顆確認 CPL 旋轉角與面別**（雙面組裝），U1 客供流程，以及工藝邊或拼板。
7. 組裝間隙：`fab_r5/body_report.txt` 依規格書外形檢查所有同面零件組合，名義和最大尺寸都沒有重疊，但沒有實物驗證。下面是沒有餘量的組合，DRC 的 18 個 courtyard 警告見下一節。最差值假設每顆零件有 ±0.1 mm 貼裝誤差，**這是假設**，JLC 沒有公開數字。
   - L1/U12：名義 0.45，最大尺寸 0.05，最差 -0.15 mm。零件中心沒動，要動 U12 要另外決定。
   - FB2/C24：名義 0.325，最大尺寸 0.075，最差 -0.125 mm。
   - U7/Y1：名義 0.30，最差 -0.05 mm。C61/C62：名義 0.55，最差 -0.05 mm。
   - U4/U5：名義 0.40，最差 0.05 mm。U4/Q1：名義 0.49，最差 0.155 mm。TI 圖面 note 4 允許每邊 0.25 mm 毛邊，算到上限時 U4/U5 是 -0.20，U4/Q1 是 -0.095。
   - **Q1 的外形不是原廠圖**：AOS 的 AO3401A 規格書沒有外形頁，也沒找到另外的外形檔，暫用 TI DBZ0003A（JEDEC TO-236）。
8. 孔位餘量：過孔孔到走線最小 0.2000 mm，剛好等於限值、沒有餘量（(2.75,-6.00) 的過孔到背面 HDMI_CEC）。PTH 最小 0.3017 mm（J5.2 到背面 VDDC）過 0.28 mm，但低於 JLC 建議的 0.35 mm。(18,18) 安裝孔到 (16.44,18.45) 的 GND 過孔，孔壁距 0.425 mm；JLC 列的焊盤孔間距是 0.45 mm，過孔孔間距是 0.2 mm，NPTH 對過孔適用哪一條要請 CAM 確認。`holecheck.py` 沒有檢查孔到孔。
9. J5 A1B12 的 GND 散熱連接只有 1 條（DRC 警告 starved_thermal），可焊性要確認。
10. 絲印：JLC 公開規格是字高 1.0 mm、線寬 0.15 mm 以上，低於此可能無法辨識。MF KVM 字樣符合；REV 字串（0.8 mm）和測試點標籤（0.5/0.08 mm）低於規格，可能印不清楚，沒有列為擋件條件。

## Courtyard 警告
DRC 現在有 18 個 courtyard 重疊警告，全部是最大尺寸加 0.1 mm 邊界造成的，零件本體和引腳沒有重疊。表中是名義間隙，單位 mm。

| 組合 | 名義 | 判斷 |
|---|---|---|
| L1/U12 | 0.45 | 真的很緊，見上一節 |
| FB2/C24 | 0.325 | 真的很緊，見上一節 |
| C61/C62 | 0.55 | 公差疊滿才碰，見上一節 |
| U5/C11、U4/C10 | 0.65 | 只是邊界 |
| C10/Q1 | 0.595 | 只是邊界，最差 0.094 |
| Q1/R43、Q1/R44、Q1/R45 | 0.55、0.46、0.47 | 只是邊界，最差 0.10 |
| Q1/R46 | 1.02 | 只是邊界 |
| J4/U11 | 0.79 | 只是邊界，r3 最大尺寸時會碰，r4 最差 0.40 |
| U2/L1 | 0.625 | 只是邊界，最差 0.15 |
| C19/Y1、C17/Y1 | 0.55 | 只是邊界，最差 0.25 |
| C41/R53 | 0.70 | 只是邊界 |
| R42/R52 | 0.73 | R42 不焊，沒有實體 |
| U3/C30 | 0.62 | 只是邊界 |
| J7/C40 | 0.81 | 只是邊界 |

J6/U1 不算問題：用 Waveshare 25 x 25 mm 模組外形，名義 1.375 mm，最差 0.925 mm。之前的 0.225 mm 只是 courtyard 算出來的。

## 新光耦（需要實機測試）
**ATX 開機和重置要實機測試過才算數**，新光耦沒有焊上去測過。R52、R53 維持 470 Ω。

| 項目 | 數字 |
|---|---|
| CTR，C 級 | 200–400%（IF 5 mA、VCE 5 V，規格書 p3）。JLC 頁面也寫 200–400%，但它的 API 描述文字寫 130%/260%，那是 B 級的數字，收料時看印字的等級 |
| IF，3.3 V GPIO | 約 4.5 mA。ESP32-P4 規格書只保證 VOH 至少 2.64 V（0.8 × VDD），那時 IF 約 3.1 mA |
| GPIO 電流 | 規格書表 5-4：輸出 40 mA（typ，PAD_DRIVER 3）。4.5 mA 沒有接近這個數字 |
| 可吸收電流 | 25 °C、IF 4.5 mA：約 8.3 mA。IF 3.1 mA、70 °C（圖 3、圖 5 讀值）：約 3.9 mA |
| ATX 排針上拉 | **假設**低於 5 mA，沒有量過，也沒有規範可查。IF 和溫度都在最差角落時，低於 5 mA 的假設不一定夠 |
| VCE(sat) | 最大 0.2 V，但條件是 IF 10 mA、IC 1 mA。低 IF、較大 IC 時的飽和壓降規格書沒有保證 |

U10、U11、U12 的 1 腳方向在 `fab_r5/opto_pin1_check.png`。

## 接線
| 接頭 | 用途 |
|---|---|
| J2 HDMI、J3 USB-C | 接主機，在 I/O 面。J3 是 P4 的 USB OTG-HS，主機看到的鍵盤、滑鼠和虛擬媒體都走這裡；不供電給板子，也不是燒錄或 console |
| J5 USB-C | 5V 供電，也是燒錄口（USB-Serial-JTAG，GPIO24/25）和**次要** console：只有應用程式的 log 輸出，不能輸入、沒有 REPL，bootloader 的 log 也不走這裡。站在接線面外看在左牆 |
| J7 microSD | 站在接線面外看從右牆插入，推拉式，卡片約露出外殼 1.5 mm |
| J6 SM08B | 圓形螢幕：3V3 GND DIN CLK CS DC RST BL |
| J4 SM06B | 前面板：PWR C/E、RST C/E、LED K/A，在背面 |
| TP1–TP8 | 底面：BOOT、EN、UART0 TX/RX、C6 RX/TX/BOOT、GND。**主要 console 是這裡的 UART0（GPIO37/38，115200）**，要看 bootloader log 或要輸入都接這裡 |

腳位：TC358743 I2C 7/8、RESET 23；LCD DIN 9、CLK 10、CS 11、DC 12、RST 13；ATX PWR 4、RST 5、LED 2；TF 39–45；GPIO3 是主機 VBUS 分壓，韌體尚未使用。

## 韌體
設定在 `firmware/p4_kvm_mini.defaults`，要搭配 `firmware/patches/0001-*.patch`，建置紀錄見 `firmware/BUILD_v2.md`。**兩個版本都編譯過，沒有燒錄、沒有實機跑過**，所以下面寫的開機行為都來自讀程式碼。

- **第一次開機（依程式碼）：** 沒有 NVS 設定時，板子開自己的熱點 ESP-KVM-xxxx，密碼第一次隨機產生，圓形螢幕（GC9A01）顯示加入 QR，console 在 `http://192.168.4.1/`。
- **ATX 預設關閉：** 韌體不碰 GPIO4、5、2，console 也不會出現電源和重置按鍵。要用 ATX：接好 J4，到 web console 的 Settings → Power → ATX wiring 打開 **Enable ATX control**，不用重開機；腳位已經設好，不用再選。打開之後 GPIO4、5 平時輸出低電位，只有在 console 按下才動作。登入預設是 admin / admin，第一次要求改密碼。示波器量過之後才決定要不要改成預設開啟，量測計畫見 `firmware/BUILD_v2.md`。
- **更新：** `CONFIG_KVM_UPDATE_URL` 是空的，因為官方 DEV-KIT 映像沒有這塊板的腳位。manifest 更新路徑因此關閉，但**還有三條路可以裝到錯的映像**：開啟 `fw_fetch` 可以從 console 裝 GitHub 上的版本、可以手動上傳 `.bin`、NVS 已存的 `upd_url` 會蓋過空預設。不要對這塊板用這三條路裝官方映像。
- **重新編譯：** 既有的 `sdkconfig` 會蓋過 defaults，而且不會警告。改了 defaults 一定要用新的 build 目錄。
- **晶片版本：** rev 3 和舊版映像互斥。收到模組先用 esptool 讀晶片版本，再決定燒哪一個。
- **console 顯示的板名還是 DEV-KIT**，Pins 頁的 2x20 排針也是 DEV-KIT 的，這塊板沒有。只是顯示問題，真要改得動上游程式碼。
- **實機要確認：** 面板 pin、QR 能不能掃、ATX 接線與光耦、開機瞬間 GPIO4、5 會不會讓光耦導通（韌體初始化之前的腳位狀態沒查證）、PSRAM 大小偵測。

## 重新產生
```
python gen_mini.py out                      # 產生板子和 DSN
python tools/ses_patch_r4.py out/final_r3.ses out/final.ses   # r4 布線：以 r3 為底，只改列出的網路。r5 沒有改布線。不要重跑 freerouting，那會把全板的非高速線重走一次
sh tools/check.sh out/final.ses             # 匯入布線，跑 ERC、DRC
python tools/stock.py out                   # JLC 型號與庫存
python tools/verify.py out data/antmicro/a.net > out/verify.out   # 裡面會跑 maskcheck、holecheck 和 bodycheck
python tools/fab_pack.py out fab_r5         # 任何檢查沒過就拒絕出檔；目標已有打板包也拒絕，新版要用新資料夾
python tools/maskcheck.py fab_r5/p4_kvm_mini_gerber.zip   # 單獨量任何 Gerber 的阻焊
python tools/holecheck.py fab_r5/p4_kvm_mini_gerber.zip   # 單獨量任何打板包的孔到銅，要有全部銅層和兩個鑽孔檔
python tools/bodycheck.py out               # 零件外形互相比對，來源列在報告裡；要有 design.json 和 .kicad_pcb
```

## 外殼
**外殼已修正鏡像，尚未試印。** 用 `case/stl/` 的新檔，舊打包資料夾和舊 ZIP 裡的 STL 都不要印。檢查結果見 `case/check_report.txt`。
- **列印：** 上蓋上下顛倒印；底殼開口朝上。
- **組裝：** 4 支 M2 x 16 從底部穿過底殼、PCB，鎖進上蓋的 1.6 mm 導孔。
- **螢幕：** 圓形模組以直徑 39 mm、厚 3.6 mm 估算，用雙面膠貼在上蓋，尺寸要量實物。

## 參考來源
- Antmicro hdmi-mipi-bridge（Apache-2.0）：TC358743 周邊電路。PFIL、DAOUT 依規格書，HPD 依韌體，和它不同。`verify.py` 用的網表和授權聲明在 `data/antmicro/`。
- Waveshare：ESP32-P4-Module 焊盤圖、STEP、腳位表，DEV-KIT 原理圖。
- KiCad 官方封裝庫：microSD、JST SH、SO-4、SOT、VSSOP、振盪器、電感。
