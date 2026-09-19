"""Traditional Chinese research interface. Run: streamlit run app.py."""
from dataclasses import asdict
from io import BytesIO
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "thinfilm_matplotlib"))
import matplotlib.pyplot as plt
from thinfilm.data import SpectrumData
from thinfilm.fit import FitConfig, DEFAULT_BOUNDS, fit_spectrum, thickness_profile
from thinfilm.demo import simulate, CASES
from thinfilm.analysis import compare_reference, envelope
from thinfilm.report import figures, result_files, zip_files

# Server-log-only provenance: never changes the analysis or its visible output.
try:
    _revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True, timeout=3, check=True,
    ).stdout.strip()
    if len(_revision) == 40 and all(c in "0123456789abcdef" for c in _revision):
        print(f"THINFILM_DEPLOYMENT commit={_revision}", flush=True)
except (OSError, subprocess.SubprocessError):
    # Git metadata may be absent from an exported ZIP; analysis remains usable.
    print("THINFILM_DEPLOYMENT commit=unavailable", flush=True)

st.set_page_config(page_title="薄膜光譜研究室", page_icon="🔬", layout="wide")
st.title("薄膜光譜研究室")
st.caption("修正包絡法 · ATLU 全光譜擬合 · Tauc 能隙 · 交叉驗證")
st.info("適用：空氣／均勻單層薄膜／透明厚基板，正入射量測。請使用絕對 T、R；若儀器已用裸基板歸一化，需先還原。")

with st.sidebar:
    st.header("量測與模型設定")
    mode = st.radio("資料來源", ["示範光譜（模擬）", "匯入 CSV"])
    units = st.selectbox("光譜單位", ["0–1 小數", "0–100 百分比"], disabled=mode.startswith("示範"))
    substrate = st.number_input("基板折射率（無色散資料時）", min_value=1., max_value=5., value=1.5, step=.01)
    sigma = st.number_input("預設量測標準差（0–1 單位）", min_value=.00001, max_value=.2, value=.005, format="%.5f")
    backside = st.checkbox("包含透明厚基板背面反射", True)
    fit_scatter = st.checkbox("擬合經驗散射損失", False)
    starts = st.slider("搜尋起點數", 1, 20, 6)
    d_bounds = st.slider("厚度搜尋範圍（nm）", 1., 3000., (5., 1500.))
    transition = st.selectbox("Tauc 圖型態", ["非晶 Tauc：1/2 次方", "間接躍遷：1/2 次方", "直接躍遷：2 次方"])
    with st.expander("進階設定與固定參數"):
        st.caption("Gamma 是 ATLU 模型展寬，並非儀器頻寬。可變更以評估模型敏感度。")
        gamma = st.number_input("Gamma（eV，固定）", min_value=.001, max_value=.2, value=.02, format="%.3f")
        step = st.selectbox("積分步長（eV）", [.01, .005, .0025])
        loss = st.selectbox("擬合損失", ["soft_l1", "linear"])
        scatter_power = st.number_input("散射波長冪次（固定）", min_value=1., max_value=6., value=4.)
        fixed_text = st.text_area("固定參數 JSON（例如獨立量測厚度）", value="{}")
        st.caption('例如 {"d_nm": 60} 或 {"tail_fraction": 0.08}。固定來源請自行記錄。')
        manual_tauc = st.checkbox("指定 Tauc 線性區間")
        ta = st.number_input("Tauc 下限（eV）", min_value=.1, value=1.8)
        tb = st.number_input("Tauc 上限（eV）", min_value=.1, value=2.4)

raw, truth, synthetic_params = None, None, None
if mode.startswith("示範"):
    labels = {"ultrathin_60nm": "極薄膜 60 nm", "absorbing_180nm": "吸收薄膜 180 nm",
              "fringes_900nm": "干涉條紋 900 nm", "scattering_120nm": "含散射損失 120 nm"}
    case = st.selectbox("示範樣品", list(CASES), format_func=lambda k: labels[k])
    raw, truth, synthetic_params = simulate(case)
    st.warning("目前是模擬資料，已知真值僅供測試。這些結果不能當作橢偏儀或 Macleod 實測證據。")
    if case.startswith("scattering") and not fit_scatter:
        st.caption("此示範含散射衰減；可啟用左側散射擬合，比較模型選擇的影響。")
