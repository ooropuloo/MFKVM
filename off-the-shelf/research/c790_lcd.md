# MF KVM v3 研究：C790 與 SPI LCD 機構／電氣資料

調查日期 2026-11-06。只有資料，沒有實體量測。**手上還沒有實品，所有「照片推算」值都要到貨後用卡尺確認。**

標記：
- **[V]** 已查證：原廠圖、原廠 CAD、原廠文字或原始碼。
- **[V2]** 二手查證：第三方文件或原始碼轉述。
- **[P]** 照片推算：會寫比例尺。
- **[G]** 工程估計，沒有文件依據。
- **[?]** 未知。

## 來源

| 代號 | 來源 |
|---|---|
| G1 | https://wiki.geekworm.com/C790 （2026-07-29 版） |
| G2 | 尺寸圖 https://wiki.geekworm.com/images/1/12/C790-size.jpg |
| G3 | 介面與接腳圖 https://wiki.geekworm.com/images/d/db/C790-Interface-Description.jpg |
| G4 | 正反面照 https://wiki.geekworm.com/images/2/2c/C790-IMG-4490.jpg 、 https://wiki.geekworm.com/images/3/30/C790-IMG-4491.jpg |
| G5 | 含排線尺寸 https://geekworm.com/cdn/shop/products/C790-IMG-4491-size-1.jpg |
| G6 | 接排線照 https://wiki.geekworm.com/images/f/fd/C790-IMG-4493.jpg |
| E1 | https://github.com/espkvm/espkvm/blob/main/boards/firebeetle2_p4.defaults |
| E2 | https://github.com/espkvm/espkvm/blob/main/docs/BOARDS.md 與 boards/README.md |
| E3 | https://github.com/espkvm/espkvm/blob/main/docs/HARDWARE-NOTES.md |
| E4 | https://github.com/espkvm/espkvm/blob/main/components/tc358743/ （.c、.h） |
| W19 | https://www.waveshare.com/img/devkit/LCD/1.9inch-LCD-Module/1.9inch-LCD-Module-details-size.jpg 、STEP https://files.waveshare.com/upload/9/98/1.9inch_LCD_Module_3D.zip 、原理圖 https://files.waveshare.com/upload/7/7f/1.9inch_LCD_Module.pdf |
| W15 | 圖 https://files.waveshare.com/wiki/1.5inch-LCD-Module/1.5inch%20LCD%20Module.pdf 、STEP https://files.waveshare.com/wiki/1.5inch-LCD-Module/1_5inch-lcd-module.zip 、原理圖 https://files.waveshare.com/wiki/1.5inch-LCD-Module/1.5inch-LCD-Module-Schematic1.pdf |
| W147 | 面板規格 https://files.waveshare.com/upload/c/c5/SPEC_LBS147TC-IG01_VER_A.pdf 、STEP https://files.waveshare.com/upload/c/c5/1_47inch_lcd_module_asm-221122.zip 、原理圖 https://files.waveshare.com/upload/c/c5/1.47inch_LCD_Module_SchDoc.pdf |
| WC | 範例碼 https://files.waveshare.com/upload/8/8d/LCD_Module_code.zip |

STEP 的數值是我用 OCCT 讀檔後，算各零件 bounding box 與 z 切片得到的。

---

## C790

座標系（下面所有 C790 位置都用它）：從正面（TC358743 那面）看，**X=0 是 HDMI 短邊，X=45 是 FPC 短邊；Y=0 是 I2S／J4 那條長邊，Y=30 是對側長邊**。Z=0 是 PCB 正面。

照片比例尺：G4 孔距 30 mm = 845 px，23 mm = 650 px，所以 **28.2 px/mm**。照片有透視，高於 PCB 面的零件會偏大。

### 1. 外形與安裝孔

