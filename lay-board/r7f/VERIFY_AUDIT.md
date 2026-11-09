# MF KVM v2 r7c：驗證工具稽核

日期 2026-11-08。工作副本 `D:/git/p4-kvm-box/v2_r7c`，由 `v2_r7b` 複製。**`v2_r7b` 沒有動**（下 JLC Y6 的那一版；稽核期間沒有任何檔案的修改時間晚於複製時間，`fab_r7b` 打板包 sha256 仍是 `3603c749…`）。沒有 commit、沒有聯絡 JLC、**沒有改任何銅箔**。

目的：讓「PASS」真的證明一些事。r6 的 `verify.py` 把設計當時的錯誤（U6.5 接 3V3）寫成預期值；r7 和 r7b 的 ERC 把 512 支腳全部寫成 passive，所以「ERC 0」什麼都沒檢查。

## 0. 更新（同日稍晚）：r7c 改了銅

第 1 到 9 節寫於 r7c 還和 r7b 銅箔相同的時候，第 7 節的「Gerber 幾何相同」只適用於那個階段。之後依指示在 r7c 改了銅：5V 阻尼、孔距、本體間隙、IR、板子改 40×45。改了什麼見 `R7C_REPORT.md`；因改銅而新增或修改的檢查見第 10 節；外部審查總表見第 11 節。目前的突變測試是 **72 次執行、0 次失手**。

## 1. 結論

- **沒有發現需要改銅箔的新設計錯誤。** 升級後的檢查在 r7c（＝r7b）上全部 PASS，另有 5 項警告，都附了證據（第 2 節）。
- **找出並修好 9 個有問題的檢查**（第 3 節）。舊的 `verify.py` 對 32 個注入的錯誤，**有 10 個照樣 ALL PASS**；新版 32 個都抓到。
- **突變測試：62 次執行、0 次失手**（`MUTATION_REPORT.txt`）。每一族先在未改動的副本上跑一次對照組，對照組必須通過；每個突變必須由**指定的那一項檢查**擋下來，被別的檢查順帶擋下不算數。
- **銅箔沒變：** 新產生的 `fab_r7c/` 和 `fab_r7b/` 的 17 個 Gerber/鑽孔檔，逐層幾何比對完全相同（`tools/gerber_equal.py`）。BOM、CPL、不貼件清單逐位元組相同，CPL 的 U15 仍是 0°。
- **Gerber zip 的 sha256 不會一樣**：KiCad 每次出圖都把時間寫進檔頭（`%TF.CreationDate`），所以 `fab_r7c` 的 zip 是 `1fb148b8…`，不是 `3603c749…`。內容相同的證明改用幾何比對，並用反向對照驗證過這個比對器：r7 對 r7b（真的改過銅）會報 11 個檔不同。

## 2. 設計上的發現（全部沒有改銅，等你裁決）

| # | 項目 | 證據 | 嚴重度 |
|---|---|---|---|
| 1 | **J5（電源 USB-C）外殼槽孔到一顆 GND 過孔，孔緣距 0.259 mm** | 槽孔 0.6 mm，位置 (12.52, −1.82)；過孔鑽 0.2 mm。JLC 規格頁（2026-11-08 讀）寫「Pad hole-to-hole spacing 0.45mm」和「Via-to-via hole spacing 0.2mm」，沒有說焊盤孔對過孔用哪一條。KiCad DRC 只有一個 `min_hole_to_hole`（0.2），所以從 r6 起都沒被報過 | **新發現，等 CAM 回答**。依 0.45 算不合格，依 0.2 算合格。`verify.py` 現在以 WARN 回報 |
| 2 | TC358743 IR（B4）輸入空接 | Toshiba 2014-05-16 p10：IR 是 Sch 型，沒有內部上下拉，沒有「不用時」的接法 | 已知（2026-11-07 腳位稽核 O2）。浮接的施密特輸入 |
| 3 | TC358743 EDID_SDA/SCL（G6、H6）空接 | p10：type N，沒有上下拉，沒有「不用時」的接法 | 已知（O2） |
| 4 | Y1 供電最高 3.440 V，規格書列 1.8–3.3 V | YSO110TR p1 只列數值，沒有容差 | 已知（R7B 報告第 1 節第 5 點） |
| 5 | ATX 光耦驅動餘量依賴假設 | VOH 0.8×VDD（P4 p89）、VF 1.4 V **假設**、CTR 200%（舊報告引用 p3），算出 IF 2.47 mA、可吸 4.44 mA；主機板前面板的上拉電流沒有規格 | 舊版用 VOH 3.3 V、VF 1.14 V，算出比較好看的數字。現在以 WARN 層級的保守值呈現 |

