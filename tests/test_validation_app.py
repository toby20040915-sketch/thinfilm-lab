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
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py")).run()
    assert not app.exception
    assert app.error  # Units cannot be guessed.
    assert not any(b.label == "開始全光譜分析" for b in app.button)
    next(s for s in app.selectbox if s.label == "Reference R/T unit").set_value("fraction")
    next(s for s in app.selectbox if s.label == "Reference wavelength unit").set_value("nm")
    app.run()
    assert not app.exception and not app.error
    assert any("未確認 Macleod" in w.value for w in app.warning)
    assert any("Ready for Essential Macleod comparison" in w.value for w in app.warning)
    app.checkbox[0].check().run()
    assert any("PASS" in i.value for i in app.info)
    next(s for s in app.selectbox if s.label == "Forward input").set_value(list(CASES)[1]).run()
    assert not app.checkbox[0].value
    assert any("未確認 Macleod" in w.value for w in app.warning)


def test_custom_nk_UI_routes_direct_forward(monkeypatch):
    frame = pd.DataFrame(dict(wavelength_nm=[400, 500, 600], film_n=[2., 2.1, 2.2],
                              film_k=[0., .1, .2], substrate_n=[1.5]*3))
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw:
        BytesIO(frame.to_csv(index=False).encode()) if label == "Known n/k CSV" else None)
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py")).run()
    next(s for s in app.selectbox if s.label == "Forward input").set_value("Custom known n/k CSV").run()
    assert not app.exception and not app.error
    assert app.dataframe[0].value.film_n.tolist() == [2., 2.1, 2.2]


def test_native_reference_ui_displays_provenance_before_comparison(monkeypatch):
    raw = (Path(__file__).parent / "fixtures" / "synthetic_macleod_performance.csv").read_bytes()
    uploaded = BytesIO(raw)
    uploaded.name = "synthetic_macleod_performance.csv"
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw: uploaded)
    app = AppTest.from_file(str(Path(__file__).parents[1]/"pages"/"1_Forward_Model_Validation.py")).run()
    next(s for s in app.selectbox if s.label == "Reference R/T unit").set_value("percent")
    next(s for s in app.selectbox if s.label == "Reference wavelength unit").set_value("nm")
    app.run()
    assert not app.exception
    text = "\n".join(element.value for element in app.markdown)
    assert "Essential Macleod Performance CSV" in text
    assert "Wavelength  (nm) → wavelength" in text
    assert "Reflectance (%) → R" in text
    assert "Transmittance (%) → T" in text
    assert "Reflectance-Phase (deg)" in text
    assert "Reference points: 3" in text
    assert "Reference wavelength: 400–420 nm" in text
    assert "Alignment: exact" in text
    assert not any("PASS" in element.value for element in app.info)
