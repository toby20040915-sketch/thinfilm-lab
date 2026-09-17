"""Bounded multi-start regression with explicit numerical and inverse diagnostics."""
from dataclasses import dataclass, field, asdict, replace
import hashlib
import numpy as np
import pandas as pd
from scipy.optimize import least_squares, differential_evolution
from threadpoolctl import threadpool_limits
from .physics import Parameters, ATLU, HC, spectrum
from .analysis import envelope, tauc_plot

DEFAULT_BOUNDS = {
    "d_nm": (5., 2000.), "A_eV": (5., 300.), "Eg_eV": (0.3, 3.5),
    "gap_eV": (0.3, 4.), "C_eV": (0.2, 5.), "tail_fraction": (0.005, 0.25),
    "scatter_q": (0., 0.5),
}
LOG_PARAMETERS = {"d_nm", "A_eV", "C_eV", "gap_eV", "tail_fraction"}


@dataclass
class FitConfig:
    starts: int = 8
    seed: int = 35
    max_nfev: int = 450
    global_iterations: int = 100
    loss: str = "soft_l1"
    backside: bool = True
    fit_scatter: bool = False
    scatter_power: float = 4.
    gamma_eV: float = 0.02  # held fixed; assess sensitivity, not instrument bandwidth
    step_eV: float = 0.01
    cutoff_eV: float = 160.
    bounds: dict = field(default_factory=lambda: dict(DEFAULT_BOUNDS))
    fixed: dict = field(default_factory=dict)
    transition: str = "amorphous"
    tauc_window_eV: tuple | None = None

    def validate(self):
        if not 1 <= self.starts <= 100 or self.max_nfev < 1:
            raise ValueError("搜尋起點需介於 1–100，迭代上限需大於零。")
        if not 0 <= self.global_iterations <= 2000:
            raise ValueError("global_iterations 必須介於 0–2000。")
        if self.loss not in ("linear", "soft_l1"):
            raise ValueError("支援 linear 或 soft_l1 loss。")
        if not np.isfinite(self.scatter_power) or self.scatter_power <= 0:
            raise ValueError("散射冪次必須為正。")
        if set(self.bounds) != set(DEFAULT_BOUNDS) or not set(self.fixed) <= set(DEFAULT_BOUNDS):
            raise ValueError("參數名稱錯誤或 bounds 缺少參數。")
        for key, limits in self.bounds.items():
            a, b = limits
            if not np.isfinite(a+b) or a >= b or a < 0 or (key != "scatter_q" and a == 0):
                raise ValueError(f"{key} 的上下限無效。固定參數請放入 fixed。")
            if key == "tail_fraction" and b > 0.25:
                raise ValueError("本參數化限制 tail_fraction <= 0.25，以維持正 Urbach 能量。")
            if key in self.fixed and not a <= self.fixed[key] <= b:
                raise ValueError(f"固定 {key} 超出設定範圍。")


@dataclass
class FitResult:
    parameters: Parameters
    config: FitConfig
    table: pd.DataFrame
    summary: dict
    starts: pd.DataFrame
    envelope: dict
    tauc: dict
    correlation: pd.DataFrame
    uncertainty: pd.DataFrame


def _encode(key, value):
    return np.log(value) if key in LOG_PARAMETERS else value


def _decode(key, value):
    return np.exp(value) if key in LOG_PARAMETERS else value


def fit_spectrum(data, config=None, initial=None, progress=None):
    config = config or FitConfig()
    config.validate()
    with threadpool_limits(limits=1):
        return _fit(data, config, initial or Parameters(), progress)


