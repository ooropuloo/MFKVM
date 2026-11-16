# MF KVM v2 r8b

40 × 40 mm、6 層單片板的 KVM over IP。主控是 Waveshare ESP32-P4-Module 基本款（SKU 28101，內建 ESP32-C6，2.4 GHz），影像用 TC358743。r8 由 r7f 改版，目標是外形對齊 JetKVM Mini（42 × 42 × 23 mm）。改了什麼、驗了什麼、還缺什麼，看 `R8_REPORT.md`。

**狀態（2026-11-12，r8b）：** 現行版是 r8b，打板包 `fab_r8b/`，通過全部檔案層級檢查。r8b 把三處走線往板內移、外殼改外接天線（SMA）、改掉高度方向的雙重夾持，細節看 `R8B_REPORT.md`。`fab_r8/` 是上一版，不要送。沒有打過板、沒有焊過、沒有上電、沒有任何實測；外殼的料（SMA 線、泡棉墊圈）還沒選定料號。

## 打板包（JLCPCB）

- 上傳 `fab_r8b/p4_kvm_mini_gerber.zip`。板廠的阻抗控制選項另外要一份阻抗表和走線位置圖，用 `fab_r8b/impedance_table.xlsx` 和 `fab_r8b/impedance_positions.jpg`，兩個檔由 `tools/jlc_impedance_sheet.py go` 產生。受控網路以網路名認定（TMDS、CSI 100 Ω；USB_DP/DN 90 Ω；LNA_OUT 50 Ω），不是以線寬：0.127 mm 也用在一般訊號線。雜湊在 `fab_r8b/SHA256.txt` 和 `SHA256_extra.txt`。BOM 用 `fab_r8b/BOM_JLC.csv`，座標用 `fab_r8b/CPL_JLC.csv`。
- 下單預覽逐顆對照 `fab_r8b/CPL_pin1_check.md` 和 `fab_r8b/CPL_polarity_pin1_r8.md`。U16（eFuse）第 1 腳一定要核對，轉 180° 會讓 VBUS 直接短到 GND。
- **不要用 `v2_r7f/fab_r7f/` 或更早的包**，那是 40 × 45 mm 的板子。
- 每次重跑 release 雜湊都會變，即使設計沒改。比版本用 `tools/gerber_equal.py` 比幾何。

| 項目 | 設定 |
|---|---|
| 外形 | 40.0 × 40.0 mm，四角 1.5 mm 倒角，三顆 2.2 mm 鍍通安裝孔（GND，銅環 2.9 mm） |
| 層數、厚度 | 6 層，1.2 mm，外層 1 oz |
| 疊構 | JLC06121H-3313，要開阻抗控制。TMDS／CSI 100 Ω 差動 0.127/0.198 mm，USB 90 Ω 0.18/0.32 mm，RF 50 Ω 0.15 mm |
| 最小線寬線距 | 0.09 mm |
| 過孔 | 0.4/0.2 mm，Epoxy Filled & Capped。不要選阻焊塞孔 |
| 阻焊 | 綠色，開窗 1:1，最小 bridge 0.1088 mm |
| 組裝 | 雙面 Standard PCBA，BGA 要 X-ray。U1 模組不貼，客戶手焊 |
| 拼板 | **要自己指定。** 四個邊都有東西貼著板邊：J2／J3／J5 伸出板邊 0.7 mm，J7 離邊 0.1 mm，後緣（+y）有 ATX_LED 走線 0.437 mm、J4 0.225 mm、C72／C73 0.65 mm。C72／C73 的長軸垂直後緣，掰板最容易裂，後緣不要放郵票孔或 V-cut，改用銑槽加側邊連接 |

## r8b 和 r8 的差別

- 板子：SD_CMD_C、SD_CMD 兩顆過孔和 ATX_LED 走線往板內移到離板邊 0.40 mm 以上，LDO_VO4 一段走線讓位 0.10 mm。零件位置、BOM、CPL 和 r8 相同，108 個網路只有這 4 個的銅不同。絲印 R8B。
- 外殼：天線改外接，左牆開 SMA 孔，後牆的天線窗和塑膠嵌件取消；蓋柱不再壓板子，改用泡棉墊圈；卡槽開孔加高，讓 J7 焊盤和 ESP_EN 不對著鋁牆；tray 內面也陽極。
- 拼板：郵票孔要內縮或斷開後磨平，不能凸出 40.00 mm 外形（鋁牆離板邊只有 0.25 mm）。

## r8 和 r7f 的差別

- 板子 40 × 45 → 40 × 40 mm。安裝孔 4 顆 → 3 顆（J6 那一角沒有孔）。
- 5V 阻尼：C69（330 µF 7343）拿掉，R68 改成 0.47 Ω 0402（C423162），新增 C72、C73（22 µF 0805，C45783，和 C60 同料）。三顆都在背面 J6 下方那一角，都沒有極性。
- 其餘 105 個網路的銅和 r7f 逐段相同，TMDS、CSI、USB 沒有動。
- 外殼由「鋁上蓋＋塑膠底殼＋外接風扇導管」改成全鋁、無風扇、42 × 42 × 23 mm。

## 供電

用能供 1.5 A 以上的 Type-C 電源接 J5。1.0 A 和 0.55 A 限流的埠在全負載下起不來（`fab_r8b/coldstart_r8.txt`）。

## 沿用 r7f 的事項

U1 手焊注意事項、不焊零件、1.2 V 遠端回授、接線與腳位、韌體設定都沒有變，見 `../v2_r7f/README.md` 和 `../v2_r7f/R7F_REPORT.md` 第 7、8 節。

## 重新產生

```
sh tools/r8_release.sh        # 全部閘門加突變測試，約 40 分鐘，結果在 out/release_r8.log
```

外殼檢查要 cadquery，直譯器用 `../v2_r7f/.venv-case/Scripts/python.exe`（release 腳本已指過去）。
