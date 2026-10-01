from copy import deepcopy
from thinfilm.ui_text import metadata_view, text


def test_metadata_translation_keeps_source_and_numeric_values():
    raw = {"case": "B — Transparent film / semi-infinite substrate", "thickness_nm": 300.,
           "backside_enabled": False, "reference": {"original_spectrum_unit": "percent"},
           "metrics": {"R": {"RMSE": 2.4e-16}}, "overlap_nm": [400., 1000.]}
    original = deepcopy(raw)
    shown = metadata_view(raw)
    assert raw == original
    assert shown["Physical thickness（物理厚度，nm）"] == 300.
    assert shown["Backside enabled（啟用基板背面反射）"] is False
    assert shown["Metrics（比較指標）"]["R"]["RMSE（均方根誤差）"] == 2.4e-16
    shown["Overlap（共同波段，nm）"].append(2000.)
    assert raw == original
    assert text("unrecognized filename.csv") == "unrecognized filename.csv"
