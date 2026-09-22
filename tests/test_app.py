from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_demo_app_fit_export_and_stale_result_guard():
    app = AppTest.from_file(str(Path(__file__).parents[1]/"app.py"), default_timeout=90).run()
    assert not app.exception
    # Test the actual UI computation path using one start for speed.
    for slider in app.slider:
        if slider.label == "搜尋起點數":
            slider.set_value(1)
    app.run()
    next(b for b in app.button if b.label == "開始全光譜分析").click().run()
    assert not app.exception
    assert any("薄膜厚度" in metric.label for metric in app.metric)
    assert app.session_state["result"].summary["optimizer_success"]
    assert abs(app.session_state["result"].parameters.d_nm - 60) < .1
    next(n for n in app.number_input if n.label == "Fit wavelength min (nm)").set_value(400.)
    app.run()
    assert any("已變更" in w.value for w in app.warning)
    assert not any("薄膜厚度" in metric.label for metric in app.metric)
    next(n for n in app.number_input if n.label == "Fit wavelength min (nm)").set_value(300.)
    app.run()
    for number in app.number_input:
        if number.label == "Gamma（eV，固定）":
            number.set_value(.03)
    app.run()
    assert not app.exception
    assert any("已變更" in w.value for w in app.warning)
    assert not any("薄膜厚度" in metric.label for metric in app.metric)


def test_professor_intake_UI_subsets_before_fitting(monkeypatch):
    from io import BytesIO
    import streamlit as st
    import thinfilm.fit
    raw = ("\n".join(f"{2000-i}    {92.7096-i*.0076}" for i in range(24))+"\n").encode()
    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs:
                        BytesIO(raw) if label == "上傳光譜 CSV" else None)
    received = []
    def capture(data, cfg, **kwargs):
        received.append(data)
        raise ValueError("TEST: captured fitting input")
    monkeypatch.setattr(thinfilm.fit, "fit_spectrum", capture)
    app = AppTest.from_file(str(Path(__file__).parents[1]/"app.py"), default_timeout=90).run()
    app.radio[0].set_value("匯入 CSV").run()
    next(s for s in app.selectbox if s.label == "匯入格式").set_value("無表頭兩欄 T-only（教授量測格式）").run()
    assert any("明確指定" in e.value for e in app.error)
    next(s for s in app.selectbox if s.label == "第一欄").set_value("Wavelength (nm)")
    next(s for s in app.selectbox if s.label == "第二欄").set_value("Transmittance T")
    next(s for s in app.selectbox if s.label == "光譜單位").set_value("0–100 百分比")
    app.run()
    assert not app.exception and not app.error
    text = " ".join(m.value for m in app.markdown)
    assert "Original wavelength order: descending" in text
    assert "R measurement: Not provided" in text
    assert "Original unit: percent" in text
    next(n for n in app.number_input if n.label == "Fit wavelength min (nm)").set_value(1980.)
    next(n for n in app.number_input if n.label == "Fit wavelength max (nm)").set_value(1995.)
    app.run()
    next(b for b in app.button if b.label == "開始全光譜分析").click().run()
    assert not app.exception
    assert received[0].wavelength.tolist() == list(range(1980, 1996))
    assert received[0].R is None
    assert len(app.dataframe[0].value) == 24
    next(n for n in app.number_input if n.label == "Fit wavelength min (nm)").set_value(1995.)
    app.run()
    assert app.error and not any(b.label == "開始全光譜分析" for b in app.button)
