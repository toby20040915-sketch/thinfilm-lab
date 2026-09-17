"""Strict, explicit-unit CSV input. No silent percent or wavelength guessing."""
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
import numpy as np
import pandas as pd


def read_table(source):
    if isinstance(source, pd.DataFrame):
        return source.copy()
    raw = source.read() if hasattr(source, "read") else Path(source).read_bytes()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = raw.decode("cp950")
    df = pd.read_csv(StringIO(raw), sep=None, engine="python", comment="#")
    df.columns = df.columns.str.strip()
    if df.columns.duplicated().any():
        raise ValueError("CSV 欄位名稱不得重複。")
    return df


@dataclass
class SpectrumData:
    wavelength: np.ndarray
    T: np.ndarray | None
    R: np.ndarray | None
    sigma_T: np.ndarray | None
    sigma_R: np.ndarray | None
    substrate_n: np.ndarray
    notes: list = field(default_factory=list)

    @classmethod
    def from_csv(cls, source, units="fraction", substrate_n=1.5, sigma=0.005):
        df = read_table(source)
        if "wavelength_nm" not in df:
            raise ValueError("需要 wavelength_nm 欄位，波長單位固定為 nm。")
        if not {"T", "R"}.intersection(df.columns):
            raise ValueError("需要 T 或 R 欄位。")
        if units not in ("fraction", "percent"):
            raise ValueError("units 必須是 fraction 或 percent。")
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("預設標準差必須大於零。")
        cols = [c for c in ("wavelength_nm", "T", "R", "sigma_T", "sigma_R", "substrate_n") if c in df]
        df = df[cols].apply(pd.to_numeric, errors="raise")
        if len(df) < 12 or not np.all(np.isfinite(df.to_numpy())):
            raise ValueError("至少需要 12 筆完整且有限的數值；請先處理缺值。")
        if (df.wavelength_nm <= 0).any() or df.wavelength_nm.duplicated().any():
            raise ValueError("波長必須大於零且不可重複。")
        notes = []
        if not df.wavelength_nm.is_monotonic_increasing:
            notes.append("輸入資料已依波長排序；沒有平滑或刪除量測點。")
        df = df.sort_values("wavelength_nm").reset_index(drop=True)
        scale = 100. if units == "percent" else 1.
        values, errors = {}, {}
        for c in ("T", "R"):
            if c not in df:
                if "sigma_"+c in df:
                    raise ValueError(f"sigma_{c} 缺少對應的 {c} 欄位。")
                values[c], errors[c] = None, None
                continue
            values[c] = df[c].to_numpy()/scale
            if np.any((values[c] < 0) | (values[c] > 1)):
                raise ValueError(f"{c} 超出 0–1，請檢查百分比選項與儀器校正；程式不會裁切。")
            errors[c] = (df["sigma_"+c].to_numpy()/scale if "sigma_"+c in df
                         else np.full(len(df), sigma))
            if np.any(errors[c] <= 0):
                raise ValueError("量測標準差必須大於零。")
        s = df.substrate_n.to_numpy() if "substrate_n" in df else np.full(len(df), substrate_n)
        if np.any(~np.isfinite(s)) or np.any(s < 1):
            raise ValueError("此模型需透明基板折射率 n >= 1；吸收基板不適用。")
        if values["T"] is not None and values["R"] is not None:
            if np.any(values["T"]+values["R"] > 1.02):
                raise ValueError("T+R 明顯超過 1，請檢查單位、校正或樣品是否一致。")
        return cls(df.wavelength_nm.to_numpy(), values["T"], values["R"],
                   errors["T"], errors["R"], s, notes)

    def frame(self):
        d = {"wavelength_nm": self.wavelength, "substrate_n": self.substrate_n}
        for c in ("T", "R"):
            if getattr(self, c) is not None:
                d[c] = getattr(self, c)
                d["sigma_"+c] = getattr(self, "sigma_"+c)
        return pd.DataFrame(d)
