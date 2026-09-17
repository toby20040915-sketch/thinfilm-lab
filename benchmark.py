"""Reproducible, explicitly synthetic recovery experiment."""
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
from thinfilm.demo import CASES, simulate
from thinfilm.data import SpectrumData
from thinfilm.fit import FitConfig, fit_spectrum
from thinfilm.report import result_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="results/benchmark")
    parser.add_argument("--starts", type=int, default=5)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in CASES:
        df, ref, p = simulate(case, points=181)
        cfg = FitConfig(starts=args.starts, fit_scatter=p.scatter_q > 0)
        print(f"Case: {case}", flush=True)
        fit = fit_spectrum(SpectrumData.from_csv(df), cfg,
                           progress=lambda i, total, err: print(f"  {i}/{total}: {err:.4f}", flush=True))
        row = {"case": case, "synthetic": True, "d_true_nm": p.d_nm, "d_fit_nm": fit.parameters.d_nm,
               "d_error_percent": 100*abs(fit.parameters.d_nm/p.d_nm-1),
               "n_RMSE": np.sqrt(np.mean((fit.table.n-ref.n)**2)),
               "k_RMSE": np.sqrt(np.mean((fit.table.k-ref.k)**2)),
               "converged": fit.summary["optimizer_success"], "envelope_available": fit.envelope["available"],
               "envelope_d_nm": fit.envelope["d_nm"], "warning_count": len(fit.summary["warnings"]),
               **fit.summary["metrics"]}
        rows.append(row)
        folder = out/case
        folder.mkdir(exist_ok=True)
        for name, content in result_files(fit).items():
            (folder/name).write_bytes(content)
        pd.DataFrame(rows).to_csv(out/"benchmark.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
