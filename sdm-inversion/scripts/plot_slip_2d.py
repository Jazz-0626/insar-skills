#!/usr/bin/env python3
"""
Visualize slip distribution on fault plane(s).

Y-axis is DEPTH (km). Both subplots share the same depth range (0–15 km) and
the same physical height. Subplot widths use GridSpec `width_ratios` so that
patches come out square in display: width_ratio_i = strike_range_i · sin(dip_i).

Shared horizontal colorbar at the bottom.
Auto-detects segments by x_local_km reset (large negative jump).
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize
import os
import sys

# ---------- input ----------
if os.path.exists('slip_model_merged.dat'):
    fname = 'slip_model_merged.dat'
else:
    fname = 'slip_model.dat'
if len(sys.argv) > 1:
    fname = sys.argv[1]

data = np.loadtxt(fname, skiprows=1)
print(f'Reading: {fname} ({len(data)} patches)')

x_local = data[:, 3]
dx = np.diff(x_local)
jumps = np.where(dx < -5)[0]
seg_starts = [0] + list(jumps + 1)
seg_ends = list(jumps + 1) + [len(data)]
n_seg = len(seg_starts)
strikes = data[:, 10]

vmax = np.ceil(data[:, 9].max() * 10) / 10
norm = Normalize(vmin=0, vmax=vmax)

DEPTH_MIN = 0.0
DEPTH_MAX = 15.0
DEPTH_DATA_MAX = 12.5   # only render slip patches / arrows within this depth;
                        # 12.5–15 km band is left blank for the segment label.

# ---------- compute width ratios for equal heights + square patches ----------
strike_ranges = []
sin_dips = []
for si in range(n_seg):
    s, e = seg_starts[si], seg_ends[si]
    seg = data[s:e]
    sr = (seg[:, 3].max() - seg[:, 3].min()) + seg[:, 5].mean()
    sd = np.sin(np.radians(np.mean(seg[:, 11])))
    strike_ranges.append(sr)
    sin_dips.append(sd)
# subplot width ∝ strike_range × sin(dip) → with same subplot height (H km of depth)
# each subplot has px_per_y = H/15, px_per_x = sin(dip) * H/15, so patches
# (dlen × dlen·sin(dip)) appear as squares
width_ratios = [sr * sd for sr, sd in zip(strike_ranges, sin_dips)]

# ---------- figure ----------
# Pick total figure width so subplot heights (in inches) match DEPTH_MAX=15km
# at a legible px/km. With left/right/padding of ~2 inches, target subplot
# y-height = TARGET_DEPTH_HEIGHT inches.
TARGET_DEPTH_HEIGHT = 5.0     # inches for 15 km of depth
total_axes_width = sum(width_ratios) * (TARGET_DEPTH_HEIGHT / DEPTH_MAX)
fig = plt.figure(figsize=(total_axes_width + 1.5, TARGET_DEPTH_HEIGHT + 2.0))

gs = fig.add_gridspec(1, n_seg, width_ratios=width_ratios,
                      bottom=0.22, top=0.95, left=0.06, right=0.98, wspace=0.10)

collections = []
for si in range(n_seg):
    ax = fig.add_subplot(gs[0, si])
    s, e = seg_starts[si], seg_ends[si]
    seg = data[s:e]

    x_strike = seg[:, 3]
    depth    = seg[:, 2]
    dlen     = seg[:, 5]
    dwid     = seg[:, 6]
    dip_col  = seg[:, 11]
    slip_ss  = seg[:, 7]
    slip_dd  = seg[:, 8]
    slip_amp = seg[:, 9]
    y_local  = seg[:, 4]
    mean_st  = np.mean(strikes[s:e])
    dip_mean = np.mean(dip_col)

    h_depth = dwid * np.sin(np.radians(dip_col))
    half_l = dlen / 2.0
    half_h = h_depth / 2.0

    # Only render patches whose center lies within the data window; deeper
    # patches are hidden so the 12.5–15 km band is kept clean for the label.
    in_window = depth <= DEPTH_DATA_MAX
    patches = []
    slip_amp_draw = []
    for i in np.where(in_window)[0]:
        x0 = x_strike[i] - half_l[i]
        y0 = depth[i] - half_h[i]
        patches.append(Rectangle((x0, y0), dlen[i], h_depth[i]))
        slip_amp_draw.append(slip_amp[i])
    slip_amp_draw = np.array(slip_amp_draw)

    coll = PatchCollection(patches, cmap='hot_r', edgecolors='none', linewidths=0)
    coll.set_array(slip_amp_draw)
    coll.set_norm(norm)
    ax.add_collection(coll)
    collections.append(coll)

    # -------- slip-vector arrows (denser grid, shorter arrows) --------
    x_unique = np.unique(np.round(x_strike, 4))
    yl_unique = np.unique(np.round(y_local, 4))
    nl = len(x_unique)
    nw = len(yl_unique)
    # Denser sampling: target ~25 arrows along strike, ~10 along dip
    thin_x = max(1, nl // 25)
    thin_y = max(1, nw // 10)
    mask = (slip_amp > 0.1) & in_window
    mask_thin = np.zeros(len(slip_amp), dtype=bool)
    for i in range(len(slip_amp)):
        ix = np.searchsorted(x_unique, np.round(x_strike[i], 4))
        iy = np.searchsorted(yl_unique, np.round(y_local[i], 4))
        if ix % thin_x == 0 and iy % thin_y == 0:
            mask_thin[i] = True
    m = mask & mask_thin
    if m.sum() > 0:
        # Arrow length: max arrow ≈ 0.45 × patch length (≈ 30% longer than 0.35).
        arrow_scale = 0.455 * dlen.mean() / max(slip_amp.max(), 0.01) * max(thin_x, thin_y)
        v_arrow = slip_dd * np.sin(np.radians(dip_col))
        ax.quiver(
            x_strike[m], depth[m],
            slip_ss[m] * arrow_scale,
            v_arrow[m] * arrow_scale,
            angles='xy', scale_units='xy', scale=1,
            color='#1f4fd1',             # solid blue, no outline
            width=2.5, units='dots',
            headwidth=4, headlength=5, headaxislength=4.5,
            zorder=6,
        )

    # -------- axes --------
    ax.set_xlim(0, x_unique[-1] + half_l.mean())
    ax.set_ylim(DEPTH_MIN, DEPTH_MAX)
    ax.invert_yaxis()
    ax.set_xlabel('Along strike (km)', fontsize=11)
    if si == 0:
        ax.set_ylabel('Depth (km)', fontsize=11)

    # ---- label placed in the reserved 12.5–15 km blank band at bottom ----
    slip_drawn_max = slip_amp_draw.max() if len(slip_amp_draw) > 0 else 0.0
    slip_drawn_mean = slip_amp_draw.mean() if len(slip_amp_draw) > 0 else 0.0
    seg_label = (f'Segment {si+1}   strike~{mean_st:.0f}°   dip~{dip_mean:.0f}°\n'
                 f'max_slip={slip_drawn_max:.2f}m   mean={slip_drawn_mean:.2f}m')
    # y-data coordinate 13.5 sits in the reserved 12.5–15 km band
    ax.text(0.5 * ax.get_xlim()[1], 13.5, seg_label,
            fontsize=10, ha='center', va='center',
            bbox=dict(facecolor='white', alpha=0.9, edgecolor='grey',
                      boxstyle='round,pad=0.4'))

    # Horizontal line marking the 12.5 km data cutoff (explicit visual boundary)
    ax.axhline(DEPTH_DATA_MAX, color='grey', ls='--', lw=0.8, alpha=0.6)

    # Natural inversion depth extent: if < DEPTH_DATA_MAX (e.g. WBF hits its
    # width limit before 12.5 km), annotate it.
    deepest_patch = depth.max() + half_h[depth.argmax()]
    if deepest_patch < DEPTH_DATA_MAX - 0.1:
        ax.axhline(deepest_patch, color='grey', ls=':', lw=0.8, alpha=0.6)
        ax.text(ax.get_xlim()[1] * 0.98, deepest_patch + 0.2,
                f'inversion ends at {deepest_patch:.1f} km',
                fontsize=8, color='grey', ha='right', va='top', alpha=0.85)

    # Do NOT set aspect; GridSpec width_ratios already make patches square
    # with equal subplot heights.
    ax.tick_params(labelsize=9)
    ax.grid(True, alpha=0.15, ls=':')

    n_shown = int(in_window.sum())
    n_hidden = int((~in_window).sum())
    print(f'  Seg {si+1} (strike~{mean_st:.0f}°, dip~{dip_mean:.0f}°, {e-s} patches): '
          f'depth 0–{deepest_patch:.1f}km, drawing {n_shown} patches (hiding {n_hidden} below {DEPTH_DATA_MAX}km), '
          f'max_slip(drawn)={slip_drawn_max:.2f}m')

# Shared horizontal colorbar at the bottom
cbar_ax = fig.add_axes([0.20, 0.06, 0.60, 0.025])
cb = fig.colorbar(collections[0], cax=cbar_ax, orientation='horizontal')
cb.set_label('Slip amplitude (m)', fontsize=11)
cb.ax.tick_params(labelsize=9)

fig.savefig('slip_distribution.png', dpi=300, bbox_inches='tight')
fig.savefig('slip_distribution.pdf', bbox_inches='tight')
print('Saved: slip_distribution.png / .pdf')
