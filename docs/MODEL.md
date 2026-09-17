# 數學模型與選擇

## 1. 色散與因果積分

能量 E 使用 eV，波長 lambda 使用 nm，`E = 1239.8419843320026 / lambda`。
採用 exp(-i omega t) 時間慣例，複數折射率 N=n+ik，被動吸收材料 k>=0，epsilon=N²。

採 Ballester et al. (2022) Eqs. 6–9 的 corrected TLU，而非直接將 `exp(E/Eu)/E` 延伸至零能量。

對正能量定義吸收權重 f(E)：

```text
D(E) = (E² − E0²)² + C²E²
f(E) = A E0 C (E − Eg)² / [E D(E)]                    E > Ec
f(E) = f(Ec) (E/Ec) exp[(E − Ec)/Eu]                  0 <= E <= Ec
1/Eu = 2/(Ec − Eg) − 2/Ec − D'(Ec)/D(Ec)
Ec = Eg (1 + tail_fraction)
E0 = Ec + gap
```

接點值與一階導數連續，且 f(0)=0。tail_fraction 上限 0.25 是這份程式的參數化選擇，不是文獻的普適材料界線。Eu 由接點條件導出，不是獨立任意參數。

將權重向負能量奇延伸，令 z=E+i Gamma 且 Gamma>0：

```text
epsilon(z) = 1 + (1/pi) integral_0^infinity f(x)[1/(x-z) + 1/(x+z)] dx
n + i k = sqrt(epsilon)
alpha (cm^-1) = 4*pi*k / (lambda_nm * 1e-7)
```

這個正、負頻率組合共同保證所用因果響應的對稱性。不能只算正頻率的 `1/(x-z)`。

數值方法：將 f(x) 在網格上作線性插值，每段積分使用複數 log 原始函數精確計算。預設 0–20 eV 採 0.01 eV 步長（高能量輸入時自動延長密集區），後段用幾何網格延伸至 160 eV。這比直接用固定梯形法去取樣窄 Lorentz 峰更穩定，但仍有權重插值誤差與尾端截斷誤差。

每次完成擬合後，用半步長與雙截斷能量重新計算最佳解，輸出最大 n、k 及 T/R 差。若差大於量測 sigma 的 10%，應加密後重新擬合。Gamma 固定但可調，應在報告記錄敏感度；本版不採 Ei 閉式式，避免分支選取與浮點指數相消問題。模型大能量背景固定為 1。

本程式依公開數學式獨立實作。數值積分與閉式 ATLU 計算是同一目標積分的不同實現，不能稱為逐項重現論文所有實驗設定。

## 2. 正入射光學模型

對透明入射介質 a、吸收薄膜 b、透明出射介質 c，使用 Fresnel 界面振幅與
`P=exp(i 2*pi*N*d/lambda)`。總振幅為：

```text
r = (r_ab + r_bc P²)/(1 + r_ab r_bc P²)
t = t_ab t_bc P/(1 + r_ab r_bc P²)
R = |r|²
T = Re(c)/Re(a) * |t|²
```

P 在強吸收時衰減，避免傳統特徵矩陣 cos/sin 複數厚度溢位。

透明厚基板的背面反射採非相干強度級數，先計算薄膜正面 Rf/Tf、反面 Rb/Tb，基板背面 Rs：

```text
T_total = Tf (1-Rs)/(1-Rb Rs)
R_total = Rf + Tf Rs Tb/(1-Rb Rs)
```

裸玻璃、零厚度極限回復 `T=2s/(s²+1)`。無吸收時 R+T=1。此版不含基板吸收或厚基板的相干 Fabry–Perot 條紋。

## 3. 經驗散射項

```text
S(lambda) = exp[-scatter_q (550/lambda)^scatter_power]
T_collected = S T_total
R_collected = S R_total
scattered_loss = (1-S)(T_total + R_total)
A_intrinsic = 1-T_total-R_total
```

`T_collected + R_collected + A_intrinsic + scattered_loss = 1`。

