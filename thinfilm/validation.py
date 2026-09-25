"""Normal-incidence propagation benchmarks, independent of ATLU and fitting."""
from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import re
import zipfile
import numpy as np
import pandas as pd
from .data import read_table
from .physics import spectrum


INPUT_COLUMNS = ["wavelength_nm", "film_n", "film_k", "substrate_n"]
CASES = {
    "A — Bare substrate / zero film": (2., 0., 0., True),
    "B — Transparent film": (2., 0., 300., True),
    "C — Absorbing film": (2.3, .15, 120., True),
    "D — Backside OFF": (2.3, .15, 120., False),
    "E — Backside ON": (2.3, .15, 120., True),
}


def numeric_grid(frame, columns):
    if not set(columns).issubset(frame.columns):
        raise ValueError("Required columns: " + ", ".join(columns))
    result = frame[columns].apply(pd.to_numeric, errors="raise").copy()
    if len(result) < 2 or not np.isfinite(result.to_numpy()).all():
        raise ValueError("At least two finite rows are required.")
    w = result.iloc[:, 0]
    if (w <= 0).any() or w.duplicated().any():
        raise ValueError("Wavelengths must be positive and unique.")
    return result.sort_values(columns[0]).reset_index(drop=True)


@dataclass
class ForwardRun:
    table: pd.DataFrame
    metadata: dict


def forward(frame, thickness_nm, backside, *, label="Custom known n/k"):
    """Use the unchanged production solver; never invoke the material model."""
    data = numeric_grid(frame, INPUT_COLUMNS)
    d = float(thickness_nm)
    if not isinstance(backside, (bool, np.bool_)):
        raise ValueError("backside must be an explicit boolean.")
    result = spectrum(data.wavelength_nm.to_numpy(), data.film_n.to_numpy(),
                      data.film_k.to_numpy(), d, data.substrate_n.to_numpy(), backside)
    data["thickness_nm"] = d
    for channel in ("R", "T"):
        data["Program_" + channel] = result[channel]
    data["Program_A"] = 1 - data.Program_R - data.Program_T
    metadata = dict(schema_version=1, case=label, incidence_angle_deg=0,
        polarization="normal incidence: s and p equivalent; no oblique-angle support",
        backside_enabled=bool(backside), incident_medium="air n=1 k=0",
        exit_medium="air n=1 k=0" if backside else "semi-infinite substrate",
        substrate_assumption="transparent, real n(lambda) >= 1, substrate k=0",
        film_coherence="coherent",
        substrate_coherence="incoherent thick substrate" if backside else "semi-infinite; no rear interface",
        wavelength_unit="nm", thickness_unit="nm", spectrum_unit="fraction",
        complex_index_convention="N=n+i*k; exp(-i*omega*t); passive k>=0",
        scatter_q=0, thickness_nm=d, material_input="known n/k; no ATLU",
        status="Ready for Essential Macleod comparison")
    return ForwardRun(data, metadata)


def example_case(name):
    n, k, d, back = CASES[name]
    frame = pd.DataFrame({"wavelength_nm": np.linspace(400, 1000, 61),
                          "film_n": n, "film_k": k, "substrate_n": 1.5})
    return forward(frame, d, back, label=name)


@dataclass
class Reference:
    raw_bytes: bytes
    raw_frame: pd.DataFrame
    analysis: pd.DataFrame
    metadata: dict


def reference_columns(columns, spectrum_unit, wavelength_unit):
    """Map an explicit canonical or native Performance Table header, never data values."""
    native = {
        "wavelength": re.compile(r"wavelength\s*\((nm|um)\)", re.I),
        "R": re.compile(r"reflectance\s*\((%|fraction)\)", re.I),
        "T": re.compile(r"transmittance\s*\((%|fraction)\)", re.I),
    }
    matches = {key: [] for key in native}
    for column in columns:
        base = re.sub(r"\.\d+$", "", column)  # pandas disambiguates repeated CSV headers this way
        for key, pattern in native.items():
            if base == key or pattern.fullmatch(base):
                matches[key].append(column)
    if any(len(found) != 1 for found in matches.values()):
        raise ValueError("Reference requires exactly one wavelength, R and T column; missing or ambiguous columns are not allowed.")
    mapping = {found[0]: key for key, found in matches.items()}
    canonical = set(mapping) == {"wavelength", "R", "T"}
    if not canonical and any(column in ("wavelength", "R", "T") for column in mapping):
        raise ValueError("Do not mix canonical and Essential Macleod reference columns.")
    if not canonical:
        for column, key in mapping.items():
            match = native[key].fullmatch(column)
            declared = match.group(1).lower() if match else None
            expected = wavelength_unit if key == "wavelength" else ("%" if spectrum_unit == "percent" else "fraction")
            if declared != expected:
                raise ValueError(f"Reference header {column!r} conflicts with selected {key} unit {expected!r}.")
    ignored = [column for column in columns if column not in mapping]
    return ("Canonical wavelength,R,T CSV" if canonical else "Essential Macleod Performance CSV"), mapping, ignored


