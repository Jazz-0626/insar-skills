#!/usr/bin/env python3
"""
3D visualization of slip distribution on dipping fault plane(s).
Supports single-fault and multi-fault slip models.
Segments auto-detected by x_local reset (large negative jump).

Usage:
  python3 plot_slip_3d.py [<slip_file>]
  - default search: slip_model_merged.dat -> slip_model.dat
  - outputs slip_distribution_3d.png/pdf in the current working directory
"""
import sys, os, glob, types
# Prefer the native mpl_toolkits (e.g. inside a conda env this just works).
# Fallback for the rare setup where a system-installed mpl_toolkits (pinned to
# an older matplotlib API via pkg_resources.declare_namespace) shadows a newer
# pip-installed matplotlib in ~/.local: inject a mpl_toolkits whose __path__
# points at the user-local copy before any submodule import. Portable glob, no
# hardcoded python version.
try:
    import mpl_toolkits.mplot3d  # noqa: F401  (use native if available, e.g. conda)
except Exception:
    _cands = sorted(glob.glob(os.path.expanduser("~/.local/lib/python3*/site-packages/mpl_toolkits")))
    if _cands:
        _mod = types.ModuleType("mpl_toolkits")
        _mod.__path__ = [_cands[-1]]
        sys.modules["mpl_toolkits"] = _mod

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.colors import Normalize

REARTH = 6371.0

if os.path.exists('slip_model_merged.dat'):
    fname = 'slip_model_merged.dat'
else:
    fname = 'slip_model.dat'
if len(sys.argv) > 1:
    fname = sys.argv[1]

data = np.loadtxt(fname, skiprows=1)
print(f'Reading: {fname} ({len(data)} patches)')

lat      = data[:, 0]
lon      = data[:, 1]
depth    = data[:, 2]
dlen     = data[:, 5]
dwid     = data[:, 6]
slip_amp = data[:, 9]
strike   = data[:, 10]
dip_deg  = data[:, 11]

vmax = np.ceil(slip_amp.max() * 10) / 10

lat0 = lat.mean()
km_per_deg_lat = np.pi * REARTH / 180.0
km_per_deg_lon = km_per_deg_lat * np.cos(np.radians(lat0))

st = np.radians(strike)
di = np.radians(dip_deg)

ax_e = np.sin(st)
ax_n = np.cos(st)
dip_e =  np.cos(st) * np.cos(di)
dip_n = -np.sin(st) * np.cos(di)
dip_z =  np.sin(di)

half_l = 0.5 * dlen
half_w = 0.5 * dwid

corners = []
for i in range(len(slip_amp)):
    offsets = np.array([
        [-half_l[i], -half_w[i]],
        [+half_l[i], -half_w[i]],
        [+half_l[i], +half_w[i]],
        [-half_l[i], +half_w[i]],
    ])
    pts = np.zeros((4, 3))
    for k, (sl, sw) in enumerate(offsets):
        de = sl * ax_e[i] + sw * dip_e[i]
        dn = sl * ax_n[i] + sw * dip_n[i]
        dz = sw * dip_z[i]
        pts[k] = [lon[i] + de / km_per_deg_lon,
                  lat[i] + dn / km_per_deg_lat,
                  depth[i] + dz]
    corners.append(pts)

# Detect segments by x_local_km reset (large negative jump = new fault)
x_local = data[:, 3]
dx = np.diff(x_local)
jumps = np.where(dx < -10)[0]
seg_starts = [0] + list(jumps + 1)
seg_ends = list(jumps + 1) + [len(data)]
n_seg = len(seg_starts)

fig = plt.figure(figsize=(13, 9))
ax = fig.add_subplot(111, projection='3d')

cmap = plt.colormaps['hot_r']
norm = Normalize(vmin=0, vmax=vmax)

poly = Poly3DCollection(corners, cmap='hot_r', edgecolor='k', linewidth=0.1)
poly.set_array(slip_amp)
poly.set_norm(norm)
ax.add_collection3d(poly)

lon_min = lon.min() - 0.08
lon_max = lon.max() + 0.08
lat_min = lat.min() - 0.10
lat_max = lat.max() + 0.10
dep_max = max(depth.max() + 3.0, 20.0)

# Expand limits to include all corners
for c in corners:
    lon_min = min(lon_min, c[:, 0].min() - 0.02)
    lon_max = max(lon_max, c[:, 0].max() + 0.02)
    lat_min = min(lat_min, c[:, 1].min() - 0.02)
    lat_max = max(lat_max, c[:, 1].max() + 0.02)
    dep_max = max(dep_max, c[:, 2].max() + 1.0)

ax.set_xlim(lon_min, lon_max)
ax.set_ylim(lat_min, lat_max)
ax.set_zlim(dep_max, 0)

xx = np.array([[lon_min, lon_max], [lon_min, lon_max]])
yy = np.array([[lat_min, lat_min], [lat_max, lat_max]])
zz = np.zeros_like(xx)
ax.plot_surface(xx, yy, zz, alpha=0.15, color='lightgreen')

# Annotate segments
for si in range(n_seg):
    s, e = seg_starts[si], seg_ends[si]
    seg_lon = lon[s:e].mean()
    seg_lat = lat[s:e].mean()
    seg_dep = depth[s:e].min()
    label = f'Seg {si+1}' if n_seg > 1 else ''
    if label:
        ax.text(seg_lon, seg_lat, max(0, seg_dep - 2),
                label, fontsize=10, fontweight='bold', color='navy', zorder=10)

ax.set_xlabel('Longitude (°E)', fontsize=11, labelpad=8)
ax.set_ylabel('Latitude (°N)', fontsize=11, labelpad=8)
ax.set_zlabel('Depth (km)', fontsize=11, labelpad=6)

from matplotlib.ticker import MaxNLocator
ax.xaxis.set_major_locator(MaxNLocator(5))
ax.yaxis.set_major_locator(MaxNLocator(5))
ax.zaxis.set_major_locator(MaxNLocator(6))

cb = fig.colorbar(poly, ax=ax, pad=0.04, shrink=0.4, aspect=18)
cb.set_label('Slip amplitude (m)', fontsize=11)

ax.view_init(elev=25, azim=194)

lon_range = (lon_max - lon_min) * km_per_deg_lon
lat_range = (lat_max - lat_min) * km_per_deg_lat
dep_range = dep_max
try:
    ax.set_box_aspect([lon_range, lat_range, dep_range])
except Exception:
    pass

title = f'Slip Distribution 3D ({n_seg} segment{"s" if n_seg > 1 else ""})'
ax.set_title(title, fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('slip_distribution_3d.png', dpi=300, bbox_inches='tight')
plt.savefig('slip_distribution_3d.pdf', bbox_inches='tight')
for si in range(n_seg):
    s, e = seg_starts[si], seg_ends[si]
    seg_slip = slip_amp[s:e]
    print(f'  Seg {si+1}: {e-s} patches, max_slip={seg_slip.max():.2f}m, mean_slip={seg_slip.mean():.2f}m')
print('Saved: slip_distribution_3d.png / .pdf')