| 項目 | 值 | 標記 |
|---|---|---|
| PCB 外形 | 45 × 30 mm | [V] G1、G2、G5 |
| 安裝孔 | 4 × Ø2.75（M2.5 可過） | [V] G2 |
| 孔位 | X=3.5、33.5；Y=3.5、26.5（孔距 30 × 23，FPC 端邊距 11.5） | [V] G2 尺寸；Y 邊距 3.5 由 (30-23)/2 推得，圖上對稱 |
| 孔周露銅環 | 約 Ø6 | [P] G2 比例 16.44 px/mm |
| 圓角 | 約 R2.5 | [P] G2 |
| PCB 厚 | 約 1.6 | [G] 文件沒寫，要量 |
| 尺寸圖／STEP | 只有 G2 的 2D 外形，**沒有高度資料，也沒找到 STEP** | [V] 找過 G1、商品頁與網路搜尋 |
| 重量 | 10 g | [V] G1 |

### 2. HDMI

| 項目 | 值 | 標記 |
|---|---|---|
| 型式 | 全尺寸 Type-A 母座（標準 HDMI 線直插） | [V] G4、wiki 應用照 |
| 所在邊 | X=0 短邊，裝在正面 | [V] G2、G3 |
| 沿邊位置 | 寬 15.1，Y=7.4 到 22.6，置中 | [P] G2 比例 16.44 px/mm：Y 邊距 122 px = 7.44 |
| 懸出 PCB 邊 | **2.1 mm**（照片量得 2.6，受透視影響，以 G2 為準） | [P] G2 34 px |
| 佔 PCB 深度 | 殼體到 X≈7.6，尾端焊腳到 X≈10.1 | [P] G4 |
| 距 PCB 頂高 | 約 6（可能 5.6–6.5） | [G] 全尺寸座常見值；**照片無法量，要量** |
| 背面焊腳 | 背面四個長圓焊盤，X≈1.3–9.1，凸出估 ≤1.2 | [P] G4 焊盤位置；凸出高度是 [G] |

### 3. FPC 接頭

兩個接頭**都有焊上** [V] G3、G4。

| 項目 | 15-pin 1.0 mm（J2） | 22-pin 0.5 mm（J3） |
|---|---|---|
| 面 | 正面 [V] | 背面 [V] |
| 外形 | X≈38.1–43.6，Y≈4.6–25.1（20.5 × 5.5） [P] | X≈39–44.7，Y≈6.9–22.6（15.7 × 5.7） [P] |
| 排線方向 | 往 +X，越過 X=45 邊 [V] G6 | 往 +X [V] 照片 |
| 鎖扣 | 黑色活動條在 X=45 側（入口側）。滑扣或翻扣未判定 [P] | 同左 [P] |
| 接點方向 | 排線藍色補強朝上（背離 PCB），金屬接點朝下貼 PCB 側 [V] G6 | 同左 [P] |
| Pin 1 記號 | 三角形在低 Y 端（靠 I2S 那側） [P]，視為 pin 1 | 同左 [P] |
| 高度 | 約 2.5–3 [G]，要量 | 約 1.2–2 [G]，要量 |

**15-pin 接腳（J2）[V] G3，與 Pi 相同順序：**

| Pin | 訊號 | Pin | 訊號 | Pin | 訊號 |
|---|---|---|---|---|---|
| 1 | GND | 6 | CSID1_P | 11 | CAM_GPIO |
| 2 | CSID0_N | 7 | GND | 12 | **未接（圖上打叉）** |
| 3 | CSID0_P | 8 | CSIC_N | 13 | SCL0 |
| 4 | GND | 9 | CSIC_P | 14 | SDA0 |
| 5 | CSID1_N | 10 | GND | 15 | VCC（3.3 V） |

A1、A2 固定腳也是 GND。

- **15-pin 走 2 lanes：** D0、D1、CLK [V] G3 標註「15-Pin 2 channels output」。D2、D3 只在 22-pin。
- **能單用 15-pin：** ESP-KVM 就這樣用 [V] E2。FireBeetle 的 lane 順序跟 C790 一致，都是 2/3 D0、5/6 D1、8/9 CLK [V] E1。
- **兩個接頭的 lane 同名** [V] G3，應該是同一組走線，所以未插的 22-pin 是一段 stub。ESP-KVM 跑 972 Mbit/s/lane 沒回報問題 [V] E3。**22-pin 不要同時接東西。**

