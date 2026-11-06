# MF KVM v2 courtyard 警告實體審查

板子：`kicad/p4_kvm_mini.kicad_pcb`（sha256 `bd67d82c…`，**fab_r3**）。這份只有調查，沒有動 `gen_mini.py`、`out/`、`kicad/`、`fab*`、銅。DRC 在 scratch 複本重跑，結果相同：10 個 courtyard 重疊、1 個 starved_thermal、0 個未連接。

> **後續狀態（2026-11-06 補記）：** 這份描述的是 fab_r3。修法 A、B、D 已在 fab_r4 套用，fab_r5 保留。現行數字見 `../fab_r5/body_report.txt`。報告原由 builder `v2-courtyard` 撰寫，因寫檔被環境擋下，內容分段回傳後由主 session 依使用者同意存檔。

## 結論

1. **問的 10 對，實體本體都沒有相撞。** 最小本體間隙是 Y1 對 C17、C19 的 0.55 mm。
2. **J4/U11 是 MARGINAL，不是 COLLIDES。** 本體差 0.90 mm，但 U11 第 3 腳的腳尖離 J4 塑膠後壁只有 0.155 mm，兩顆加起來 0.2 mm 的放置誤差就會碰到。插頭從 +y 進來，到 U11 還有 3.97 mm，不會撞。
3. **DRC 沒報的才是真問題。** 用 datasheet 外形掃全板，找到 3 對本體重疊和 1 對只差 0.025 mm，都沒有出現在 DRC 警告裡：

| 新發現 | 重疊或間隙（標稱） | 依據 | 圖 |
|---|---|---|---|
| **U10 / U11** | **重疊 0.25 x 4.40 mm**（最壞 0.55） | LITE-ON 3.85±0.3，兩顆中心距只有 3.6 | [圖](img/extra_A_U10_U11.png) |
| **U12 / L1** | **重疊 0.125 x 1.40 mm** | LITE-ON 3.85；Sunlord 4.0±0.2 | [圖](img/extra_B_U12_L1.png) |
| **U4 / Q1** | **重疊 0.21 x 0.45 mm**，兩顆都取最小尺寸仍重疊 0.075 mm | TI DBV0005A；Q1 用 JEDEC TO-236（AOS 規格書沒有外形頁） | [圖](img/extra_C_U4_Q1.png) |
| C11 / U10 | 間隙 0.025 mm，公差內會碰 | LITE-ON、Samsung | [圖](img/extra_D_C11_U10.png) |

原因：`gen_mini.py` 的 `bbox()` 只用焊盤加 0.1 mm 算 courtyard，沒有傳 `body` 的零件不含本體。光耦本體在 y 方向是 ±1.925，courtyard 只有 ±1.69；SOT-23-5 本體在 x 方向是 ±1.45，courtyard 只有 ±1.35。

**這三對重疊不解決，v2 不能下 PCBA。** U10/U11 兩顆標稱就壓在一起，後放的那顆會墊在前一顆上，腳浮起來變空焊或歪斜。

公差說明：U10/U11 在兩顆都取最小本體（3.55）時還有 0.05 間隙（未計放置誤差），U12/L1 有 0.125。所以這是標稱和最壞情況下的碰撞，不是所有公差下都碰。Q1 的尺寸來自記憶中的 JEDEC 值，未開原文，U4/Q1 這一對要拿實料或 AOS 外形確認。

## 10 對總表

全部都在 B 面，同面才有相撞問題。單位 mm。放置誤差假設每顆 ±0.10，**這是假設**，JLC 沒有公布數字。「最壞」是兩顆都取最大實體尺寸，再扣兩顆的放置誤差；負值代表公差內會碰。JLC 門檻來自 [Minimum Spacing for SMD Components](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)，是建議最小值。[量法](sources/jlc_spacing_measure.png)：沿引腳方向量焊盤到焊盤，其他方向量本體到本體。

