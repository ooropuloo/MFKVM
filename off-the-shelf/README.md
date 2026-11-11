# MF KVM 現成料版（off-the-shelf，第三版）

FireBeetle 2 ESP32-P4（DFR1172）核心板、Geekworm C790、Waveshare 1.9 吋 LCD、ATX 小板，全塑膠外殼。網路只有 Wi-Fi。

**狀態：只有設計，沒有下單，也沒有實品。** C790 的高度都是估計的上限值，到貨要先量。

| 項目 | 值 |
|---|---|
| 外形 | **75.0 × 38.05 × 26.73 mm，76 cm³**（`lay-board` 是 39 cm³，JetKVM Mini 是 41 cm³） |
| 擺法 | 排線斜捲一次，C790 順著核心板疊在上方，LCD 再疊上去。比較見 `layout_study.md` |
| 備案 | 扁 L 形，95 × 65 × 17 mm，實體 70 cm³，不用斜捲 |
| 查驗結果 | `case/case.log`、`case/asm/insert_path.json`、`case/handedness/test.log`、`fab_atx_b/verify_report.txt` |
| 頁面 | `v3.html`，單檔，底部有 build 字串 |

## 還缺什麼

**沒有下單，也沒有實品。** 外殼和 ATX 小板都只過了檔案層級的檢查，韌體只編譯過。下面每一項都要實物才能回答，到貨怎麼確認也列在「沒驗證，或還是估計值」。

### 買料和到貨驗證
- [ ] **買料：** 依下面的 BOM。Würth 排線查到的交期是 14 週，先確認庫存或用 GCT 替代料。接點異面和同面各買一條。
- [ ] **FPC 接點面：** J1 的接點方向只看過原廠 STEP 剖面（`case/j1_section.png`，含原廠模型，已撤下，見 THIRD_PARTY.md），不是實物。實物接點在 +x 就改用同面線。
- [ ] **pin 1 導通：** 插之前目視，插之後用電錶量上電檢查第 1 到 4 項。接反是 3V3 對 GND。C790 pin 1 的依據只是照片上的三角形。
- [ ] **C790 高度：** HDMI、J2、J3、J5 都是估計，總高取上限 11 mm。卡尺量完再對 `case/gen_case.py` 的尺寸，太高就要改殼。
- [ ] **針孔配合：** Ø0.64 銅線對 Ø0.9 孔，孔徑取自 STEP，實板沒量。

### 機構和訊號
- [ ] **45° FPC 斜捲：** 理論上每條線等長，但這個排線、這個半徑、972 Mbit/s 沒有人測過。排線路徑 41.7 mm，可用 42.0 mm，只剩 0.3 mm。先看 1080p 穩不穩，不行就改備案 B（`layout_study.md`）。
- [ ] **ATX 斜著裝入和公差：** `case/insert_path.py` 模擬 22 個姿勢都不碰，但 ATX 到 -X 牆只剩 0.30 mm，BOOT 凹槽約 0.6 mm，FDM 公差沒試過。先用裸板試裝，再焊 ATX。焊完就分不開。
- [ ] **試印：** 卡扣、舌片、開口、尾端溝槽（溝底剩 0.52 mm）都沒試印。`case/stl/` 建議 PETG。

### 功能
- [ ] **約 9 fps 夠不夠：** 上游 issue #63 有使用者回報 FireBeetle 走 Wi-Fi、1080p MJPEG 約 9 fps（韌體 0.56.2），輸入是 30 fps，我們沒量過。要實測後決定這個版本能不能接受，來源見 `research/firebeetle_firmware.md`。
- [ ] **ST7789 偏移和顏色：** gap X 0、Y 35、反相、RGB 來自廠商範例，沒上過真螢幕。還有 40 MHz SPI、旋轉、QR 能不能掃、GPIO33 背光。接頭 MX1.25 與 GH1.25 不互插，附線先確認。
- [ ] **不接 VBUS 的線：** 接錯線不會有症狀，KVM 的 5 V 會默默和主機並聯。每條線用之前都量（上電檢查第 5 項）。
- [ ] **散熱：** C790 約 0.9 W，有開孔，沒有量。長時間跑，量 TC358743 溫度。
- [ ] **塑膠殼裡的 Wi-Fi：** 排線距天線 7.1 mm，沒量過距離。比裸板和裝殼的 RSSI。C6 韌體和 v1.0 矽版的風險見 `research/firebeetle_firmware.md`。
- [ ] **ATX 修補上板驗證：** `firmware/patches/0002` 只編譯過。用示波器量 GPIO28、29 的開機和重開機瞬間，量測表在 `../lay-board/firmware/BUILD_v2.md`，同時要接真主機板測按鍵。
- [ ] **ATX 小板：** `fab_atx_b/` 還沒下單，CPL 旋轉角要看 JLC 預覽。