**CSI_IO0／IO1：**
- FireBeetle 的 CSI_IO0（pin 11）接 C790 CAM_GPIO。FireBeetle 那邊只有 10K 上拉，沒接 GPIO；IO1 的上拉沒焊 [V] E1。
- CSI_IO1（pin 12）在 C790 是未接 [V] G3，沒有作用。
- CAM_GPIO 在 C790 上是否直連 RESETN：**[?]**。原理圖只給接頭，RESETN 另外出在 J4-3。ESP-KVM 在其他板把 reset 接到 CSI 控制線 [V2] E2、E3，但沒有 C790 內部網表可證。
- **不驅動這兩條能否開機並回 I2C：可以。** E1 寫「there is no RESETN to drive. The C790 resets itself at power-on」，`CONFIG_KVM_TC358743_RST_GPIO=-1`，並記錄使用者在 issue #63 回報 FireBeetle 的 capture、USB、Wi-Fi 都可用，1080p MJPEG 約 9 fps [V2]。
- 代價：沒有硬體 reset。需要時可從 FireBeetle 空 GPIO 飛線到 C790 背面 J4-3（RST 孔）。

**排線種類：**
- C790 附的排線是**接點異面（opposite-side）**：G5 同一面看到一端藍補強、另一端裸接點 [P]。G6 也一致。Arducam 也說 Pi 預設排線是 opposite side [V2]。
- E1 明寫「A Geekworm C790 ribbon plugs straight in」，也轉述 DFRobot「銀色接點朝連接器接點，藍色朝黑色夾扣」[V2]。**所以買短線要買異面款。**

**短排線幾何（會短路，不可略過）[G，幾何推導]：** 排線內導體是直的，pin 對應只由板子擺法決定。C790 是「板面朝上時，沿排線往外看 pin 1 在右手邊、接點朝 PCB」。假設 FireBeetle 同慣例（**請對照 FireBeetle 那份研究確認**）：

| 擺法 | 異面排線結果 |
|---|---|
| 兩板正面同向疊放、接頭在同一端、排線 U 形折回 | pin 1 對 pin 1，正確 |
| 兩板正面相對、接頭相向、排線拉平 | pin 1 對 pin 1，正確 |
| **兩板正面同向並排、接頭相向、排線拉平** | **pin 1 對 pin 15：3V3 短到 GND。不可用** |

上電前必測：
1. FireBeetle 3V3 對 C790 背面 J4「3U3」孔應約 0 Ω。
2. FireBeetle 3V3 對 GND 不可短路。

### 4. 電源與其他

| 項目 | 值 | 標記 |
|---|---|---|
| 供電 | 3.3 V，由 FPC VCC 供，**不需外部 5 V，板上也沒有 5 V 腳** | [V] G1「Power: 3.3V」、G3；E3 確認 ribbon 帶 3.3 V |
| 3.3 V 腳 | J4-4（背面孔位，未焊排針）。推定與 FPC VCC 同網 | [V] 腳位；同網是推定 |
| 額定電流 | **Geekworm 沒寫** | [?] |
| 參考電流 | 同晶片的 Waveshare 19137 約 260 mA，C790 未量 | [V] https://www.waveshare.com/wiki/HDMI_to_CSI_Adapter |
| 晶片功耗 | 約 0.48 W（1080p30）、0.54 W（1080p60） | [V2] 搜尋摘要所引 datasheet 副本，未自行讀 PDF |
| I2C 位址 | 7-bit 0x0F | [V] E4 |
| I2C 上拉 | FireBeetle 端有 2.2K；C790 板上是否另有 [?] | [V] E1 |
| refclk | 27 MHz | [P] G4 晶振印 27.000；韌體值來自 Kconfig |
| EDID | 無 EEPROM 需求。韌體經 I2C 寫進晶片 EDID RAM（0x8C00），用 E-DDC 模式 | [V] E4 |
| 兩 lane 上限 | EDID 不可宣告超過約 81 Mpixel/s，所以 1080p60 不行 | [V] E3 |
| HDMI 反灌 | Geekworm 宣稱 C790 已解決 C779 的 back-power | [V] G1（僅廠商宣稱） |
| LED | 正面 X≈25–28、Y≈27 有一顆電源 LED，白殼會透光 | [P] G4 |

