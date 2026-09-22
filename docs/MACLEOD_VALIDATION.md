# Essential Macleod 手動比較流程

狀態：**Ready for Essential Macleod comparison**。本專案未提供真實 Essential Macleod reference；synthetic tests 不能取代 external software benchmark。

## 共同物理條件

僅限 0° normal incidence，S/P 等價；不支援斜入射或獨立 polarization 設定。
入射介質 air n=1、k=0；單層薄膜 coherent，已知被動 n(λ)>0、k(λ)≥0 與厚度 d。
透明基板只接受實數 n(λ)≥1、k=0。沒有散射或儀器歸一化。

- Backside OFF：Air / Film / semi-infinite Glass；T 為進入基板的功率比例，沒有後表面。
- Backside ON：Air / Film / Glass / Air；厚透明基板採 incoherent 強度多次反射，T 為穿出後表面的功率比例。不要在 Macleod 使用 coherent substrate fringes。
- n+i k 對應 exp(-iωt)；Macleod 的內部符號慣例若不同，應確認輸入欄位代表正的 extinction coefficient，不可直接猜測 complex sign。

## Cases

所有內建案例使用 400–1000 nm、每 10 nm 一點及 substrate n=1.5。

| Case | Film n | Film k | d (nm) | Backside | 用途 |
|---|---:|---:|---:|---|---|
| A | 2 | 0 | 0 | ON | 零膜厚極限：等價裸基板 |
| B | 2 | 0 | 300 | ON | 干涉與 R+T=1 |
| C | 2.3 | 0.15 | 120 | ON | 吸收：A=1−R−T>0 |
| D | 2.3 | 0.15 | 120 | OFF | 半無限基板 |
| E | 2.3 | 0.15 | 120 | ON | 與 D 成對隔離 backside 影響；刻意與 C 相同 |

Custom known n/k CSV 支援 wavelength_nm,film_n,film_k,substrate_n 四個有表頭欄位。
厚度（nm）與 backside 另行明確指定。排序僅供 forward 計算，不插值 optical constants。
API：`thinfilm.validation.forward(frame, thickness_nm, backside)` 直接呼叫 production `spectrum`；完全不經 ATLU。

## Export → Macleod → Import

1. 在獨立 Forward Model Validation 頁選案例或上傳已知 n/k。下載 exchange ZIP。
2. `program.csv` 包含 wavelength_nm,film_n,film_k,substrate_n,thickness_nm,Program_R,Program_T,Program_A；R/T 為 fraction。`metadata.json` 包含版本 SHA、單位、0°、coherence、backside 與介質假設。
3. 人工在 Essential Macleod 建立相同結構。直接帶入匯出的 n/k；確認 wavelength grid 與材料插值設定，在每一取樣點核對 n/k；A 案例移除薄膜或設 d=0。不要讓 Macleod 重新以其他材料模型產生 n/k。
4. OFF 排除後表面；ON 設定透明厚基板的非相干多次反射。若軟體版本無法表達相同假設，記錄不相容並停止將其稱為等條件 benchmark。此流程不是 native Macleod file integration，不提供未核實的按鈕名稱。
5. 保存 Macleod 版本、結構／材料檔、設定截圖、匯出精度及原始匯出檔。將待匯入表整理成 `wavelength,R,T` 有表頭 CSV；若需整理欄位，另外保存未整理原檔與轉換步驟。
6. 明確指定 wavelength unit nm 或 um，以及 R/T fraction 或 percent。Importer 保存上傳原始 bytes、原順序、單位與 SHA256；另建 ascending nm/fraction copy。
7. 預設 exact 要求正規化後 wavelength grid 完全相同。若不同，必須明確選 interpolate：只在共同 overlap 內，將 reference 線性內插至 program 點，絕不外插。報告被排除的 Program 點數；至少需要兩個比較點。插值誤差不等同 solver 誤差，優先重新輸出相同網格。
8. R 與 T 分別報告 max absolute difference、MAE、RMSE，以及逐點 Δ=Program−Reference。只有兩通道各自 max |Δ|≤tolerance 才達工程門檻。預設 1e-4 fraction（0.01 percentage point）只是可修改的工程起點，並無文獻物理標準背書；依匯出精度和 grid convergence 記錄 rationale。
9. 下载 comparison evidence ZIP：Program 輸入輸出、metadata、reference 原始 bytes、正規化表、單位／hash、逐點 comparison.csv 與 comparison.json（含門檻、理由與來源確認）。即使數值 PASS，也僅適用該案例、網格與條件；沒有來源／條件確認時不能宣稱 Macleod validation。

## 兩層證據

既有 analytical / independent tmm tests 保留不變；新案例另外對照 tmm（只作 test dependency）。
Macleod 是第二層外部軟體 benchmark，需實際人工執行。這些比較均不驗證 ATLU 是否適用 SiO₂/TiO₂，也不驗證教授樣品膜厚或 inverse fitting 唯一性。
