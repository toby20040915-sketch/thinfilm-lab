# 薄膜光譜研究室

Python / Streamlit 獨立薄膜光譜分析頁面。

可匯入絕對穿透率 T 與／或反射率 R，利用包絡線初估與 ATLU 全光譜擬合求取 n、k、d；另提供 Tauc 能隙診斷、經驗散射損失模型、參數可信度及獨立參考資料比較。

## Streamlit Community Cloud 部署

- Python：3.12
- 主程式：`app.py`
- 依賴檔案：根目錄 `requirements.txt`
- 不需要 API 金鑰、密碼或 secrets。
- 保留完整 `thinfilm/` 模組資料夾；不要只上傳 app.py。

## 本機執行

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 使用流程

1. 先選模擬樣品，按「開始全光譜分析」。
2. 或匯入實測 CSV：必填 `wavelength_nm`，至少包含 `T` 或 `R`。可提供 `sigma_T`、`sigma_R`、`substrate_n`。
3. 明確選擇 0–1 或百分比單位；波長固定 nm。
4. 檢查收斂、殘差、多起點與可信度資訊。
5. 匯入同樣品的橢偏儀與 Macleod 參考 CSV，或下載分析結果。

網站版會把上傳的 CSV 傳到代管此網站的伺服器進行運算；本程式不另行保存上傳檔案至資料庫。請依實驗室規範選擇可上傳的數據。每個檔案上限 10 MB。

## 教授 T-only 實測資料匯入

在「匯入 CSV」選擇「無表頭兩欄 T-only（教授量測格式）」，明確指定第一欄
`Wavelength (nm)`、第二欄 `Transmittance T`，並在側欄選擇「0–100 百分比」。
接受 tab、一般空白或混合 whitespace 分隔的恰好兩欄資料，不推測 T/R 或單位。
原有有表頭 importer 與命令列流程維持相容；新增的格式與波段控制可由網站介面使用。

程式保留原始上傳位元組、原始順序及原始單位，另建 ascending／fraction 分析副本。
摘要顯示完整匯入點數、波長範圍、原始順序、單位與 T min/max。
`Fit wavelength min (nm)`／`Fit wavelength max (nm)` 預設完整匯入範圍，
含上下限且至少需 12 點；只有範圍內資料進入既有 fitting，完整原始資料仍可查看及下載。
圖上陰影標示 fitting range，原始光譜不做 smoothing。

完整結果 ZIP 另外包含：

- `original_upload.txt`：原始檔案位元組，未修改；統一安全檔名。
- `raw_imported_spectrum.csv`：解析後的完整資料，保留原始順序與單位。
- `normalized_full_spectrum.csv`：完整排序與 fraction 換算後資料。
- `normalized_input.csv`：實際參與 fitting 的子集。
- `summary.json` 的 `data_intake`：原始檔 SHA-256、欄位對應、原始單位／順序、完整範圍、要求的 fitting 範圍與實際取樣範圍、點數。

上傳內容只在當次資料流程及可下載匯出中保留，不是伺服器永久檔案庫，請自行保存下載檔。
T-only 不會生成假的量測 R；圖上未量測的 R 標示為 `Model predicted R — not measured`。
T-only 的獨立光學資訊較少，收斂不證明參數唯一，仍需檢查相關性、邊界敏感度及外部參考。
本功能未修改 ATLU、optimizer 或 backside 模型，亦不代表教授樣品膜厚已獲驗證。
測試中的兩欄資料只是小型 synthetic parser fixture，並非教授四份實測檔。

## 物理範圍與驗證

本版適用正入射、均勻單層薄膜、透明厚基板。無條紋不代表不能擬合，但也不能保證參數唯一。散射 q 屬經驗損失參數，不等同 AFM 表面粗糙度。

附帶資料均為模擬資料。T-only intake 更新於 2026-09-22 通過 61 項本機測試（既有 36 項及新增 25 項）。既有四個 T/R 模擬案例膜厚重建誤差約 0.004%–0.034%；不可把這些數字當成實測精度。

數學式、假設與測試條件見 `docs/MODEL.md` 與 `docs/VALIDATION.md`。雲端套件解析與伺服器效能可能與本機不同，部署後需再次測試。

## 開發驗證

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python benchmark.py
```

模型參考：[Ballester et al. (2022)](https://doi.org/10.3390/coatings12101549)；[Byrnes, Multilayer optical calculations](https://arxiv.org/abs/1603.02720)。