第 1 項是本次唯一的新發現。依你的指示，發現設計問題就停在改銅之前：我沒有動 J5 或那顆過孔。

## 3. 有問題的檢查，以及怎麼修

| # | 檢查 | 問題 | 修法 | 證明 |
|---|---|---|---|---|
| 1 | KiCad ERC | `gen_mini.py` 把 512 支腳全部寫成 `passive`，ERC 永遠 0 | 新的 `tools/schgen.py` 依 `data/pin_types.json` 給每支腳真正的電氣型態，**沒有預設值**（缺資料就中止）。PWR_FLAG 只放在追得到電源的網路上（經電感、磁珠、0 Ω、Q1，或外部接頭）。新的 `tools/erc_check.py` 把電路圖裡的腳型態讀回來逐腳比對，任何 ERC 違規都要在 `data/erc_waivers.json` 寫理由（目前空的），輸入腳空接必須有理由 | erc 族 8/8 抓到；同樣的錯誤用 r7b 的全 passive 寫法跑 ERC，**0 個錯誤** |
| 2 | `verify.py` U6.5 | r6 把「U6.5 = 3V3」當預期值 | 改成規則：EN 的電位下限 ≥ 0.7 × VCCB 上限（TI SCPS245E p5）。網路名稱不再出現在預期值裡 | 「U6.5 接回 3V3」由 U6.5 自己的 VIH 規則擋下 |
| 3 | `verify.py` 穩壓器輸出 | 輸出電壓用寫死的電阻值計算（`0.6×(1+150/33)`，連 R51 的 33.2k 都寫錯成 33k），跟板子上實際的電阻無關 | 從板子讀出回授網路，用節點分析解出輸出範圍：每顆電阻依**料號解出的容差**取上下限（UNI-ROYAL `0402WGF`=1%、Yageo `RT0402B`=0.1%、Viking `AR02B`=0.1%），VREF 0.588–0.612 V，IFB ±50 nA（Silergy p4） | 舊 verify 對 R50/R51 對調、R51 改 30k、R62/R63 對調**全部 ALL PASS**；新版全部 FAIL。r7b 板上算出 3V3 3.1846–3.4405 V、V1V2 1.1831–1.2373 V，和 R7B 報告一致 |
| 4 | `verify.py` 約 150 筆「腳位→網路名稱」表（WIKI/ROLE、EXPECT、HDMI、SD、USB、REG、r7b 料號清單） | 全部是設計當下的快照 | 刪掉。改成：(a) 依廠商腳名的腳對腳連線（例：模組 CSI_DATAP0 必須和 TC358743 CSID0P 同網路）；(b) GPIO 用途改由韌體 `sdkconfig.v2r7_rev3` 決定；(c) 電氣規則表 65 條，全部來自 `pin_types.json` 的規格書限制 | 舊 verify 對 REXT 2.2k、VBUS 分壓 R10 100k、R67 不焊、R40 不焊、CC 10k、FB5 不焊**全部 ALL PASS** |
| 5 | `fab_pack.py` DRC 閘門 | 只數 error。這版 KiCad 把 `hole_to_hole` 報成 **warning**，所以兩孔距 0.15 mm 也能出檔 | 專案設定 `hole_to_hole` 為 error；閘門改成任何 warning 類型都要列在 `data/drc_accepted.json`（目前只接受 courtyards_overlap、starved_thermal，各附理由） | drc 族「兩孔距 0.15 mm」由 `hole_to_hole` 擋下 |
| 6 | `impedance_r7.py` | 算的是寫死的線寬（0.127/0.198），沒讀板子；線寬超出 ±10% 只印 OFF，仍 exit 0 | 超出就 exit 1；`verify.py` 新增：受控阻抗網路的每一段線寬必須等於解過的寬度（TMDS/CSI 0.127、USB HS 0.18、LNA_OUT 0.15） | 舊 verify 對「D1_P 一段加寬到 0.2」ALL PASS；新版 FAIL |
| 7 | `check_case.py` J6 對 M2 螺絲 | 間隙用 `design.json` 的 bbox 算，不是用板子的焊盤 | 程式沒改：這個依賴靠 `bodycheck.py` 的「design.json 和板子位置一致」把關。補了兩個突變證明兩邊都有效 | case 族「J6 往螺絲移 0.8 mm」→ 間隙 −0.12 mm FAIL；body 族「只動板子不重產 design.json」→ FAIL |
| 8 | `fab_pack.py`、`holecheck.py` | 用 `python -I` 執行時找不到同目錄模組 | `fab_pack.py` 加上路徑（README 原本不用 `-I`，所以 r7b 沒碰到）。`holecheck.py` 沒改，照 README 不加 `-I` 跑 | — |
| 9 | 「Gerber 雜湊相同」這個驗收方式 | 每次出圖時間不同，雜湊不可能相同 | 新增 `tools/gerber_equal.py`：逐層比較形狀聯集（差異面積 < 1e-6 mm²）、每個物件（功能、腳、網路、中心、面積），以及每個鑽孔 | 正向 r7b 對 r7c 相同；反向 r7 對 r7b 報 11 個檔不同 |