### 怎麼重新編譯韌體
上游 [ESP-KVM](https://github.com/espkvm/espkvm) commit `0893eef16c1cb16ff24cc4607f4d75f002ffa129`（tag `v.0.77.0`），依序套 `firmware/patches/0001-Add-ST7789V2-*.patch`、`0002-ATX-*.patch`。**這裡的 0001 是 ST7789 驅動，和 `lay-board` 的 0001 不是同一個修補。** ESP-IDF 用 v6.1。

```powershell
git clone --recurse-submodules https://github.com/espkvm/espkvm off-the-shelf\firmware\espkvm   # 這個路徑已列入 .gitignore
git -C off-the-shelf\firmware\espkvm checkout -b mf-v3-st7789 0893eef
git -C off-the-shelf\firmware\espkvm am <repo 絕對路徑>\off-the-shelf\firmware\patches\0001-Add-ST7789V2-170x320-landscape-as-a-build-time-SPI-p.patch <repo 絕對路徑>\off-the-shelf\firmware\patches\0002-ATX-never-leave-a-button-pressed-across-a-reset-or-f.patch
pwsh -File off-the-shelf\firmware\scripts\idf_build.ps1 -Name v3r2_st7789 -Defaults "sdkconfig.defaults;boards/firebeetle2_p4.defaults;../boards/mf_kvm_v3.defaults;../boards/mf_kvm_v3_st7789.defaults"
python off-the-shelf\firmware\scripts\check_sdkconfig.py off-the-shelf\firmware\espkvm\build.v3r2_st7789\sdkconfig off-the-shelf\firmware\boards\mf_kvm_v3.defaults off-the-shelf\firmware\boards\mf_kvm_v3_st7789.defaults
```

GC9A01 圓形螢幕把最後一層換成 `mf_kvm_v3_gc9a01.defaults`。改了 defaults 一定要用新的 `-Name`，既有 `sdkconfig` 會蓋過 defaults 而且不會警告。工具路徑用環境變數 `MFKVM_IDF_PATH`、`MFKVM_IDF_TOOLS_PATH`、`MFKVM_PYTHON_DIR` 覆寫，見 `firmware/scripts/idf_env.ps1`。

## BOM

| 數量 | 料件 | 備註 |
|---|---|---|
| 1 | DFRobot DFR1172 FireBeetle 2 ESP32-P4 | 只要核心板，不要 IO 擴充板 |
| 1 | Geekworm C790 | 不要買 X1300、X1301，它們只有 22-pin |
| 1 | Waveshare 1.9inch LCD Module | 接頭是 MX1.25 8P，附線到貨要確認 |
| 1 | Würth 686715050001，15-pin 1.0 mm，50 mm，接點異面 | 替代料 GCT 10-15-D-0050-C-4-08-4-T。Würth 查到的交期是 14 週，先確認庫存 |
| 1 | Würth 686615050001，同規格，接點同面 | 備用。只有 J1 實物的接點在 +x 側才用得到 |
| 1 | ATX 小板 rev B，11.05 × 35.4 mm | `fab_atx_b/`，JLC 打板加上件。舊版 `fab_atx/` 要飛線、零件本體間距也不足，沒有放進這個 repo |
| 5 支 | Ø0.64 mm 鍍錫單芯銅線（AWG 22），每支剪約 10 mm | ATX 直針。**不能用 2.54 排針的 0.64 mm 方針：**對角線 0.905 mm，孔只有 0.9 mm。排針的塑膠座也放不進 1.2 mm 的間隙 |
| 1 組 | JST SHR-06V-S 外殼、SSH-003T-P0.2 端子，或現成 SH1.0 6P 線 | 接主機板前面板 |
| 2 | 自攻螺絲 M1.6 × 5 | 核心板，孔只有 Ø2.0，所以不用 M2 |
| 1 / 1 / 1 | 自攻螺絲 M2.5 × 10、× 8、× 6 | C790 的 A、B、C 孔 |
| 2 | 自攻螺絲 M2 × 8 | 上蓋 |
| 8 條 | LCD 線 | 裁原廠附線。ATX 不用線 |
| 1 | 5 V 2 A USB-C 電源 | 插頭不可超過寬 13 mm、高 6.6 mm。電腦 USB-A 的 500 mA 不夠 |
| 1 | 不接 VBUS 的 USB 線 | 見下一節 |
| 1 組 | 列印件：`case/stl/` 的 tray、lid、bridge、former、atx_shim | 建議 PETG，因為上蓋的卡扣要有彈性。不用支撐。`atx_shim` 只在焊針時用，厚度要準，層高 0.2 mm |

沒有用到 C790 的 22-pin 和 I2S。LCD 的 4 顆 M2 銅柱也沒有用到，LCD 靠上蓋的 4 個卡扣固定。

## 主機 USB 的 VBUS

FireBeetle 的 OTG VBUS 直接接板上 5 V，中間沒有隔離。接普通的線，KVM 的 5 V 會和主機並聯，主機關機時還會反灌。

**決定：用拿掉 VBUS 的線，線上貼標籤。外殼上刻 HOST 和 NO VBUS。**

| | 不接 VBUS 的線（採用） | 內部 USB-C 轉接板 |
|---|---|---|
| 外殼 | 不變，38 mm 寬 | 寬 49 mm，外框體積多約 29% |
| 防呆 | 靠標籤，接錯線一樣能動 | 任何線都安全 |
| TF 卡 | 開口就在 USB 下方 | 被轉接板擋住，要從底部拿 |
| 其他風險 | 無 | 公頭對 U8 的公差、多一段高速走線 |

做法：USB-A 轉 C 線，把 A 頭第 1 腳貼 Kapton，或剪斷紅線。CC、D+、D- 都保留。韌體不需要 VBUS 感測。

**接錯線不會有任何症狀，所以每條線用之前都要量，見上電檢查第 5 項。**

## 排線

- **要買接點異面的線。** 異面線的 pin 1 會接到 pin 1。推導見 `layout_study.md`。
- **J1（FireBeetle）：** 直立式。接點面朝 -x，也就是朝 DSI 接頭。補強（藍色）朝 +x，也就是朝黑色滑扣。pin 1 在靠 P4 那端，有白點。
- **J2（C790）：** 接點面朝 PCB，補強朝上。pin 1 在靠 I2S 接頭那端。
- **J1 的接點方向來自原廠 3D 模型的剖面（`case/j1_section.png`，含原廠模型，已撤下，見 THIRD_PARTY.md），不是實物。** 如果實物接點在 +x，擺法不變，改用同面的線。插之前先用眼睛確認。
- **不要把線對折壓死。** 斜捲處用 `former` 撐住，半徑 3 mm。

## 接線

FireBeetle 排針孔的位置都以 STEP 為準。Y 是到天線端的距離。

| LCD 絲印 | FireBeetle | 排針孔 | Y (mm) |
|---|---|---|---|
| VCC | 3V3（不要接 5V） | P2 | 35.69 |
| GND | GND | P2 | 33.15 |
| DIN | GPIO21 | P2 | 17.91 |
| CLK | GPIO20 | P2 | 15.37 |
| CS | GPIO22 | P2 | 20.45 |
| DC | GPIO23 | P2 | 22.99 |
| RST | GPIO51 | P2 | 25.53 |
| BL | GPIO33 | P2 | 28.07 |

**ATX 小板不接線。** 5 支直針穿過小板的鍍通孔，再穿過核心板的排針孔，兩邊焊死。

| ATX 孔 | 網路 | FireBeetle P1 | Y (mm) | 韌體 |
|---|---|---|---|---|
| H1 | 3V3 | 第 2 腳 3V3 | 45.85 | |
| H2 | GND | 第 4 腳 GND | 40.77 | |
| H3 | ATX_PWR | 第 6 腳 GPIO28 | 35.69 | `KVM_ATX_PWR_GPIO=28` |
| H4 | ATX_RST | 第 7 腳 GPIO29 | 33.15 | `KVM_ATX_RST_GPIO=29` |
| H5 | ATX_LED | 第 8 腳 GPIO30 | 30.61 | `KVM_ATX_LED_GPIO=30` |

P1 第 1 腳（RST）不接。第 3、5 腳不放針：兩端的針已經撐出 15.2 mm 的跨距，多兩支幾乎沒有增加強度。而且原理圖寫 NC、ESP-KVM 的 `board_header.c` 寫 GND，實板是哪個還不確定。小板在這三個位置沒有開孔。GPIO28、29、30 是 3.3 V 電源域，不是綁腳，`board_reserved.c` 也沒有佔用。

P1 第 3、5 腳在原理圖上是 NC。LCD 排線順序請照絲印，原理圖的 P2 編號是反的。

| ATX JST 腳 | 主機板前面板 |
|---|---|
| 1 / 2 | PWR 開關 + / - |
| 3 / 4 | RST 開關 + / - |
| 5 / 6 | 電源 LED - / + |

韌體要覆寫的設定：`KVM_DISP_SCLK_GPIO=20`、`MOSI=21`、`CS=22`、`DC=23`、`RST=51`，`KVM_ATX_PWR_GPIO=28`、`RST=29`、`LED=30`，`disp_bl=33`。ESP-KVM 目前沒有 ST7789 驅動，要移植。

**第一次開機要到網頁設定打開螢幕和 ATX：** `disp_enable` 和 `atx_enable` 的預設值是 0。

## 組裝順序

1. **裝殼前先測核心板。** 只接 CDC，確認 C6 韌體、Wi-Fi、P4 版本。C6 韌體可能有問題，這時最好修。
2. 焊 LCD 8 條線到核心板 P2 排。線留長一點。
3. **把 ATX 小板焊到核心板。** 這一步做完就分不開了，先看清楚方向：
   - 兩塊板都正面朝上，ATX 在下面，絲印「AWAY FROM CORE」朝下。ATX 的 JST 在 USB-CDC 那一端、核心板外側。
   - `atx_shim` 夾在兩塊板中間，開口朝 USB-CDC 端，把間隙定在 1.2 mm。用夾子固定。
   - 對照 H1 到 H5 的絲印：3V3、GND、28、29、30 要對上核心板絲印的同名孔。**不要焊 RST 那一孔。**
   - 5 支針從核心板上面插到底。先焊核心板正面，再翻面焊 ATX 背面。
   - 剪針：核心板上方含焊點不超過 1.0 mm，ATX 背面含焊點不超過 0.78 mm。太長會碰橋架或底殼。
   - `atx_shim` 往天線端抽出來。**做上電檢查第 3、3a、3b 項。**
4. **放進 tray，要斜著放，不能垂直放。** 核心板加 ATX 總寬 34.27 mm，腔體 34.85 mm，y 42 的螺絲柱又懸在核心板 +X 邊上方。-X 側抬高約 45°，+X 邊先進，OTG 對準開口，BOOT 開關會進 +X 牆內側的凹槽。一邊放平一邊讓核心板貼近 +X 牆。`case/insert_path.py` 模擬這條路徑 22 個姿勢都不碰殼。放平後，用 2 顆 M1.6 × 5 鎖 USB 端。另一端靠底部的塑膠支點撐住。ATX 的 JST 會對準 -X 牆開口。
5. 排線插進 J1（接點朝 -x）並關上滑扣，用眼睛確認接點方向和 pin 1。
6. 放 `former`，排線沿它斜捲一次，用 Kapton 輕貼。不要壓死。
7. 把 `bridge` 放到 A 柱上，兩隻腳踩在核心板上。
8. 排線另一端插進 C790 J2 並鎖扣，C790 由上往下放，HDMI 落進端面開口。鎖 A（× 10）、B（× 8）、C（× 6）。D 角只是靠著，沒有螺絲。
9. **做上電檢查第 1 到 4 項。**
10. LCD 壓進上蓋的 4 個卡扣，插上 MX1.25 線。
11. 上蓋先把 -X 和 -Y 的舌片勾進槽，再蓋下 +X 側，鎖 2 顆 M2 × 8。

## 上電檢查

全部用電錶，不接電源。

| # | 量什麼 | 應得 |
|---|---|---|
| 1 | FireBeetle 3V3 對 C790 背面 J4「3U3」孔 | 約 0 Ω |
| 2 | FireBeetle GND 對 C790 背面 J4「GND」孔 | 約 0 Ω |
| 3 | FireBeetle 3V3 對 GND | **不可短路。** 排線接上後短路，是 pin 1 接到 pin 15，立刻拔線。排線接上前短路，就是 ATX 焊反或焊點連錫 |
| 3a | ATX：H1 對 3V3 孔、H2 對 GND 孔、H3、H4、H5 對絲印 28、29、30 | 約 0 Ω |
| 3b | H3、H4、H5 對 GND；H3、H4、H5 對 3V3；P1 第 1 腳 RST 對 H1 到 H5 | H5 對 GND 約 10 kΩ，H3、H4 對 GND 不應低於 470 Ω（有串 LED，可能量成不通）。其他都不通 |
| 4 | FireBeetle GPIO8 排針孔對 C790 J2 第 13 腳，GPIO7 對第 14 腳 | 約 0 Ω |
| 5 | 主機線的 A 頭 VBUS 對 C 頭 VBUS（A4） | **不通。** 通了就不能用 |
| 6 | 主機線的 D+、D-、GND | 兩端相通 |

然後：

7. 只接 5 V 電源，不接主機線。量 3V3，抓 3.2–3.4 V。摸 TC358743 和 U6，用手碰得住才繼續。
8. 接 HDMI，先確認有畫面，再測 MIPI 斜捲是否穩定。
9. 接主機線，確認 USB 列舉，主機關機時 KVM 不會讓主機亮燈。
10. 接 ATX 前用電錶確認開關腳導通一次。
11. 到網頁設定打開螢幕和 ATX，設定 PWR 28、RST 29、LED 30，再測開機鍵和重置鍵。

## 按鍵和維修

- **BOOT：** +X 牆的小孔。
- **RST：** -X 牆的小孔，要用 12 mm 以上的細針，會穿過一段空腔，在 ATX 零件上方經過。
- **ATX 插頭：** 從 -X 牆插入。推和拉的方向分別有核心板固定柱（0.60 mm）和外殼牆（0.30 mm）當擋塊，但碰到之前是 5 支針在受力，插拔時用手扶著。
- **C6 燒錄點：** 底部的開口。位置是從 DFRobot 底面圖估的，約 (-2, 18)、(-4, 18)、(-6, 18)、(-8, 18)、(-8, 16)、(-8, 14)，誤差可能到 0.5 mm。線序以 Test Points 圖為準，**不要接 5 V**。論壇回報 wiki 接線圖把 GND 和 IO9 畫反。開口在 y 12.8 到 19.4，ATX 從 y 29.65 才開始，裝好後還是碰得到，不用拆核心板。
- **天線：** 底部開了一個窗，天線下方是空氣。不要把盒子放在金屬桌面或機殼上，它離桌面只有約 1.5 mm。

## 沒驗證，或還是估計值

| 項目 | 現況 | 到貨怎麼確認 |
|---|---|---|
| MIPI 斜捲 | 理論上每條線等長，但這個組合沒有人測過 | 看 1080p 畫面是否穩定。不行就改備案 B |
| J1 接點方向 | 只看過 STEP 剖面 | 目視，再量上電檢查第 4 項 |
| C790 高度 | HDMI、J2、J3、J5 都是估計，總高取 11 mm | 卡尺量 |
| C790 pin 1 | 照片上的三角形 | 目視 |
| 排線長度 | 路徑 41.7 mm，可用 42.0 mm，插入深度是估計。餘量只有 0.3 mm | 試裝。如果太緊，稍微少插不行，要改殼 |
| 排線補強長度 | 假設露出 J2 不超過 4.5 mm | 量實物 |
| 散熱 | C790 約 0.9 W，有開孔，但沒有量 | 長時間跑，量 TC358743 溫度 |
| Wi-Fi | 排線距天線 7.1 mm，沒有量過距離 | 比裸板和裝殼的 RSSI |
| 3V3 餘量 | U6 1.5 A，最壞約用到 90% | 量壓降 |
| 列印公差 | 卡扣、舌片、開口都沒有試印 | 先印一次 |
| 插頭尺寸 | 5 V 凹槽只容納 13 × 6.6 mm 以內 | 試插 |
| 韌體 | ST7789 要移植，v1.0 矽版和 TF 都沒有人在這塊板上驗過 | 見 `research/firebeetle_firmware.md` |
| ATX 重開機安全 | `firmware/patches/0002` 修了按鍵途中重開機、放開後的上拉和設定順序，只編譯過。晶片重置到韌體設定腳位之間，韌體管不到 | 用示波器量 GPIO28、29，計畫見 `../lay-board/firmware/BUILD_v2.md` |
| ATX 小板 | 沒有打過，CPL 旋轉角要看 JLC 預覽 | 下單時看預覽 |
| ATX 零件本體 | `atx/tools/bodycheck.py` 用規格書最壞尺寸逐對算，每顆假設 ±0.1 mm 擺放誤差。JST 外殼公差、擺放誤差和焊點半徑是假設值，沒有旋轉誤差 | 看 JLC 上件預覽 |
| ATX 焊接後的間隙 | 1.2 mm 靠列印件，FDM 公差沒試過。底殼的肋比小板低 0.15 mm，所以焊點不受力 | 焊完量間隙 |
| 斜著裝入 | 模擬通過，零件用外框計算，比實物大。BOOT 凹槽處餘量約 0.6 mm。ATX 到 -X 牆 0.30 mm，假設 FDM 側向要 0.25 mm 以上，沒實測 | 先用裸板試裝，再焊 ATX |
| 針孔配合 | Ø0.64 銅線對 Ø0.9 孔，孔徑取自 STEP，實板沒量 | 到貨先試插 |
| 尾端溝槽 | 溝底剩 0.52 mm 塑膠，沒有試印 | 試印後透光看 |

## 左右方向

KiCad 的 y 朝下，直接當右手座標用會得到鏡像。v3 的殼、組裝和頁面都用 FireBeetle STEP 的右手座標。ATX 小板的 KiCad y 對應外殼的 -Y，所有要對準核心板的位置都走 `gen_atx.py` 的 `case_to_board()`。`case/pinmap_check.py` 拿 Gerber 和鑽孔檔對 STEP 的孔，逐孔比對網路和 0.1 mm 誤差，再把檔案改寫成鏡像、反排、轉 180°、換網路、差一格，全部必須失敗。`case/test_handedness.py` 用官方圖和原廠檔案逐項比對：上面朝上、CDC 朝外時，OTG 在右手邊。每項也拿鏡像資料跑一次，必須失敗。結果在 `case/handedness/test.log`，並排圖是 `case/handedness/official_vs_page.png`。

## 重新產生

需要 Python 3.11，裝 `cadquery`、`trimesh`、`shapely`、`networkx`、`pillow`。FireBeetle STEP 是 DFRobot 的檔案，**不在這個 repo**，來源見 `research/firebeetle_firmware.md`。`bb.json`、C790 圖、LCD 的 `lcd.stp` 也沒有放進來，所以 `case/gen_case.py`、`case/insert_path.py`、`case/test_handedness.py` 要先自己準備這些輸入。

`atx/fab_atx.py`、`case/pinmap_check.py`、`case/test_handedness.py` 用相對路徑匯入 `../lay-board/tools/`，所以兩個資料夾要留在同一個 repo。工具路徑和 `lay-board` 一樣用 `KICAD_CLI`、`KICAD_TOOL_HOME`、`FREEROUTING_JAR` 覆寫。`atx/out/` 只追蹤 `design.json`、`final.ses`，其他由 `atx/build_atx.sh` 重新產生。`case/gen_case.py` 的字型指向 `C:/Windows/Fonts/arialbd.ttf`，其他系統要改。

```
python layout_study.py                                # 比較表和 layout.json
sh atx/build_atx.sh                                   # 產生、布線、ERC、DRC
python atx/fab_atx.py atx/out fab_atx_b               # 任何檢查沒過就不出檔
python case/gen_case.py <fb.step> <bb.json>           # 殼、組裝、全部碰撞檢查
python case/insert_path.py <bb.json>                  # 焊好 ATX 的核心板能不能放進底殼
python case/export_core.py <fb.step>                  # 頁面用的核心板模型
python case/sections.py                               # 剖面圖，case/sections/（要先用原廠 STEP 跑 case/export_core.py，見 THIRD_PARTY.md）
python build_page.py                                  # v3.html，檢查沒過就不出檔
node case/page_top.cjs v3.html case/handedness <playwright-core>      # 從上方看頁面的真實網格
python case/test_handedness.py <bb.json> <fb.step> <layout.png> <C790 圖> <lcd.stp> case/handedness/page_top.json case/handedness/page_top.png
```
