"""Synthetic/analytical benchmarks; NOT actual Essential Macleod evidence."""
from io import BytesIO
from pathlib import Path
import json
import zipfile
import numpy as np
import pandas as pd
import pytest
from tmm import coh_tmm, inc_tmm
from thinfilm.validation import (CASES, example_case, forward, import_reference,
                                compare, bundle)


@pytest.mark.parametrize("name", CASES)
def test_known_cases_against_independent_tmm(name):
    run = example_case(name)
    errors = {"R": [], "T": []}
    for row in run.table.itertuples():
        n = row.film_n + 1j*row.film_k
        if run.metadata["backside_enabled"]:
            expected = inc_tmm("s", [1, n, row.substrate_n, 1],
                [np.inf, row.thickness_nm, 1e6, np.inf], ["i", "c", "i", "i"], 0, row.wavelength_nm)
        else:
            expected = coh_tmm("s", [1, n, row.substrate_n],
                [np.inf, row.thickness_nm, np.inf], 0, row.wavelength_nm)
        for c in errors:
            errors[c].append(getattr(row, "Program_"+c)-expected[c])
    for c, values in errors.items():
        print(name, c, "max_abs", max(np.abs(values)), "RMSE", np.sqrt(np.mean(np.square(values))))
        assert max(np.abs(values)) < 2e-12


def test_bare_transparent_absorbing_and_backside_pair():
    a, b, c, d, e = [example_case(name).table for name in CASES]
    assert np.allclose(a.Program_R, 2*.04/(1+.04), atol=1e-14)
    assert np.allclose(a.Program_T, (1-.04)/(1+.04), atol=1e-14)
    assert np.allclose(b.Program_R+b.Program_T, 1, atol=1e-14)
    assert np.ptp(b.Program_R) > .1  # Interference, not a flat-interface response.
    assert (c.Program_A > 0).all() and (c.Program_R+c.Program_T < 1).all()
    assert np.allclose(c.Program_A, 1-c.Program_R-c.Program_T)
    assert not np.allclose(d.Program_R, e.Program_R)
    assert not np.allclose(d.Program_T, e.Program_T)
    off_bare = forward(a, 0, False).table
    assert np.allclose(off_bare.Program_R, .04)
    assert np.allclose(off_bare.Program_T, .96)


def test_dispersive_direct_input_sorted_without_atlu(monkeypatch):
    import thinfilm.physics
    monkeypatch.setattr(thinfilm.physics.ATLU, "nk", lambda *a: pytest.fail("ATLU called"))
    frame = pd.DataFrame(dict(wavelength_nm=[800, 600, 400], film_n=[2., 2.1, 2.2],
                              film_k=[.01, .02, .03], substrate_n=[1.5, 1.51, 1.52]))
    original = frame.copy()
    run = forward(frame, 80, False)
    pd.testing.assert_frame_equal(frame, original)
    assert run.table.film_n.tolist() == [2.2, 2.1, 2.]
    assert run.metadata["incidence_angle_deg"] == 0
    assert run.metadata["material_input"] == "known n/k; no ATLU"


@pytest.mark.parametrize("column,value", [("film_n", 0), ("film_k", -.1),
    ("substrate_n", .9), ("wavelength_nm", 0), ("film_n", np.nan)])
def test_invalid_forward_inputs(column, value):
    frame = example_case(next(iter(CASES))).table.copy()
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        forward(frame, 100, True)


@pytest.mark.parametrize("unit,scale", [("fraction", 1), ("percent", 100)])
@pytest.mark.parametrize("wunit,wscale", [("nm", 1), ("um", .001)])
def test_reference_explicit_units_and_preservation(unit, scale, wunit, wscale):
    frame = pd.DataFrame(dict(wavelength=np.array([600, 500, 400])*wscale,
                              R=np.array([.1, .2, .3])*scale, T=np.array([.8, .7, .6])*scale))
    raw = frame.to_csv(index=False).encode()
    ref = import_reference(raw, spectrum_unit=unit, wavelength_unit=wunit)
    assert ref.raw_bytes == raw
    assert ref.raw_frame.wavelength.iloc[0] == 600*wscale
    assert np.allclose(ref.analysis.wavelength_nm, [400, 500, 600])
    assert np.allclose(ref.analysis.R, [.3, .2, .1])
    assert ref.metadata["original_order"] == "descending"
    assert ref.metadata["original_spectrum_unit"] == unit


