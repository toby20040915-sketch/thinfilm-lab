"""Bilingual presentation only; canonical data and export schemas stay unchanged."""

TEXT = {
    "fraction": "fraction（0–1 小數）",
    "percent": "percent（百分比）",
    "nm": "nm（奈米）",
    "um": "um（微米）",
    "ascending": "ascending（遞增）",
    "descending": "descending（遞減）",
    "unsorted": "unsorted（未排序）",
    "exact": "Exact alignment（精確網格對齊）",
    "interpolate": "Interpolation（線性內插）",
    "coherent": "coherent（相干）",
    "incoherent thick substrate": "incoherent thick substrate（非相干厚基板）",
    "semi-infinite; no rear interface": "semi-infinite（半無限基板；不考慮背面界面）",
    "semi-infinite substrate": "semi-infinite substrate（半無限基板）",
    "air n=1 k=0": "Air（空氣） n=1 k=0",
    "transparent, real n(lambda) >= 1, substrate k=0": "Transparent substrate（透明基板）：實數 n(λ) ≥ 1，k=0",
    "known n/k; no ATLU": "Known n/k（已知折射率／消光係數）；不使用 ATLU",
    "normal incidence: s and p equivalent; no oblique-angle support": "Normal incidence（正入射）：S、P 等價；不支援斜入射",
    "Ready for Essential Macleod comparison": "Ready for Essential Macleod comparison（可進行 Essential Macleod 比較）",
    "Custom known n/k CSV": "Custom known n/k CSV（自訂已知 n/k）",
    "Custom known n/k": "Custom known n/k（自訂已知 n/k）",
    "A — Bare substrate / zero film": "A — Bare substrate（裸基板） / zero film（零膜厚）",
    "B — Transparent film / semi-infinite substrate": "B — Transparent film（透明薄膜） / semi-infinite substrate（半無限基板）",
    "C — Absorbing film": "C — Absorbing film（吸收薄膜）",
    "D — Backside OFF": "D — Backside（基板背面反射） OFF（關閉）",
    "E — Backside ON": "E — Backside（基板背面反射） ON（開啟）",
    "identical grid": "Identical grid（相同波長網格）",
    "linear reference interpolation onto program grid; overlap only": "Linear reference interpolation（參考資料線性內插至程式網格；僅共同波段）",
    "engineering validation threshold": "Engineering validation threshold（工程驗證門檻）",
    "max absolute difference <= tolerance for each channel": "Max absolute difference（最大絕對差異）：每個通道皆須 ≤ tolerance（容許差）",
    "Essential Macleod Performance CSV": "Essential Macleod Performance CSV（性能表匯出）",
    "canonical CSV": "Canonical CSV（標準欄位格式）",
}