else:
    uploaded = st.file_uploader("上傳光譜 CSV", type=["csv", "txt", "tsv"])
    st.caption("必填 wavelength_nm，以及 T 或 R。選填 sigma_T、sigma_R、substrate_n；提供基板色散欄位時優先採用。")
    if uploaded:
        raw = BytesIO(uploaded.getvalue())

if raw is None:
    st.stop()
try:
    data = SpectrumData.from_csv(raw, "fraction" if mode.startswith("示範") or units.startswith("0–1 ") else "percent", substrate, sigma)
    bounds = dict(DEFAULT_BOUNDS)
    bounds["d_nm"] = d_bounds
    fixed = json.loads(fixed_text)
    if not isinstance(fixed, dict):
        raise ValueError("固定參數必須是 JSON 物件。")
    cfg = FitConfig(starts=starts, backside=backside, fit_scatter=fit_scatter,
                    bounds=bounds, gamma_eV=gamma, step_eV=step, loss=loss, fixed=fixed,
                    scatter_power=scatter_power, transition=["amorphous", "indirect", "direct"][
                        ["非晶 Tauc：1/2 次方", "間接躍遷：1/2 次方", "直接躍遷：2 次方"].index(transition)],
                    tauc_window_eV=(ta, tb) if manual_tauc else None)
    cfg.validate()
    if manual_tauc and ta >= tb:
        raise ValueError("Tauc 下限必須小於上限。")
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()

fingerprint = hashlib.sha256((data.frame().to_csv(index=False)+json.dumps(asdict(cfg), sort_keys=True)).encode()).hexdigest()
left, right = st.columns([2, 1])
with left:
    st.line_chart(data.frame().set_index("wavelength_nm")[[c for c in ("T", "R") if getattr(data, c) is not None]], height=250)
with right:
    st.metric("量測點數", len(data.wavelength))
    st.write(f"波長 {data.wavelength.min():.1f}–{data.wavelength.max():.1f} nm")
    env = envelope(data)
    st.caption(env["reason"])
    if env["d_nm"]:
        st.write(f"傳統包絡法初估：{env['d_nm']:.2f} nm")
    st.download_button("下載目前光譜 CSV", data.frame().to_csv(index=False).encode("utf-8-sig"), "spectrum.csv", "text/csv")

if st.button("開始全光譜分析", type="primary"):
    bar = st.progress(0., text="建立模型並搜尋初始值…")
    try:
        result = fit_spectrum(data, cfg, progress=lambda i, total, err: bar.progress(i/total, text=f"起點 {i}/{total} · 最佳標準化 RMSE {err:.3f}"))
        st.session_state["result"] = result
        st.session_state["fingerprint"] = fingerprint
        st.session_state.pop("profile", None)
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
        st.error("分析失敗："+str(exc))
    finally:
        bar.empty()

if "result" not in st.session_state:
    st.stop()
if fingerprint != st.session_state.get("fingerprint"):
    st.warning("資料或設定已變更，請重新分析；先前結果已隱藏，避免混用。")
    st.stop()
result = st.session_state["result"]
if result.summary["fit_quality_pass"]:
    st.success("數值擬合已收斂。請繼續檢查可信度及獨立參考資料。")
else:
    st.error("最佳候選未通過擬合品質檢查。請檢查殘差、噪音、模型與參數範圍；數值收斂本身不足以採用結果。")
