#!/usr/bin/env python3
"""
checker_compare.py — TRUE vs INVERTED slip figure + recovery stats for one or
more resolution-test cases. One ROW per case (TRUE | INVERTED on the fault plane,
along-strike x_local vs depth). Each row gets its OWN colour bar (block amplitudes
often differ ~10x). For block cases the requested window is drawn as a dashed
rectangle and recovery%/corr annotated.

A case is  DIR[:xmin,xmax,zmin,zmax[:label]]  — give the window for blocks (draws
the box + restricts the recovery 'on' set to that window); omit it for cells mode
(then 'on' = patches whose TRUE slip > --on-thresh).

Usage:
  checker_compare.py --case block1:0,30,0,10:"Block 1" \
                     --case block2:40,48,2,7:"Block 2" \
                     --out figs/manual_blocks_summary.png
  checker_compare.py --case cell5 --case cell8 --case cell10 --out figs/cells.png

Each DIR must contain slip_dmcf_true.dat and slip_dmcf_inverted.dat.
Recovery = mean(inverted slip over 'on' patches) / mean(true slip over 'on').
Leakage  = mean(inverted slip over 'off' patches).
"""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize

C_DEPTH, C_X, C_LEN, C_WID, C_DIP, C_SAMP = 2, 3, 5, 6, 11, 9


def load(p):
    return np.loadtxt(p, skiprows=1)


def parse_case(spec):
    parts = spec.split(":")
    d = parts[0]
    win = None
    label = Path(d).name
    if len(parts) >= 2 and parts[1]:
        win = [float(v) for v in parts[1].split(",")]
    if len(parts) >= 3 and parts[2]:
        label = parts[2]
    return d, win, label


def panel(ax, data, vmax, win, depth_max):
    x, z = data[:, C_X], data[:, C_DEPTH]
    dlen, dwid, dip, slip = data[:, C_LEN], data[:, C_WID], np.radians(data[:, C_DIP]), data[:, C_SAMP]
    hl, hh = 0.5 * dlen, 0.5 * dwid * np.sin(dip)
    rects, vals = [], []
    for i in range(len(data)):
        if z[i] - hh[i] > depth_max:
            continue
        rects.append(Rectangle((x[i] - hl[i], z[i] - hh[i]), dlen[i], 2 * hh[i]))
        vals.append(slip[i])
    pc = PatchCollection(rects, cmap="hot_r", edgecolors="none")
    pc.set_array(np.array(vals)); pc.set_norm(Normalize(0, vmax))
    ax.add_collection(pc)
    if win:
        ax.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2],
                               fill=False, ec="dodgerblue", lw=1.6, ls="--"))
    ax.set_xlim(0, x.max() + 0.5 * dlen.mean()); ax.set_ylim(0, depth_max); ax.invert_yaxis()
    ax.tick_params(labelsize=9)
    return pc


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", action="append", required=True,
                    metavar="DIR[:xmin,xmax,zmin,zmax[:label]]")
    ap.add_argument("--out", default="figs/checker_summary.png")
    ap.add_argument("--depth-max", type=float, default=15.0, help="render depth window (km)")
    ap.add_argument("--on-thresh", type=float, default=1e-6, help="true-slip threshold defining 'on' patches")
    args = ap.parse_args()

    cases = [parse_case(c) for c in args.case]
    nrow = len(cases)
    fig, axes = plt.subplots(nrow, 2, figsize=(12.5, 3.9 * nrow), squeeze=False)
    fig.subplots_adjust(left=0.07, right=0.88, top=0.94, bottom=0.07, hspace=0.32, wspace=0.10)

    print(f"{'case':<24}{'true_amp':>9}{'corr':>7}{'in':>8}{'recov%':>8}{'leak':>8}")
    for r, (d, win, label) in enumerate(cases):
        T = load(Path(d) / "slip_dmcf_true.dat")
        I = load(Path(d) / "slip_dmcf_inverted.dat")
        vmax = float(np.ceil(T[:, C_SAMP].max() * 10) / 10) or 1.0
        pcI = panel(axes[r][1], I, vmax, win, args.depth_max)
        panel(axes[r][0], T, vmax, win, args.depth_max)

        # 'on' set: inside window if given, else true-slip above threshold
        if win:
            on = ((T[:, C_X] >= win[0]) & (T[:, C_X] <= win[1]) &
                  (T[:, C_DEPTH] >= win[2]) & (T[:, C_DEPTH] <= win[3]))
        else:
            on = T[:, C_SAMP] > args.on_thresh
        true_amp = T[on, C_SAMP].mean()
        in_blk = I[on, C_SAMP].mean()
        recov = 100 * in_blk / true_amp if true_amp else 0.0
        leak = I[~on, C_SAMP].mean()
        corr = np.corrcoef(T[:, C_SAMP], I[:, C_SAMP])[0, 1]
        print(f"{label:<24}{true_amp:>9.3f}{corr:>7.3f}{in_blk:>8.3f}{recov:>7.0f}%{leak:>8.3f}")

        axes[r][0].set_title("TRUE", fontsize=11, fontweight="bold")
        axes[r][1].set_title("INVERTED", fontsize=11, fontweight="bold")
        axes[r][0].set_ylabel("Depth (km)", fontsize=10)
        axes[r][1].text(0.97, 0.06, f"recovery {recov:.0f}%\ncorr {corr:.2f}",
                        transform=axes[r][1].transAxes, ha="right", va="bottom", fontsize=9,
                        color="0.15", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.6", alpha=0.85))
        if nrow > 1:
            axes[r][0].text(-0.16, 0.5, label, transform=axes[r][0].transAxes, rotation=90,
                            va="center", ha="center", fontsize=10, fontweight="bold")
        pos1 = axes[r][1].get_position()
        cax = fig.add_axes([0.895, pos1.y0, 0.014, pos1.height])
        fig.colorbar(pcI, cax=cax).set_label("Slip (m)", fontsize=9)
        cax.tick_params(labelsize=8)

    for c in range(2):
        axes[-1][c].set_xlabel("Along strike (km)", fontsize=10)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    print(f"[saved] {out}")
    print(f"[saved] {out.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