另外 `verify.py` 新增的檢查（舊版沒有）：design.json 和板子逐腳一致、同一網路沒有兩個推挽輸出、每個接地腳都在板地、每條 TMDS/USB 線上有 ESD 通道、SD 卡電源來自 3V3 而不是 VO4（同時抓「R41、R42 都焊」）、MOSFET 閘極在 GPIO 放開時有確定電位、元件孔對其他孔 0.45 mm（WARN）。

## 4. 各項檢查：證明了什麼、沒證明什麼

突變結果見 `MUTATION_REPORT.txt`；「突變」欄是該族擋下的數量 / 注入數量，不含對照組。

| 檢查 | PASS 證明了 | PASS 沒證明 | 預期值來源 | 突變 |
|---|---|---|---|---|
| **ERC**（`kicad-cli sch erc` + `erc_check.py`） | 沒有輸出對輸出、電源輸出對電源輸出；每個 power_in 腳都追得到電源；電路圖的腳型態和資料檔逐腳相同；必須有連接的輸入腳沒有無故空接；沒有只出現一次的全域標籤 | 電壓位準對不對（那是 verify 的工作）；PWR_FLAG 認為的電源路徑本身合不合理（例如磁珠電流）；KiCad 預設的衝突矩陣本身 | `pin_types.json`（每支腳都有文件和頁碼）；KiCad 10.99 預設矩陣 | 8/8 |
| **verify：design.json ↔ 板子** | 電路圖、ERC、數值計算用的檔案描述的是這塊板子 | 位置（由 bodycheck 管） | 板檔本身 | 1/1 |
| **verify：電阻容差** | 每顆電阻的容差來自料號解碼 | 料號解碼表本身（依廠商命名規則手寫） | UNI-ROYAL、Yageo、Viking 料號規則 | 透過 R61–R63 5% 突變 |
| **verify：電源軌推導** | 每條電源軌的電壓範圍由板上實際零件算出：外部來源、SY8089 回授網路節點分析、TLV73325 固定 ±1.4%，再經電感、磁珠、0 Ω、Q1 傳下去 | 動態（上電暫態、負載暫態、漣波）；磁珠壓降只算兩項（AVDD12 用 current_budget.md 的 21.5 mV，VDDC/MIPI 用 50 mV 容許值）；VREF 只有 25°C 規格 | Silergy p2/p4、TI SBVS235 p6、USB Type-C vSafe5V、HDMI +5V 4.7–5.3 V（**HDMI 規範未重讀**） | 透過 6 個數值突變 |
| **verify：電氣規則表**（65 條） | 每顆 IC 的供電腳在規格內；EN/RESET/TEST/OE 的靜態電位相對**正確的那一條電源**符合 VIH/VIL；輸入腳的最高電壓不超過絕對最大值或 VDDIO+0.3（同一條電源時比同一瞬間）；REXT 2k ±1%；I²C 上拉接到對的那一側；Y1 負載；Q1 閘極有確定電位 | 時序（上電順序、重置時序，見 O5）；被 GPIO 驅動的腳只檢查最高電壓，不檢查韌體真的驅動多高；未列在資料檔的腳沒有限制 | `pin_types.json` 的 `limits`（Toshiba p10–p16、TI p5、Silergy p2/p4、TLV p5/p6、YXC p1、P4 p89、AOS p1、TPD p7） | 16 個突變的第一個 FAIL 就是規則表 |
| **verify：腳對腳連線** | CSI、HDMI、DDC 經 TCA9517A、HPD、USB、天線、microSD、ATX，每一條都是依廠商腳名和韌體設定逐腳連對 | 線材另一端（J4、J6 的線束順序：J6 依 Waveshare LCD wiki，J4 是本設計自訂） | Waveshare wiki 腳位表（oldid 108255）、Toshiba p12 球位圖、HDMI Type A 腳序、SD 規範腳序、`sdkconfig.v2r7_rev3` | 7 個 |
| **verify：兩個推挽輸出、接地腳、ESD、SD 電源來源** | 見名稱 | open-drain 互接、強弱驅動衝突 | `pin_types.json` | 4 個 |
| **verify：差動對長度差 ≤ 3.0 mm** | 各對 P/N 線段長度總和的差 | 這是線段**總和**，不是焊盤到焊盤路徑（`pairs.py` 才是）；殘段會被算進去；3.0 mm 是專案預算（20 ps），不是規範值 | 專案預算 | 1/1 |
| **verify：受控阻抗線寬** | TMDS/CSI 全部 0.127、USB HS 0.18、LNA_OUT 0.15，和 impedance_r7.py 解的一致 | 線距、參考平面是否連續、介電常數 | `impedance_r7.py` 的計算列 | 1/1 |
| **verify：過孔不碰 BGA 焊盤、沒有單腳網路、料號解碼、庫存** | 見名稱 | 庫存是 `stock.json` 抓取當時的數字 | JLC 料號頁面 | 間接 |
| **DRC**（kicad-cli，含灌銅） | 規則表內的間距、線寬、孔徑、孔距、板邊、未連線、與電路圖一致；任何未列入 `drc_accepted.json` 的警告都會擋 | 見下方規則對照的缺口；絲印字高字寬（設成 ignore）；courtyard 只是焊盤外框 | `.kicad_pro` 規則 | 5/5 |
| **maskcheck** | 從 Gerber 量出的防焊橋 ≥ 0.10 mm、開窗到他網導體 ≥ 0.09 mm | 黑/白防焊（0.13 mm，目前 1 處低於 0.13，綠色沒問題） | JLC 規格頁 2026-11-06 | 1/1；另有 `--selftest` 通過 |
| **holecheck** | 從鑽孔檔和銅層量出：過孔 0.2、PTH 外層 0.28、內層 0.30、NPTH 0.2 | 孔對孔（現在由 DRC 0.2 和 verify 的 0.45 WARN 處理）；同網路豁免 | JLC 規格頁 2026-11-06 | 1/1；`--selftest` 通過 |
| **bodycheck** | 實際零件本體和引腳不重疊，含 ±0.1 mm 貼片誤差（**假設**）；design.json 和板子位置一致 | 高度方向（矮零件在高零件懸空部分下會被誤報）；TI 模具毛邊只是警告 | 各零件圖面 | 2/2 |
| **pairs.py** | 只是報表（焊盤到焊盤長度、轉角），沒有通過/失敗 | — | — | 不適用 |
| **impedance_r7.py** | 板檔疊構和求解器常數一致；用 0.127/0.198 等幾何算出的阻抗在 ±10% 內（現在超出會 exit 1） | 介電常數、防焊厚度是**假設**；JLC 自己的計算器沒跑；板上實際線寬由 verify 檢查，線距沒檢查 | 板檔疊構 | 1/1 |
| **check_case.py** | 外殼 STL/STEP 和實板（kicad-cli 匯出的 STEP 和 Gerber）的開孔、螺絲、零件碰撞，71 項 | 零件包絡來自 design.json（靠 bodycheck 確保同步）；沒有試印；LCD 模組是估計值 | 實板匯出 | 1/1（需 cadquery，見 `tools/mutate.py` 的 `CASE_PY`） |
| **fab_pack.py 閘門** | 只對「verify ALL PASS 且跑在這塊板上」「erc_check PASS 且跑在這份電路圖上」「DRC 無錯誤、無未接受警告」的檔案出包；出包前再量一次 mask、hole、body | — | 各報告內的雜湊 | 3/3 |
| **fab_pack.py CPL 角度**（`JLC_ROT`） | **什麼都沒證明。** 角度是人工在 JLC 預覽對過後填的表，程式只是照抄 | U15 的 0° 沒有在 JLC 預覽對過（README） | 人工 | 無法自動化：只有 JLC 預覽能驗證 |