METADATA_LABELS = {
    "schema_version": "Schema version（格式版本）",
    "case": "Case（案例）",
    "incidence_angle_deg": "Incident angle（入射角，deg）",
    "polarization": "Polarization（偏振）",
    "backside_enabled": "Backside enabled（啟用基板背面反射）",
    "incident_medium": "Incident medium（入射介質）",
    "exit_medium": "Exit medium（出射介質）",
    "substrate_assumption": "Substrate assumption（基板假設）",
    "film_coherence": "Film coherence（薄膜相干性）",
    "substrate_coherence": "Substrate treatment（基板處理）",
    "wavelength_unit": "Wavelength unit（波長單位）",
    "thickness_unit": "Thickness unit（厚度單位）",
    "spectrum_unit": "Spectrum unit（光譜單位）",
    "complex_index_convention": "Complex index convention（複數折射率慣例）",
    "scatter_q": "Scattering q（散射參數）",
    "thickness_nm": "Physical thickness（物理厚度，nm）",
    "material_input": "Material input（材料輸入）",
    "status": "Status（狀態）",
    "criterion": "Criterion（判定條件）",
    "threshold_type": "Threshold type（門檻類型）",
    "tolerance_fraction": "Tolerance（容許差，fraction）",
    "tolerance_reason": "Tolerance rationale（容許差依據）",
    "metrics": "Metrics（比較指標）",
    "max_absolute_difference": "Max |Δ|（最大絕對差異）",
    "mean_absolute_difference": "MAE（平均絕對誤差）",
    "RMSE": "RMSE（均方根誤差）",
    "pass": "PASS（通過）",
    "passed": "Overall PASS（整體通過）",
    "alignment": "Alignment（網格對齊）",
    "requested_alignment": "Requested alignment（選定對齊方式）",
    "overlap_nm": "Overlap（共同波段，nm）",
    "compared_points": "Matched points（對齊點數）",
    "excluded_program_points": "Excluded program points（排除的程式點數）",
    "reference": "Reference（參考資料）",
    "original_spectrum_unit": "Original spectrum unit（原始光譜單位）",
    "original_wavelength_unit": "Original wavelength unit（原始波長單位）",
    "analysis_spectrum_unit": "Analysis spectrum unit（分析光譜單位）",
    "analysis_wavelength_unit": "Analysis wavelength unit（分析波長單位）",
    "original_order": "Original order（原始順序）",
    "sha256": "SHA256（原始檔校驗碼）",
    "original_filename": "Original filename（原始檔名）",
    "source_format": "Source format（來源格式）",
    "original_columns": "Original columns（原始欄位）",
    "column_mapping": "Column mapping（欄位對應）",
    "ignored_columns": "Ignored columns（未用於 R/T 比較的欄位）",
    "alignment_method": "Alignment method（對齊方式）",
    "user_attests_macleod_and_matching_settings": "User confirmation（使用者確認來源與條件一致）",
}

COLUMN_LABELS = {
    "wavelength_nm": "Wavelength（波長，nm）",
    "film_n": "Film n（薄膜折射率）",
    "film_k": "Film k（薄膜消光係數）",
    "substrate_n": "Substrate n（基板折射率）",
    "thickness_nm": "Thickness d（厚度，nm）",
    "n": "n（折射率）", "k": "k（消光係數）",
    "T": "T（穿透率）", "R": "R（反射率）",
    "Program_R": "Program R（程式反射率）",
    "Program_T": "Program T（程式穿透率）",
    "Program_A": "Program A（程式吸收率）",
    "Reference_R": "Reference R（參考反射率）",
    "Reference_T": "Reference T（參考穿透率）",
    "Delta_R": "ΔR（反射率差異）", "Delta_T": "ΔT（穿透率差異）",
    "R_measured": "Measured R（量測反射率）",
    "T_measured": "Measured T（量測穿透率）",
    "R_fit": "Fitted R（擬合反射率）", "T_fit": "Fitted T（擬合穿透率）",
    "R_residual": "R residual（反射率殘差）",
    "T_residual": "T residual（穿透率殘差）",
    "sigma_R": "R σ（反射率標準差）", "sigma_T": "T σ（穿透率標準差）",
}


def text(value):
    """Format known display values without changing widget values."""
    return TEXT.get(value, value)


def metadata_view(value):
    """Return a translated display copy; never mutate export metadata."""
    if isinstance(value, dict):
        return {METADATA_LABELS.get(k, k): metadata_view(v) for k, v in value.items()}
    if isinstance(value, list):
        return [metadata_view(v) for v in value]
    return text(value) if isinstance(value, str) else value


BACKSIDE_HELP = "Backside（基板背面反射）：ON 包含厚透明基板背面反射的非相干強度；OFF 使用半無限基板，不計背面界面。"
COHERENCE_HELP = "Coherent（相干）：保留薄膜內反射的相位與干涉。半無限基板只有前側界面；正入射時 S、P 偏振的 R/T 等價。"
OPTICS_GLOSSARY = "Wavelength（波長）；Reflectance R（反射率）；Transmittance T（穿透率）；Refractive index n（折射率）；Extinction coefficient k（消光係數）；Physical thickness d（物理厚度）。"
