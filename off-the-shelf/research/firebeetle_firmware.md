# MF KVM v3：FireBeetle 2 ESP32-P4 (DFR1172) 與 ESP-KVM 韌體適配調查

2026-11-06。未碰實機，全部是文件、原理圖、STEP 與原始碼的結論。

標記：**[V]** 已由一手來源查證，**[I]** 推論，**[U]** 查不到。

## 來源

| 代號 | 內容 |
|---|---|
| SCH pN | `DFR1172_..._schematics_V1.0.pdf`，第 N 頁（2025-04-10，Rev V1.0）。本機副本沒有放進 repo |
| STEP | 官方 `[DFR1172]FireBeetle 2 ESP32-P4(V1.1.0).step`，[下載](https://dfimg.dfrobot.com/wiki/21103/DFR1172_firebeetle-esp32-p4r32-development-board_stpfile_V1.0.zip)，免登入 |
| KVM | `espkvm/espkvm` commit `0893eef`（0.77.0，2026-11-05），完整 clone |
| P4DS | ESP32-P4 Datasheet Pre-release v0.5（DFRobot 掛的 datasheet 連結其實是這份） |
| WIKI | [wiki.dfrobot.com/dfr1172](https://wiki.dfrobot.com/dfr1172/) 與 [中文版](https://wiki.dfrobot.com.cn/SKU_DFR1172_FireBeetle_2_ESP32_P4) |

STEP 座標：原點在 PCB 頂面、寬度中線、天線端邊緣。+Y 朝 USB-CDC 端，+X 朝 P2 排針（OTG 那側），Z=0 是頂面，PCB 底面 Z=-1.62。

注意：STEP 檔名是 V1.1.0，原理圖與絲印是 V1.0。兩者差異未知 [U]，到貨先對實板。

## 1. CSI 接頭與 I2C

- **CSI_IO0、CSI_IO1 沒有接任何 GPIO。[V]** SCH p2：這兩條 net 只接 J1 pin 11/12，加上 R20 10K 到 3V3（IO0）與 R21 10K 標 NC（IO1，未上件）。SCH p1 的 P4 腳位上沒有這兩個 net。無串聯元件。
  - KVM 同結論：`boards/firebeetle2_p4.defaults:80` 設 `TC358743_RST_GPIO=-1`。
- 排線腳序（SCH p2 + wiki csi.png，兩者一致）[V]：1/4/7/10 GND，2/3 D0 N/P，5/6 D1 N/P，8/9 CLK N/P，11/12 IO0/IO1，13 SCL，14 SDA，15 3V3。與 Raspberry Pi 相同。J1 旁有 C45 10uF、C46 100nF。
- 接頭料號 [U]：原理圖只寫 `J1 CSI`，wiki 未列。STEP 模型名 `FPC1.0`。
- 規格（STEP）：15 pin、1.0 mm pitch [V]。佔位 X +2.25..+6.75、Y 3.85..25.95（長軸沿板長），**離 PCB 頂面高 5.40 mm**，本體寬 2.5 mm，腳往兩側伸出到 4.5 mm。DSI 接頭 J2 鏡射在 X -6.75..-2.25。
- **排線方向 [I]：直立式、由上方（+Z）插入。** 依據是 STEP 剖面：窄而高、兩側對稱焊腳、中央有槽，加上 wiki 照片中央是白色槽。這會直接影響機構高度，見第 6 節。
- 排線金手指朝哪一側 [U]。STEP 看不出夾片方向。KVM 引述 DFRobot 說法：銀色接點朝接點、藍色背膠朝黑色夾片（`firebeetle2_p4.defaults` 檔頭）。到貨看實物。
- I2C 上拉（GPIO7/8）[V]：**有，R18、R19 = 2.2K/1% 到 ESP_3V3**，SCH p2。C790 自己的上拉會並聯上去，另一位 agent 確認。

## 2. 電源

電源樹（SCH p3、p5）[V]：

```
U5 USB-C (CDC) VBUS = VUSB --[F1 PTC 1.5A/6V]--> VCC_5V
U8 USB-C (OTG) VBUS ------- 直接 ------------> VCC_5V
排針 VCC (P2-14) ---------- 直接 ------------> VCC_5V
VCC_5V --> U6 EM3485PDYG (EN 接 VIN，常開) --> ESP_3V3
ESP_3V3 --> U7 EM3485PDYG (EN=EN_DCDC，P4 控) --> ESP_VDD_HP (1.2V 標稱)
```

- **沒有任何二極體或負載開關隔離。[V]** 三個 5V 來源綁在一起，只有 CDC 路徑串一顆 PTC。OTG 路徑連 PTC 都沒有。
- U6 額定：原理圖 p5 註記 `Iout(max) = 1.5A`、`Default 3.33V` [V，只有原理圖註記]。查不到 EM3485 datasheet [U]。回授 44.2K/10K 配 FB=0.6V 算出來是 3.25V [I]。
- **只用 CDC 供電，OTG 接主機：板子能跑，但一定反灌。[V]** CDC 的 5V 經 PTC 到 VCC_5V，再直接出現在 U8 的 VBUS 腳，順著線進主機的 VBUS。
  - 主機開機時：兩組 5V 並聯，OTG 這側無限流。
  - 主機關機時：KVM 反向供電給主機的 VBUS 網路。
  - KVM 文件也寫明這點：VBUS 直接綁板子 5V，只靠目標供電時拔線會讓 KVM 重開（`firebeetle2_p4.defaults` 檔頭，`docs/BOARDS.md:270-273`）。
  - **板上沒有可斷開的元件。** 不反灌只有一條路：U8 與主機之間的線不接 VBUS（面板轉接或內部線剪掉 VBUS）。CC 與 D+/D- 保留。KVM 不需要 VBUS 感測，見第 3 節。
  - 同時注意：這樣接之後，主機關機時 P4 的 D+ 上拉仍在，會有微量漏電 [I]。

3V3 預算（**估算，未量測**）：

| 負載 | 平常 | 峰值 | 依據 |
|---|---|---|---|
| P4 核心，經 U7 轉換 | 130 mA | 170 mA | [I] 假設 1.2V 端 300-400 mA。P4DS 表 5-7 在 360 MHz 只給 123 mA（不含編碼器） |
| P4 內部 LDO：flash、PSRAM、MIPI、SD IO | 100 mA | 200 mA | [V] P4DS 表 2-11 每路上限 50 mA，共 4 路；平常值是 [I] |
| USB PHY、IO | 50 mA | 50 mA | [I] |
| C6 | 180 mA | 382 mA | [V] 峰值：C6-MINI-1 datasheet 表 6-4（802.11b）；OFDM/ax 為 251-316 mA。平常值是 [I] |
| TF 卡（有用才算） | 0 | 150 mA | [I] |
| **板上小計** | **約 460 mA** | **約 950 mA** | |
| C790 | 200-300 mA | 300 mA | 見下 |
| LCD + 背光 | 40-80 mA | 80 mA | [I] 2" 級面板，背光約 60 mA |
| **合計** | **約 700-840 mA** | **約 1.33 A** | |

- TC358743 用電 [V，datasheet p8，欄位依功率回推]：1080p60 共 543 mW，分別為 1.2V 共 182 mA、3.3V 88 mA、2.5V 13 mA、1.8V 1 mA。
- 換算成 C790 從 3V3 吃的電流 [I]：1.2V 用 LDO 約 285 mA，用 buck 約 180 mA。實際穩壓方式由 C790 那份調查定。
- **結論**：平常約用掉 U6 額定的 50%，最壞約 90%。**裕度不大。**
- **DFRobot 自己量的峰值很高** [V，WIKI]：5V 端 STA 平均 80 mA、峰值 1050 mA；AP 平均 130 mA、峰值 1330 mA（板子沒接任何外設）。換算到 3V3 已經接近或超過 1.5A，可能是瞬間啟動電流，但原因未說明 [U]。
- 5V 輸入：平常約 600-700 mA，峰值約 1 A [I]。**PC 的 USB-A 500 mA 不夠。** 需要 5V ≥ 1.5A，建議 2A 電源接 CDC 口（有 PTC 保護）。
- 背光電流建議不要從 3V3 排針直接拉超過 50 mA，改由 VCC_5V 經限流驅動 [I]。

## 3. USB

[V] SCH p1、p3，STEP：

| 接頭 | 位置 | 訊號 | P4 |
|---|---|---|---|
| U5 "USB CDC" | 板端（+Y），伸出 PCB 1.47 mm | USB1_P/N，各串 22R | GPIO25 / GPIO24，USB-Serial-JTAG（封裝腳 53/52）。**無 UART 橋接晶片** |
| U8 "USB 2.0 OTG" | 側邊（+X），開口約與板邊齊 | USB0_P/N，各串 22R | 專用 DP/DM（**封裝腳 50/49**） |

- **更正交辦的前提：** HS PHY 的 DP/DM 是封裝第 49、50 腳的專用腳，**不是 GPIO49/50**。GPIO49、50 是另外的腳（封裝腳 92、93），接到 P1 排針可自由使用。SCH p1 [V]
- CC 電阻：兩個接頭 CC1、CC2 都是 5.1K 到 GND（R28/R31，R41/R44）。USB-C UFP，device 模式可用 [V]。
- **VBUS 感測：沒有。** P4 沒有任何腳接 VBUS 分壓 [V]。
- 韌體不需要 [V]：`components/kvm_hid` 沒有設定 `self_powered` 或 `vbus_monitor_io`；`usb_hid.c:1877` 開機時用 `tud_disconnect` 重列舉來處理 VBUS 不掉的情況。
- 主機關機再開機時的列舉，靠韌體 watchdog 與 `tud_disconnect` [I]，沒看到專門在 VBUS 斷開線材上的實測。
- 每個 USB-C 的 D+/D-、VBUS 各有 TVS（D10-15）[V]。

## 4. GPIO

排針 [V]（SCH p1 + 尺寸圖 + STEP）：

```
P1 (X=-11.43，18 腳，Y=48.39 往下到 5.21):
 RST, 3V3, NC, GND, NC, 28, 29, 30, 8/SCL, 7/SDA, 48, 49, 50, 52, 4, 5, 37/TX, 38/RX
P2 (X=+11.43，14 腳，Y=38.23 往下到 5.21):
 VCC_5V, 3V3, GND, 32, 33, 51, 23, 22, 21, 20, 36, 35, 34, 31
```

KVM 的 `board_header.c:136` 把 P1 pin 3、5 標成 GND；原理圖與絲印是 NC，以原理圖為準（pin 3、5 無 net）。

未引出 [V]：0, 1, 2, 10, 11, 13, 24-27, 46, 47, 53。

可用腳（已扣板載功能）：

| GPIO | 電源域 | 注意 |
|---|---|---|
| 4, 5 | VDD_LP = 3V3 | 無 |
| 20-23 | VDD_IO_0 = 3V3 | 無 |
| 28-33 | VDD_IO_4 = 3V3 | 無。絲印 SCK/MO/MI/I3C 只是建議用途 |
| 49-52 | VDD_IO_6 = 3V3 | 無。ETH 關閉後 KVM 不佔用 |
| **48** | **VDD_IO_5 = ESP_LDO_VO4** | **電壓靠 LDO4，不是 3V3 直供。韌體開 LDO4 前不可靠。避開。** |
| 31 | VDD_IO_4 | 無 |
| **34** | VDD_IO_4 | 綁腳，JTAG 來源，預設浮接。可用但不建議接會拉電平的負載 |
| **35** | VDD_IO_4 | 綁腳 + BOOT 按鍵，弱上拉，R24 未上件。**不可用** |
| **36** | VDD_IO_4 | 綁腳，R3 10K 上拉到 3V3，控制 ROM 訊息。避開 |
| **37, 38** | VDD_IO_4 | 綁腳 + UART0。Overlay 走 USB-Serial-JTAG 所以韌體不佔，但開機 ROM 會輸出在 37。避開 |

- 電源域對應 [V]：P4DS 表 2-1 / 2-11，配 SCH p1 接線（VDDPST_1/2/4/6 接 ESP_3V3，VDDPST_5 接 ESP_LDO_VO4）。
- 綁腳 [V]：P4DS §3 列 GPIO34（JTAG）、35-38（開機模式）、36（ROM 訊息）。
- 只能輸入的腳：無。P4DS 表 2-1 所有 GPIO 都是 IO 型 [V]。
- MIPI 走 LDO_VO3（2.5V），KVM `kvm_board.h:17` 也用通道 3、2500 mV，相符 [V]。

建議腳位 [I]（避開以上全部，全部 3.3V 域）：

| 功能 | GPIO | 排針位置 |
|---|---|---|
| LCD CLK | 20 | P2 連續一排，旁邊就是 3V3、GND |
| LCD DIN | 21 | |
| LCD CS | 22 | |
| LCD DC | 23 | |
| LCD RST | 51 | |
| LCD BL | 33 | |
| ATX PWR | 49 | P1 連續，GND 在 P1-4 |
| ATX RST | 50 | |
| ATX LED | 52 | |
| C790 RESET（選配） | 31 | 非必要，見第 8 節 |
| 備用 | 4, 5, 28, 29, 30, 32 | 音訊 I2S 若要做，用 28/29/30 |

對應 KVM 選項：`KVM_DISP_SCLK_GPIO=20`、`MOSI=21`、`CS=22`、`DC=23`、`RST=51`；`KVM_ATX_PWR_GPIO=49`、`RST=50`、`LED=52`。

- **必須覆寫：** Kconfig 預設的 DC=26、ATX PWR=46、RST=47 都沒引出（`Kconfig.projbuild:94`、`:130`）。`firebeetle2_p4.defaults` 沒有覆寫這些。
- 背光沒有 Kconfig：`disp_bl` 預設 -1（`kvm_settings_table.c:1508`），要改程式碼預設或進 console 設定。

## 5. TF 卡

SCH p4 [V]：

- VDD = ESP_3V3 經 Q1 AO3401（P-MOS），閘極是 `SD1_PWRN`（GPIO45），R4 51K 下拉。**低電位導通，預設導通。**
- 訊號上拉：DAT0-3、CMD 各 51K 到 **ESP_LDO_VO4**（R35-39）。CLK 串 R40 0R，無上拉。
- IO 電源 VDD_IO_5 同樣接 ESP_LDO_VO4（SCH p1 註記 VO4 = 3.3V）。
- 卡偵測：M1 的 SWITCH 腳未接。
- D0-3 = 39-42，CLK = 43，CMD = 44（SCH p1 + wiki pins.png）。

對應 ESP-KVM（全部與預設相同）[V]：

| 選項 | 值 |
|---|---|
| `KVM_SD_PWR_GPIO` | 45（`firebeetle2_p4.defaults` 明寫） |
| `KVM_SD_PWR_ACTIVE_LOW` | y（預設） |
| `KVM_SD_IO_LDO_CHAN` | 4（預設，`Kconfig.projbuild:356`） |
| `KVM_SD_CD_GPIO` | -1（預設） |
| `KVM_SD_MAX_KHZ` | 40000（因 LDO 開啟） |

韌體作者的註記：這張板的 SD 設定「讀原理圖，尚未在此板跑過，卡跟不上會自動降速」（`CHANGELOG.md:1635` 附近）。**虛擬媒體在此板未實測。**

## 6. 高度與固定

來源：STEP 邊界框 [V]。高度都從各自 PCB 表面算起。

**頂面（離頂面）：**

| 零件 | 高度 |
|---|---|
| J1 / J2 FPC 接頭 | **5.40 mm** |
| K1 / K2 側按鍵 | 3.35 mm（底部 -0.5，X 超出板邊約 0.03 mm） |
| U5 / U8 USB-C | 3.21 mm（中板式，往下到 -1.0） |
| U6 buck | 1.40 mm |
| U4 麥克風 | 1.10 mm |
| U1 P4 | 1.00 mm |

**底面（離底面）：**

| 零件 | 高度 | 位置 |
|---|---|---|
| U3 ESP32-C6-MINI-1 | **2.40 mm** | X ±6.6，Y 0..16.6（與 datasheet 13.2×16.6×2.4 相符） |
| M1 TF 座 | 1.52 mm | Y 40.05..51.83，X -2.49..+12.66 |
| U7 buck | 1.40 mm | |
| Q1 AO3401 | 1.20 mm | |
| U2 flash | 0.75 mm | |

- 整體 Z：+5.40 到 -4.02，共 **9.42 mm**（PCB 1.62，不含排針與排線）。
- 直立排線要再加彎折空間。**頂面上方預留 ≥ 9-10 mm** 比較安全 [I]。
- TF 卡從 +X 邊插入（與 OTG 同側，上下相對）[I，依 STEP 與 layout.png]。
- 電感沒有獨立模型，U6/U7 群組內建；最高仍是 1.4 mm [I]。

**固定孔：**

- **只有 2 個孔，Ø2.0 mm，圓心 (±11.0, 58.3)。** [V] STEP 圓柱面 + 尺寸圖 22.0 mm（圖上 11.76pt 圓，用 22.0 標尺換算即 2.0 mm）。
- 離 USB 端邊 1.7 mm、離側邊約 1.7 mm。**天線端沒有孔**，板子是懸臂。
- STEP 裡 Ø3.0 @ (±11.2, 1.5 / 58.5) 是 **R1.5 板角圓角，不是孔** [V]。

**外形：**

- 25.4 × 60.0 mm，PCB 1.6（圖）/ 1.62（STEP）。
- 排針 Ø0.9 通孔在 X=±11.43（間距 22.86），pitch 2.54，首腳距天線端 5.21 mm。
- 另外在 X=±12.70 有半孔（郵票孔），也是 Ø0.9 [V]。

**STEP 模型：[V] 存在，免登入。** DFRobot 2026-06-17 才上傳（[論壇回覆](https://www.dfrobot.com/forum/topic/402278)），中文 wiki 還沒列，英文 wiki 有。本機副本沒有放進 repo：`b.step`（ASCII 檔名副本）、`bb.json`（所有零件邊界框，由 STEP 算出）。模型不含排針。

## 7. 天線

- 型號：**ESP32-C6-MINI-1-N4**，PCB 天線，4 MB flash [V]（SCH p7）。
- 位置：**PCB 底面，天線端（遠離 USB-CDC）** [V]。STEP 的屏蔽殼範圍 Y 6.03..15.97，因此 PCB 天線段約 **Y 0..6、X ±6.6**，貼齊板邊 [I]。
- 淨空：載板銅箔是否挖空，要 Gerber 才知道 [U]。layout.png 只看到天線走線在板邊。
- 頂面背對背：CSI/DSI 接頭從 Y=3.85 開始，**接頭末端壓在天線段的另一面**（X ±2.25..6.75）。這是原廠設計，無法改。排線與 C790 要往遠離天線的方向走 [I]。
- DFRobot 文件：**沒有任何機殼或金屬警告** [V，兩版 wiki 都查了]。
- Espressif 規範：[C6 Hardware Design Guidelines](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32c6/pcb-layout-design.html)：「A clearance of at least 15 mm is recommended in all directions」、機殼內天線要有足夠淨空 [V]。該章節沒有專門講金屬外殼。
- C6 燒錄點：底面 6 個測試點（C6_RX0、C6_TX0、C6_IO9、C6_RST、3V3、GND），SCH p7 [V]。**機殼設計要保留可達性**，理由見第 9 節第 2 點。

## 8. 韌體適配（ESP-KVM 0.77.0）

**ESP-KVM 已經官方支援這張板。** `boards/firebeetle2_p4.defaults`、CI 目標 `firebeetle2-p4`、[預編譯 manifest](https://fw.espkvm.io/firmware/firebeetle2-p4/manifest.json)（v.0.76.0，2.48 MB）[V]。

使用者 @Diego-fe 在 [issue #63](https://github.com/espkvm/espkvm/issues/63) 回報 capture、USB、Wi-Fi 都能動，0.56.2 上約 9 fps 1080p MJPEG [V]。但該 issue 沒提到 C790 型號（SYS_STATUS=0x9f 是 TC358743 暫存器，推論是 TC358743 類板子 [I]）。`board_header.c:159` 的 `BOARD_VERIFIED false` 與 README 的 tested 不一致，只是旗標沒更新 [I]。

| 問題 | 答案 | 證據 |
|---|---|---|
| 2-lane 972 Mbps | **支援，預設值** | [V] `Kconfig.projbuild:202`，`capture_hw.c:454-455`，`tc358743.c:319`；REFCLK 27 MHz 預設 |
| P4 v1.0 | 用預設 `REV_LESS_V3` + `REV_MIN_100`，**不要套 rev3 overlay**（兩邊映像不互通） | [V] `sdkconfig.defaults:10-11`，`firebeetle2_p4.defaults`「left at the base build's pre-3.0」 |
| 實際矽版本 | **DFRobot 說 v1.0，#63 回報 v1.3。** 只有 v1.3 被測過，v1.0 未測 | [V] 兩者都有出處；實際出貨版本 [U]，到貨讀 `esptool chip_id` |
| rev3 差異 | rev3：CSI 直出 YUV422、PSRAM 250 MHz、H.264 25-27 fps；pre-3.0：經 PPA 或 CPU 轉換、PSRAM 200 MHz、**1080p H.264 約 7 fps** | [V] `README.md:231`，`HARDWARE-NOTES.md:60-101` |
| Wi-Fi 腳位 | **完全相符**。P4 14-17/18/19、reset 54，esp-hosted preset `FUNC_BOARD`。#63 log 確認 CLK=18 CMD=19 D0-3=14-17 RESET=54 | [V] `firebeetle2_p4.defaults:62`，SCH p7，#63 |
| SDIO 上拉 | 板上沒有，韌體自動開內部上拉 | [V] SCH p7；`Kconfig.projbuild:400` |
| 原廠 C6 韌體 | `C6_v14_eco2_0022.bin`，esp-hosted-mcu `network_adapter` commit `83efce6-dirty`，slave 0.0.22，IDF v5.4-dev，2024-10-24 | [V] 我從 DFRobot 下載的 zip 裡讀出字串；與 `HARDWARE-NOTES.md:634` 相符 |
| 版本是否相符 | **主機 3.0.9、slave 0.0.0，log 報 major version mismatch 但可運作**，只能 streaming SDIO | [V] #63；`Kconfig.projbuild:530` 的 C6 OTA 預設關閉，因 3.0.9 的 aggregated 模式在影像下 stall |
| 關 Ethernet | `CONFIG_KVM_ETH_ENABLE=n`，此 overlay 已設 | [V] `firebeetle2_p4.defaults:60`；首次開機進 setup 熱點 |
| 顯示驅動 | I2C OLED（SSD1306/SH1106/SSD1315/SH1107）+ **SPI 只有 GC9A01**。**沒有 ST7789** | [V] `kvm_display.c:45-58`，`kvm_panels.c` |
| 解析度 / 版面 | **寫死。** GC9A01 `LCD_W/H=240`（`gc9a01.c:42-43`），ring/arc/chord 文字全按圓形（`:107`、`:130`、`:190`） | [V] |
| H.264 @ v1.0 | 開機探測，失敗退回 MJPEG。v1.3 上可用，**720p 可、1080p 約 6-7 fps**；v1.0 未測 | [V] `h264_probe.c`，`BOARDS.md:198`；v1.0 [U] |
| 360 / 400 MHz | pre-3.0 就是 360 MHz，無 400 選項；已測 v1.3 是 360 | [V] `HARDWARE-NOTES.md:15`，#63 |
| 16 MB flash | 有專用 `partitions_16mb.csv`（ota 4M×2、rescue 4M、storage 3.875M），2.48 MB 映像放得下 | [V] |
| 32 MB PSRAM | 假設 HEX 200 MHz，與 P4NRW32 相符；VDD_PSRAM 接 VO2=1.8V | [V] `sdkconfig.defaults:66-67`，SCH p1 |
| TC358743 reset | **可留 -1。** 開機只等 500 ms；TC358743 恢復走 hotplug_reset 而非硬重置 | [V] `capture_hw.c:130-168`、`:925-933`，`tc358743_bridge.c:101` |
| reset 不接的代價 | 晶片真的卡死時只能斷電；P4 軟重開不會斷 C790 的 3V3 | [I] 無實際回報案例 |

**加 ST7789 的工作量 [I]：約 1-2 天，加上實機除錯。** 全部在 C 層，看不到需要動 web 的地方（console 用 `disp_type` choices 動態產生，未細查）：

1. 新增 `components/kvm_display/drivers/st7789/st7789.c`：從 `gc9a01.c`（615 行）複製 `attach`/`flush`/`detach`，`esp_lcd_new_panel_gc9a01` 換成 IDF 內建的 `esp_lcd_new_panel_st7789`，補 `esp_lcd_panel_set_gap`。重寫 `render_status`、`render_splash`、`render_notice`、`draw_join_qr` 成矩形版面。拿掉 `ring`、`arc`、`TEXT_R`、`text_fit` 的圓形邏輯。
2. `kvm_panels.h`：enum 加 `KVM_PANEL_DRV_ST7789`。**`w`/`h` 是 `uint8_t`（`:22-23`），320 會溢位，要改 `uint16_t`。** 240×240、240×280 不受影響。
3. `kvm_panels.c`：**附加在陣列尾端**（index 存在 NVS）。
4. `kvm_display.c`：`s_drivers[]` 加一筆（`:45-58`）。
5. `kvm_config/kvm_settings_table.c`：`s_display_choices[]` 附加（`:72`）。SPI 腳位那幾列寫死 `.visible_val = 2`（`:1462-1511`，GC9A01 only），新型號看不到腳位欄，要改可見性判斷（`kvm_settings.h:60`）。
6. `CMakeLists.txt`：SRCS 加檔。
7. Kconfig：`KVM_GC9A01_SPI_HOST` 可直接共用。

## 9. 硬體阻礙，依嚴重度排序

1. **OTG VBUS 硬接 VCC_5V，無隔離。** [V] 外接電源與目標主機會直接並聯，主機關機時反灌。板上無法斷開。**必須**用不接 VBUS 的線或內部轉接。這不會讓功能失效，但照一般接法是實質風險。
2. **C6 韌體可能根本不能開機，而這張板 Wi-Fi 是唯一網路。** [V 為回報，未親測] [論壇](https://www.dfrobot.com/forum/topic/400107)：有人 dump 出原廠映像**被寫在 0x10000 而不是 0x0**，另有人回報收到時沒有韌體，DFRobot 則說出廠有預燒。我驗過正確映像：0x0 是 bootloader，0x8000 是分割表，所以偏移必須是 0x0。
   - 中招的話，setup 熱點、KVM 全部不通，只剩 USB-Serial log。修法是 USB-TTL 從底面測試點燒錄。
   - **同一串貼文警告：wiki 接線圖把 GND 與 IO9 畫反，並把 5V 接到 NC 測試點，照做板子會發熱。** 以 Test Points 圖為準，不接 5V。
   - 機殼要留出這 6 個測試點，或組裝前先驗。
3. **沒有 ST7789 驅動。** [V] 矩形 LCD 不能直接用，要移植（第 8 節）。不想改韌體就只能用圓形 GC9A01 或 I2C OLED。
4. **效能上限。** [V] 1080p 經 Wi-Fi 實測約 9 fps MJPEG；H.264 在 pre-3.0 約 7 fps。此板沒有 rev3 版本。對 KVM 可接受，但別期待 20+ fps。主因可能在 streaming SDIO + 舊 C6 韌體 [I]；升級路徑目前因 stall 被關掉。
5. **3V3 與 5V 裕度。** U6 只有 1.5A（且僅原理圖註記），加 C790、LCD 最壞約 90% [I]。DFRobot 量到的 5V 峰值已經超過 1A [V]。PC USB-A 供電不夠，需 2A 電源。建議到貨實測 3V3 壓降。
6. **天線與機殼。** 需要 15 mm 淨空 [V]，但板子小，天線朝下、貼板端，上方又壓著接頭與排線。金屬外殼或鋁底板會直接吃掉 Wi-Fi，而 Wi-Fi 是唯一鏈路。機殼形式由其他 agent 定，但這是限制條件 [I]。
7. **直立 CSI 接頭吃高度。** 5.40 mm 再加排線彎折，上方至少 9-10 mm [I]。若實物不是直立式則此點作廢，到貨先確認。
8. **只有 2 個固定孔且集中在 USB 端**，天線端懸臂。可用排針或半孔輔助固定 [V]。
9. **C790 無硬重置、無 VBUS 感測。** [V] 韌體都能接受，低風險。

**不是阻礙（已查證）：** CSI 腳序與 C790 排線相同、2-lane 972 Mbps、I2C 上拉、Wi-Fi 腳位、PSRAM/flash 配置、關閉 Ethernet、TF 腳位。

## 未解決（到貨才能確定）

- 實際 P4 矽版本（v1.0 或 v1.3）。
- C6 韌體是否在正確偏移。
- FPC 接頭料號與接點面方向。
- EM3485 真實額定。
- 載板天線區淨空。
- STEP V1.1.0 與原理圖 V1.0 的差異。
- SD 與 v1.0 上的 H.264 在此板皆未實測。