### DRC 規則對照 JLC 6 層能力（JLC 規格頁 2026-11-08 讀）

| 項目 | 專案規則 | JLC 多層板 | 結論 |
|---|---|---|---|
| 線寬 / 間距 | 0.09 / 0.09（netclass 0.1） | 0.09 / 0.09；焊盤到線 0.1（BGA 局部 0.09） | 合（netclass 0.1 讓實際間距 ≥ 0.1） |
| 過孔 孔 / 徑 | 孔 ≥ 0.15，徑 ≥ 0.35，環寬 ≥ 0.075 | 0.15 / 0.25 | 合，比較嚴 |
| 孔到線 | 0.2 | 過孔 0.2；PTH 0.28；內層 PTH 0.3 | DRC 只管 0.2，PTH 的較大值由 holecheck 管 |
| 孔到孔 | 0.2（**r7c 起是 error**） | 過孔對過孔 0.2；焊盤孔對焊盤孔 **0.45** | 0.45 沒有 DRC 規則，由 verify WARN 補上（見第 2 節第 1 項） |
| 銅到板邊 | 0.2 | 0.2（V-cut 0.4） | 合（本板沒有 V-cut） |
| 防焊 | 擴張 0 | 1:1；橋 0.10（黑白 0.13） | 由 maskcheck 量 |
| NPTH 最小孔 | 0.15（共用） | 0.5 | 沒有規則；本板 NPTH 是 2.2 mm，合 |
| 絲印 | 字高 0.5、字寬 0.08，兩項都 ignore | 線寬 ≥ 0.15，字高 ≥ 1.0 | **沒有檢查**；只影響可讀性 |

