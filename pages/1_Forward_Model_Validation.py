"""Separate research workflow; does not call the inverse-fitting pipeline."""
from io import BytesIO
from pathlib import Path
import hashlib
import subprocess
import matplotlib.pyplot as plt
import streamlit as st
from thinfilm.data import read_table
from thinfilm.validation import CASES, example_case, forward, import_reference, compare, bundle

st.set_page_config(page_title="Forward Model Validation", layout="wide")
st.title("Forward Model Validation")
st.caption("獨立於 Spectrum Analysis 的研究工具：已知 n/k → R/T；不執行 ATLU 或 inverse fitting。")
st.info("僅支援 0° normal incidence，S/P 等價。薄膜 coherent；基板 k=0。背面 ON：厚透明基板 incoherent；OFF：半無限基板。")
st.warning("Ready for Essential Macleod comparison — 內建案例沒有真實 Macleod 輸出，不代表已通過 Macleod 驗證。")
try:
    revision = subprocess.run(["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        check=True, timeout=3).stdout.strip()
except (OSError, subprocess.SubprocessError):
    revision = "unavailable"
print(f"THINFILM_DEPLOYMENT commit={revision}", flush=True)

source = st.selectbox("Forward input", [*CASES, "Custom known n/k CSV"])
if source == "Custom known n/k CSV":
    st.caption("CSV header: wavelength_nm,film_n,film_k,substrate_n；每列提供已知色散，不推測單位。波長 nm、被動 film k≥0、substrate n≥1。")
    uploaded = st.file_uploader("Known n/k CSV", type=["csv", "txt", "tsv"])
    d = st.number_input("Known thickness (nm)", min_value=0., value=100.)
    back = st.checkbox("Backside enabled", True)
    if uploaded is None:
        st.stop()
    try:
        run = forward(read_table(BytesIO(uploaded.getvalue())), d, back)
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        st.stop()
else:
    run = example_case(source)
st.json(run.metadata, expanded=False)
st.dataframe(run.table, hide_index=True)
st.line_chart(run.table.set_index("wavelength_nm")[["Program_R", "Program_T", "Program_A"]],
              x_label="Wavelength (nm)", y_label="Fraction")
st.download_button("Download Macleod exchange ZIP", bundle(run, revision=revision),
                   "macleod_exchange.zip", "application/zip")
with st.expander("人工 Macleod 設定與 exchange 說明"):
    st.markdown((Path(__file__).resolve().parents[1]/"docs"/"MACLEOD_VALIDATION.md").read_text(encoding="utf-8"))

st.subheader("Macleod reference import / comparison")
st.caption("可直接上傳 Essential Macleod Performance CSV，或使用 wavelength,R,T 有表頭 CSV。請明確選擇單位；原始上傳 bytes 會保留。")
unit = st.selectbox("Reference R/T unit", ["fraction", "percent"], index=None)
wunit = st.selectbox("Reference wavelength unit", ["nm", "um"], index=None)
alignment = st.selectbox("Wavelength grid alignment", ["exact", "interpolate"],
    help="exact 拒絕不同網格；interpolate 明確使用線性內插，僅比較共同範圍內的 Program 點，不外插。")
tol = st.number_input("Max absolute difference tolerance (fraction)", min_value=1e-12,
    value=1e-4, format="%.8f")
reason = st.text_input("Tolerance rationale", value="工程初始門檻 1e-4 fraction（0.01 percentage point）；需依 Macleod 匯出精度與網格收斂重新評估，非文獻物理標準。")
st.caption("Engineering validation threshold：R 與 T 各自的 max |Δ| ≤ tolerance 才 PASS；RMSE 與 MAE 分別報告。")
ref_file = st.file_uploader("Macleod reference CSV", type=["csv", "txt", "tsv"])
if ref_file is None:
    st.stop()
# A previous attestation must not carry over to another case, file or unit mapping.
attestation_key = hashlib.sha256(run.table.to_csv(index=False).encode() +
    str(run.metadata).encode() + ref_file.getvalue() + str((unit, wunit)).encode()).hexdigest()
confirmed = st.checkbox("我已確認這是真實 Macleod 匯出，且 n/k、d、0°、backside 與 coherence 設定一致",
                        key="attest_" + attestation_key)
if unit is None or wunit is None:
    st.error("請明確指定 reference 的 R/T 與 wavelength 單位。")
    st.stop()
try:
    reference = import_reference(ref_file.getvalue(), spectrum_unit=unit, wavelength_unit=wunit,
                                 filename=getattr(ref_file, "name", None))
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()
st.write("Reference source format: " + reference.metadata["source_format"])
st.write("Original filename: " + str(reference.metadata["original_filename"] or "unavailable"))
st.write("Column mapping:")
for original, normalized in reference.metadata["column_mapping"].items():
    st.write(f"{original} → {normalized}")
st.write("Ignored for R/T comparison: " +
         (", ".join(reference.metadata["ignored_columns"]) or "None"))
st.write(f"Reference points: {len(reference.analysis)}")
st.write(f"Reference wavelength: {reference.analysis.wavelength_nm.min():g}–{reference.analysis.wavelength_nm.max():g} nm")
st.write(f"Reference R/T unit: {unit} · Reference wavelength unit: {wunit} · Alignment: {alignment}")
try:
    comparison = compare(run, reference, alignment=alignment, tolerance=tol, tolerance_reason=reason)
except (ValueError, TypeError) as exc:
    st.error(str(exc))
    st.stop()
table, report = comparison
report["user_attests_macleod_and_matching_settings"] = confirmed
st.caption(report["alignment"] + f"; compared points: {report['compared_points']}; excluded program points: {report['excluded_program_points']}")
if confirmed:
    st.info("使用者確認的 Macleod reference：" + ("PASS" if report["passed"] else "FAIL") + "（僅針對本案例及所選工程門檻）")
else:
    st.warning("未確認 Macleod 來源／條件；以下僅為數值比較，不構成 Macleod validation。")
st.json(report)
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
st.download_button("Download comparison evidence ZIP",
    bundle(run, revision=revision, reference=reference, comparison=comparison),
    "macleod_comparison.zip", "application/zip")
