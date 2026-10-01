"""Separate research workflow; does not call the inverse-fitting pipeline."""
from io import BytesIO
from pathlib import Path
import hashlib
import subprocess
import matplotlib.pyplot as plt
import streamlit as st
from thinfilm.data import read_table
from thinfilm.validation import CASES, example_case, forward, import_reference, compare, bundle
from thinfilm.ui_text import text, metadata_view, COLUMN_LABELS, BACKSIDE_HELP, COHERENCE_HELP, OPTICS_GLOSSARY

st.set_page_config(page_title="Forward Model Validation（正向模型驗證）", layout="wide")
st.header("Forward Model Validation（正向模型驗證）")
st.caption("獨立於 Spectrum Analysis（光譜分析）的研究工具：已知 n/k → R/T；不執行 ATLU 或 inverse fitting（反向擬合）。")
st.info("Normal incidence（正入射）0°，S/P 等價；薄膜 coherent（相干），基板 k=0。Backside（基板背面反射）ON（開啟）：非相干厚透明基板；OFF（關閉）：半無限基板。")
st.warning("Ready for Essential Macleod comparison（可進行 Essential Macleod 比較）— 內建案例沒有真實 Macleod 輸出，不代表已通過 Macleod 驗證。")
try:
    revision = subprocess.run(["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        check=True, timeout=3).stdout.strip()
except (OSError, subprocess.SubprocessError):
    revision = "unavailable"
print(f"THINFILM_DEPLOYMENT commit={revision}", flush=True)

source = st.selectbox("Forward input（正向模型輸入）", [*CASES, "Custom known n/k CSV"], format_func=text,
    help="Built-in case（內建案例）使用固定已知 n/k；Custom known n/k（自訂已知 n/k）接受逐波長材料資料。")
if source == "Custom known n/k CSV":
    st.caption("CSV header（表頭）: wavelength_nm,film_n,film_k,substrate_n；每列提供已知色散，不推測單位。Wavelength（波長）nm、被動薄膜 k≥0、基板 n≥1。")
    uploaded = st.file_uploader("Known n/k CSV（已知折射率／消光係數）", type=["csv", "txt", "tsv"])
    d = st.number_input("Physical thickness（物理厚度，nm）", min_value=0., value=100.)
    back = st.checkbox("Backside enabled（啟用基板背面反射）", True, help=BACKSIDE_HELP)
    if uploaded is None:
        st.stop()
    try:
        run = forward(read_table(BytesIO(uploaded.getvalue())), d, back)
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        st.stop()
else:
    run = example_case(source)
st.write("Backside（基板背面反射）: " + ("ON（開啟）" if run.metadata["backside_enabled"] else "OFF（關閉）"))
st.write("Substrate treatment（基板處理）: " + text(run.metadata["substrate_coherence"]))
st.write("Film coherence（薄膜相干性）: " + text(run.metadata["film_coherence"]))
st.write(f"Incident angle（入射角）: {run.metadata['incidence_angle_deg']:g}°")
st.write("Polarization（偏振）: S/P equivalent at normal incidence（正入射時 S、P 偏振等價）")
st.caption(COHERENCE_HELP)
st.json(metadata_view(run.metadata), expanded=False)
st.dataframe(run.table, hide_index=True, column_config={
    c: st.column_config.NumberColumn(label, help=COLUMN_LABELS[c], width="small",
                                     format="%.3e" if c == "Program_A" else None)
    for c, label in {"wavelength_nm": "λ (nm)", "film_n": "n", "film_k": "k",
                     "substrate_n": "nₛ", "thickness_nm": "d (nm)",
                     "Program_R": "R", "Program_T": "T", "Program_A": "A"}.items()
})
st.caption(OPTICS_GLOSSARY + " Absorptance A（吸收率）= 1 − R − T。")
st.line_chart(run.table.set_index("wavelength_nm")[["Program_R", "Program_T", "Program_A"]].rename(columns=COLUMN_LABELS),
              x_label="Wavelength（波長，nm）", y_label="Fraction（0–1 小數）")
st.download_button("Download Macleod exchange ZIP（下載交換資料）", bundle(run, revision=revision),
                   "macleod_exchange.zip", "application/zip")
with st.expander("Macleod settings / exchange（設定與交換資料說明）"):
    st.markdown((Path(__file__).resolve().parents[1]/"docs"/"MACLEOD_VALIDATION.md").read_text(encoding="utf-8"))

st.subheader("Macleod reference import / comparison（參考資料匯入／比較）")
st.caption("可直接上傳 Essential Macleod Performance CSV，或使用 wavelength,R,T 有表頭 CSV。請明確選擇單位；原始上傳 bytes 會保留。")
unit = st.selectbox("Reference R/T unit（參考光譜單位）", ["fraction", "percent"], index=None, format_func=text)
wunit = st.selectbox("Reference wavelength unit（參考波長單位）", ["nm", "um"], index=None, format_func=text)
alignment = st.selectbox("Wavelength grid alignment（波長網格對齊）", ["exact", "interpolate"], format_func=text,
    help="Exact alignment（精確網格對齊）拒絕不同網格；Interpolation（線性內插）僅比較共同範圍內的程式點，不外插。")
tol = st.number_input("Engineering tolerance（工程容許差，fraction）", min_value=1e-12,
    value=1e-4, format="%.8f")
reason = st.text_input("Tolerance rationale（容許差依據）", value="工程初始門檻 1e-4 fraction（0.01 percentage point）；需依 Macleod 匯出精度與網格收斂重新評估，非文獻物理標準。")
st.caption("Engineering validation threshold（工程驗證門檻）：R、T 各自的 max |Δ|（最大絕對差異）≤ tolerance（容許差）才 PASS（通過）；分別報告 RMSE（均方根誤差）與 MAE（平均絕對誤差）。")
ref_file = st.file_uploader("Macleod reference CSV（參考資料）", type=["csv", "txt", "tsv"])
if ref_file is None:
    st.stop()
# A previous attestation must not carry over to another case, file or unit mapping.
attestation_key = hashlib.sha256(run.table.to_csv(index=False).encode() +
    str(run.metadata).encode() + ref_file.getvalue() + str((unit, wunit)).encode()).hexdigest()
confirmed = st.checkbox("我已確認這是真實 Macleod 匯出，且 n/k、d、0°、Backside（基板背面反射）與 coherence（相干性）設定一致",
                        key="attest_" + attestation_key)
if unit is None or wunit is None:
    st.error("請明確指定 Reference（參考資料）的 R/T 與 Wavelength（波長）單位。")
    st.stop()
try:
    reference = import_reference(ref_file.getvalue(), spectrum_unit=unit, wavelength_unit=wunit,
                                 filename=getattr(ref_file, "name", None))
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()
st.write("Reference source format（參考來源格式）: " + text(reference.metadata["source_format"]))
st.write("Original filename（原始檔名）: " + str(reference.metadata["original_filename"] or "unavailable（無法取得）"))
st.write("Column mapping（欄位對應）:")
for original, normalized in reference.metadata["column_mapping"].items():
    st.write(f"{original} → {normalized}")
st.write("Ignored for R/T comparison（未用於 R/T 比較）: " +
         (", ".join(reference.metadata["ignored_columns"]) or "None（無）"))
st.write(f"Reference points（參考點數）: {len(reference.analysis)}")
st.write(f"Reference wavelength（參考波長）: {reference.analysis.wavelength_nm.min():g}–{reference.analysis.wavelength_nm.max():g} nm")
st.write(f"Reference R/T unit（參考光譜單位）: {text(unit)} · Reference wavelength unit（參考波長單位）: {text(wunit)}")
st.write(f"Alignment（網格對齊）: {text(alignment)}")
try:
    comparison = compare(run, reference, alignment=alignment, tolerance=tol, tolerance_reason=reason)
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()
table, report = comparison
report["user_attests_macleod_and_matching_settings"] = confirmed
st.caption(text(report["alignment"]) + f"；Matched points（對齊點數）: {report['compared_points']}；Excluded program points（排除的程式點數）: {report['excluded_program_points']}")
if confirmed:
    st.info("使用者確認的 Macleod reference（參考資料）：" + ("PASS（通過）" if report["passed"] else "FAIL（未通過）") + "（僅針對本案例及所選工程門檻）")
else:
    st.warning("未確認 Macleod 來源／條件；以下僅為數值比較，不構成 Macleod validation（Macleod 驗證）。")
st.json(metadata_view(report))
st.caption("Program（程式結果）；Reference（參考資料）；Comparison（比較）；ΔR／ΔT（程式 − 參考）；Fraction（0–1 小數）；Wavelength（波長，nm）。")
fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
for ax, c in zip(axes, ("R", "T")):
    ax.plot(table.wavelength_nm, table["Program_"+c], label="Program " + c)
    ax.plot(table.wavelength_nm, table["Reference_"+c], "--", label="Reference " + c)
    ax.set_ylabel(c + " (fraction)")
    ax.legend()
for c in ("R", "T"):
    axes[2].plot(table.wavelength_nm, table["Delta_"+c], label="Δ"+c)
axes[2].axhline(tol, color="gray", linestyle=":")
axes[2].axhline(-tol, color="gray", linestyle=":")
axes[2].set(xlabel="Wavelength (nm)", ylabel="Program − Reference")
axes[2].legend()
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)
st.download_button("Download comparison evidence ZIP（下載比較證據）",
    bundle(run, revision=revision, reference=reference, comparison=comparison),
    "macleod_comparison.zip", "application/zip")