## 5. `verify.py` 每一項預期值的來源

| 斷言 | 預期值來源 | r7b 的寫法 |
|---|---|---|
| design.json 與板子逐腳一致 | 板子本身 | 沒有 |
| 每個零件都有腳型態資料 | `pin_types.json` | 沒有 |
| 電阻容差 | 料號解碼 | 寫死在數值裡 |
| 3V3、V1V2 範圍 | Silergy p2/p4 + 板上回授網路 + 料號容差 | 寫死 150k/33.2k、33.56k/33k |
| V2V5 | TI SBVS235 p6 ±1.4% | 同 |
| 5V、HOST_VBUS、HDMI_5V | USB Type-C vSafe5V、HDMI 1.4（未重讀） | 5V 寫 4.75–5.5（SY8089 上限） |
| 65 條電氣規則 | `pin_types.json` 的 limits，各附頁碼 | 24 條，其中多條同時要求「網路名稱 = 某值」 |
| 兩個推挽輸出 | 腳型態 | 沒有 |
| 接地腳 | 各廠商腳名（GND、VSS、VPGM、外殼） | 快照 |
| 韌體 GPIO | `sdkconfig.v2r7_rev3` + Waveshare 腳名 + Toshiba 球名 + LCD wiki + SD 規範 | 快照（ROLE） |
| CSI、HDMI、DDC、HPD | Waveshare 腳名、Toshiba p12、HDMI Type A、TI p4 | 快照（EXPECT 由 Antmicro 網表推出，網路名稱比對） |
| ESD | TI p4 通道腳 | 沒有 |
| USB-C | 連接器 A/B 腳名、Rd 5.1k ±20%（**USB 規範憑記憶，未重讀**） | 快照 |
| 天線 | Waveshare pin 2、Hirose p3 | 快照 |
| microSD 上拉接 VO4 | Espressif 設計指引 1.3.11（經 2026-11-07 腳位稽核 F1 引述） | 快照 |
| SD 電源不取自 VO4 | P4 p32 VO4 最大 50 mA（經 F1） | 「R42 焊、R41 不焊」快照 |
| USB_DP 下拉 | 腳位稽核 F4（晶片 rev < 3） | 快照（R60.1/R60.2） |
| HPDI 串聯電阻 | 審查 M5；倒灌上限 0.5 mA 是**假設**（Toshiba 沒有給箝位電流） | 寫死 51k |
| 光耦驅動 | P4 p89 VOH；VF 1.4 V **假設**；CTR p3（舊引用） | 寫死 3.3 V、1.14 V、470 Ω |
| 長度差 ≤ 3.0 mm | 專案預算 | 同（依網路名稱找對） |
| 受控阻抗線寬 | `impedance_r7.py` 的計算列 | 沒有 |
| 元件孔對孔 0.45 mm（WARN） | JLC 規格頁 | 沒有 |
| 料號解碼、庫存、mask、hole、body | JLC 頁面、各自模組 | 同 |