**其他會凸出的東西：**

| 零件 | 位置 | 標記 |
|---|---|---|
| I2S：J5，GH1.25-5P，臥式，開口朝 Y=0 外側 | 正面，X≈20.2–29.8，Y≈0–5，貼邊 | 型號 [V] G3；位置 [P] G4；高度約 4 [G] |
| J5 腳位 | 1 SCK、2 SD、3 WFS、4 OSCK、5 GND | [V] G3 |
| J4：5 孔 2.54 mm，**未焊排針**，不凸出 | X≈7.6、10.2、12.7、15.3、17.8，Y≈1.7 | 未焊 [V] G4；位置 [P] |
| J4 腳位 | 1 INT、2 IR、3 RESETN、4 3.3V、5 GND（背面絲印順序 INT、IR、RST、3U3、GND） | [V] G3 |
| 跳線、其他排針 | 無 | [V] G4 |
| 背面最高件 | 22-pin FPC（其餘只有 HDMI 焊腳） | [P] G4 |
| 組裝總高 | 約 9.6（6 + 1.6 + 2），容許範圍先抓 9–11 | [G] **要量** |

### 5. 已知問題

- **ESP32-P4 + C790 有實例，就是 ESP-KVM。** Waveshare P4-ETH 是參考組合，FireBeetle 2 有官方 build 與使用者回報 [V2] E1、E2。Geekworm wiki 也列 ESP32-P4-ETH 相容 [V] G1。
- **仿品：** E2 記錄「Run by a user with a C790 from AliExpress, no problems」。**沒查到 C790 仿品出問題的報告**，但也不代表沒有。
- **過熱／散熱片：** **沒查到針對 C790 的過熱報告或散熱片要求**；Geekworm 不附散熱片 [?]。估算板功耗約 0.9 W（260 mA × 3.3 V，用 19137 的數字），在密閉小盒會升溫，**建議開孔並到貨實測** [G]。BOARDS.md 提到某 P4-NANO 外殼可放 10×10×7 散熱片，文中沒說是給哪顆晶片。
- **4-lane-only：** C790 不是，15-pin 就是 2 lane。同系列 **X1300、X1301 只有 22-pin**，買錯就接不上 FireBeetle 的 15-pin [V] G1。
- **影像相關（屬韌體，簡記）：** 目標機休眠可能讓 USB 掉電 [V] E3；E1 記 FireBeetle 走 Wi-Fi 1080p MJPEG 約 9 fps。
- **ESP-KVM 目前沒有 ST7789 驅動：** repo 的 `components/kvm_display/drivers` 只有 GC9A01 與單色 OLED [V]。ESP-IDF 的 `esp_lcd` 有內建 ST7789 可接 [V2]。

---

## LCD

### 6. 尺寸總表

Z 基準：面板表面到模組最背面。PCB 都是 1.6 mm。

