from io import BytesIO
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
from thinfilm.validation import CASES, example_case


def test_validation_page_isolated_and_reference_comparison(monkeypatch):
    # Synthetic round-trip only, deliberately do not attest Macleod provenance.
    run = example_case(next(iter(CASES)))
    raw = pd.DataFrame(dict(wavelength=run.table.wavelength_nm,
        R=run.table.Program_R, T=run.table.Program_T)).to_csv(index=False).encode()
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw: BytesIO(raw))
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py"), default_timeout=15).run()
    assert not app.exception
    assert app.error  # Units cannot be guessed.
    assert not any(b.label == "開始全光譜分析" for b in app.button)
    next(s for s in app.selectbox if s.label == "Reference R/T unit（參考光譜單位）").set_value("fraction")
    next(s for s in app.selectbox if s.label == "Reference wavelength unit（參考波長單位）").set_value("nm")
    app.run()
    assert not app.exception and not app.error
    assert any("未確認 Macleod" in w.value for w in app.warning)
    assert any("Ready for Essential Macleod comparison" in w.value for w in app.warning)
    app.checkbox[0].check().run()
    assert any("PASS" in i.value for i in app.info)
    next(s for s in app.selectbox if s.label == "Forward input（正向模型輸入）").set_value(list(CASES)[1]).run()
    assert not app.checkbox[0].value
    assert any("未確認 Macleod" in w.value for w in app.warning)


def test_custom_nk_UI_routes_direct_forward(monkeypatch):
    frame = pd.DataFrame(dict(wavelength_nm=[400, 500, 600], film_n=[2., 2.1, 2.2],
                              film_k=[0., .1, .2], substrate_n=[1.5]*3))
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw:
        BytesIO(frame.to_csv(index=False).encode()) if label == "Known n/k CSV（已知折射率／消光係數）" else None)
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py"), default_timeout=15).run()
    next(s for s in app.selectbox if s.label == "Forward input（正向模型輸入）").set_value("Custom known n/k CSV").run()
    assert not app.exception and not app.error
    assert app.dataframe[0].value.film_n.tolist() == [2., 2.1, 2.2]


def test_native_reference_ui_displays_provenance_before_comparison(monkeypatch):
    raw = (Path(__file__).parent / "fixtures" / "synthetic_macleod_performance.csv").read_bytes()
    uploaded = BytesIO(raw)
    uploaded.name = "synthetic_macleod_performance.csv"
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw: uploaded)
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py"), default_timeout=15).run()
    next(s for s in app.selectbox if s.label == "Reference R/T unit（參考光譜單位）").set_value("percent")
    next(s for s in app.selectbox if s.label == "Reference wavelength unit（參考波長單位）").set_value("nm")
    app.run()
    assert not app.exception
    text = "\n".join(element.value for element in app.markdown)
    assert "Essential Macleod Performance CSV" in text
    assert "Wavelength  (nm) → wavelength" in text
    assert "Reflectance (%) → R" in text
    assert "Transmittance (%) → T" in text
    assert "Reflectance-Phase (deg)" in text
    assert "Reference points（參考點數）: 3" in text
    assert "Reference wavelength（參考波長）: 400–420 nm" in text
    assert "Alignment（網格對齊）: Exact alignment（精確網格對齊）" in text
    assert not any("PASS" in element.value for element in app.info)


def test_case_b_conditions_are_visible_before_reference_upload():
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py"), default_timeout=15).run()
    next(s for s in app.selectbox if s.label == "Forward input（正向模型輸入）").set_value(
        "B — Transparent film / semi-infinite substrate").run()
    assert not app.exception and not app.error
    text = "\n".join(element.value for element in app.markdown)
    assert "Backside（基板背面反射）: OFF（關閉）" in text
    assert "Substrate treatment（基板處理）: semi-infinite（半無限基板；不考慮背面界面）" in text
    assert "Film coherence（薄膜相干性）: coherent（相干）" in text
    assert "Incident angle（入射角）: 0°" in text
    assert "Polarization（偏振）: S/P equivalent at normal incidence（正入射時 S、P 偏振等價）" in text
    expected = example_case("B — Transparent film / semi-infinite substrate")
    pd.testing.assert_frame_equal(app.dataframe[0].value, expected.table)
    assert next(s for s in app.selectbox if s.label == "Forward input（正向模型輸入）").value == expected.metadata["case"]


def test_bilingual_comparison_preserves_metrics_tolerance_and_exports(monkeypatch):
    import json
    import zipfile
    from thinfilm.validation import compare, import_reference, bundle
    from thinfilm.ui_text import metadata_view

    name = "B — Transparent film / semi-infinite substrate"
    run = example_case(name)
    raw = pd.DataFrame(dict(wavelength=run.table.wavelength_nm,
        R=run.table.Program_R * 100, T=run.table.Program_T * 100)).to_csv(index=False).encode()
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw: BytesIO(raw))
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py"), default_timeout=15).run()
    next(s for s in app.selectbox if s.label == "Forward input（正向模型輸入）").set_value(name)
    next(s for s in app.selectbox if s.label == "Reference R/T unit（參考光譜單位）").set_value("percent")
    next(s for s in app.selectbox if s.label == "Reference wavelength unit（參考波長單位）").set_value("nm")
    app.run()
    assert not app.exception and not app.error
    assert next(s for s in app.selectbox if s.label == "Wavelength grid alignment（波長網格對齊）").value == "exact"
    assert next(n for n in app.number_input if n.label == "Engineering tolerance（工程容許差，fraction）").value == 1e-4
    ref = import_reference(raw, spectrum_unit="percent", wavelength_unit="nm")
    rationale = app.text_input[0].value
    comparison = compare(run, ref, alignment="exact", tolerance=1e-4, tolerance_reason=rationale)
    report = comparison[1] | {"user_attests_macleod_and_matching_settings": False}
    assert json.loads(app.json[1].value) == metadata_view(report)
    pd.testing.assert_frame_equal(app.dataframe[0].value, run.table)
    with zipfile.ZipFile(BytesIO(bundle(run, reference=ref, comparison=comparison))) as archive:
        assert json.loads(archive.read("comparison.json"))["metrics"] == report["metrics"]
        assert json.loads(archive.read("metadata.json"))["case"] == name
