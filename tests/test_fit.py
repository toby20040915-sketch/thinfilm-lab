from dataclasses import replace
import json
import numpy as np
import pytest
from thinfilm.demo import simulate
from thinfilm.data import SpectrumData
from thinfilm.fit import FitConfig, fit_spectrum, thickness_profile
from thinfilm.physics import Parameters
from thinfilm.report import result_files, zip_files


@pytest.fixture(scope="module")
def fitted():
    df, ref, p = simulate(points=121, noise=.0005)
    data = SpectrumData.from_csv(df)
    config = FitConfig(starts=3, max_nfev=250, fixed={"tail_fraction": p.tail_fraction}, loss="linear")
    return data, p, fit_spectrum(data, config)


def test_synthetic_ultrathin_recovery(fitted):
    data, p, result = fitted
    assert result.summary["optimizer_success"]
    assert result.parameters.d_nm == pytest.approx(p.d_nm, rel=.015)
    assert result.summary["metrics"]["T_RMSE"] < .001
    assert np.all(result.table.k >= 0)


def test_exports_are_complete_and_finite_json(fitted):
    _, _, result = fitted
    files = result_files(result)
    assert files["analysis.png"].startswith(b"\x89PNG")
    summary = json.loads(files["summary.json"])
    assert summary["experimental_validation"]
    assert b"NaN" not in files["summary.json"]
    assert "normalized_input.csv" in files
    assert "sigma_T" in files["normalized_input.csv"].decode("utf-8-sig")
    assert len(summary["normalized_input_sha256"]) == 64
    assert zip_files(files).startswith(b"PK")


def test_T_only_and_fixed_thickness(fitted):
    data, p, _ = fitted
    frame = data.frame().drop(columns=["R", "sigma_R"])
    cfg = FitConfig(starts=1, fixed={"d_nm": p.d_nm, "tail_fraction": p.tail_fraction})
    result = fit_spectrum(SpectrumData.from_csv(frame), cfg)
    assert result.parameters.d_nm == p.d_nm
    assert "R_measured" not in result.table
    assert any("單一光譜" in w for w in result.summary["warnings"])


def test_nonconvergence_is_not_success():
    df, _, _ = simulate(points=31)
    result = fit_spectrum(SpectrumData.from_csv(df), FitConfig(starts=1, max_nfev=1, global_iterations=0))
    assert not result.summary["optimizer_success"]


def test_invalid_fixed_values_fail():
    with pytest.raises(ValueError):
        FitConfig(fixed={"Eg_eV": -1.}).validate()


def test_thickness_profile_refits(fitted):
    data, p, result = fitted
    profile = thickness_profile(data, result, [p.d_nm*.8, p.d_nm, p.d_nm*1.2], starts=1)
    assert profile.loc[profile.chi_square.idxmin(), "d_nm"] == p.d_nm


def test_T_only_without_known_thickness():
    df, _, p = simulate(points=121, noise=.0005)
    data = SpectrumData.from_csv(df.drop(columns=["R", "sigma_R"]))
    result = fit_spectrum(data, FitConfig(starts=3, loss="linear"))
    assert result.summary["fit_quality_pass"]
    assert result.parameters.d_nm == pytest.approx(p.d_nm, rel=.03)


def test_poor_fit_is_flagged_even_when_optimizer_stops():
    df, _, _ = simulate(points=61)
    result = fit_spectrum(SpectrumData.from_csv(df),
                          FitConfig(starts=1, fixed={"d_nm": 150.}, global_iterations=0))
    assert not result.summary["fit_quality_pass"]
