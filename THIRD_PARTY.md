# 第三方內容

MF KVM 自己的檔案依 [LICENSE](LICENSE) 授權：硬體 CERN-OHL-P-2.0、程式 Apache-2.0、文件 CC-BY-4.0。下面這些內容來自第三方，各自適用原本的條款，優先於 LICENSE。這份清單是整理時能查到的來源，**不是法律意見**。

## 2026-11-11 公開時撤下的內容

這些檔案已從目前的版本移除，只留來源連結；舊的 commit 裡還看得到。

- **廠商照片**：`lay-board/parts_img` 的 `p4`、`lcd128`，`off-the-shelf/parts_img` 的 `fb`、`c790`、`lcd19`，改成自繪示意圖。`kvm-mini.html`、`v3.html` 內嵌的縮圖也一起換掉。商品頁連結在各自的 `SOURCES.md`。
- **規格書和圖面截圖**：`lay-board/courtyard_review/sources/` 全部、`lay-board/fab_r5/r4_land_vs_datasheet.png`。`courtyard_review/REPORT.md` 裡原本的圖連結改成純文字，規格書網址保留。
- **由原廠 3D 模型產生的圖**：`off-the-shelf/case/j1_section.png`、`case/sections/*.png`、`case/handedness/official_vs_page.png`。要重新產生，先下載下面的 FireBeetle STEP，跑 `case/export_core.py`，再跑 `case/sections.py`。
- **由原廠 3D 模型轉出的網格**：`off-the-shelf/case/asm/core_board.stl`、`core_parts.stl` 換成只依外形尺寸做的方塊（主板一塊、零件 14 塊），`v3.html` 內嵌的網格也一起換掉。外殼的干涉檢查原本是用原廠網格做的，要重做同樣要先跑 `case/export_core.py`。

## 韌體

| 項目 | 授權 | 來源 | 在哪裡 |
|---|---|---|---|
| ESP-KVM | Apache-2.0 | https://github.com/espkvm/espkvm ，commit `0893eef16c1cb16ff24cc4607f4d75f002ffa129`（tag `v.0.77.0`） | **原始碼不在這個 repo。** `*/firmware/patches/` 是對它的修補，`firmware/sdkconfig_evidence/` 和 `firmware/logs/dependencies.lock.*` 是建置產生的設定檔。修補檔含上游程式碼的上下文行 |
| ESP-IDF | Apache-2.0 | https://github.com/espressif/esp-idf ，v6.1 | 不在 repo，只有建置設定引用 |

## 電路和封裝

| 項目 | 授權 | 來源 | 在哪裡 |
|---|---|---|---|
| Antmicro hdmi-mipi-bridge | Apache-2.0 | https://github.com/antmicro/hdmi-mipi-bridge | `lay-board/data/antmicro/a.net`（匯出的網表，只移除頂端 source 行的本機路徑）、`LICENSE`、`NOTICE.txt`；`lay-board/data/ant.json` 是從它的 BGA 封裝擷取的焊盤。TC358743 周邊電路參考它 |
| KiCad 官方封裝庫 | CC-BY-SA 4.0 加 KiCad 設計用例外 | https://gitlab.com/kicad/libraries/kicad-footprints | `lay-board/data/kicad_official.json` 和由它產生的封裝；`off-the-shelf/atx/gen_atx.py` 用的 SO-4 等官方封裝；`lay-board/kicad/mini.pretty/`，以及 `atx` 產生的封裝 |
| ExoAnchor Desktop R0 | MIT，Copyright (c) 2026 ExoAnchor contributors，全文在 [LICENSES/MIT-ExoAnchor.txt](LICENSES/MIT-ExoAnchor.txt)；內含的 KiCad 庫另依 KiCad 條款 | ExoAnchor KiCad 審查包 | `lay-board/data/exo.json`（USB-C、HDMI、USON-10 的焊盤幾何）。壓縮檔本身沒有放進來 |
| Waveshare ESP32-P4-Module | 廠商資料，未標示授權 | https://www.waveshare.com/ | `lay-board/data/land.json` 和 `ESP32-P4-Module` 封裝是照它的焊盤圖、腳位表量出的尺寸做的，沒有放它的圖面 |

## 機構模型

| 項目 | 來源 | 在哪裡 |
|---|---|---|
| DFRobot FireBeetle 2 ESP32-P4 STEP | DFRobot wiki，[下載](https://dfimg.dfrobot.com/wiki/21103/DFR1172_firebeetle-esp32-p4r32-development-board_stpfile_V1.0.zip)，未標示授權 | **STEP 和由它轉出的網格都不在 repo。** `off-the-shelf/case/export_core.py` 會從它產生 `asm/core_board.stl`、`core_parts.stl`；repo 裡的這兩個檔是方塊外形替代品 |
| Waveshare 1.9 吋 LCD STEP | Waveshare wiki，未標示授權 | **STEP 不在 repo。** `off-the-shelf/case/asm/lcd.stl` 是依它的外形尺寸自己建的模型 |

## 圖面來源

`lay-board/courtyard_review/REPORT.md` 的尺寸判讀依據 JST、LITE-ON、Everlight、Molex、Texas Instruments、YXC、JLCPCB 的規格書和說明頁，網址列在該報告的「來源」一節。截圖已撤下。

## 頁面執行時載入

`lay-board/kvm-mini.html`、`off-the-shelf/v3.html` 從 jsDelivr 載入 three.js 0.147.0（MIT），從 Google Fonts 載入字型，都沒有放進 repo。