def import_reference(raw, *, spectrum_unit, wavelength_unit, filename=None):
    """Accept canonical or native Performance CSV; preserve original bytes and columns."""
    if spectrum_unit not in ("fraction", "percent") or wavelength_unit not in ("nm", "um"):
        raise ValueError("Specify spectrum unit fraction/percent and wavelength unit nm/um.")
    raw = bytes(raw)
    frame = read_table(BytesIO(raw))
    source_format, mapping, ignored = reference_columns(frame.columns, spectrum_unit, wavelength_unit)
    data = numeric_grid(frame.rename(columns=mapping), ["wavelength", "R", "T"])
    scale = 100. if spectrum_unit == "percent" else 1.
    if ((data[["R", "T"]] < 0) | (data[["R", "T"]] > scale)).any().any():
        raise ValueError("Reference R/T must lie within the declared unit range.")
    data[["R", "T"]] /= scale
    data["wavelength"] *= 1000. if wavelength_unit == "um" else 1.
    data = data.rename(columns={"wavelength": "wavelength_nm"})
    original_w = pd.to_numeric(frame[next(column for column, key in mapping.items() if key == "wavelength")])
    order = "ascending" if original_w.is_monotonic_increasing else (
        "descending" if original_w.is_monotonic_decreasing else "unsorted")
    return Reference(raw, frame.copy(deep=True), data,
        dict(original_spectrum_unit=spectrum_unit, original_wavelength_unit=wavelength_unit,
             analysis_spectrum_unit="fraction", analysis_wavelength_unit="nm",
             original_order=order, sha256=hashlib.sha256(raw).hexdigest(),
             original_filename=filename, source_format=source_format,
             original_columns=list(frame.columns), column_mapping=mapping,
             ignored_columns=ignored))


def compare(run, reference, *, alignment="exact", tolerance, tolerance_reason):
    """Criterion: max absolute difference <= tolerance independently for R and T."""
    if not np.isfinite(tolerance) or tolerance <= 0 or not tolerance_reason.strip():
        raise ValueError("Provide a finite positive tolerance and its rationale.")
    if alignment not in ("exact", "interpolate"):
        raise ValueError("Choose exact or interpolate alignment explicitly.")
    p, r = run.table, reference.analysis
    same = np.array_equal(p.wavelength_nm.to_numpy(), r.wavelength_nm.to_numpy())
    if alignment == "exact" and not same:
        raise ValueError("Wavelength grids differ. Explicit overlap-only interpolation is required.")
    low = max(p.wavelength_nm.min(), r.wavelength_nm.min())
    high = min(p.wavelength_nm.max(), r.wavelength_nm.max())
    selected = p[p.wavelength_nm.between(low, high)].copy()
    if len(selected) < 2:
        raise ValueError("At least two program wavelengths within the common overlap are required.")
    metrics = {}
    for c in ("R", "T"):
        ref = r[c].to_numpy() if same else np.interp(selected.wavelength_nm, r.wavelength_nm, r[c])
        selected["Reference_" + c] = ref
        delta = selected["Program_" + c].to_numpy() - ref
        selected["Delta_" + c] = delta
        metrics[c] = dict(max_absolute_difference=float(np.max(np.abs(delta))),
                          mean_absolute_difference=float(np.mean(np.abs(delta))),
                          RMSE=float(np.sqrt(np.mean(delta**2))))
        metrics[c]["pass"] = metrics[c]["max_absolute_difference"] <= tolerance
    report = dict(criterion="max absolute difference <= tolerance for each channel",
        threshold_type="engineering validation threshold", tolerance_fraction=float(tolerance),
        tolerance_reason=tolerance_reason, metrics=metrics,
        passed=all(m["pass"] for m in metrics.values()),
        alignment="identical grid" if same else "linear reference interpolation onto program grid; overlap only",
        requested_alignment=alignment, overlap_nm=[float(low), float(high)],
        compared_points=len(selected), excluded_program_points=len(p)-len(selected),
        reference=reference.metadata | {"alignment_method": alignment})
    return selected.reset_index(drop=True), report


def bundle(run, *, revision="unavailable", reference=None, comparison=None):
    """Portable exchange and raw reference evidence."""
    files = {"program.csv": run.table.to_csv(index=False),
             "metadata.json": json.dumps(run.metadata | {"program_revision": revision}, indent=2),
             "README.txt": "Manual Essential Macleod exchange. See docs/MACLEOD_VALIDATION.md.\n"
             "Match n/k, thickness, wavelength grid, 0 degrees and backside/coherence assumptions exactly.\n"
             "Reference accepts wavelength,R,T or native Essential Macleod Performance CSV. Explicit units are required.\n"
             "No actual Macleod benchmark is supplied with the synthetic cases.\n"}
    if reference is not None:
        files["reference_original.csv"] = reference.raw_bytes
        files["reference_normalized.csv"] = reference.analysis.to_csv(index=False)
        files["reference_metadata.json"] = json.dumps(reference.metadata, indent=2)
    if comparison is not None:
        table, report = comparison
        files["comparison.csv"] = table.to_csv(index=False)
        files["comparison.json"] = json.dumps(report, indent=2)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buf.getvalue()
