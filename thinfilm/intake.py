"""Traceable data intake and range selection; no optical-model transformations."""
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from .data import SpectrumData, read_table


@dataclass
class ImportedSpectrum:
    raw_frame: pd.DataFrame
    analysis: SpectrumData
    metadata: dict
    original_bytes: bytes | None = None

    @classmethod
    def from_source(cls, source, units="fraction", substrate_n=1.5, sigma=.005,
                    input_format="header", columns=None):
        if input_format not in ("header", "no_header_t"):
            raise ValueError("未知的匯入格式。")
        if input_format == "no_header_t":
            if columns != ("wavelength_nm", "T") or units != "percent":
                raise ValueError("無表頭模式必須明確指定第一欄 Wavelength (nm)、第二欄 Transmittance T，以及 Percent (0–100)。")
        original = None
        if isinstance(source, pd.DataFrame):
            if input_format != "header":
                raise ValueError("無表頭模式需要原始文字檔。")
            frame = source.copy(deep=True)
        else:
            original = source.read() if hasattr(source, "read") else Path(source).read_bytes()
            if isinstance(original, str):
                original = original.encode("utf-8")
            if input_format == "header":
                frame = read_table(BytesIO(original))
            else:
                try:
                    text = original.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = original.decode("cp950")
                frame = pd.read_csv(StringIO(text), sep=r"\s+", header=None, comment="#")
                if frame.shape[1] != 2:
                    raise ValueError("無表頭 T-only 資料必須恰好兩欄。")
                frame.columns = list(columns)
        analysis = SpectrumData.from_csv(frame, units, substrate_n, sigma)
        # Preserve original order and units before making any analysis copies.
        wavelength = pd.to_numeric(frame["wavelength_nm"])
        order = ("ascending" if wavelength.is_monotonic_increasing else
                 "descending" if wavelength.is_monotonic_decreasing else "unsorted")
        channels = [c for c in ("T", "R") if getattr(analysis, c) is not None]
        metadata = dict(input_format=input_format, original_wavelength_order=order,
                        original_unit=units, analysis_unit="fraction", measured_channels=channels,
                        imported_point_count=len(frame),
                        imported_range_nm=[float(wavelength.min()), float(wavelength.max())],
                        original_bytes_sha256=hashlib.sha256(original).hexdigest() if original is not None else None,
                        column_mapping=list(columns) if input_format == "no_header_t" else None)
        for c in channels:
            values = pd.to_numeric(frame[c])
            metadata[c+"_original_min_max"] = [float(values.min()), float(values.max())]
        analysis.notes.extend([f"Original wavelength order: {order}",
                               f"Original unit: {units}", "Analysis unit: fraction"])
        return cls(frame.copy(deep=True), analysis, metadata, original)

    def select_fit_range(self, minimum, maximum):
        """Inclusive mask; neither the raw nor full normalized input is mutated."""
        minimum, maximum = float(minimum), float(maximum)
        low, high = self.metadata["imported_range_nm"]
        if not np.isfinite([minimum, maximum]).all() or not low <= minimum < maximum <= high:
            raise ValueError("擬合波長範圍必須有限、下限小於上限，且位於完整匯入範圍內。")
        a = self.analysis
        mask = (a.wavelength >= minimum) & (a.wavelength <= maximum)
        if np.count_nonzero(mask) < 12:
            raise ValueError("擬合波長範圍內至少需要 12 個量測點。")
        values = {name: None if getattr(a, name) is None else getattr(a, name)[mask].copy()
                  for name in ("wavelength", "T", "R", "sigma_T", "sigma_R", "substrate_n")}
        return SpectrumData(**values, notes=[*a.notes, f"Fit wavelength range: {minimum:g}–{maximum:g} nm (inclusive)"])

    def selection_metadata(self, minimum, maximum):
        selected = self.select_fit_range(minimum, maximum)
        return self.metadata | dict(fit_range_nm=[float(minimum), float(maximum)],
                                    fit_point_count=len(selected.wavelength),
                                    fit_sampled_range_nm=[float(selected.wavelength.min()),
                                                          float(selected.wavelength.max())])
