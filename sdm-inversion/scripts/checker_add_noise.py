#!/usr/bin/env python3
"""
checker_add_noise.py — turn SDM forward output into synthetic noisy observations
for a resolution test. Reads each forward file fwd_<short>.dat (col5 = prediction
at the real obs lat/lon) and writes <out>_synth.dat = `lat lon (pred+noise) err`.

Noise is zero-mean Gaussian with a per-component sigma you supply — set it to the
FAR-FIELD std of your real field so the SNR is realistic (so the test honestly
reflects what the data can resolve). err column = sigma (so weight = 1/err^2).

Usage (ENU 3-component, sigmas in metres):
  checker_add_noise.py --map un:ns:0.107 --map ue:ew:0.023 --map uz:up:0.018 --seed 20260609

Usage (LOS):
  checker_add_noise.py --map ulos_asc:los_asc:0.02 --map ulos_des:los_des:0.02

Each --map is  fwd_short:out_name:sigma_m  (reads fwd_<short>.dat -> <out>_synth.dat).
Prints SNR = predRMS/sigma per component (SNR<~1 => component at/below noise floor).
"""
import argparse
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", action="append", required=True,
                    metavar="SHORT:OUT:SIGMA", help="fwd_<SHORT>.dat -> <OUT>_synth.dat, sigma metres")
    ap.add_argument("--seed", type=int, default=20260609, help="RNG seed (fixed for reproducibility)")
    ap.add_argument("--dir", default=".", help="directory holding fwd_*.dat / writing *_synth.dat")
    args = ap.parse_args()

    here = Path(args.dir)
    rng = np.random.default_rng(seed=args.seed)
    for spec in args.map:
        short, out, sig = spec.split(":")
        sigma = float(sig)
        a = np.loadtxt(here / f"fwd_{short}.dat", skiprows=1)
        lat, lon, pred = a[:, 0], a[:, 1], a[:, 4]
        disp = pred + rng.normal(0.0, sigma, size=len(pred))
        np.savetxt(here / f"{out}_synth.dat",
                   np.column_stack([lat, lon, disp, np.full(len(disp), sigma)]),
                   fmt="%.8f %.8f %.6f %.4f")
        prms = float(np.sqrt(np.mean(pred ** 2)))
        print(f"  fwd_{short} -> {out}_synth.dat  N={len(disp)} predRMS={prms:.3f} "
              f"sigma={sigma:.3f} SNR={prms/sigma:.1f}")


if __name__ == "__main__":
    main()
