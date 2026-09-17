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
    for number in app.number_input:
        if number.label == "Gamma（eV，固定）":
            number.set_value(.03)
    app.run()
    assert not app.exception
    assert any("已變更" in w.value for w in app.warning)
    assert not any("薄膜厚度" in metric.label for metric in app.metric)