| 項目 | 1.9inch | 1.5inch | 1.47inch |
|---|---|---|---|
| 解析度／驅動 | 170×320 ST7789V2 [V] | 240×280 NV3030B [V] | 172×320 ST7789V3 [V] |
| PCB 外形 | **51.2 × 27.3** [V] | 35 × 28.5，R3.2 [V] | 38.5 × 22.0 [V] |
| 顯示區 AA | 42.72 × 22.70 [V] | 28.9 × 24.77 [V] | 32.35 × 17.39 [V] |
| AA 面積 | **970 mm²** | 716 mm² | 563 mm² |
| 像素間距 | 0.1335 [V] | 0.1032 [V] | 0.1011 × 0.1011 等效（規格 0.0337H 為子像素）[V] |
| 長邊 AA 邊距 | **6.25 / 2.23** [V] | 約 4.2 / 1.9 [P] 圖 10.57 px/mm | 約 4.08 / 2.07 [G，由下兩項組合] |
| 短邊 AA 邊距 | 2.30 / 2.30 [V] | 1.865 / 1.865 [V] | 約 2.3 / 2.3 [V，(22-17.39)/2] |
| 面板本體 | 50.16 × 25.81 [V STEP] | 33.45 × 26.77 [V] | 36.28 × 19.39 [V，STEP 為 36.36 × 19.51] |
| 偏光片頂面 | 49.17 × 24.80 [V STEP] | 30.7 × 26.27 [V] | 33.65 × 18.79 [V] |
| 面板在 PCB 上 | X 0.30–50.46，Y 0.75–26.56 | X 0.87–27.64，Y 0.20–34.25 | X 1.07–37.43，Y 1.25–20.76 |
| 安裝柱中心 | (2.8, 2.8)、(48.4, 2.8)、(2.8, 24.5)、(48.4, 24.5)，孔距 **45.6 × 21.7** [V] | 邊距 3.5，孔距 **21.5 × 28** [V] | (3.5, 3.47)、(35, 3.47)、(3.5, 18.52)、(35, 18.52)，孔距 **31.5 × 15.05** [V STEP] |
| 螺柱 | M2，OD 3.5，凸出 PCB 背 2.5 [V] | M2，OD 3.5，凸出 2.5 [V] | OD 3.5，凸出 2.5 [V] |
| 接頭 | **MX1.25 8P 臥式** [V wiki、STEP] | **GH1.25 8P 臥式** [V] | **PH2.0 8P 臥式**，另有排針孔 [V] |
| 接頭位置（STEP 座標） | X 12.5–17.6，Y 6.3–21.0 | X 20.1–25.3，Y 9.9–25.1 | X 9.25–29.25，Y 11.45–19.05 |
| 接頭開口 | **朝 X=0 短邊，距板邊 12.5** [V STEP] | 朝 X=28.5 長邊，距板邊 3.2 [P 圖] | 朝 Y=22 長邊，距板邊 2.95 [P 圖] |
| 接頭背凸 | 3.5（Z -3.911） | 3.3（Z -3.711） | **5.6**（Z -6.011） |
| 面板表面到 PCB 背 | 3.5 | 3.5 [V 圖] | 3.5 |
| **總厚（到接頭背）** | **7.0** [V STEP] | **6.8** [V STEP] | **9.1** [V STEP] |

1.9 的座標方向：從面板正面看，X 向右、原點在左下，與 W19 尺寸圖同向，6.25 那邊（FPC 轉折端）在 X=0。W19 圖面上的「3.50」「2.00」是螺柱外徑與 M2 螺紋，不是孔距邊距；由 2.80 + 45.60 + 2.80 = 51.2 與 STEP 孔位 (2.8, …) 交叉確認。

1.5 的 STEP 面板 Y 長 34.05 比圖面 33.45 多 0.6，應是含 FPC 轉折處，機構以圖面為準。

**1.9 背面其他零件（STEP）：** ZIF P1 X 36.3–42.8，Y 5.75–21.85，Z 到 -2.41。其餘 IC 不超過 -1.61。

### 電氣

三片架構相同 [V] 原理圖：**RT9193-33 LDO + 8 位元電平轉換**（1.9、1.5 用 TXS0108E，1.47 用 TXB0108）+ S8050 低側驅動背光（10 Ω 串聯）。