def _fit(data, cfg, initial, progress):
    model = ATLU(HC/data.wavelength, cfg.gamma_eV, cfg.step_eV, cfg.cutoff_eV)
    fixed = dict(cfg.fixed)
    if not cfg.fit_scatter:
        fixed.setdefault("scatter_q", 0.)
    keys = [k for k in DEFAULT_BOUNDS if k not in fixed]
    if not keys:
        raise ValueError("至少保留一個待擬合參數。")
    lo = np.array([_encode(k, cfg.bounds[k][0]) for k in keys])
    hi = np.array([_encode(k, cfg.bounds[k][1]) for k in keys])
    # Optimize on a unit box so finite differences and condition numbers have a
    # declared scale. Report local covariance back in physical parameter units.
    def pack(p):
        return np.clip((np.array([_encode(k, getattr(p, k)) for k in keys])-lo)/(hi-lo), 1e-8, 1-1e-8)

    def unpack(x):
        d = {k: float(_decode(k, v)) for k, v in zip(keys, lo+x*(hi-lo))}
        return Parameters(**(d | fixed))

    def prediction(p):
        n, k = model.nk(p)
        return n, k, spectrum(data.wavelength, n, k, p.d_nm, data.substrate_n,
                              cfg.backside, p.scatter_q, cfg.scatter_power)

    def residual(x):
        _, _, sp = prediction(unpack(x))
        return np.concatenate([(sp[c]-getattr(data, c))/getattr(data, "sigma_"+c)
                               for c in ("T", "R") if getattr(data, c) is not None])

    def objective(r):
        return float(np.sum(r*r) if cfg.loss == "linear" else np.sum(2*(np.sqrt(1+r*r)-1)))

    env = envelope(data)
    rng = np.random.default_rng(cfg.seed)
    candidates = [pack(initial)]
    if env["available"] and cfg.backside and "d_nm" in keys:
        candidates.append(pack(replace(initial, d_nm=env["d_nm"])))
    global_summary = {"enabled": cfg.global_iterations > 0}
    if cfg.global_iterations:
        # Joint global search over thickness and dispersion is crucial: ranking a
        # handful of random optical parameters can systematically reject the
        # correct thickness basin. Use a deterministic reduced spectrum only for
        # seeding; all final residuals and fits use every original point.
        ix = np.unique(np.linspace(0, len(data.wavelength)-1, min(101, len(data.wavelength))).astype(int))
        coarse = ATLU(HC/data.wavelength[ix], cfg.gamma_eV, cfg.step_eV, cfg.cutoff_eV)
        def coarse_objective(x):
            pp = unpack(x)
            nn, kk = coarse.nk(pp)
            ss = spectrum(data.wavelength[ix], nn, kk, pp.d_nm, data.substrate_n[ix],
                          cfg.backside, pp.scatter_q, cfg.scatter_power)
            rr = np.concatenate([(ss[c]-getattr(data, c)[ix])/getattr(data, "sigma_"+c)[ix]
                                 for c in ("T", "R") if getattr(data, c) is not None])
            return objective(rr)
        global_fit = differential_evolution(coarse_objective, [(0., 1.)]*len(keys),
            maxiter=cfg.global_iterations, popsize=10, seed=cfg.seed, polish=False,
            tol=.005, updating="immediate")
        candidates.insert(0, global_fit.x)
        global_summary.update(iterations=int(global_fit.nit), evaluations=int(global_fit.nfev),
                              converged=bool(global_fit.success), coarse_objective=float(global_fit.fun))
        # Keep several different members of the final population as local seeds.
        for j in np.argsort(global_fit.population_energies):
            x = global_fit.population[j]
            if len(candidates) >= cfg.starts:
                break
            if all(np.linalg.norm(x-y) > .08 for y in candidates):
                candidates.append(x)
    # A cheap pool ranks initial states; local solves keep spatially diverse starts.
    pool = rng.uniform(0.03, 0.97, (max(40, cfg.starts*16), len(keys)))
    ranked = sorted(pool, key=lambda x: objective(residual(x)))
    for x in ranked:
        if len(candidates) >= cfg.starts:
            break
        if all(np.linalg.norm(x-y) > 0.18 for y in candidates):
            candidates.append(x)
    while len(candidates) < cfg.starts:
        candidates.append(rng.uniform(0.05, 0.95, len(keys)))
    runs, solutions = [], []
    for i, x in enumerate(candidates[:cfg.starts]):
        sol = least_squares(residual, x, bounds=(np.zeros(len(keys)), np.ones(len(keys))),
                            loss=cfg.loss, f_scale=1., x_scale="jac", max_nfev=cfg.max_nfev,
                            ftol=1e-9, xtol=1e-9, gtol=1e-8)
        p = unpack(sol.x)
        r = residual(sol.x)
        runs.append(dict(start=i+1, success=bool(sol.success), nfev=sol.nfev,
                         objective=objective(r), weighted_rmse=float(np.sqrt(np.mean(r*r))),
                         message=sol.message, **p.report()))
        solutions.append(sol)
        if progress:
            progress(i+1, len(candidates[:cfg.starts]), min(row["weighted_rmse"] for row in runs))
    # Select the lowest declared objective; a stopped best fit is explicitly marked.
    best = min(range(len(runs)), key=lambda i: runs[i]["objective"])
    sol, p = solutions[best], unpack(solutions[best].x)
    n, k, sp = prediction(p)
    r = residual(sol.x)
    table = pd.DataFrame({"wavelength_nm": data.wavelength, "energy_eV": HC/data.wavelength,
                          "n": n, "k": k, "alpha_cm-1": 4*np.pi*k/(data.wavelength*1e-7),
                          "substrate_n": data.substrate_n})
    for name, values in sp.items():
        table[name+"_fit" if name in ("T", "R") else name] = values
    metrics = {}
    for c in ("T", "R"):
        if getattr(data, c) is not None:
            table[c+"_measured"] = getattr(data, c)
            table["sigma_"+c] = getattr(data, "sigma_"+c)
            table[c+"_residual"] = sp[c]-getattr(data, c)
            metrics[c+"_RMSE"] = float(np.sqrt(np.mean(table[c+"_residual"]**2)))
    warnings = list(data.notes)
    if data.T is None or data.R is None:
        warnings.append("只有單一光譜通道，n、k、d 及散射可能互相補償；建議補充同樣品 R/T 或獨立厚度。")
    if not sol.success:
        warnings.append("最佳候選未達收斂條件；不得作為完成量測的結果。")
    weighted_rmse = float(np.sqrt(np.mean(r*r)))
    if weighted_rmse > 3:
        warnings.append("光譜殘差超過指定噪音尺度（標準化 RMSE > 3）；即使數值收斂，也未通過擬合品質檢查。")
    boundary = [name for name, v in zip(keys, sol.x) if v < 0.01 or v > 0.99]
    if boundary:
        warnings.append("參數靠近設定邊界："+", ".join(boundary)+"；需檢查先驗範圍與模型適用性。")
    # Raw whitened residual Jacobian, rather than scipy's robust-loss modified J.
    jac = np.empty((len(r), len(keys)))
    for j in range(len(keys)):
        a, b = sol.x.copy(), sol.x.copy()
        a[j], b[j] = max(0, a[j]-1e-5), min(1, b[j]+1e-5)
        jac[:, j] = (residual(b)-residual(a))/(b[j]-a[j])
    _, sv, vt = np.linalg.svd(jac, full_matrices=False)
    rank = int(np.sum(sv > sv[0]*1e-8)) if len(sv) and sv[0] > 0 else 0
    condition = float(sv[0]/sv[-1]) if sv[-1] > 0 else None
    covariance_ok = rank == len(keys) and not boundary and (condition is not None and condition < 1e8)
    corr = pd.DataFrame(index=keys, columns=keys, dtype=float)
    unc = pd.DataFrame({"parameter": keys, "value": [getattr(p, name) for name in keys],
                        "local_standard_error": np.nan})
    if covariance_ok:
        cov = (vt.T*(1/sv**2))@vt
        # sigma columns are treated as known measurement standard deviations.
        # Do not shrink covariance to zero for an exact synthetic fit.
        std = np.sqrt(np.diag(cov))
        corr[:] = cov/np.outer(std, std)
        scale = np.array([(hi[j]-lo[j])*(getattr(p, name) if name in LOG_PARAMETERS else 1.)
                          for j, name in enumerate(keys)])
        unc["local_standard_error"] = std*scale
        if np.any(np.abs(corr.to_numpy()-np.eye(len(keys))) > 0.98):
            warnings.append("部分參數局部相關係數 > 0.98；小光譜誤差不代表參數唯一。")
    else:
        warnings.append("Jacobian 秩不足、條件不佳或解靠近邊界，停用局部標準誤估計。")
    if cfg.loss != "linear":
        warnings.append("局部標準誤使用未加 robust 權重的線性化近似，不是 robust 信賴區間。")
    close = [row for row in runs if row["objective"] <= runs[best]["objective"]*1.02+1.]
    if len(close) > 1 and np.ptp([row["d_nm"] for row in close]) > 0.05*p.d_nm:
        warnings.append("近似相同擬合誤差對應不同膜厚；存在多解候選。")
    if cfg.fit_scatter or p.scatter_q > 0:
        warnings.append("散射為固定冪次的經驗鏡向收光損失，不能單憑此值推得 AFM 粗糙度或證明吸收與散射已分離。")
    if data.T is not None and np.mean(data.T < 3*data.sigma_T) > 0.2:
        warnings.append("超過 20% 的 T 點接近噪音底，吸收/厚度的資訊可能不足。")
    refined = ATLU(HC/data.wavelength, cfg.gamma_eV, cfg.step_eV/2, cfg.cutoff_eV*2)
    nr, kr = refined.nk(p)
    sr = spectrum(data.wavelength, nr, kr, p.d_nm, data.substrate_n,
                  cfg.backside, p.scatter_q, cfg.scatter_power)
    numerical = max(float(np.max(np.abs(sr[c]-sp[c]))) for c in ("T", "R"))
    sigma_min = min(float(np.min(getattr(data, "sigma_"+c))) for c in ("T", "R")
                    if getattr(data, c) is not None)
    if numerical > sigma_min*0.1:
        warnings.append("積分網格加密後光譜差超過最小標準差的 10%，請減小 step_eV 並重新擬合。")
    if HC/data.wavelength.min() < p.E0_eV:
        warnings.append("量測能量未涵蓋共振峰，色散外推與模型參數可能受先驗範圍影響。")
    tau = tauc_plot(data.wavelength, k, cfg.transition, cfg.tauc_window_eV)
    summary = dict(parameters=p.report(), config=asdict(cfg), metrics=metrics,
                   normalized_input_sha256=hashlib.sha256(data.frame().to_csv(index=False).encode("utf-8")).hexdigest(),
                   optimizer_success=bool(sol.success), optimizer_message=sol.message,
                   best_start=best+1, weighted_rmse=weighted_rmse,
                   fit_quality_pass=bool(sol.success and weighted_rmse <= 3 and numerical <= sigma_min*.1),
                   fit_quality_rule="optimizer success, weighted RMSE <= 3, numerical delta RT <= 0.1 * min sigma; not experimental validation",
                   global_search=global_summary,
                   jacobian_rank=rank, free_parameter_count=len(keys),
                   scaled_jacobian_condition=condition, covariance_available=covariance_ok,
                   numerical_refinement_max_delta_RT=numerical,
                   numerical_refinement_max_delta_n=float(np.max(np.abs(nr-n))),
                   numerical_refinement_max_delta_k=float(np.max(np.abs(kr-k))),
                   spectrum_range_nm=[float(data.wavelength.min()), float(data.wavelength.max())],
                   warnings=warnings, experimental_validation="尚未驗證；需同樣品獨立量測。")
    return FitResult(p, cfg, table, summary, pd.DataFrame(runs), env, tau, corr, unc)


def thickness_profile(data, result, thicknesses, starts=2, progress=None):
    """Re-fit nuisance parameters at each fixed d; raw chi-square diagnostic.

    Uses linear loss and does not convert delta chi-square into confidence limits
    automatically. Global convergence and noise/model assumptions must be checked.
    """
    rows = []
    for i, d in enumerate(thicknesses):
        cfg = replace(result.config, starts=starts, loss="linear",
                      global_iterations=0,
                      fixed=result.config.fixed | {"d_nm": float(d)})
        fitted = fit_spectrum(data, cfg, replace(result.parameters, d_nm=float(d)))
        count = len(data.wavelength)*(int(data.T is not None)+int(data.R is not None))
        rows.append({"d_nm": float(d), "chi_square": count*fitted.summary["weighted_rmse"]**2,
                     "converged": fitted.summary["optimizer_success"]})
        if progress:
            progress(i+1, len(thicknesses), fitted.summary["weighted_rmse"])
    frame = pd.DataFrame(rows)
    frame["delta_chi_square"] = frame.chi_square-frame.chi_square.min()
    return frame