| 對 | courtyard 重疊 | 本體間隙 | 本體或腳到對方的金屬間隙 | 最壞 | 不同網路焊盤間隙 | JLC 門檻 | 判定 | 實際會出什麼事 |
|---|---|---|---|---|---|---|---|---|
| [U11/J4](img/pair_01_U11_J4.png) | 1.65 x 1.27 | **0.90** | U11.3 腳到 J4 塑膠 **0.155** | **≤ -0.20** | 0.15（RST_E / PWR_C） | 無對應（連接器） | **MARGINAL** | 腳尖可能頂到 J4 後壁；U11.3 焊盤離塑膠只有 0.035；0.15 的錫橋會讓 RST 和 PWR 串線 |
| [C11/U5](img/pair_02_C11_U5.png) | 2.56 x 0.03 | 1.25 | 腳到電容 0.65 | 0.25 | 0.175（GND / V2V5） | 0.2 | MARGINAL（規則） | 本體不會碰；低於 JLC 門檻 0.025，有輕微錫橋風險 |
| [C19/Y1](img/pair_03_C19_Y1.png) | 0.82 x 0.03 | 0.55 | 0.55 | 0.25 | 0.188（GND / OSC_VDD） | 無對應（振盪器） | MARGINAL（錫膏） | 本體不會碰；Y1 焊盤比端子大，多的錫膏靠近 C19 |
| [C40/J7](img/pair_04_C40_J7.png) | 0.23 x 0.22 | 0.81 | 焊盤到 J7 外殼 0.46 | 0.37 | 2.25 | 無對應（連接器） | **OK** | courtyard 是誤報；卡片不經過 C40（[圖](img/pair_04b_J7_card.png)） |
| [R52/R42](img/pair_05_R52_R42.png) | 0.02 x 0.12 | R42 不焊，無本體（若焊 0.73） | 無 | 若焊 0.31 | 0.197 | 0.15 | **OK** | R42 有 B.Paste，不焊也會留兩顆錫點，焊盤間距 0.40，應該不會短路 |
| [R53/C41](img/pair_06_R53_C41.png) | 0.02 x 0.32 | 0.70 | 0.70 | 0.35 | 0.18 | 0.15 | **OK** | 無 |
| [Y1/C17](img/pair_07_Y1_C17.png) | 0.82 x 0.03 | 0.55 | 0.55 | 0.25 | 0.165（GND / VDD_MIPI） | 無對應（振盪器） | MARGINAL（錫膏） | 同 C19，是 10 對裡次小的焊盤間隙 |
| [U10/R22](img/pair_08_U10_R22.png) | 0.01 x 0.82 | 2.40 | 腳到 R22 1.10 | 0.70 | 0.19（PWR_LED / 3V3） | 0.4 | MARGINAL（規則） | 本體不會碰；光耦焊盤比腳尖長 0.65，AOI 或錫膏上可能被標記 |
| [U10/R23](img/pair_09_U10_R23.png) | 0.01 x 0.82 | 2.40 | 腳到 R23 1.22 | 0.85 | 0.389（GND / 3V3） | 0.4 | MARGINAL（只差 0.011） | 實務上可接受 |
| [U4/C10](img/pair_10_U4_C10.png) | 2.56 x 0.03 | 1.25 | 腳到電容 0.65 | 0.25 | 0.175（3V3 / GND） | 0.2 | MARGINAL（規則） | 同 C11/U5 |

J4/U11 的「最壞」值是 lead 取 pitch +0.25、寬度上限，J4 取假設公差 ±0.1。只算放置誤差、零件取標稱時，0.155 - 0.20 = -0.045，也會碰。圖和數字已逐張對過，一致。

## J4 / U11 詳細