- **VCC 要接 3V3，不要接 5V。** 官方要求「電源與邏輯電壓一致」[V]。電平轉換 B 側 Vcc 接 VCC，P4 的 3.3 V 邏輯輸入 5 V 側不保證夠高 [G]。
- **背光預設亮：** BL 經 10K 上拉到 LCD_3V3 [V] 1.9 原理圖。拉低才滅，可 PWM。
- **接腳順序（絲印）：** VCC、GND、DIN、CLK、CS、DC、RST、BL [V]。1.9 原理圖的 P2 編號是反的：1 BL、2 RST、3 DC、4 CS、5 CLK、6 DIN、7 GND、8 VCC，編號順序與 wiki 表格列法相反，**接線一律照絲印** [V]。
- **背光電流：** 僅 1.47 有資料，3 顆白光 LED 並聯，If=60 mA、Vf 2.8–3.2 V [V] W147。實際由 10 Ω 限流：(3.3 - Vf - 約 0.1) / 10，Vf=3.0 時約 20 mA，Vf=2.8 時約 40 mA，上限不到 60 mA [G]。1.9、1.5 面板無公開規格 [?]，預算抓每片 ≤60 mA。面板本身 IDD 8–10 mA（1.47）[V]。
- **offset（廠商範例碼）[V] WC：**

| 型號 | 直向 | 橫向 |
|---|---|---|
| 1.9（170×320） | X+35，Y+0，MADCTL 0x00 | X+0，Y+35，MADCTL 0x70 |
| 1.47（172×320） | X+34，Y+0 | 範例未提供 |

  兩者都下 INVON（0x21）。`esp_lcd_panel_set_gap(35,0)` 或 `(0,35)` 對應 [V2]。1.5（NV3030B）offset [?]，沒查到；原廠範例要另外讀。

**裸 FPC 版本：**
- **Waveshare 沒查到賣裸屏** [?]。
- 1.47 面板本身是 Limito LBS147TC-IG01，19.39 × 36.28 × 1.46，12P，有完整圖 [V] W147，但採購管道未確認，且 VDD 上限 3.3 V、背光建議定電流。
- 1.9 模組內部是 24+2P ZIF 接面板 [V] 原理圖，可拆下裸屏，但面板無公開規格。
- 第三方 Cool Components 賣 1.9" 320×170 ST7789，頁面提到可裸用，需自行固定前框與背光 [V2]，未驗。

### 7. 建議：**1.9inch，長邊沿 65 mm 方向**

假設：外形 65 × 35，內寬 31.8，由此推壁厚 1.6，**內長 61.8 是我的假設**（請對照實際殼體）。

| | 1.9 | 1.5 | 1.47 |
|---|---|---|---|
| 寬度餘量 (31.8 - PCB 寬) / 2 | (31.8-27.3)/2 = **2.25** | (31.8-28.5)/2 = **1.65** | (31.8-22)/2 = **4.9** |
| 長度餘量 61.8 - PCB 長 | 61.8-51.2 = **10.6** | 61.8-35 = 26.8 | 61.8-38.5 = 23.3 |
| AA 佔頂面（2275 mm²） | 970 / 2275 = **42.6%** | 31.5% | 24.7% |
| 接頭開口到內壁 | 12.5（板內）+ 長度餘量 | 3.2 + 1.65 = **4.85**（整片貼對側也只有 6.5） | 2.95 + 4.9 = **7.85**（貼對側 12.8） |
| 拔插與走線 | **線可留在模組背面投影內** | 插頭加線彎需 ≥8 [G]，不夠 | 夠，但 PH2.0 大 |
| 總厚 | 7.0 | 6.8 | 9.1 |
| 驅動 | esp_lcd 內建 ST7789 | NV3030B 要自帶 init | esp_lcd 內建 ST7789 |

結論：
- **1.9 螢幕最大，也是唯一接頭開口朝短邊、線能留在板內的。** 接頭距板邊 12.5 mm 的空間讓 MX1.25 插頭與線彎都在背面投影內，再往 FireBeetle 走。
- 1.5 的 28.5 寬最擠，開口又朝長邊，排除。
- 1.47 最寬裕但螢幕最小、厚 2.1 mm。除非高度以外另有理由，不選。