這是收光損失的現象模型，預設 power=4，但**不代表任意表面粗糙散射皆服從 Rayleigh 型波長冪律**。不能把 q 轉成 AFM RMS nm；也未建模散射對光路、相位或再吸收的改變。積分球量測可能收集漫射能量，不能沿用相同的收光損失假設。

## 4. 包絡線角色

只有特徵擷取時使用均勻波長網格與 Savitzky–Golay 平滑，擬合仍使用原始值。峰值 prominence 至少是指定 sigma 的四倍；上、下包絡線採 PCHIP，只在共同涵蓋區間計算。依計畫書所列 Swanepoel n 式求出初估，使用相鄰同類極值的
`d=lambda1*lambda2/[2(lambda2*n1-lambda1*n2)]` 求厚度初值。

必須符合透明基板、弱吸收、足夠可辨識條紋及薄膜 n 高於基板的假設。沒有條紋時不生成假的上下包絡線。初值只是多起點之一；最終 n/k/d 由原始全光譜擬合決定，並未宣稱完成強吸收區的幾何切點解析修正。

## 5. 非線性擬合

先用差分演化進行聯合全域初值搜尋（預設 100 代、每維 10 個族群個體，最多取 101 個量測波長作初值評估），再納入預設物理初值、包絡線厚度及不同區域的候選進行多起點有界 `least_squares`。所有最終擬合與誤差評估均使用完整原始資料。d、A、C、gap、tail_fraction 使用 log 參數化；所有自由參數映射到 [0,1] 後擬合。

殘差 `r=(model-measured)/sigma`。linear 最小化 sum(r²)；soft_l1 使用 SciPy 定義並以 f_scale=1 對應一個 sigma。選取最小所選目標函數的候選，保留每個候選的終止狀態；未收斂候選絕不標記已收斂。

Jacobian 為最佳解處原始標準化殘差的有限差分，對經參數範圍縮放的變數計算 SVD。數值秩門檻 s_max*1e-8。只有滿秩、條件數 <1e8 且無接近邊界參數時提供局部標準誤，cov=(JᵀJ)^−1 後轉換回物理參數單位。輸入 sigma 作為已知噪音，不以殘差趨零來壓縮標準誤。

這不是完整的非線性、多解或模型誤差區間。特別是 robust loss 下，輸出的局部尺度不是 sandwich estimator 或 bootstrap CI。厚度 profile 會在每個 d 重擬合 nuisance parameters，固定採 linear loss，僅輸出 chi-square 相對曲線及收斂狀態。

## 6. Tauc 與物理先驗

非晶 Tauc / 間接型使用 `(alpha E)^0.5`，直接型使用 `(alpha E)^2`。自動候選要求至少 8 點、能量跨度 >=0.15 eV、alpha>=1000 cm^-1、正斜率、R²>=0.98 及正能隙截距；這些是可審查的候選篩選規則，不是材料定理。

計畫書希望用 Tauc Eg 作硬性邊界，但若 alpha 也是從同一待解的 k、d 算出，直接回灌並不增加獨立資訊。此版改由 ATLU 在擬合內維持物理結構，Tauc 圖作擬合後診斷。只有來自獨立實驗且適用同材料定義的 Eg，才應透過 `fixed` 或 bounds 約束。

不能僅憑 Tauc Plot 的形式就判定非晶材料等同晶體中的聲子輔助間接躍遷，介面保留兩者名稱但共享其常見繪圖次方。

## 7. 交叉驗證

以程式曲線插值至獨立參考波長，只保留共同涵蓋範圍，輸出逐點 signed / absolute errors。
`RMSE = sqrt(mean((program-reference)^2))`。
分波段採 UV<400 nm、visible 400–780 nm（不含 780）、IR>=780 nm；這是報表分類，不改變擬合。

## 文獻

1. Ballester et al., Coatings 12, 1549 (2022), https://doi.org/10.3390/coatings12101549 。
2. Byrnes, Multilayer optical calculations, https://arxiv.org/abs/1603.02720 。
3. Swanepoel (1983)，計畫書所列公式 (1)、(2) 及同類極值干涉階次關係。
