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

## 物理範圍與驗證

本版適用正入射、均勻單層薄膜、透明厚基板。無條紋不代表不能擬合，但也不能保證參數唯一。散射 q 屬經驗損失參數，不等同 AFM 表面粗糙度。

附帶資料均為模擬資料。已通過 36 項本機測試，四個 T/R 模擬案例膜厚重建誤差約 0.004%–0.034%；不可把這些數字當成實測精度。

數學式、假設與測試條件見 `docs/MODEL.md` 與 `docs/VALIDATION.md`。雲端套件解析與伺服器效能可能與本機不同，部署後需再次測試。

## 開發驗證

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python benchmark.py
```

模型參考：[Ballester et al. (2022)](https://doi.org/10.3390/coatings12101549)；[Byrnes, Multilayer optical calculations](https://arxiv.org/abs/1603.02720)。
