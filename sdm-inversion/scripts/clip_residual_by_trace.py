#!/usr/bin/env python3
"""
clip_residual_by_trace.py — clip residual data files by perpendicular distance
to a polyline fault trace, keeping only points within a corridor of half-width
MAX_DIST_KM. Used to isolate a second-stage (e.g. WBF) inversion from first-stage
(DMCF) residual contamination.

Input  : {comp}_res.dat   (4 cols: lat lon disp err)
Output : {comp}_res_w{D}.dat

Trace from a shapefile (first shape's points) or inline --nodes "lat,lon;lat,lon;..."

Usage:
  clip_residual_by_trace.py --trace WBF.shp --dist 10 --comps ns ew up --work .
  clip_residual_by_trace.py --nodes "28.68,87.37;28.84,87.36" --dist 10 --comps ns ew up

Run with conda smvce_tiff python (numpy + pyshp if --trace).
"""
import os
import argparse
import numpy as np

KM_PER_DEG_LAT = 111.0


def read_trace(shp):
    import shapefile
    pts = shapefile.Reader(shp).shapes()[0].points  # (lon, lat)
    return np.array([[y, x] for x, y in pts])        # -> (lat, lon)


def point_segment_dist(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return np.sqrt(apx ** 2 + apy ** 2)
    t = np.clip((apx * abx + apy * aby) / ab2, 0.0, 1.0)
    cx, cy = ax + t * abx, ay + t * aby
    return np.sqrt((px - cx) ** 2 + (py - cy) ** 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--trace", help="shapefile of the corridor trace")
    g.add_argument("--nodes", help='inline "lat,lon;lat,lon;..."')
    ap.add_argument("--dist", type=float, default=10.0, help="corridor half-width (km)")
    ap.add_argument("--comps", nargs="+", default=["ns", "ew", "up"],
                    help="component prefixes; clips {comp}_res.dat")
    ap.add_argument("--work", default=".", help="working directory")
    args = ap.parse_args()

    if args.trace:
        trace = read_trace(args.trace)
    else:
        trace = np.array([[float(v) for v in nd.split(",")] for nd in args.nodes.split(";")])

    lat0, lon0 = trace[:, 0].mean(), trace[:, 1].mean()
    kpl = KM_PER_DEG_LAT * np.cos(np.radians(lat0))

    def to_xy(lat, lon):
        return (lon - lon0) * kpl, (lat - lat0) * KM_PER_DEG_LAT

    tx, ty = to_xy(trace[:, 0], trace[:, 1])
    suffix = f"w{int(args.dist)}"
    print(f"trace {len(trace)} nodes, corridor ±{args.dist} km  "
          f"(lat {trace[:,0].min():.4f}-{trace[:,0].max():.4f}, "
          f"lon {trace[:,1].min():.4f}-{trace[:,1].max():.4f})")
    for comp in args.comps:
        src = os.path.join(args.work, f"{comp}_res.dat")
        dst = os.path.join(args.work, f"{comp}_res_{suffix}.dat")
        data = np.loadtxt(src)
        px, py = to_xy(data[:, 0], data[:, 1])
        dists = np.full(len(px), np.inf)
        for i in range(len(tx) - 1):
            dists = np.minimum(dists, point_segment_dist(px, py, tx[i], ty[i], tx[i + 1], ty[i + 1]))
        kept = data[dists <= args.dist]
        np.savetxt(dst, kept, fmt="%.8f %.8f %.6f %.4f")
        print(f"  {comp}_res.dat: {len(data)} -> {os.path.basename(dst)}: {len(kept)} "
              f"({100.0*len(kept)/max(len(data),1):.1f}%)")


if __name__ == "__main__":
    main()
