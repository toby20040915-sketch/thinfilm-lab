"""Synthetic parser fixtures only; these are not professor measurements."""
from io import BytesIO
import hashlib
import json
import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
from thinfilm.data import SpectrumData
from thinfilm.intake import ImportedSpectrum
from thinfilm.demo import simulate
from thinfilm.fit import FitConfig, fit_spectrum
from thinfilm.report import result_files, figures, imported_figure


def parser_fixture(separator="\t"):
    return ("\n".join(f"{2000-i:.4f}{separator}{92.7096-i*.0076:.4f}" for i in range(24))+"\n").encode()


def parse(raw=None, **kwargs):
    return ImportedSpectrum.from_source(BytesIO(parser_fixture() if raw is None else raw),
        units="percent", input_format="no_header_t", columns=("wavelength_nm", "T"), **kwargs)


@pytest.mark.parametrize("separator", ["\t", "    ", " \t  "])
def test_no_header_explicit_T_percent_preserves_original(separator):
    original = parser_fixture(separator)
    imported = parse(original)
    assert imported.original_bytes == original
    assert imported.metadata["original_bytes_sha256"] == hashlib.sha256(original).hexdigest()
    assert imported.metadata["original_wavelength_order"] == "descending"
    assert imported.metadata["original_unit"] == "percent"
    assert imported.metadata["analysis_unit"] == "fraction"
    assert imported.metadata["measured_channels"] == ["T"]
    assert imported.raw_frame.wavelength_nm.tolist() == list(range(2000, 1976, -1))
    assert imported.raw_frame["T"].iloc[0] == pytest.approx(92.7096)
    assert np.all(np.diff(imported.analysis.wavelength) > 0)
    assert imported.analysis.T[-1] == pytest.approx(.927096)
    assert imported.analysis.R is None and imported.analysis.sigma_R is None
    assert "Original wavelength order: descending" in imported.analysis.notes


@pytest.mark.parametrize("units,columns", [("fraction", ("wavelength_nm", "T")),
                                          ("percent", None), ("percent", ("wavelength_nm", "R"))])
def test_no_header_requires_explicit_mapping_and_percent(units, columns):
    with pytest.raises(ValueError, match="明確指定"):
        ImportedSpectrum.from_source(BytesIO(parser_fixture()), units=units,
                                      input_format="no_header_t", columns=columns)


@pytest.mark.parametrize("raw", [b"2000 90 1\n"*12, b"2000\n"*12,
                                  b"wavelength T\n"+parser_fixture(),
                                  parser_fixture().replace(b"92.7096", b"102.0000"),
                                  parser_fixture().replace(b"1999.0000", b"2000.0000")])
def test_invalid_no_header_data_rejected(raw):
    with pytest.raises(ValueError):
        parse(raw)


@pytest.mark.parametrize("channels", [("T",), ("R",), ("T", "R")])
def test_existing_header_import_matches_legacy(channels):
    frame = pd.DataFrame({"wavelength_nm": np.linspace(1200, 300, 24),
                          "substrate_n": np.linspace(1.45, 1.5, 24)})
    for c in channels:
        frame[c] = 60. if c == "T" else 20.
        frame["sigma_"+c] = .5
    original = frame.to_csv(index=False).encode("utf-8-sig")
    old = SpectrumData.from_csv(BytesIO(original), "percent")
    imported = ImportedSpectrum.from_source(BytesIO(original), "percent")
    pd.testing.assert_frame_equal(imported.analysis.frame(), old.frame())
    assert imported.original_bytes == original


def test_fit_range_preserves_full_data_and_masks_every_array():
    imported = parse()
    before_raw, before_analysis = imported.raw_frame.copy(), imported.analysis.frame().copy()
    data = imported.select_fit_range(1980, 1995)
    assert data.wavelength.tolist() == list(range(1980, 1996))
    assert data.R is None
    assert len(data.T) == len(data.sigma_T) == len(data.substrate_n) == 16
    assert data.T[0] == pytest.approx((92.7096-20*.0076)/100)
    assert imported.selection_metadata(1980, 1995)["fit_range_nm"] == [1980., 1995.]
    data.T[:] = 0
    pd.testing.assert_frame_equal(imported.raw_frame, before_raw)
    pd.testing.assert_frame_equal(imported.analysis.frame(), before_analysis)


@pytest.mark.parametrize("limits", [(1995, 1980), (1980, 1980), (250, 2000),
                                    (1980, 2001), (1999, 2000), (np.nan, 2000), (1980, np.inf)])
def test_invalid_fit_range_rejected(limits):
    with pytest.raises(ValueError):
        parse().select_fit_range(*limits)


def test_unsorted_order_recorded():
    frame = pd.DataFrame({"wavelength_nm": list(range(400, 424)), "T": .8})
    frame = frame.iloc[[1, 0, *range(2, 24)]]
    imported = ImportedSpectrum.from_source(frame)
    assert imported.metadata["original_wavelength_order"] == "unsorted"
    assert imported.raw_frame.wavelength_nm.tolist() == frame.wavelength_nm.tolist()


def test_T_only_subset_fit_and_traceable_export():
    frame, _, truth = simulate(points=61, noise=.0005)
    # Clearly synthetic known-model case; no fabricated professor datasets.
    frame = frame[["wavelength_nm", "T"]].iloc[::-1].copy()
    frame["T"] *= 100
    original = frame.to_csv(index=False, header=False, sep="\t").encode()
    imported = parse(original, sigma=.0005)
    data = imported.select_fit_range(400, 1000)
    fixed = {k: v for k, v in truth.report().items()
             if k in ("A_eV", "Eg_eV", "gap_eV", "C_eV", "tail_fraction")}
    result = fit_spectrum(data, FitConfig(starts=1, global_iterations=0, fixed=fixed))
    assert result.summary["optimizer_success"]
    assert result.parameters.d_nm == pytest.approx(60., abs=.3)
    assert "R_measured" not in result.table
    assert result.table.wavelength_nm.tolist() == data.wavelength.tolist()
    residual = (result.table.T_fit.to_numpy()-data.T)/data.sigma_T
    assert result.summary["weighted_rmse"] == pytest.approx(np.sqrt(np.mean(residual**2)))
    files = result_files(result, imported=imported, fit_range=(400, 1000))
    assert files["original_upload.txt"] == original
    saved_raw = pd.read_csv(BytesIO(files["raw_imported_spectrum.csv"]))
    assert len(saved_raw) == 61 and saved_raw.wavelength_nm.iloc[0] == 1200
    assert len(pd.read_csv(BytesIO(files["normalized_full_spectrum.csv"]))) == 61
    assert len(pd.read_csv(BytesIO(files["normalized_input.csv"]))) == len(data.wavelength)
    metadata = json.loads(files["summary.json"])["data_intake"]
    assert metadata["imported_range_nm"] == [300., 1200.]
    assert metadata["fit_range_nm"] == [400., 1000.]
    assert metadata["measured_channels"] == ["T"]
    with pytest.raises(ValueError, match="不一致"):
        result_files(result, imported=imported, fit_range=(400, 1100))
    other = parse(original.replace(b"\t", b"    "), sigma=.005)
    with pytest.raises(ValueError, match="不一致"):
        result_files(result, imported=other, fit_range=(400, 1000))
    fig = figures(result)
    assert "Model predicted R — not measured" in fig.axes[0].get_legend_handles_labels()[1]
    plt.close(fig)
    raw_fig = imported_figure(imported, 400, 1000)
    assert len(raw_fig.axes[0].lines[0].get_xdata()) == 61
    assert len(raw_fig.axes[0].patches) == 1
    plt.close(raw_fig)
