from io import BytesIO
import numpy as np
import pandas as pd
import pytest
from thinfilm.data import SpectrumData
from thinfilm.analysis import envelope, tauc_plot, compare_reference
from thinfilm.physics import HC, spectrum


def table():
    return pd.DataFrame({"wavelength_nm": np.linspace(400, 1000, 30), "T": .8, "R": .15})


def test_units_sorting_and_uncertainties():
    df = table().iloc[::-1].copy()
    df["T"] *= 100
    df["R"] *= 100
    df["sigma_T"] = .5
    data = SpectrumData.from_csv(BytesIO(df.to_csv(index=False).encode()), "percent")
    assert np.allclose(data.T, .8)
    assert np.allclose(data.sigma_T, .005)
    assert np.all(np.diff(data.wavelength) > 0)


@pytest.mark.parametrize("bad", ["duplicate", "negative", "nan", "sigma", "percent"])
def test_reject_bad_input(bad):
    df = table()
    if bad == "duplicate": df.loc[1, "wavelength_nm"] = df.loc[0, "wavelength_nm"]
    if bad == "negative": df.loc[2, "T"] = -.01
    if bad == "nan": df.loc[2, "T"] = np.nan
    if bad == "sigma": df["sigma_T"] = 0.
    if bad == "percent": df["T"] = 80.
    with pytest.raises(ValueError): SpectrumData.from_csv(df)


def test_no_fringes_returns_unavailable():
    result = envelope(SpectrumData.from_csv(table()))
    assert not result["available"] and result["d_nm"] is None


def test_envelope_constant_n_thickness():
    w = np.linspace(400, 1600, 1201)
    sp = spectrum(w, np.full(len(w), 2.5), np.zeros(len(w)), 1200, 1.5)
    data = SpectrumData.from_csv(pd.DataFrame({"wavelength_nm": w, "T": sp["T"]}), sigma=.001)
    env = envelope(data)
    assert env["available"]
    assert env["d_nm"] == pytest.approx(1200, rel=.02)


@pytest.mark.parametrize("transition,power", [("amorphous", .5), ("direct", 2.)])
def test_tauc_known_linear_edge(transition, power):
    e = np.linspace(1.6, 3, 150)
    alpha = (1e3*(e-1.4))**(1/power)/e
    if power == 2:
        alpha *= 1e7
    w = HC/e
    k = alpha*(w*1e-7)/(4*np.pi)
    tau = tauc_plot(w, k, transition, (1.8, 2.4))
    assert tau["available"]
    assert tau["Eg_eV"] == pytest.approx(1.4, abs=1e-9)


def test_reference_overlap_only_and_known_RMSE():
    fit = pd.DataFrame({"wavelength_nm": [400, 500, 600], "n": [2., 2., 2.]})
    ref = pd.DataFrame({"wavelength_nm": [300, 400, 550, 800], "n": [99., 1.9, 1.9, 99.], "d_nm": 100.})
    metrics, errors = compare_reference(fit, ref, 102.)
    n = metrics[(metrics.parameter == "n") & (metrics.band == "all")].iloc[0]
    assert n["count"] == 2 and n.RMSE == pytest.approx(.1)
    assert errors.wavelength_nm.tolist() == [400, 550]
    assert metrics.loc[metrics.parameter == "d_nm", "RMSE"].iloc[0] == 2.


def test_reference_rejects_no_overlap():
    fit = pd.DataFrame({"wavelength_nm": [400, 500, 600], "n": [2., 2., 2.]})
    with pytest.raises(ValueError):
        compare_reference(fit, pd.DataFrame({"wavelength_nm": [700, 800], "n": [2., 2.]}), 100)