- **J4 真實外形（[JST eSH](https://www.jst-mfg.com/product/pdf/eng/eSH.pdf) p1、p3）：** B = 8.0、深 4.25、腳伸出 0.7、高 2.9（配合後 2.95）。外形前緣在固定片焊盤外緣內側 0.2。換到板上是 x -7.7 到 0.3、y 15.225 到 19.475。官方 KiCad F.Fab `(-4,-1.675)-(4,2.575)` 完全相同。
- **`gen_mini.py` 的 J4 body 寫錯：** `(-4,-1.3,4,3.28)` 的 3.28 是官方 courtyard 的值，不是本體。J6 的 `(-5,-1.3,5,3.28)` 同樣有這個問題。所以 J4 真實前緣在板內 0.525 mm，不是伸出板邊 0.18 mm。
- **固定片（J4.7）：** 離 U11 本體 2.40 mm，不是問題。
- **插頭（[圖](img/pair_01b_J4_plug.png)）：** eSH p2，SHR-06V-S 寬 7.0，SHR-06V-S-B 含凸耳寬 9.0。p1 的 (6.25) 是參考值，判讀為配合後插頭後緣超出 J4 前緣 2.0，也就是 y 21.475，落在牆內（內壁 20.4、外壁 22.0）。插頭掃過的區域內外 1.5 mm 沒有其他 B 面零件，離 U11 本體 3.97 mm。
- **外殼：** `case/check_report.txt` 的開口寬 9.2。`check_case.py` 用「8 寬」檢查，實際是 7 或 9。9.0 的版本每邊只剩 0.1，**建議線束用 SHR-06V-S（7.0）**。

## J7 卡片行程

[Molex SD-104031-001（LCSC 副本）](https://datasheet.lcsc.com/datasheet/pdf/541e9f28cb856b9ee4390625509ae3af.pdf) sheet 1：11.95±0.15 x 11.40±0.15 x 1.42±0.15，**push-pull**，圖上沒有彈出機構；卡片從焊盤那一側進入，插好後露出 4.0±0.2。卡片內端停在外殼內，C40 不在路徑上，圖上也沒有懸出外殼的金屬朝向 C40。

外殼前緣在 x -19.5，卡片尖端在 -23.5，只比外牆（-22.0）多 1.5 mm。push-pull 要靠指甲或鑷子拉出來，**建議用實物試一次**。

## courtyard 本身對不對

| 零件 | courtyard | 真實外形（含腳） | 判斷 |
|---|---|---|---|
| OPTO_SO4（U10/11/12） | y ±1.69 | y ±1.925 | **太小，漏報 U10/U11、U12/L1** |
| SOT-23-5、SOT-23 | x ±1.35 | x ±1.45（TI 另註最多 0.25 溢膠） | **太小，漏報 U4/Q1** |
| IND4020（L1） | y ±1.95 | y ±2.0 | 略小 |
| JST_SM06B（J4） | y 到 +3.38 | y 到 +2.575（焊盤到 +2.775） | 前方多 0.6，後方由焊盤決定 |
| J7 | 矩形含空角 | 角落 (-8.1, 10.095) | 右下角是 bbox 空角，**C40 警告是誤報** |
| 0402、0603、OSC3225 | 焊盤 + 0.1 | 都在內 | 正確，但邊距小，所以多數警告只差 0.01 到 0.03 mm |

**10 個警告裡，只有 J4/U11 反映真實的接近問題，其他只是邊距算出來的。真正相撞的 3 對完全沒有警告。**

## J5 starved_thermal：無害，不用修

A1B12（GND，F.Cu）在 (111.5975, 105.7)：

- 銅連接有一條 0.25 mm 花焊盤，加上一條 0.15 x 1.45 mm 的走線到外殼 PTH。少掉的一條花焊盤在靠 5V 走線與 via 那一側，推測是被它們擋掉。對應的 B1A12 有兩條花焊盤加同樣的走線。
- **焊接：** 花焊盤少代表散熱更少，比較好焊，不是壞事。
- **電流：** 以 SY8089 2 A 全載估，5V 輸入約 1.55 A（估算，假設效率 85%）。GND 由 A1B12、B1A12 和外殼分擔，單腳最多約 0.8 A；0.25 mm 那條 spoke 長 0.2 mm，約 0.2 mΩ，壓降和溫升都可以忽略。實際負載應該更低。
- **未驗證：** 沒有實測，只是 1 oz 銅的計算。

## 修法，依影響範圍排序

任何銅的改動都要重跑全部關卡：ERC、DRC、`verify.py`、`maskcheck.py`、`holecheck.py`、`check_case.py`、`fab_pack.py`，並出新的打板包。

**A. U10、U11、U12 換成 2.7 mm 寬的 SSOP-4（主要建議），[預覽圖](img/fix_A_ssop_preview.png)**

[Everlight EL3H7-G](https://datasheet.chipsmall.com/EL3H7-VG/600647.pdf) 頁碼 7：4.40±0.2 x 2.70±0.2，pitch 1.27，跨距 7.00±0.3，建議焊盤 1.5 x 0.6，內距 4.85、外距 7.85。料號用 [EL3H7(C)(TA)-G C92243](https://jlcpcb.com/partdetail/EverlightElec-EL3H7_C_TA_G/C92243)：JLC Extended，SSOP-4-1.27mm，CTR 200-400%，和現用 LTV-357T-C 同一級。

**零件中心都不動**，算出來的結果：

| 對 | 現在 | 換後 |
|---|---|---|
| U10/U11 本體 | 重疊 0.25 | **間隙 0.90** |
| U12/L1 本體 | 重疊 0.125 | **間隙 0.45** |
| C11/U10 本體 | 0.025 | 0.60 |
| U11 腳到 J4 塑膠 | 0.155 | 0.79 |
| U11/J4 焊盤 | 0.15 | 0.375 |
| U10/R22、R23 焊盤 | 0.19、0.39 | 0.415、0.415 |

- 一次解掉 J4/U11、U10/R22、U10/R23、U10/U11、U12/L1、C11/U10。
- 腳位功能相同（1 陽極、2 陰極、3 射極、4 集極），但 pitch 不同（1.27 對 2.54），**不是 footprint 相容**。
- 要改：一個 footprint、BOM 一行、12 個焊盤周邊的短走線。網路有 PWR_C、PWR_E、PWR_LED、RST_C、RST_E、RST_LED、LED_IN、LED_K、ATX_LED、3V3、GND。
- 附近最近的訊號只有 U10 旁的 I2C_SCL、I2C_SDA。TC358743（U7，y ≤ -1）和 TMDS、CSI 都在很遠的地方，**不會碰到高速走線**。
- **電氣（計算，未實測）：** VF 規格相同，R52、R53 不用改，IF 約 4.0 到 4.5 mA；VCEO 從 35 V 提高到 80 V。ESP32-P4 的 VOH 與單腳電流、主機板上拉電流都沒有查證。
- **換之前要確認：** JLC 實際庫存；走線能否繞通；用實際 ATX 前面板針腳測一次。

電氣細節（計算，未實測）：GPIO4、GPIO5 經 470 Ω（R52、R53）驅動 LED。VF 1.2 典型、1.4 最大（都在 20 mA 規格），3.3 V 高電位時 IF 約 4.0–4.5 mA。若 VOH 為 2.64 V（當時的假設），IF 約 3.1 mA。C 檔最低 CTR 下，以 5 mA 的 CTR 值估算，光電晶體在 4 mA IF 約可流過 8 mA，但沒讀 CTR 對 IF 曲線。主機板 PWR/RST 上拉電流未知，假設小於 5 mA。VCE(sat) 只規定在 IF 10 mA、IC 1 mA（最大 0.2 V），這個工作點未規定。U12 不是 GPIO 驅動：LED 由主機板 LED 針腳經 R54 270 Ω 驅動，輸出經 R55 10k 接 3V3，約 0.33 mA。結論：同 CTR 等級和 VF 規格，應不比現況差，但仍要接真實 ATX 前面板測。

**B. U4 往 +x 移 0.7 mm，到 (0.5, 5.2)（必做，A 解不了這對）**

- U4/Q1 本體間隙變 0.49，U4/U5 變 0.40。Q1 尺寸來自記憶中的 JEDEC 值，未開原文。
- 要改 3V3、GND、V2V5 三條短線，旁邊有 SD_PWR_N。
- **Q1 往左移不可行：** 移 0.5 就會壓到 R44、R45 焊盤。

**C. C10、C11 往 +y 移 0.05，C17、C19 往 +y 移 0.1（可選，A 做完才有空間）**

- 焊盤間隙變 0.225（U4、U5）、0.265（Y1）。C17、C19 移動後，幾何檢查沒有撞到別的網路銅。
- C10、C11 的移動必須在 A 之後：現況移了 C11 會壓到 U10 本體。
- 不做也可以，交給 CAM 判斷。

**D. 修 `gen_mini.py` 的 courtyard（不動銅，建議和 A、B 一起做）**

給 OPTO、SOT-23-5、SOT-23、L1 真實 `body`，修正 J4、J6 的 body。這樣 DRC 才看得到這類碰撞。這一項不解決任何實體問題，但會讓後面的警告有意義。

**不採用：不換料、直接移動 U10、U11、U12。** 試算 U10 +0.3y、U11 +0.85x +1.05y、U12 +1.2x +0.2y、L1 和 U2 -0.5y，加上修短焊盤，仍然撞到 C62，也太靠近 R54，要動 5 顆零件、十多條網路和 buck 迴路。只把 U12 往左移 1.75 也會離 R54、R55 太近。

## 來源

| 零件 | LCSC → MPN | 來源 | 用到的值 |
|---|---|---|---|
| J4 | C160405 → SM06B-SRSS-TB(LF)(SN) | [JST eSH](https://www.jst-mfg.com/product/pdf/eng/eSH.pdf) p1、p3（[land](sources/jst_eSH_p1_land.png)、[header](sources/jst_eSH_p3_header.png)）；[KiCad 官方](https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/master/Connector_JST.pretty/JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal.kicad_mod) F.Fab | 8.0 x 4.25 x 2.9，腳 0.7 |
| 插頭 | SHR-06V-S(-B) | [eSH p2](sources/jst_eSH_p2_plug.png) | 7.0 或 9.0 x 5 x 2.8 |
| U10-12 | C119091 → LTV-357T-C | [LCSC 本 p2](https://datasheet.lcsc.com/datasheet/pdf/19537dc919c84021962b2f5e5f031337.pdf)（[圖](sources/liteon_ltv357t_p2.png)）、[新版](https://cdn.eicom.ru/media/PDF/5723357.pdf) 第 2 頁（[圖](sources/liteon_ltv357t_newer_p2.png)）、[建議焊盤 p11](sources/liteon_ltv357t_p11_land.png) | 4.40±0.2 x 3.85±0.3 x 2.00±0.2，跨距 7.00 +0.2/-0.7，pitch 2.54±0.25 |
| J7 | C585350 → 1040310811 | [Molex](https://datasheet.lcsc.com/datasheet/pdf/541e9f28cb856b9ee4390625509ae3af.pdf) sheet 1（[圖](sources/molex_SD-104031-001_sheet1.png)） | 見上 |
| Y1 | C725995 → OT322527MJBA4SL | [YXC YSO110TR](https://datasheet.lcsc.com/datasheet/pdf/b336a5b52993e15e0134a8f3d7decec7.pdf) p3（[圖](sources/yxc_yso110tr_p3.png)） | 3.2±0.1 x 2.5±0.1 x 1.2 max |
| U4、U5 | C882825、C2871228 → TLV73325PDBVR、TLV73312PDBVT | [TI DBV0005A](https://www.ti.com/lit/ds/symlink/tlv733p.pdf) PDF p35（[圖](sources/ti_dbv0005a.png)） | L 2.75-3.05，W 1.45-1.75，跨距 2.6-3.0，溢膠 ≤ 0.25 |
| R22/23/42/52/53 | C25879、C17168、C25117 → 0402WGF… | [UNI-ROYAL](https://datasheet.lcsc.com/datasheet/pdf/0a975aaa49b7c97f38a963127be4a823.pdf) p4 | 1.00±0.10 x 0.50±0.05 x 0.35±0.05 |
| C17、C19 | C1537 → 0402B471K500NT | [FH](https://datasheet.lcsc.com/datasheet/pdf/09fe2daf22580a99fa7fea93ccb20fb7.pdf) 第 3 頁（PDF p5）CA 列 | 1.00±0.05 x 0.50±0.05 x 0.50±0.05 |
| C41 | C1525 → CL05B104KO5NNNC | [Samsung](https://datasheet.lcsc.com/datasheet/pdf/02336ea48ea44ca18c72517dd3cb7b47.pdf) p6 | 0402 |
| C10、C11、C40 | C19702 → CL10A106KP8NNNC | 同上 | 1.60 x 0.80 x 0.80，±0.10 |
| L1 | C83423 → SWPA4020S2R2MT | [Sunlord SWPA 系列](https://static.chipdip.ru/lib/172/DOC013172777.pdf) p2（不在 sources/） | 4.0±0.2 x 4.0±0.2 x 2.0 max，系列表，非單一料號頁 |
| 修法 A | C92243 → EL3H7(C)(TA)-G | [EL3H7-G](https://datasheet.chipsmall.com/EL3H7-VG/600647.pdf)（[圖](sources/everlight_el3h7g_pkg.png)）、[JLC](https://jlcpcb.com/partdetail/EverlightElec-EL3H7_C_TA_G/C92243) | 見修法 A |
| JLC 規則 | | [spacing](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)、[capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities) | 表內門檻；放置精度沒有公布 |

**找不到，用標準值或假設（都有標示）：**

- **Q1 AO3401A：** LCSC 上的 AOS 規格書沒有外形頁，用記憶中的 JEDEC TO-236 值，未開原文：D 2.80-3.04（模型取 2.92），E1 1.20-1.40。依這組值，TI 最小 2.75 + Q1 最小 2.80 仍重疊 0.075。**這對的判定要拿實料或 AOS 外形確認。**
- **J4 外殼公差、腳寬：** JST 沒有公布。±0.1、0.3 是假設。
- **JLC 放置精度：** ±0.10 是假設。
- **SHR-06V-S-B 凸耳位置：** 沒有查到，保守當作整段 9.0 寬。

## 沒有實物或 JLC 回覆就無法確認

- U11 腳尖和 J4 後壁在 z 方向的真實干涉。JST 圖顯示外殼離板面約 0.05，所以假設腳不能滑進去。
- U10/U11、U12/L1、U4/Q1 這類重疊會不會被 JLC DFM 擋下來，或是直接以歪斜的方式組裝。
- JLC 怎麼對待低於表格門檻 0.025 mm 的焊盤（C11/U5、U4/C10），以及實際鋼網開孔。
- R42 不焊時的錫膏處理。
- J6/U1 在 F 面間隙 0.225 mm：只用 courtyard 推算，當時沒有查 Waveshare 模組的真實外形，沒有判定（r4 已判定為 1.375 mm 標稱）。
- 修法 A 當時的走線能否繞通、JLC 實際庫存（r4 已確認有貨並繞通）、換料後光耦驅動 ATX 腳的實際動作（仍未實測）。

## 重現

在 `lay-board/courtyard_review/` 底下執行：

```
python -X utf8 tools/analyze.py tools img tools/bot_plot.pdf
python -X utf8 tools/sweep2.py tools
python -X utf8 tools/thermal.py tools
```

`tools/parse.py` 只讀 `kicad/p4_kvm_mini.kicad_pcb`（現在是 r5 的板，本報告的數字是當時 r3 的板算出來的，重跑結果會不同）。`tools/bot_plot.pdf` 是 kicad-cli 從 scratch 複本輸出的 B.Cu、B.Silkscreen、Edge.Cuts，頁面座標等於板座標（Edge.Cuts 校準為 80.0 到 120.0 mm）。數字見 `numbers.json`。