**1.9 開窗與組裝注意：**
- AA 中心偏離 PCB 中心：長邊方向偏 (6.25-2.23)/2 = **2.01 mm** 往 X=51.2 那端。要 AA 在殼面置中的話，PCB 要反向偏 2.01；內長 61.8 放得下（餘量 10.6）。
- 開窗建議比 AA 每邊大 0.3（W147 註 9 的廠商建議，用於 1.9 為類比）：43.32 × 23.30。
- 背面淨空：接頭背凸 3.5，加面板表面到 PCB 背 3.5，共 7.0。MX1.25 插頭在座內，線從開口側出，下彎先留 ≥5 mm [G]。
- 用 M2 螺柱鎖固，凸出 2.5。

**連接器注意：** 1.9 官方寫 MX1.25，選型表亦同；PiShop 上架文字寫 GH1.25 線 [V2]。**兩者不互插**。原廠附線先確認，要延長或裁線時照實物。

---

## 15-pin 1.0 mm 短排線

| 來源 | 長度 | 接點 | 備註 |
|---|---|---|---|
| Würth **686715050001** | 50 mm | **異面**（DigiKey：Top on One Side, Bottom on Other） | 建議款；[V2] DigiKey 列標準交期 14 週，當下庫存未確認 |
| Würth 686615050001 | 50 mm | 同面（DigiKey：Top on Both Sides） | 這案不適用 |
| GCT 10-15-D-0050-C-4-08-4-T | 50 mm | DigiKey 列為上面異面款的替代品，頁面顯示 698 pcs | [V2] 替代關係來自 DigiKey，規格書未讀 |
| Geekworm 隨附 | 150 mm | 異面 | 只有這個長度，官方沒有短線 [V] G1 |
| 一般 Pi 線 | 常見 100、150、300 mm 起 | 多為異面 | [V2] 零售列表，**同型號的異面／同面標示不一，買時看照片：兩端藍補強在不同面才對** |

排線寬度 16 mm（15 × 1.0 + 1）[G，對照 G5]，開槽留 ≥17。

**最小彎曲半徑：** 沒查到這幾款的官方值 [?]。可參考：
- Teledyne FLIR 建議約 10 倍線厚 [V2]：https://flir.com/support-center/iis/machine-vision/knowledge-base/what-is-the-bend-radius-of-my-flex-cable
- Molex FFC 規格的測試條件是 180° 手折 R=4 mm、20 次 [V2]（SparkFun 論壇引述，不是設計下限）：https://community.sparkfun.com/t/smol-questions-regarding-ffc-cable-mounting/43424

**建模用值 [G]：** 靜態 R≥2，**建議留 R≥3**；不要在補強段彎折，也不要壓死摺。接頭出口先留 ≥5 mm 直段。這是 MIPI 高速線，折痕的影響未驗證，打樣後要實測畫面。

---

## 未知，到貨要量

1. C790：PCB 厚、HDMI 頂高、15-pin／22-pin 高度、I2S 高度、背面焊腳凸出、組裝總高。
2. C790：鎖扣型式與開鎖需要的空間；FireBeetle 的接點方向與 pin 1 側（決定擺法是否成立）。
3. C790：實際電流與 TC358743 溫度。
4. 1.5 的 offset、1.9／1.5 背光電流、MX1.25 附線實物。

## 風險

1. **短排線擺法錯會讓 3V3 短到 GND。** 上電前必做第 3 節的兩項量測。
2. **C790 高度全是估計值**，先別把殼體 Z 餘量壓死。
3. **FireBeetle 沒有硬體 reset 控制 C790**，要的話得飛線到 J4-3。
4. **1.9 模組的 AA 不置中**，開窗位置要照 2.01 mm 偏移算。
5. 密閉殼內 C790 約 0.9 W 的散熱未驗證。