def reference_of(table):
    return import_reference(table.to_csv(index=False).encode(),
                            spectrum_unit="fraction", wavelength_unit="nm")


def test_metrics_sign_threshold_and_evidence_bundle():
    run = example_case(list(CASES)[1])
    frame = pd.DataFrame(dict(wavelength=run.table.wavelength_nm,
        R=run.table.Program_R-.001, T=run.table.Program_T+.002))
    ref = reference_of(frame)
    result = compare(run, ref, tolerance=.0015, tolerance_reason="synthetic test threshold")
    table, report = result
    assert np.allclose(table.Delta_R, .001)
    assert np.allclose(table.Delta_T, -.002)
    for key in ("max_absolute_difference", "mean_absolute_difference", "RMSE"):
        assert report["metrics"]["R"][key] == pytest.approx(.001)
        assert report["metrics"]["T"][key] == pytest.approx(.002)
    assert report["metrics"]["R"]["pass"] and not report["passed"]
    with zipfile.ZipFile(BytesIO(bundle(run, revision="test", reference=ref, comparison=result))) as z:
        assert z.read("reference_original.csv") == ref.raw_bytes
        meta = json.loads(z.read("metadata.json"))
        assert meta["film_coherence"] == "coherent" and meta["program_revision"] == "test"
        assert json.loads(z.read("comparison.json"))["threshold_type"] == "engineering validation threshold"
        assert len(pd.read_csv(z.open("program.csv"))) == 61


def test_grid_mismatch_overlap_only_and_raw_unchanged():
    run = example_case(list(CASES)[1])
    ref = reference_of(pd.DataFrame(dict(wavelength=[455., 655., 855.], R=[.1, .2, .3], T=[.8, .7, .6])))
    original = ref.raw_bytes
    with pytest.raises(ValueError, match="grids differ"):
        compare(run, ref, tolerance=.01, tolerance_reason="test")
    table, report = compare(run, ref, alignment="interpolate", tolerance=.01, tolerance_reason="test")
    assert table.wavelength_nm.iloc[0] == 460 and table.wavelength_nm.iloc[-1] == 850
    assert table.Reference_R.iloc[0] == pytest.approx(.1025)
    assert report["excluded_program_points"] == 21
    assert ref.raw_bytes == original and len(run.table) == 61
    no_overlap = reference_of(pd.DataFrame(dict(wavelength=[2000, 2100], R=[.1, .1], T=[.8, .8])))
    with pytest.raises(ValueError, match="overlap"):
        compare(run, no_overlap, alignment="interpolate", tolerance=.01, tolerance_reason="test")


@pytest.mark.parametrize("tol,reason", [(0, "test"), (-1, "test"), (np.nan, "test"), (np.inf, "test"), (.01, " ")])
def test_invalid_criterion(tol, reason):
    run = example_case(next(iter(CASES)))
    ref = reference_of(pd.DataFrame(dict(wavelength=[400, 1000], R=[.1, .1], T=[.8, .8])))
    with pytest.raises(ValueError):
        compare(run, ref, tolerance=tol, tolerance_reason=reason)


@pytest.mark.parametrize("raw,unit,wunit", [(b"wavelength,R,T\n400,1,50\n500,2,60", "fraction", "nm"),
    (b"wavelength,R,T\n400,.1,.8\n400,.2,.7", "fraction", "nm"),
    (b"wavelength,R,T\n400,.1,.8\n500,.2,.7", "auto", "nm"),
    (b"wavelength,R,T\n400,.1,.8\n500,.2,.7", "fraction", "auto")])
def test_invalid_reference(raw, unit, wunit):
    with pytest.raises(ValueError):
        import_reference(raw, spectrum_unit=unit, wavelength_unit=wunit)


