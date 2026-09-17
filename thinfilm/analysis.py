"""Classical envelope initialization, Tauc diagnostics and independent comparison."""
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.signal import find_peaks, savgol_filter
from scipy.stats import linregress
from .data import read_table
from .physics import HC


def envelope(data, prominence=0.015, min_spacing_nm=30.0):
    result = {"available": False, "reason": "需要穿透率 T。", "d_nm": None,
              "curve": pd.DataFrame(), "extrema": pd.DataFrame()}
    if data.T is None:
        return result
    w = data.wavelength
    # Uniform-grid smoothing is used ONLY for detecting features, never regression.
    u = np.linspace(w.min(), w.max(), len(w))
    raw = np.interp(u, w, data.T)
    window = min(11, len(u)//2*2-1)
    y = savgol_filter(raw, window, 2)
    noise = float(np.median(data.sigma_T))
    prom = max(prominence, 4*noise)
    distance = max(2, int(min_spacing_nm/(u[1]-u[0])))
    peaks, _ = find_peaks(y, prominence=prom, distance=distance)
    valleys, _ = find_peaks(-y, prominence=prom, distance=distance)
    result["extrema"] = pd.DataFrame({"wavelength_nm": np.r_[u[peaks], u[valleys]],
                                      "T_smoothed": np.r_[y[peaks], y[valleys]],
                                      "kind": ["peak"]*len(peaks)+["valley"]*len(valleys)})
    if len(peaks) < 2 or len(valleys) < 2:
        result["reason"] = "可靠波峰或波谷不足兩個：傳統包絡法不可用，改用全光譜擬合。"
        return result
    lo, hi = max(u[peaks[0]], u[valleys[0]]), min(u[peaks[-1]], u[valleys[-1]])
    m = (w >= lo) & (w <= hi)
    x = w[m]
    if len(x) < 4:
        result["reason"] = "上下包絡線共同波長區域不足。"
        return result
    tm = PchipInterpolator(u[valleys], y[valleys], extrapolate=False)(x)
    tM = PchipInterpolator(u[peaks], y[peaks], extrapolate=False)(x)
    s = data.substrate_n[m]
    valid = (tm > 0.03) & (tM > tm) & (tM <= 1)
    N = np.full_like(x, np.nan)
    N[valid] = 2*s[valid]*(tM[valid]-tm[valid])/(tM[valid]*tm[valid])+(s[valid]**2+1)/2
    rad = N*N-s*s
    valid &= rad >= 0
    n = np.full_like(x, np.nan)
    n[valid] = np.sqrt(N[valid]+np.sqrt(rad[valid]))
    result["curve"] = pd.DataFrame({"wavelength_nm": x, "T_upper": tM, "T_lower": tm,
                                    "n_envelope": n})
    ds = []
    if valid.sum() >= 4:
        for indices in (peaks, valleys):
            xx = u[indices]
            xx = xx[(xx >= x[valid].min()) & (xx <= x[valid].max())]
            nn = np.interp(xx, x[valid], n[valid])
            for a, b, na, nb in zip(xx[:-1], xx[1:], nn[:-1], nn[1:]):
                denominator = 2*(b*na-a*nb)
                if denominator > 0:
                    ds.append(a*b/denominator)
    result.update(available=bool(ds), d_nm=float(np.median(ds)) if ds else None,
                  thickness_candidates_nm=ds,
                  reason="弱吸收、n 大於基板折射率、均勻單層假設下的初估；不是高吸收區切點修正。"
                  if ds else "可建構局部包絡線，但同類極值的有效配對不足以估厚度。")
    return result


def tauc_plot(wavelength, k, transition="amorphous", window_eV=None):
    powers = {"amorphous": 0.5, "indirect": 0.5, "direct": 2.0}
    if transition not in powers:
        raise ValueError("未知的 Tauc 躍遷型態。")
    e = HC/np.asarray(wavelength)
    alpha = 4*np.pi*np.asarray(k)/(np.asarray(wavelength)*1e-7)  # cm^-1
    order = np.argsort(e)
    e, alpha = e[order], alpha[order]
    y = (alpha*e)**powers[transition]
    table = pd.DataFrame({"energy_eV": e, "alpha_cm-1": alpha, "tauc_y": y,
                          "selected": False, "line": np.nan})
    base = {"available": False, "curve": table,
            "reason": "沒有符合條件的線性區間。", "Eg_eV": None,
            "source": "由同一擬合的 k 推得，非獨立驗證或額外硬約束。"}
    candidates = []
    if window_eV is not None:
        a, b = map(float, window_eV)
        if not 0 < a < b:
            raise ValueError("Tauc 能量區間必須 0 < 下限 < 上限。")
        selections = [np.where((e >= a) & (e <= b))[0]]
    else:
        selections = []
        # Compare several widths; require sufficient span and an absorption edge.
        for width in (0.25, 0.4, 0.6, 0.8):
            for a in np.linspace(e.min(), e.max()-width, 65):
                selections.append(np.where((e >= a) & (e <= a+width))[0])
    for ix in selections:
        if len(ix) < 8 or np.ptp(e[ix]) < 0.15 or np.min(alpha[ix]) < 1e3:
            continue
        lr = linregress(e[ix], y[ix])
        if lr.slope <= 0:
            continue
        eg = -lr.intercept/lr.slope
        r2 = lr.rvalue**2
        if 0 < eg < e[ix].min() and e[ix].min()-eg < 1.2 and r2 >= 0.98:
            candidates.append((r2-0.001/np.ptp(e[ix]), ix, lr, eg))
    if not candidates:
        return base
    _, ix, lr, eg = max(candidates, key=lambda a: a[0])
    table.loc[ix, "selected"] = True
    table["line"] = lr.slope*e+lr.intercept
    base.update(available=True, Eg_eV=float(eg), r_squared=float(lr.rvalue**2),
                slope=float(lr.slope), intercept=float(lr.intercept),
                window_eV=[float(e[ix].min()), float(e[ix].max())],
                selection="manual" if window_eV else "automatic_candidate",
                reason="線性區間僅為候選，請依材料與吸收邊人工檢查；此 Eg 可與 ATLU Eg 不同。")
    return base


def compare_reference(fitted, reference, d_nm, label="reference"):
    """Reference CSV accepts wavelength_nm, n, k, T, R, d_nm.

    Interpolate the fitted spectrum onto reference sampling within overlap only.
    Never turn reference points outside measured coverage into extrapolated values.
    """
    ref = read_table(reference)
    cols = [c for c in ("wavelength_nm", "n", "k", "T", "R", "d_nm") if c in ref]
    if not cols or not set(cols).intersection({"n", "k", "T", "R", "d_nm"}):
        raise ValueError("參考資料需要 n、k、T、R 或 d_nm。")
    ref = ref[cols].apply(pd.to_numeric, errors="raise")
    if not np.all(np.isfinite(ref.to_numpy())):
        raise ValueError("參考資料包含缺值或非有限值。")
    metrics, errors = [], pd.DataFrame()
    mapping = {"n": "n", "k": "k", "T": "T_fit", "R": "R_fit"}
    if set(mapping).intersection(ref.columns):
        if "wavelength_nm" not in ref or ref.wavelength_nm.duplicated().any():
            raise ValueError("參考光學常數需要不重複的 wavelength_nm。")
        if (ref.wavelength_nm <= 0).any():
            raise ValueError("參考波長必須為正。")
        for c in set(mapping).intersection(ref.columns):
            if (ref[c] < 0).any() or (c == "n" and (ref[c] == 0).any()):
                raise ValueError("參考光學常數不得為負，n 必須為正。")
            if c in ("T", "R") and (ref[c] > 1).any():
                raise ValueError("參考 T、R 必須先轉換成 0–1。")
        use = ref.wavelength_nm.between(fitted.wavelength_nm.min(), fitted.wavelength_nm.max())
        r = ref.loc[use].sort_values("wavelength_nm")
        if len(r) < 2:
            raise ValueError("與參考資料重疊的波長點不足兩個，禁止外插比較。")
        errors["wavelength_nm"] = r.wavelength_nm.to_numpy()
        for key, col in mapping.items():
            if key not in r:
                continue
            v = np.interp(r.wavelength_nm, fitted.wavelength_nm, fitted[col])
            err = v-r[key].to_numpy()
            errors[key+"_reference"] = r[key].to_numpy()
            errors[key+"_error"] = err
            errors[key+"_absolute_error"] = np.abs(err)
            for band, mask in [("all", np.ones(len(r), bool)),
                               ("UV", r.wavelength_nm.to_numpy() < 400),
                               ("visible", (r.wavelength_nm.to_numpy() >= 400) & (r.wavelength_nm.to_numpy() < 780)),
                               ("IR", r.wavelength_nm.to_numpy() >= 780)]:
                if not mask.any():
                    continue
                metrics.append(dict(source=label, parameter=key, band=band, count=int(mask.sum()),
                                    RMSE=float(np.sqrt(np.mean(err[mask]**2))),
                                    MAE=float(np.mean(np.abs(err[mask])))))
    if "d_nm" in ref:
        ds = ref.d_nm.to_numpy()
        if np.any(ds <= 0) or not np.allclose(ds, ds[0]):
            raise ValueError("單一樣品的參考 d_nm 必須為相同的正值。")
        metrics.append(dict(source=label, parameter="d_nm", band="scalar", count=1,
                            RMSE=abs(float(d_nm-ds[0])), MAE=abs(float(d_nm-ds[0])),
                            reference=float(ds[0]), relative_error_percent=100*abs(float(d_nm/ds[0]-1))))
    return pd.DataFrame(metrics), errors
