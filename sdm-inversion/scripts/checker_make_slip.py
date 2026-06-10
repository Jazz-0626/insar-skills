#!/usr/bin/env python3
"""
checker_make_slip.py — build a synthetic "true" slip model for a resolution test
on an EXISTING SDM mesh (your real inversion's slip_model.dat), by overwriting
the slip columns (8/9/10) + rake (13) and zeroing stress (14-16).

Two modes:

  cells  : classic alternating checkerboard. Per segment (auto-detected by
           x_local resets), a CELL×CELL km block (along-strike × down-dip depth)
           carries pure dip-slip AMP when (floor(x/CELL)+floor(depth/CELL))%2==0.
             checker_make_slip.py cells --src slip_model.dat --cell 8 --amp 2.0 [--strk 0]

  block  : ONE manually-placed rectangular block at a chosen along-strike/depth
           window. Slip in the block defaults to the MEAN strike-/dip-slip of the
           SOURCE data inside that window (same magnitude AND rake as the data),
           or override with --strk/--ddip.
             checker_make_slip.py block --src slip_model.dat \
                  --xmin 0 --xmax 30 --zmin 0 --zmax 10 [--strk S --ddip D]

Segments are auto-detected by along-strike (col4) resets, so it works for single
or multi-segment meshes. rake uses the SDM file convention:
    rake = atan2(-slp_ddip, slp_strk)   (col9 = slp_ddip = -slpmdl(2))
Output SDM format: 13f12.4 + 3f19.6 (matches slip_model.dat).
"""
import argparse
from pathlib import Path
import numpy as np

# slip_model.dat column indices (0-based)
C_DEPTH, C_X, C_LEN, C_WID = 2, 3, 5, 6
C_SSTRK, C_SDDIP, C_SAMP, C_RAKE = 7, 8, 9, 12


def detect_segments(x_local):
    seg = np.zeros(len(x_local), dtype=int)
    for i in range(1, len(x_local)):
        if x_local[i] < x_local[i - 1] - 5.0:   # along-strike reset = new segment
            seg[i:] += 1
    return seg


def write_sdm(path, header, data):
    with open(path, "w") as f:
        f.write(header + "\n")
        for row in data:
            line = "".join("%12.4f" % row[i] for i in range(13))
            line += "".join("%19.6f" % row[13 + i] for i in range(3))
            f.write(line + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["cells", "block"])
    ap.add_argument("--src", required=True, help="source mesh = real inversion slip_model.dat")
    ap.add_argument("--out", default="slip_dmcf_true.dat", help="output true-slip file")
    # cells
    ap.add_argument("--cell", type=float, default=8.0, help="[cells] cell size (km)")
    ap.add_argument("--amp", type=float, default=2.0, help="[cells] dip-slip amplitude in 'on' cells (m)")
    # block window
    ap.add_argument("--xmin", type=float, help="[block] along-strike min (km)")
    ap.add_argument("--xmax", type=float, help="[block] along-strike max (km)")
    ap.add_argument("--zmin", type=float, help="[block] depth min (km)")
    ap.add_argument("--zmax", type=float, help="[block] depth max (km)")
    # slip overrides (both modes: --strk; block also --ddip)
    ap.add_argument("--strk", type=float, default=None, help="force strike-slip (m); block default=mean of src")
    ap.add_argument("--ddip", type=float, default=None, help="[block] force dip-slip (m); default=mean of src")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    with open(src) as f:
        header = f.readline().rstrip("\n")
    data = np.loadtxt(src, skiprows=1)
    x_local, depth = data[:, C_X], data[:, C_DEPTH]
    print(f"loaded: {src.name}  ({len(data)} patches)")

    slip_strk = np.zeros(len(data))
    slip_ddip = np.zeros(len(data))

    if args.mode == "cells":
        strk = args.strk if args.strk is not None else 0.0
        seg = detect_segments(x_local)
        nseg = seg.max() + 1
        print(f"cells: cell={args.cell} km amp={args.amp} m strk={strk} m  ({nseg} segment(s))")
        for s in range(nseg):
            m = seg == s
            ix = np.floor(x_local[m] / args.cell).astype(int)
            iy = np.floor(depth[m] / args.cell).astype(int)
            on = ((ix + iy) % 2) == 0
            slip_strk[m] = np.where(on, strk, 0.0)
            slip_ddip[m] = np.where(on, args.amp, 0.0)
            print(f"  seg {s+1}: {m.sum()} patches ({int(on.sum())} on / {int((~on).sum())} off)")
    else:  # block
        for k in ("xmin", "xmax", "zmin", "zmax"):
            if getattr(args, k) is None:
                ap.error(f"block mode requires --{k}")
        on = ((x_local >= args.xmin) & (x_local <= args.xmax) &
              (depth >= args.zmin) & (depth <= args.zmax))
        if on.sum() == 0:
            raise SystemExit("ERROR: no patches inside the requested block window.")
        src_strk = float(data[on, C_SSTRK].mean())
        src_ddip = float(data[on, C_SDDIP].mean())
        strk = args.strk if args.strk is not None else src_strk
        ddip = args.ddip if args.ddip is not None else src_ddip
        slip_strk = np.where(on, strk, 0.0)
        slip_ddip = np.where(on, ddip, 0.0)
        auto = args.strk is None and args.ddip is None
        print(f"block: x_local[{args.xmin:g},{args.xmax:g}] depth[{args.zmin:g},{args.zmax:g}] km "
              f"-> {int(on.sum())}/{len(data)} on ({100*on.sum()/len(data):.1f}%)")
        print(f"  src mean in window:  strk={src_strk:+.4f}  ddip={src_ddip:+.4f} m")
        print(f"  applied:             strk={strk:+.4f}  ddip={ddip:+.4f}  |slip|={np.hypot(strk,ddip):.4f} m"
              + ("  (auto=mean)" if auto else "  (override)"))

    slip_amp = np.sqrt(slip_strk ** 2 + slip_ddip ** 2)
    data[:, C_SSTRK] = slip_strk
    data[:, C_SDDIP] = slip_ddip
    data[:, C_SAMP] = slip_amp
    nz = slip_amp > 0
    data[nz, C_RAKE] = np.degrees(np.arctan2(-slip_ddip[nz], slip_strk[nz]))
    data[~nz, C_RAKE] = 0.0
    data[:, 13:16] = 0.0

    write_sdm(args.out, header, data)
    print(f"wrote: {args.out}  active {int(nz.sum())}/{len(data)} "
          f"({100*nz.sum()/len(data):.1f}%)" + (f"  rake_on={data[nz,C_RAKE][0]:.0f}deg" if nz.any() else ""))


if __name__ == "__main__":
    main()