def test_native_macleod_header_mapping_phase_and_provenance():
    raw = (Path(__file__).parent / "fixtures" / "synthetic_macleod_performance.csv").read_bytes()
    ref = import_reference(raw, spectrum_unit="percent", wavelength_unit="nm",
                           filename="synthetic_macleod_performance.csv")
    assert ref.raw_bytes == raw
    assert ref.metadata["original_filename"] == "synthetic_macleod_performance.csv"
    assert ref.metadata["source_format"] == "Essential Macleod Performance CSV"
    assert ref.metadata["original_columns"] == ["Wavelength  (nm)", "Reflectance (%)",
        "Transmittance (%)", "Reflectance-Phase (deg)", "Transmittance-Phase (deg)"]
    assert ref.metadata["column_mapping"] == {
        "Wavelength  (nm)": "wavelength", "Reflectance (%)": "R", "Transmittance (%)": "T"}
    assert ref.metadata["ignored_columns"] == ["Reflectance-Phase (deg)", "Transmittance-Phase (deg)"]
    assert ref.analysis.columns.tolist() == ["wavelength_nm", "R", "T"]
    assert ref.analysis.R.tolist() == pytest.approx([.04, .05, .07])
    assert ref.analysis["T"].tolist() == pytest.approx([.96, .95, .93])
    with zipfile.ZipFile(BytesIO(bundle(example_case("B — Transparent film"), reference=ref))) as archive:
        assert archive.read("reference_original.csv") == raw
        evidence = json.loads(archive.read("reference_metadata.json"))
        assert evidence["original_filename"] == "synthetic_macleod_performance.csv"
        assert evidence["column_mapping"] == ref.metadata["column_mapping"]


def test_native_61_point_grid_exact_alignment_without_claiming_external_validation():
    run = example_case("B — Transparent film")
    lines = ["Wavelength  (nm),Reflectance (%),Transmittance (%),Reflectance-Phase (deg),Transmittance-Phase (deg)"]
    for row in run.table.itertuples():
        lines.append(f"{row.wavelength_nm:g},{row.Program_R*100:.14g},{row.Program_T*100:.14g},0,0")
    raw = ("\n".join(lines) + "\n").encode()
    ref = import_reference(raw, spectrum_unit="percent", wavelength_unit="nm")
    table, report = compare(run, ref, alignment="exact", tolerance=1e-4,
                            tolerance_reason="synthetic parser regression")
    assert len(ref.analysis) == len(table) == 61
    assert ref.analysis.wavelength_nm.tolist() == list(range(400, 1001, 10))
    assert report["reference"]["alignment_method"] == "exact"
    assert report["compared_points"] == 61
    assert ref.raw_bytes == raw


@pytest.mark.parametrize("header", [
    "Wavelength  (nm),Transmittance (%),Transmittance-Phase (deg)",
    "Wavelength  (nm),Reflectance (%),Reflectance-Phase (deg)",
    "Wavelength  (nm),Reflectance (%),R,Transmittance (%)",
    "Wavelength  (nm),Reflectance (%),Transmittance (%),T",
    "Wavelength  (nm),Reflectance (%),Reflectance (%),Transmittance (%)",
])
def test_native_missing_malformed_or_ambiguous_columns_rejected(header):
    raw = (header + "\n400,4,96\n410,5,95\n").encode()
    with pytest.raises(ValueError):
        import_reference(raw, spectrum_unit="percent", wavelength_unit="nm")


def test_native_malformed_numeric_row_rejected():
    raw = b"Wavelength  (nm),Reflectance (%),Transmittance (%)\n400,not-a-number,96\n410,5,95\n"
    with pytest.raises(ValueError):
        import_reference(raw, spectrum_unit="percent", wavelength_unit="nm")


@pytest.mark.parametrize("unit,wunit", [("fraction", "nm"), ("percent", "um")])
def test_native_header_unit_conflict_rejected(unit, wunit):
    raw = (Path(__file__).parent / "fixtures" / "synthetic_macleod_performance.csv").read_bytes()
    with pytest.raises(ValueError, match="conflicts"):
        import_reference(raw, spectrum_unit=unit, wavelength_unit=wunit)
