# MF KVM

MF KVM 是以 ESP32-P4 為主控、跑 [ESP-KVM](https://github.com/espkvm/espkvm) 韌體的 KVM over IP 小盒子：接上主機的 HDMI 和 USB 之後，就能透過 Wi-Fi 從瀏覽器看主機畫面、操作鍵盤滑鼠，也能按主機的電源和重置鍵。這個 repo 並列兩個設計：`off-the-shelf/` 用買得到的現成板組裝，只自製一片 ATX 小板；`lay-board/` 把所有電路自己布在一片 6 層板上。

**狀態：兩個設計都沒有做出實品，也沒有任何一項在硬體上驗證過。** 目前通過的都是檔案層級的檢查（ERC、DRC、阻焊、孔距、零件本體、外殼幾何）和韌體編譯。

**客製板目前的版本是 [`lay-board/r7f/`](lay-board/r7f/README.md)**：已送 JLC 審核、尚未付款。下表和 `lay-board/fab_r5/` 是較舊的 r5，那張單已經取消，留著當紀錄。

尚未選擇授權，保留所有權利。第三方內容見 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 兩個設計比較

| | [`off-the-shelf/`](off-the-shelf/README.md)（現成料，第三版） | [`lay-board/`](lay-board/README.md)（客製板，第二版 r5） |
|---|---|---|
| **外殼尺寸** | 75.0 × 38.05 × 26.73 mm | 44 × 44 × 20 mm |
| **體積** | 76 cm³ | 39 cm³ |
| **買什麼** | DFRobot FireBeetle 2 ESP32-P4（DFR1172）、Geekworm C790、Waveshare 1.9 吋 LCD、Würth 50 mm 15-pin 排線（接點異面、同面各 1）、改過不接 VBUS 的 USB 線、Ø0.64 銅線、JST SH 線、螺絲、5 V 電源 | Waveshare ESP32-P4-Module-U（IPEX）、FPC 天線、1.28 吋圓形 LCD、自製 SHR-08 和 SHR-06 線、M2 × 16 螺絲 4 支 |
| **打什麼板** | 2 層 ATX 小板 rev B，11.05 × 35.4 mm（`fab_atx_b/`），尚未下單 | 6 層 40 × 40 mm 主板加雙面 PCBA，含 BGA（`fab_r5/`），JLC 審查中、未付款 |
| **印什麼** | 底殼、上蓋、C790 橋架、排線捲線棒、ATX 焊接墊片（建議 PETG） | 底殼、上蓋 |
| **韌體** | ESP-KVM `0893eef`，加 ST7789 修補與 ATX 修補（兩支 patch），只編譯過 | ESP-KVM `0893eef`，加開機預設值修補與 ATX 修補（兩支 patch），只編譯過。ATX 預設關閉，到 console 打開，見 `lay-board/firmware/BUILD_v2.md` |
| **主要風險** | 排線斜捲 45° 沒人測過、回報僅約 9 fps、ATX 小板焊死後要斜著裝 | 首版 6 層加 BGA 有錯就要重打、阻抗只有公式估算、最壞公差有 4 對本體可能相碰 |
| **狀態** | 只有設計，零件未買 | 打板包只能送 CAM 預審，還不能算放行 |
| **什麼時候選它** | 想先驗證功能、不想打 6 層板和焊 BGA、接受比較大的盒子。目前建議當驗證機，也能先驗證兩邊共用的韌體 | 要最小的外形，或要走正式小型產品，且願意承擔首版改板 |

每個設計的 README 都有 **「還缺什麼」** 清單，列出下單前和實機要做的事：[off-the-shelf](off-the-shelf/README.md#還缺什麼)、[lay-board](lay-board/README.md#還缺什麼)。

## 建議順序

1. 買 `off-the-shelf` 的料，先用線接起來跑通影像、USB、Wi-Fi，不用打板也不用列印。
2. 拿實測影格率決定 `off-the-shelf` 能不能接受，同時驗證 `lay-board` 也會用到的韌體路徑。
3. `lay-board` 依 CAM 回覆決定要不要修，審查通過也先不付款，全部驗證過才打板。

## 3D 頁面

這兩個連結是**擁有者私人頁面，別人打不開**。每個資料夾裡的本機 HTML 是同一份內容，下載後用瀏覽器開就能看（3D 需要連上網路載入 three.js）：

| 設計 | 私人連結 | 本機檔案 |
|---|---|---|
| lay-board | https://claude.ai/artifact/GMou6HJAjchfPkJ2fzq8we | [`lay-board/kvm-mini.html`](lay-board/kvm-mini.html) |
| off-the-shelf | https://claude.ai/artifact/LdwRVth9BPiBVDjdgMhgdb | [`off-the-shelf/v3.html`](off-the-shelf/v3.html) |

## 不在這個 repo 的東西

- **第一版（NANO 模組疊自製底板）：** 排針位置錯，已放棄，沒有放進來。
- **舊打板包：** `fab`、`fab_new`、`fab_r2`～`fab_r4`、`fab_atx` 都不能用，原因寫在各 README。
- **建置輸出：** ESP-KVM clone、build 目錄、映像檔、建置 log。重新編譯的方法在各 README。
- **第三方原始檔：** NANO 官方 CAD、ExoAnchor 壓縮檔、FireBeetle STEP。來源見 [THIRD_PARTY.md](THIRD_PARTY.md) 和 `off-the-shelf/research/`。

## 常用檢查（在 repo 根目錄）

```sh
python lay-board/tools/maskcheck.py lay-board/fab_r5/p4_kvm_mini_gerber.zip
python lay-board/tools/holecheck.py lay-board/fab_r5/p4_kvm_mini_gerber.zip
sh lay-board/tools/check.sh out/final.ses     # 要 KiCad，路徑用 KICAD_CLI、KICAD_TOOL_HOME 覆寫
python lay-board/tools/bodycheck.py lay-board/out
python lay-board/tools/maskcheck.py off-the-shelf/fab_atx_b/mf_kvm_atx_gerber.zip
python lay-board/tools/holecheck.py off-the-shelf/fab_atx_b/mf_kvm_atx_gerber.zip
```

`.gitattributes` 設定 `* -text`，檔案逐位元組保存，不轉換行尾，所以 Gerber 雜湊不會變，`.sh` 也不會變成 CRLF。