**刪除的預期值：** U6.5 = 5V（及整份 REG 表）、R21 下拉（審查 L3 的設計選擇，不是規格書要求；需要的話應該以「審查要求」重新加回）、「U5 已移除、R66 100Ω、R61–R63 為 C728559/C319512」這類料號快照（改由容差計算決定是否合格）、`ok_single` 例外清單、`vout = 0.6×(1+150/33)`。

## 6. 突變測試

`python -I tools/mutate.py out --report MUTATION_REPORT.txt`（約 100 秒；case 族需要 cadquery）。

| 族 | 對照 | 注入 | 擋下 | 舊工具 |
|---|---|---|---|---|
| verify | 通過 | 32 | 32 | 舊 `verify.py` 有 10 個 ALL PASS（R50/R51 對調、R51 30k、R62/R63 對調、REXT 2.2k、R10 100k、R67 不焊、R40 不焊、CC 10k、FB5 不焊、D1_P 加寬）；其餘 22 個多半是被網路名稱快照擋下 |
| erc | 通過 | 8 | 8 | r7b 的全 passive 寫法：0 錯誤 |
| drc | 通過 | 5 | 5 | 孔距 0.15 只會是 warning，r7b 的閘門會放行 |
| mask / hole / body / imp | 通過 | 1 / 1 / 2 / 1 | 全部 | — |
| fabpack | — | 3 | 3 | ERC 閘門原本只看 erc.json 是否 0 |
| case | 通過 | 1 | 1 | — |

指定的突變全部在清單內：U6.5 回到 3V3、SY8089 回授電阻對調（兩組）、輸出對輸出（verify 和 ERC 各一）、Y1 負載電容 47 pF、HPDI 直接接 HDMI_5V、VDDIO 沒電（verify 和 ERC 各一）。

## 7. 回歸（D）——r7c 改銅之前的狀態，已被第 10 節取代

在 `v2_r7c` 依 README 的順序重跑：`sh tools/check.sh out/final.ses` → `python -I tools/verify.py out data/antmicro/a.net > out/verify.out` → `python -I tools/fab_pack.py out fab_r7c`。

| 項目 | 結果 |
|---|---|
| ERC | KiCad 0；erc_check PASS，3 個警告（第 2 節第 2、3 項） |
| DRC | 0 error；警告 19 個（courtyard 18、starved_thermal 1），都是已接受類型；未連線 0；與電路圖一致 |
| verify | ALL PASS，2 個警告（Y1.4、元件孔距） |
| fab_pack | 15 個閘門全過，`fab_r7c/` 已寫出 |
| check_case | 71/71 通過（`fab_r7c/case_check.txt`） |
| impedance | 全部在目標內（`fab_r7c/impedance_r7c.txt`） |
| 和 r7b 比 | 17 個 Gerber/鑽孔檔幾何相同；BOM、CPL、不貼件逐位元組相同；U15 CPL 0° |
| 雜湊 | 板檔 `01e222d7…`（KiCad 存檔時物件順序跟著隨機 UUID 改變，所以和 r7b 的 `2acf1c0f…` 不同）；zip `1fb148b8…`（時間戳） |

**生效條件：** 這些都是檔案層級的檢查。`fab_r7c/` 只是證明工具鏈產出的東西和 r7b 相同，**不要拿去下單**，訂單仍是 `v2_r7b/fab_r7b`（Y6）。`fab_r7c/README.md` 是從 r7b README 複製的，內容講的是 r7b。

## 8. 殘餘限制

- 電氣規則只涵蓋靜態直流條件：沒有上電順序、重置時序、暫態、雜訊（AVDD33 0.08 Vpp、AVDD12 0.04 Vpp 沒有量）。
- `pin_types.json` 有幾項來源標註「未重讀」：EL3H7 腳位（引用 2026-11-07 稽核）、P4 模組 3.0–3.6 V、HDMI +5V 範圍、USB Rd ±20%。「5 V tolerant = 5.5 V」是假設。
- TC358743 規格書用 2014 版；2017 版下載被拒（同 O 系列）。
- 突變測試證明「這些錯誤會被抓到」，不證明「沒有其他錯誤」。開漏互接、驅動強度、跨電源域在上電時的倒灌只有 HPDI 一處有規則。
- `check_case.py` 需要另一個有 cadquery 的 Python（`tools/mutate.py` 的 `CASE_PY`，預設指向之前 session 建的 venv）。
- CPL 旋轉角沒有任何自動檢查，只能在 JLC 預覽對。

