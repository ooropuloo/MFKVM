# 第三方內容

MF KVM 自己的檔案尚未選擇授權，保留所有權利。下面這些內容來自第三方，各自適用原本的條款。這份清單是整理時能查到的來源，**不是法律意見**；repo 公開前要再逐項確認。

## 公開前必須處理

- **廠商照片要換掉。** `*/parts_img/src/*.jpg`、`*/parts_img/thumb/*.webp` 裡的廠商照片，版權屬原廠，只供私下辨識料件。`lay-board/kvm-mini.html`、`off-the-shelf/v3.html` 也內嵌了它們的縮圖，換完要重新產生頁面。
- **規格書和圖面截圖要重新評估。** `lay-board/courtyard_review/sources/` 全部是別人的圖面節錄，公開前改成只留連結。
- **原廠 CAD 衍生的網格要確認授權。** 見下面「機構模型」。

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
| ExoAnchor Desktop R0 | MIT，Copyright (c) 2026 ExoAnchor contributors；內含的 KiCad 庫另依 KiCad 條款 | ExoAnchor KiCad 審查包 | `lay-board/data/exo.json`（USB-C、HDMI、USON-10 的焊盤幾何）。**壓縮檔本身沒有放進來**。公開前要附上 MIT 全文 |
| Waveshare ESP32-P4-Module | 廠商資料，未標示授權 | https://www.waveshare.com/ | `lay-board/data/land.json` 和 `ESP32-P4-Module` 封裝是照它的焊盤圖、腳位表做的 |

## 機構模型

| 項目 | 來源 | 在哪裡 |
|---|---|---|
| DFRobot FireBeetle 2 ESP32-P4 STEP | DFRobot wiki，[下載](https://dfimg.dfrobot.com/wiki/21103/DFR1172_firebeetle-esp32-p4r32-development-board_stpfile_V1.0.zip)，未標示授權 | **STEP 本身不在 repo。** 由它衍生：`off-the-shelf/case/asm/core_board.stl`、`core_parts.stl`、`case/j1_section.png`、`case/sections/`；`off-the-shelf/v3.html` 內嵌這些網格 |
| Waveshare 1.9 吋 LCD STEP | Waveshare wiki，未標示授權 | **STEP 不在 repo。** `off-the-shelf/case/asm/lcd.stl` 依它的尺寸建模 |
| DFRobot 官方圖 | DFRobot wiki | `off-the-shelf/case/handedness/official_vs_page.png` 並排了官方圖，用來查左右方向 |

## 圖面節錄（`lay-board/courtyard_review/sources/`）

只為了佐證尺寸判讀，版權屬各原廠，來源網址在 `lay-board/courtyard_review/REPORT.md` 的「來源」一節。

| 檔案 | 原廠 |
|---|---|
| `jst_eSH_p1_land.png`、`jst_eSH_p2_plug.png`、`jst_eSH_p3_header.png` | JST |
| `liteon_ltv357t_p2.png`、`liteon_ltv357t_newer_p2.png`、`liteon_ltv357t_p11_land.png` | LITE-ON |
| `everlight_el3h7g_pkg.png` | Everlight |
| `molex_SD-104031-001_sheet1.png` | Molex |
| `ti_dbv0005a.png` | Texas Instruments |
| `yxc_yso110tr_p3.png` | YXC |
| `jlc_spacing_measure.png` | JLCPCB |

`lay-board/fab_r5/r4_land_vs_datasheet.png` 也含 Everlight 規格書的節錄。

## 廠商照片（`*/parts_img/`）

**這些照片在 repo 公開前必須換掉。** 每張圖的來源逐項記在 `lay-board/parts_img/SOURCES.md`、`off-the-shelf/parts_img/SOURCES.md`。

| 檔案 | 內容 | 取自 |
|---|---|---|
| `lay-board/parts_img/src/p4.jpg` | Waveshare ESP32-P4-Module | OpenELAB 商品頁 |
| `lay-board/parts_img/src/lcd128.jpg` | Waveshare 1.28 吋 LCD | PiShop.ca 商品頁 |
| `off-the-shelf/parts_img/src/fb.jpg` | DFRobot FireBeetle 2 ESP32-P4 | dfrobot.com 商品頁 |
| `off-the-shelf/parts_img/src/c790.jpg` | Geekworm C790 | geekworm.com 商品頁 |
| `off-the-shelf/parts_img/src/lcd19.jpg` | Waveshare 1.9 吋 LCD | Pi Shop US 商品頁 |

同目錄的 `.svg` 是自繪示意，`.png` 是由本 repo 的 STL 或板圖渲染。

## 頁面執行時載入

`lay-board/kvm-mini.html`、`off-the-shelf/v3.html` 從 jsDelivr 載入 three.js 0.147.0（MIT），從 Google Fonts 載入字型，都沒有放進 repo。
