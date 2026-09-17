"""Command-line runner; use python cli.py --help."""
import argparse
import json
from pathlib import Path
import numpy as np
from thinfilm.data import SpectrumData
from thinfilm.fit import FitConfig, fit_spectrum, thickness_profile
from thinfilm.analysis import compare_reference
from thinfilm.demo import write_examples
from thinfilm.report import result_files


def main():
    ap = argparse.ArgumentParser(description="ATLU optical thin-film analysis")
    ap.add_argument("input", nargs="?")
    ap.add_argument("--output", default="results/analysis")
    ap.add_argument("--config", help="FitConfig JSON; supports bounds and fixed parameters")
    ap.add_argument("--units", choices=["fraction", "percent"], default="fraction")
    ap.add_argument("--substrate-n", type=float, default=1.5)
    ap.add_argument("--sigma", type=float, default=.005, help="Default absolute standard deviation in fraction units")
    ap.add_argument("--reference", action="append", default=[], help="Independent reference CSV, repeatable")
    ap.add_argument("--profile", type=int, default=0, help="Number of re-optimized thickness profile points")
    ap.add_argument("--make-examples", action="store_true")
    args = ap.parse_args()
    if args.make_examples:
        write_examples("examples")
        return 0
    if not args.input:
        ap.error("input CSV required")
    try:
        cfg = FitConfig(**json.loads(Path(args.config).read_text(encoding="utf-8-sig"))) if args.config else FitConfig()
        data = SpectrumData.from_csv(args.input, args.units, args.substrate_n, args.sigma)
        result = fit_spectrum(data, cfg, progress=lambda i, total, err: print(f"Start {i}/{total}, best weighted RMSE: {err:.5g}", flush=True))
        comparisons = []
        for ref in args.reference:
            metrics, errors = compare_reference(result.table, ref, result.parameters.d_nm, Path(ref).name)
            comparisons.append((Path(ref).name, metrics, errors))
        profile = None
        if args.profile:
            if args.profile < 3:
                raise ValueError("profile 需要至少 3 個厚度點。")
            low, high = cfg.bounds["d_nm"]
            ds = np.linspace(max(low, result.parameters.d_nm*.7), min(high, result.parameters.d_nm*1.3), args.profile)
            profile = thickness_profile(data, result, ds)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        for name, content in result_files(result, comparisons, profile).items():
            (out/name).write_bytes(content)
        print(f"d = {result.parameters.d_nm:.5f} nm; converged = {result.summary['optimizer_success']}")
        print(f"Results: {out.resolve()}")
        return 0 if result.summary["fit_quality_pass"] else 2
    except (ValueError, OSError, TypeError) as exc:
        ap.exit(1, str(exc)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