## 9. 檔案

| 檔案 | 內容 |
|---|---|
| `data/pin_types.json` | 15 種零件、265 支腳的電氣型態，限制、電源域、外部電源、可空接清單，全部附文件和頁碼 |
| `tools/build_pin_types.py` | 產生上面那個 JSON 的來源（TC358743 球位依 Toshiba p12 圖逐格抄寫） |
| `tools/schgen.py` | 電路圖產生（`gen_mini.py` 呼叫）、PWR_FLAG 追溯 |
| `tools/erc_check.py` | ERC 加上腳型態回讀、空接理由、豁免清單 |
| `data/erc_waivers.json`、`data/drc_accepted.json` | ERC 豁免（空的）、可接受的 DRC 警告類型 |
| `tools/verify.py` | 改寫 |
| `tools/mutate.py` | 突變測試 |
| `tools/gerber_equal.py` | Gerber/鑽孔幾何比對 |
| `ERC_REPORT.txt`、`MUTATION_REPORT.txt` | 報告 |
| `datasheets_r7/tpd4e05u06_slvsbo7o.pdf` | TI TPD4E05U06 規格書（新下載，腳位表 p4、VRWM p7） |
| 修改：`gen_mini.py`（電路圖改呼叫 schgen、`hole_to_hole` 設 error）、`tools/fab_pack.py`（ERC 與 DRC 警告閘門、import 路徑）、`tools/check.sh`（跑 erc_check、路徑改 v2_r7c）、`tools/route_until_clean.sh`、`tools/r6/route.sh`（路徑改 v2_r7c）、`tools/r7/impedance_r7.py`（超出目標 exit 1）、`kicad/`（換成 r7c 產出） | |

## 10. r7c 改銅時新增或修改的檢查

| 檢查 | PASS 證明了 | PASS 沒證明 | 預期值來源 | 突變 |
|---|---|---|---|---|
| **元件孔對任何孔 ≥0.45 mm**（`.kicad_dru` 規則 + verify） | 焊盤孔、槽孔、NPTH 對任何孔（含過孔）的孔緣距離至少 0.45 mm；過孔對過孔至少 0.2 mm | JLC 對「焊盤孔對過孔」到底用哪一條，規格頁沒寫；這裡採保守值 | JLC 規格頁：Pad hole-to-hole 0.45、Via-to-via 0.2 | DRC 與 verify 各 1 個：在 J5 槽孔旁 0.23 mm 放一顆過孔，都擋下 |
| **DRC 警告閘門**（`data/drc_accepted.json`） | 未列在接受清單裡的 DRC warning 類型一律擋下 | 接受清單本身是人寫的 | 每一項都寫了接受理由 | `hole_to_hole` 突變原本只是 warning，現在擋下 |
| **CSI 組內差 ≤0.15 mm** | 每組 P/N 線段長度總和差 ≤0.15 mm | 不含模組內的走線長度 | Espressif 指南 p28 規定 10 mil，本專案用更嚴的 0.15 mm | CK_P 加一段 0.3 mm 殘段 → 擋下 |
| **CSI 組間差 ≤0.762 mm** | 目前**沒通過**，回報為 WARN（已知偏離，見 R7C_REPORT 第 1 節） | — | Espressif 指南 p28 規定 30 mil | 無：目前就是不合格，對照組通不過；設 `CSI_INTER_LEVEL=FAIL` 即恢復硬門檻 |
| **本體間隙 MARGIN 0.05 mm** | 同面每對零件在最大尺寸、±0.1 mm 貼裝誤差下，仍有 ≥0.05 mm 間隙 | 0.05 mm 是本專案自訂值，不是 JLC 的數字；±0.1 mm 是假設 | 外部審查（Codex）的要求 | C20 退回 0.025 mm → 擋下 |
| **5V 熱插拔**（`hotplug.py --design` + fab_pack 閘門） | 從板上實際零件讀出陶瓷電容和阻尼 R-C，在 576 種組合下 U2 VIN 峰值 ≤5.8 V | 集總模型；線材 L、R 和電容 DC bias 都是**假設**；沒有實測 | SY8089 AN p2 絕對最大 6.0 V，另留 0.2 V 餘量 | R68 不焊、R68 改 0 Ω → 都擋下；fab_pack 收到 OVER 報告 → 拒絕 |
| **IR 必須為低**（verify 規則表） | B4 接在 VIL 以下的電位 | 不涉及 IR 功能本身 | Toshiba p10、p16 | B4 改接 3V3 → 擋下；ERC 族：B4 改回空接 → 擋下 |
| **check_case 改用設計原點為旋轉軸** | 板子不對稱時，外殼對位仍然正確 | — | design.json 的 `board` 欄 | 修好之前，對照組有 29 項 FAIL（孔位錯開 2.5 mm）；修好後 71/71 |
| **fab_pack 外框檢查** | Gerber 量到的外框尺寸等於板檔 Edge.Cuts 的尺寸 | 板子應該多大，不在這項檢查範圍內 | 板檔本身（原本寫死 40×40） | — |

