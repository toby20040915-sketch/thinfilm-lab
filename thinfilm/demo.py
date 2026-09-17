"""Synthetic cases, explicitly NOT measured a-Si datasets."""
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .physics import Parameters, ATLU, HC, spectrum

CASES = {
    "ultrathin_60nm": Parameters(d_nm=60, A_eV=95, Eg_eV=1.55, gap_eV=1.7, C_eV=2.1, tail_fraction=.09),
    "absorbing_180nm": Parameters(d_nm=180, A_eV=130, Eg_eV=1.3, gap_eV=1.8, C_eV=2.5, tail_fraction=.08),
    "fringes_900nm": Parameters(d_nm=900, A_eV=90, Eg_eV=2.2, gap_eV=1.3, C_eV=1.5, tail_fraction=.06),
    "scattering_120nm": Parameters(d_nm=120, A_eV=105, Eg_eV=1.7, gap_eV=1.6, C_eV=2., tail_fraction=.08, scatter_q=.08),
}


def simulate(case="ultrathin_60nm", noise=0.0015, seed=35, points=241):
    p = CASES[case]
    wavelength = np.linspace(300, 1200, points)
    # Generate on a finer, longer grid than regression to avoid exact grid reuse.
    with threadpool_limits(limits=1):
        n, k = ATLU(HC/wavelength, step_eV=.004, cutoff_eV=320).nk(p)
    sp = spectrum(wavelength, n, k, p.d_nm, scatter_q=p.scatter_q)
    rng = np.random.default_rng(seed)
    data = pd.DataFrame({"wavelength_nm": wavelength, "T": sp["T"]+rng.normal(0, noise, points),
                         "R": sp["R"]+rng.normal(0, noise, points),
                         "sigma_T": max(noise, 1e-5), "sigma_R": max(noise, 1e-5), "substrate_n": 1.5})
    # A strict importer rejects negative instrument readings. In demonstrations
    # use a stated floor, not silent clipping of user measurement files.
    data["T"] = np.maximum(data["T"], 0.)
    data["R"] = np.maximum(data["R"], 0.)
    ref = pd.DataFrame({"wavelength_nm": wavelength, "n": n, "k": k, "T": sp["T"],
                        "R": sp["R"], "d_nm": p.d_nm})
    return data, ref, p


def write_examples(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        data, ref, p = simulate(case)
        data.to_csv(folder/(case+".csv"), index=False)
        ref.to_csv(folder/(case+"_truth.csv"), index=False)
        (folder/(case+"_truth.json")).write_text(json.dumps({"synthetic": True,
            "note": "模擬資料；T/R 負噪音值歸零，非實測或第三方驗證。", "parameters": p.report(),
            "gamma_eV": .02, "noise_sigma": .0015, "seed": 35}, ensure_ascii=False, indent=2), encoding="utf-8")
