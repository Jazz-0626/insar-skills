#!/usr/bin/env python3
"""
plot_map_view.py — map view of slip distribution as surface-projected fault
patches over a DEM hillshade, with fault traces and (optional) aftershocks.

Each slip patch (from an SDM slip_model file, 16 cols) is rendered as a
quadrilateral surface-projected from the dipping plane to (lon, lat).

Usage:
  plot_map_view.py --slip slip_model_merged.dat --dem dem.tif \
      --traces DMCF.shp WBF.shp --aftershocks Aftershocks.txt \
      --out figs/slip_map_view.png [--title "..."]

DEM accepts .tif or .grd (via GDAL). Aftershock file: whitespace columns with
lat in col 7 and lon in col 8 (1-based), depth col 9; '#' lines skipped.
Run with conda smvce_tiff python (numpy + rasterio + pyshp + matplotlib).
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, Normalize
from matplotlib.collections import PolyCollection
import rasterio
import shapefile

REARTH = 6371.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slip", required=True, help="SDM slip_model file (16 cols)")
    ap.add_argument("--dem", required=True, help="DEM .tif/.grd")
    ap.add_argument("--traces", nargs="*", default=[], help="trace shapefiles (1st solid, rest dashed)")
    ap.add_argument("--aftershocks", default=None, help="aftershock catalog txt (lat=col7, lon=col8)")
    ap.add_argument("--out", required=True, help="output png (pdf written alongside)")
    ap.add_argument("--title", default="Slip distribution — Map view")
    args = ap.parse_args()

    d = np.loadtxt(args.slip, skiprows=1)
    lat, lon = d[:, 0], d[:, 1]
    dl, dw, slip = d[:, 5], d[:, 6], d[:, 9]
    strike, dip = d[:, 10], d[:, 11]
    print(f"slip patches: {len(d)}  max slip = {slip.max():.2f} m")

    km_per_deg_lat = np.pi * REARTH / 180.0
    km_per_deg_lon = km_per_deg_lat * np.cos(np.radians(lat.mean()))
    st, di = np.radians(strike), np.radians(dip)
    ax_e, ax_n = np.sin(st), np.cos(st)
    dip_e, dip_n = np.cos(st) * np.cos(di), -np.sin(st) * np.cos(di)
    half_l, half_w = 0.5 * dl, 0.5 * dw

    polys = []
    for i in range(len(slip)):
        offs = np.array([[-half_l[i], -half_w[i]], [half_l[i], -half_w[i]],
                         [half_l[i], half_w[i]], [-half_l[i], half_w[i]]])
        pts = np.zeros((4, 2))
        for k, (sl, sw) in enumerate(offs):
            de = sl * ax_e[i] + sw * dip_e[i]
            dn = sl * ax_n[i] + sw * dip_n[i]
            pts[k] = [lon[i] + de / km_per_deg_lon, lat[i] + dn / km_per_deg_lat]
        polys.append(pts)

    with rasterio.open(args.dem) as r:
        dem = r.read(1).astype(float)
        b = r.bounds
    dem = np.where(np.isfinite(dem) & (dem > 0), dem, np.nan)
    extent = [b.left, b.right, b.bottom, b.top]
    hill = LightSource(azdeg=315, altdeg=35).hillshade(dem, vert_exag=0.0006, dx=1, dy=1)

    fig, ax = plt.subplots(figsize=(8, 11))
    fig.subplots_adjust(top=0.95, bottom=0.16, left=0.10, right=0.97)
    ax.imshow(hill, extent=extent, origin="upper", cmap="gray", vmin=0, vmax=1, alpha=0.85, zorder=0)
    ax.imshow(dem, extent=extent, origin="upper", cmap="terrain", alpha=0.18, zorder=1)

    vmax = np.ceil(slip.max() * 10) / 10
    pc = PolyCollection(polys, cmap="hot_r", edgecolors="none", zorder=3)
    pc.set_array(slip); pc.set_norm(Normalize(vmin=0, vmax=vmax))
    ax.add_collection(pc)
    m_low = slip < 0.05
    if m_low.any():
        ax.add_collection(PolyCollection([polys[i] for i in np.where(m_low)[0]],
                          facecolor="none", edgecolor="0.55", linewidth=0.25, zorder=2))

    if args.aftershocks:
        af = []
        with open(args.aftershocks) as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                f = s.split()
                if len(f) < 9:
                    continue
                try:
                    af.append((float(f[7]), float(f[6])))  # lon, lat
                except ValueError:
                    continue
        af = np.array(af)
        if len(af):
            m = ((af[:, 0] >= extent[0]) & (af[:, 0] <= extent[1]) &
                 (af[:, 1] >= extent[2]) & (af[:, 1] <= extent[3]))
            ax.scatter(af[m, 0], af[m, 1], s=4, c="0.18", alpha=0.32, marker="o",
                       linewidths=0.0, zorder=4, label="Aftershocks")
            print(f"aftershocks in extent: {m.sum()}")

    for idx, tp in enumerate(args.traces):
        style = "k-" if idx == 0 else "k--"
        lw = 1.8 if idx == 0 else 1.4
        label = tp.split("/")[-1].rsplit(".", 1)[0]
        for sh in shapefile.Reader(tp).shapes():
            tr = np.array(sh.points)
            ax.plot(tr[:, 0], tr[:, 1], style, lw=lw, zorder=5, label=label)

    h, l = ax.get_legend_handles_labels()
    seen = {}
    for hh, ll in zip(h, l):
        seen.setdefault(ll, hh)
    if seen:
        ax.legend(seen.values(), seen.keys(), loc="upper right", fontsize=10, framealpha=0.92)

    cax = fig.add_axes([0.25, 0.07, 0.5, 0.018])
    cb = fig.colorbar(pc, cax=cax, orientation="horizontal")
    cb.set_label("Slip [m]", fontsize=11)
    ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude (°E)", fontsize=11); ax.set_ylabel("Latitude (°N)", fontsize=11)
    ax.set_title(args.title, fontsize=13, fontweight="bold")
    ax.grid(True, ls=":", lw=0.4, alpha=0.4)

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.savefig(args.out.rsplit(".", 1)[0] + ".pdf", bbox_inches="tight")
    print(f"[saved] {args.out}")


if __name__ == "__main__":
    main()