## 11. 外部審查總表

狀態代號：**已修**＝在 r7b 或 r7c 的檔案中改好，並經檢查確認；**不修**＝附理由；**待實測**＝檔案層級無法判定；**r8**＝留到下一版。

| 來源 | 項目 | 狀態 | 說明 |
|---|---|---|---|
| ChatGPT `MFKVM_r6_Feasibility_Cost_Review` | — | **未取得** | 磁碟上找不到這份文件，已請 team lead 提供路徑 |
| REVIEW_independent (r7) | M1 AVDD12 窗口 | 已修（r7b） | 改用 0.1% 電阻；verify 從料號解出容差後計算，球上電壓 1.1616–1.2373 V |
| 同上 | M2 CPL 旋轉角 | 待實測（JLC 預覽） | `fab_r7c/CPL_pin1_check.md` 列 22 顆，含新加的 C69 和移動過的 U12；U15 維持 0° |
| 同上 | M3 U1 絲印 | 已修（r7b） | |
| 同上 | M4 遠端回授斷線 | 已修（r7b，R66）；殘留 R61/R62 開路 | 殘留風險用第一次上電程序處理（r7b 審查 R1） |
| 同上 | M5 HPDI | 已修（r7b，R67 51k） | verify 檢查串聯電阻和倒灌電流（上限 0.5 mA 是假設） |
| 同上 | M6 AVDD12 雜訊 | 待實測 | |
| 同上 | M7 J6 間隙 | 部分修（0.425 mm），其餘接受 | r7b 審查建議選 (b) |
| 同上 | L1 3V3 上限 | 已修（r7b） | verify 由回授網路算出 3.185–3.440 V |
| 同上 | L2 VBUS 熱插拔 | **已修（r7c）** | C69 + R68，最差 5.406 V（原 9.826 V） |
| 同上 | L3 RESETN | 已修（r7b） | |
| 同上 | L4 IR／EDID／INT | IR **已修（r7c）**；EDID r8；INT 位址待韌體 | EDID 放不下兩顆 0402，直接接 3V3 有短路風險 |
| 同上 | L5 CEC | r8 | 產品不用 CEC；沒電時 CEC 匯流排可能被拉低 |
| 同上 | L6 錫膏 | 已修（r7b） | |
| 同上 | L7 防焊開窗擴張 0 | 待 JLC 確認 | maskcheck 用 0 擴張量測，防焊橋最小 0.1088 mm |
| 同上 | L8 C32 位置 | r8 | |
| 同上 | L9 工藝邊 | 待 JLC 確認 | r7c 後緣多了 5 mm，工藝邊比較好加 |
| 同上 | L10 kicad/ | 已修（r7b） | r7c 的 `kicad/` 是 r7c 的檔案 |
| 同上 | L11 starved thermal | 不修 | 已列入 `drc_accepted.json` 並附理由 |
| 同上 | 建議：頻寬、供電 ≥1.5 A、C65、AVDD33 雜訊、Q1 湧浪 | 產品規格／r8／待實測 | 不影響打樣 |
| REVIEW_r7b | R1 R61/R62 開路 | 第一次上電程序 | |
| 同上 | R2 沒電時 3V3 被墊高 | 待實測 | |
| 同上 | R3 韌體必須拉高 GPIO23 | 寫進文件（firmware defaults 註解） | |
| 同上 | R4 留下的 M6、L2、L4、L5、L7、L8、L9 | L2、L4 的 IR 在 r7c 已修，其餘照上表 | |
| Codex | CSI 組間長度匹配 | **不修（已知偏離）** | 理由和選項見 R7C_REPORT 第 1 節第 1 點；組內差合格 |
| Codex | 本體間隙餘量 | **已修（r7c）** | MARGIN 0.05 mm，4 組移件 |
| Codex | 5V 熱插拔模擬超過 6 V | **已修（r7c）** | 同 L2 |

