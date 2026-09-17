"""Portable CSV, JSON, PNG and self-contained HTML exports."""
from io import BytesIO
import base64
import html
import json
import zipfile
import os
import tempfile
from pathlib import Path
import numpy as np
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "thinfilm_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def figures(result):
    t = result.table
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    w = t.wavelength_nm
    for c, color in (("T", "#008c95"), ("R", "#cf7d2f")):
        axes[0, 0].plot(w, t[c+"_fit"], color=color, label=c+" model")
        if c+"_measured" in t:
            axes[0, 0].scatter(w, t[c+"_measured"], s=7, alpha=.4, color=color, label=c+" data")
            axes[1, 0].plot(w, t[c+"_residual"], color=color, label=c+" residual")
    axes[0, 0].set(xlabel="Wavelength (nm)", ylabel="Fraction", title="Spectrum fit")
    axes[0, 0].legend(ncol=2, fontsize=8)
    axes[1, 0].axhline(0, color="#999999", lw=.6)
    axes[1, 0].set(xlabel="Wavelength (nm)", ylabel="Model - measured", title="Residuals")
    axes[1, 0].legend()
    axes[0, 1].plot(w, t.n, color="#008c95", label="n")
    axes[0, 1].plot(w, t.k, color="#a04d86", label="k")
    axes[0, 1].set(xlabel="Wavelength (nm)", title=f"Optical constants | d = {result.parameters.d_nm:.3f} nm")
    axes[0, 1].legend()
    tau = result.tauc
    curve = tau["curve"]
    axes[1, 1].plot(curve.energy_eV, curve.tauc_y, color="#566b8d", label="From fitted k")
    if tau["available"]:
        m = curve.selected
        axes[1, 1].scatter(curve.loc[m, "energy_eV"], curve.loc[m, "tauc_y"], s=8, color="#cf7d2f")
        e = np.array([tau["Eg_eV"], tau["window_eV"][1]])
        axes[1, 1].plot(e, tau["slope"]*e+tau["intercept"], "--", color="#cf7d2f",
                        label=f"Candidate Eg = {tau['Eg_eV']:.3f} eV")
    axes[1, 1].set(xlabel="Photon energy (eV)", ylabel="Tauc ordinate (see transition)", title="Tauc diagnostic")
    axes[1, 1].legend(fontsize=8)
    return fig


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def result_files(result, comparisons=None, profile=None):
    summary = result.summary | {
        "tauc": {k: v for k, v in result.tauc.items() if k != "curve"},
        "envelope": {k: v for k, v in result.envelope.items() if k not in ("curve", "extrema")},
    }
    files = {"summary.json": json.dumps(_clean(summary), ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")}
    tables = {"optical_constants_and_fit": result.table, "multistart": result.starts,
              "local_uncertainty": result.uncertainty, "correlation": result.correlation.reset_index(),
              "envelope": result.envelope["curve"], "extrema": result.envelope["extrema"],
              "tauc": result.tauc["curve"]}
    original = {"wavelength_nm": result.table.wavelength_nm, "substrate_n": result.table.substrate_n}
    for channel in ("T", "R"):
        if channel+"_measured" in result.table:
            original[channel] = result.table[channel+"_measured"]
            if "sigma_"+channel in result.table:
                original["sigma_"+channel] = result.table["sigma_"+channel]
    import pandas as pd
    tables["normalized_input"] = pd.DataFrame(original)
    if profile is not None:
        tables["thickness_profile"] = profile
    for i, (label, metrics, errors) in enumerate(comparisons or []):
        # Fixed safe filenames avoid interpreting uploaded names as paths.
        tables[f"reference_{i+1}_metrics"] = metrics
        tables[f"reference_{i+1}_errors"] = errors
    for name, frame in tables.items():
        files[name+".csv"] = frame.to_csv(index=False).encode("utf-8-sig")
    fig = figures(result)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    files["analysis.png"] = buf.getvalue()
    warnings = "".join("<li>"+html.escape(w)+"</li>" for w in result.summary["warnings"])
    params = "".join(f"<tr><td>{html.escape(k)}</td><td>{v:.7g}</td></tr>" for k, v in result.parameters.report().items())
    comparison_html = "".join("<h2>"+html.escape(label)+"</h2>"+metrics.to_html(index=False)
                              for label, metrics, _ in (comparisons or []))
    image = base64.b64encode(files["analysis.png"]).decode("ascii")
    success = "通過數值擬合品質檢查" if result.summary["fit_quality_pass"] else "未通過數值擬合品質檢查"
    files["report.html"] = f"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<title>薄膜光譜分析報告</title><style>body{{font-family:system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#23313b;line-height:1.7}}h1{{color:#007c83}}table{{border-collapse:collapse}}td,th{{padding:6px 16px;border-bottom:1px solid #ddd}}img{{width:100%}}li{{margin:8px 0}}.note{{background:#edf6f6;padding:16px;border-radius:10px}}</style>
<h1>薄膜光譜分析報告</h1><p>ATLU 全光譜數值修正包絡法 · 狀態：{success}</p>
<p class="note">此報告是指定物理模型與設定下的反演結果。模擬重建不等於實測驗證；小光譜殘差不保證 n、k、d 唯一。Tauc 結果使用同一組擬合 k，不能視為獨立驗證。</p>
<img alt="光譜、殘差、光學常數與 Tauc 圖" src="data:image/png;base64,{image}">
<h2>參數</h2><table>{params}</table><h2>判讀事項</h2><ul>{warnings}</ul>{comparison_html}
<h2>重現與模型範圍</h2><p>完整設定、最佳化狀態及積分加密誤差見 summary.json；逐波長數據見 optical_constants_and_fit.csv。支援空氣／均勻單層／透明基板的正入射模型。</p>
<p>模型依據：<a href="https://doi.org/10.3390/coatings12101549">Ballester et al. (2022), Eqs. 6–9</a>；<a href="https://arxiv.org/abs/1603.02720">Byrnes, Multilayer optical calculations</a>。</p></html>""".encode("utf-8")
    return files


def zip_files(files):
    target = BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return target.getvalue()