cols = st.columns(4)
cols[0].metric("薄膜厚度 d", f"{result.parameters.d_nm:.3f} nm")
cols[1].metric("ATLU 模型 Eg", f"{result.parameters.Eg_eV:.3f} eV")
cols[2].metric("Tauc 候選 Eg", f"{result.tauc['Eg_eV']:.3f} eV" if result.tauc["available"] else "無可靠區間")
cols[3].metric("標準化 RMSE", f"{result.summary['weighted_rmse']:.3f}")
tabs = st.tabs(["光譜與結果", "可信度與多解", "交叉驗證", "匯出"])
with tabs[0]:
    fig = figures(result)
    st.pyplot(fig)
    plt.close(fig)
    st.caption("圖中的 T、R 模型曲線都會顯示；只有已提供的量測通道參與擬合。")
    st.write(result.tauc["reason"])
    st.caption(result.tauc["source"])
    st.dataframe(result.table, hide_index=True)
    if synthetic_params:
        st.write(f"模擬厚度真值：{synthetic_params.d_nm:g} nm；厚度絕對誤差：{abs(result.parameters.d_nm-synthetic_params.d_nm):.4f} nm")
with tabs[1]:
    for warning in result.summary["warnings"]:
        st.warning(warning)
    st.caption("d < 100 nm 與 k > 10⁻³ 不是普適失效界線。能否反演取決於波段、訊噪比、吸收光程與參數可辨識性。")
    st.dataframe(result.starts, hide_index=True)
    st.write("局部參數標準誤（不是總誤差或保證精度）")
    st.dataframe(result.uncertainty, hide_index=True)
    st.dataframe(result.correlation)
    st.write(f"積分加密後最大 T/R 差：{result.summary['numerical_refinement_max_delta_RT']:.3g}")
    st.caption("厚度掃描會在每個指定厚度重新擬合其他參數；需較長運算時間。平坦或多谷曲線代表厚度可能不唯一。")
    if st.button("執行 9 點厚度可信度掃描"):
        lo, hi = cfg.bounds["d_nm"]
        ds = np.linspace(max(lo, result.parameters.d_nm*.7), min(hi, result.parameters.d_nm*1.3), 9)
        bar = st.progress(0.)
        try:
            st.session_state["profile"] = thickness_profile(data, result, ds,
                progress=lambda i, total, err: bar.progress(i/total))
        except ValueError as exc:
            st.error(str(exc))
        finally:
            bar.empty()
    if "profile" in st.session_state:
        st.line_chart(st.session_state["profile"].set_index("d_nm")[["delta_chi_square"]])
        st.dataframe(st.session_state["profile"], hide_index=True)

comparisons = []
with tabs[2]:
    st.write("匯入同一樣品的橢偏儀與 Macleod 匯出資料，各自計算逐波長誤差和分波段 RMSE。")
    st.caption("CSV：wavelength_nm + n/k/T/R，可加相同的 d_nm；T/R 必須是 0–1。只比較重疊波段，不外插。此處不會直接連線或操作儀器。")
    for label in ("橢偏儀", "Essential Macleod"):
        ref = st.file_uploader(label+"參考 CSV", type=["csv"], key="ref_"+label)
        if ref:
            try:
                metrics, errors = compare_reference(result.table, BytesIO(ref.getvalue()), result.parameters.d_nm, label)
                comparisons.append((label, metrics, errors))
                st.dataframe(metrics, hide_index=True)
            except (ValueError, TypeError) as exc:
                st.error(label+"："+str(exc))
    if truth is not None:
        with st.expander("模擬真值比較（非第三方實驗驗證）"):
            metrics, errors = compare_reference(result.table, truth, result.parameters.d_nm, "synthetic_truth")
            st.dataframe(metrics, hide_index=True)
            comparisons.append(("synthetic_truth", metrics, errors))
with tabs[3]:
    files = result_files(result, comparisons, st.session_state.get("profile"))
    st.download_button("下載完整結果 ZIP", zip_files(files), "thinfilm_result.zip", "application/zip", type="primary")
    st.download_button("下載可離線閱讀的報告", files["report.html"], "report.html", "text/html")
    st.download_button("下載 n、k 與擬合光譜", files["optical_constants_and_fit.csv"], "optical_constants_and_fit.csv", "text/csv")
    st.download_button("下載全部設定與判讀資訊", files["summary.json"], "summary.json", "application/json")
