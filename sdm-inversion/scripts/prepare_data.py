#!/usr/bin/env python3
"""
prepare_data.py — adaptive quadtree downsampling of deformation fields (grd/tif)
into SDM2025 data files (4 cols: lat lon disp err, no header).

Default mapping = ENU 3D field:
  enu_north.{tif,grd} -> ns.dat   (err floor/cap 0.02/0.10 m)
  enu_east.{tif,grd}  -> ew.dat   (0.02/0.10)
  enu_up.{tif,grd}    -> up.dat   (0.04/0.12)
Override with one or more --comp "SRCFILE:OUTNAME:EFLOOR:ECAP" (e.g. LOS tracks).

Quadtree: recursive 4-way split if in-block variance > thresh; binary search of
thresh to reach ~TARGET points per dataset. err = std/sqrt(n) clamped per dataset.
Reads .grd (GMT netcdf via GDAL) and .tif via rasterio.

Run with conda smvce_tiff python (numpy + rasterio).
"""
import os
import argparse
import numpy as np
import rasterio

MIN_BOX = 4
MAX_BOX = 128
MIN_VALID_FRAC = 0.3


def quadtree(data, var_thresh):
    leaves = []
    H, W = data.shape

    def recurse(x0, y0, w, h):
        sub = data[y0:y0 + h, x0:x0 + w]
        valid = sub[np.isfinite(sub)]
        n_v = len(valid)
        if w > MAX_BOX or h > MAX_BOX:
            split = True
        elif w <= MIN_BOX or h <= MIN_BOX:
            split = False
        elif n_v < MIN_VALID_FRAC * w * h:
            split = True
        elif n_v == 0:
            split = False
        else:
            split = float(np.var(valid)) > var_thresh
        if split and w > MIN_BOX and h > MIN_BOX:
            w2, h2 = w // 2, h // 2
            recurse(x0, y0, w2, h2)
            recurse(x0 + w2, y0, w - w2, h2)
            recurse(x0, y0 + h2, w2, h - h2)
            recurse(x0 + w2, y0 + h2, w - w2, h - h2)
        else:
            if n_v >= max(2, MIN_VALID_FRAC * w * h):
                leaves.append((x0, y0, w, h, float(valid.mean()), float(valid.std()), n_v))
    recurse(0, 0, W, H)
    return leaves


def bsearch(data, target, tol):
    valid = data[np.isfinite(data)]
    v_hi = float(np.var(valid)) * 4.0
    v_lo = v_hi * 1e-6
    leaves = quadtree(data, v_hi)
    for _ in range(40):
        v_mid = np.sqrt(v_lo * v_hi)
        leaves = quadtree(data, v_mid)
        n = len(leaves)
        if abs(n - target) / target < tol:
            return v_mid, leaves
        if n > target:
            v_lo = v_mid
        else:
            v_hi = v_mid
    return v_mid, leaves


DEFAULT_COMPS = [
    ("enu_north", "ns.dat", 0.02, 0.10),
    ("enu_east", "ew.dat", 0.02, 0.10),
    ("enu_up", "up.dat", 0.04, 0.12),
]


def resolve_src(src_dir, stem):
    """Accept a stem (no ext) or full filename; find .tif/.grd."""
    p = os.path.join(src_dir, stem)
    if os.path.exists(p):
        return p
    for ext in (".tif", ".grd", ".nc"):
        if os.path.exists(p + ext):
            return p + ext
    raise FileNotFoundError(f"{stem} (.tif/.grd) not found in {src_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", required=True, help="directory of input deformation fields")
    ap.add_argument("--out-dir", default=".", help="output directory for .dat files")
    ap.add_argument("--target", type=int, default=5000, help="target points per dataset")
    ap.add_argument("--tol", type=float, default=0.05, help="point-count tolerance")
    ap.add_argument("--comp", action="append", default=[],
                    help='override mapping "SRCFILE:OUTNAME:EFLOOR:ECAP" (repeatable)')
    args = ap.parse_args()

    if args.comp:
        comps = []
        for c in args.comp:
            parts = c.split(":")
            comps.append((parts[0], parts[1], float(parts[2]), float(parts[3])))
    else:
        comps = DEFAULT_COMPS

    os.makedirs(args.out_dir, exist_ok=True)
    for stem, out_name, efloor, ecap in comps:
        src = resolve_src(args.src_dir, stem)
        with rasterio.open(src) as r:
            data = r.read(1).astype(np.float64)
            if r.nodata is not None:
                data[data == r.nodata] = np.nan
            transform = r.transform
        v, leaves = bsearch(data, args.target, args.tol)
        rows = []
        for x0, y0, w, h, mean, std, n_v in leaves:
            lon, lat = transform * (x0 + w / 2.0, y0 + h / 2.0)
            err = float(np.clip(std / np.sqrt(n_v), efloor, ecap))
            rows.append((lat, lon, mean, err))
        rows = np.array(rows)
        rows = rows[np.lexsort((rows[:, 1], -rows[:, 0]))]
        out = os.path.join(args.out_dir, out_name)
        np.savetxt(out, rows, fmt="%.6f %.6f %.6f %.5f")
        print(f"{os.path.basename(src):18s} -> {out_name}: {len(rows)} pts  "
              f"disp[{rows[:,2].min():+.2f},{rows[:,2].max():+.2f}]  "
              f"err[{rows[:,3].min():.3f},{rows[:,3].max():.3f}]")


if __name__ == "__main__":
    main()
