#!/usr/bin/env python3
"""
sdm_to_pscmp.py — convert an SDM2025 slip_model.dat into a complete PSCMP2020
input file for coseismic Coulomb-stress-change (dCFS) calculation.

Mapping (verified against PSCMP source pscdisc.f / pscgetinp.f — SDM and
PSGRN/PSCMP are by the same author and share the rake convention
rake = atan2(-slip_d, slip_s), so NO sign flip is needed):
  PSCMP pos_s   <- SDM x_local (col4, along-strike, km)
  PSCMP pos_d   <- SDM y_local (col5, down-dip, km)
  PSCMP slip_s  <- SDM slp_strk (col8, m)         [strike-slip, as-is]
  PSCMP slip_d  <- SDM slp_ddip (col9, m)         [dip-slip, normal +, as-is]
  open          <- 0
The whole SDM mesh becomes ONE rectangular subfault: np_st x np_di patches of
size (length/np_st) x (width/np_di). Reference point O (pos_s=pos_d=0) is the
updip strike-start corner, back-projected from the corner patch (it should
match your SDM trace start node — the script prints it; verify!). A single
representative dip (slip-weighted mean) replaces a variable-dip SDM plane; the
patch-depth error is printed (typically <0.3 km for ~10 deg dip variation).

CFS output: icfs=1 with the receiver ("master") mechanism (strike0,dip0,rake0);
snapshot column 'CFS_Mas' (col 18 when insar=0) = coseismic dCFS on that fault
= tau + f*(sigma_n + p), tension-positive. VALIDATE the run: PSCMP prints
"Seismic moment ... (Mw = X)" recomputed from the converted slip — it must
match your SDM inversion Mw within ~0.05 (shear-modulus difference only).

Usage:
  sdm_to_pscmp.py --slip slip_model.dat --out pscmp_10km.inp \
     --lat0 <s> --lat1 <n> --nlat <n> --lon0 <w> --lon1 <e> --nlon <n> \
     [--friction 0.4 --skempton 0.0] \
     [--rstrike <deg> --rdip <deg> --rrake <deg>]   (receiver mech; default = source slip-weighted; literature often uses near-pure rake, e.g. -85/-90 for normal faults) \
     [--grndir ./grnfcts_10km/ --outdir ./output_10km/ --snap coulomb.dat]
NOTE: the obs grid must lie inside the PSGRN distance range r2.
"""
import argparse
from pathlib import Path
import numpy as np

R_EARTH = 6371.0


def move(lat0, lon0, az_deg, dist_km):
    """great-circle move from (lat0,lon0) by dist_km at azimuth az_deg."""
    latr = np.radians(lat0); az = np.radians(az_deg); dr = dist_km / R_EARTH
    lat2 = np.arcsin(np.sin(latr) * np.cos(dr) + np.cos(latr) * np.sin(dr) * np.cos(az))
    lon2 = np.radians(lon0) + np.arctan2(np.sin(az) * np.sin(dr) * np.cos(latr),
                                         np.cos(dr) - np.sin(latr) * np.sin(lat2))
    return np.degrees(lat2), np.degrees(lon2)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slip", required=True, help="SDM slip_model.dat (16 cols)")
    ap.add_argument("--out", default="pscmp_coulomb.inp")
    ap.add_argument("--lat0", type=float, required=True); ap.add_argument("--lat1", type=float, required=True)
    ap.add_argument("--nlat", type=int, required=True)
    ap.add_argument("--lon0", type=float, required=True); ap.add_argument("--lon1", type=float, required=True)
    ap.add_argument("--nlon", type=int, required=True)
    ap.add_argument("--friction", type=float, default=0.4)
    ap.add_argument("--skempton", type=float, default=0.0)
    ap.add_argument("--rstrike", type=float, default=None)
    ap.add_argument("--rdip", type=float, default=None)
    ap.add_argument("--rrake", type=float, default=None)
    ap.add_argument("--grndir", default="./grnfcts/")
    ap.add_argument("--outdir", default="./output/")
    ap.add_argument("--snap", default="coulomb.dat")
    args = ap.parse_args()

    d = np.loadtxt(Path(args.slip), skiprows=1)
    lat, lon, dep, xl, yl, ln, wd, ss, ds, am, stk, dip, rake = [d[:, i] for i in range(13)]
    nst = len(np.unique(np.round(xl, 4)))
    ndi = len(np.unique(np.round(yl, 4)))
    assert nst * ndi == len(d), f"grid {nst}x{ndi} != {len(d)} patches"
    dx = (xl.max() - xl.min()) / (nst - 1)
    dy = (yl.max() - yl.min()) / (ndi - 1)
    length = nst * dx
    width = ndi * dy
    strike = float(np.average(stk, weights=np.ones_like(stk)))     # constant strike
    dip_w = float(np.average(dip, weights=am))                     # slip-weighted dip
    rake_w = float(np.degrees(np.arctan2(np.average(-ds, weights=am), np.average(ss, weights=am))))

    # reference corner O (pos_s=pos_d=0): from the corner patch, back 0.5dx along
    # strike (az=strike+180) and 0.5dy*cos(dip) updip-horizontal (az=strike-90).
    ic = np.where((np.abs(xl - xl.min()) < 1e-3) & (np.abs(yl - yl.min()) < 1e-3))[0][0]
    la, lo = move(lat[ic], lon[ic], strike + 180.0, 0.5 * dx)
    la, lo = move(la, lo, strike - 90.0, 0.5 * dy * np.cos(np.radians(dip_w)))
    O_lat, O_lon, O_dep = la, lo, 0.0

    # receiver ("master") fault mechanism: default = source (strike, slip-wtd dip/rake)
    rstrike = args.rstrike if args.rstrike is not None else strike
    rdip = args.rdip if args.rdip is not None else dip_w
    rrake = args.rrake if args.rrake is not None else rake_w

    # sanity: reconstruct patch depths under the single-dip plane vs SDM depths
    dep_model = O_dep + yl * np.sin(np.radians(dip_w))
    derr = np.abs(dep_model - dep)
    print(f"grid {nst}x{ndi}={len(d)}  length={length:.3f} width={width:.3f} km")
    print(f"strike={strike:.2f}  dip(slip-wtd)={dip_w:.2f} (range {dip.min():.1f}-{dip.max():.1f})  rake(slip-wtd)={rake_w:.1f}")
    print(f"O(ref corner)=({O_lat:.5f},{O_lon:.5f}) depth={O_dep} km   <- VERIFY vs your trace start node")
    print(f"single-dip patch-depth error vs SDM: mean={derr.mean():.3f} max={derr.max():.3f} km")
    print(f"receiver mech: strike={rstrike:.1f} dip={rdip:.1f} rake={rrake:.1f}; friction={args.friction} skempton={args.skempton}")

    L = []
    w = L.append
    w("#=======================================================================")
    w("# PSCMP2020 input — coseismic Coulomb stress change from an SDM slip model.")
    w("# Auto-generated by sdm_to_pscmp.py (sdm-inversion skill).")
    w("# Receiver-fault dCFS = column 'CFS_Mas' in the snapshot (Pa).")
    w("#=======================================================================")
    w("# OBSERVATION ARRAY: iposrec=2 (2D), then [nlat lat1 lat2], [nlon lon1 lon2]")
    w("  2")
    w(f"  {args.nlat}   {args.lat0:.4f}   {args.lat1:.4f}")
    w(f"  {args.nlon}   {args.lon0:.4f}   {args.lon1:.4f}")
    w("#=======================================================================")
    w("# OUTPUTS")
    w("# insar xlos ylos zlos  (insar=0 -> no LOS)")
    w(" 0   0.0  0.0  0.0")
    w("# icfs friction skempton strike0 dip0 rake0 sigma1 sigma2 sigma3 [Pa]")
    w("#   icfs=1: receiver(master)-fault dCFS -> 'CFS_Mas'; sigma1..3 only affect")
    w("#   the 'optimal' columns (CFS_Max/CFS_Opt), not CFS_Mas.")
    w(f" 1   {args.friction:.3f}  {args.skempton:.3f}  {rstrike:.3f}  {rdip:.3f}  {rrake:.3f}   0.1E+07  -0.5E+07  -1.0E+07")
    w(f" '{args.outdir}'")
    w("# time-series selects (all 0 -> snapshots only) + filenames")
    w(" 0   0   0")
    w(" 'U_north.dat'  'U_east.dat'  'U_down.dat'")
    w(" 0   0   0   0   0   0")
    w(" 'S_nn.dat'  'S_ee.dat'  'S_dd.dat'  'S_ne.dat'  'S_ed.dat'  'S_dn.dat'")
    w(" 0   0   0   0   0")
    w(" 'Tilt_n.dat'  'Tilt_e.dat'  'Rotation.dat'  'geoid.dat'  'Gravity.dat'")
    w("# nsnap, then [time_day  'file'] per snapshot (t=0 -> coseismic)")
    w("  1")
    w(f"   0.00  '{args.snap}'")
    w("#=======================================================================")
    w("# GREEN'S FUNCTION DATABASE: iesmodel=1 (psgrn), grndir, then 14 names")
    w(" 1")
    w(f" '{args.grndir}'")
    w(" 'uz'  'ur'  'ut'")
    w(" 'szz' 'srr' 'stt' 'szr' 'srt' 'stz'")
    w(" 'tr'  'tt'  'rot' 'gd'  'gr'")
    w("#=======================================================================")
    w("# RECTANGULAR SUBFAULTS:  ns, then per subfault a header line + patches")
    w("#  header: n O_lat O_lon O_depth length width strike dip np_st np_di start_time")
    w("#  patch : pos_s pos_d slip_stk slip_ddip open   (km,km,m,m,m)")
    w("  1")
    w(f" 1  {O_lat:.5f} {O_lon:.5f} {O_dep:.4f}  {length:.3f} {width:.3f} "
      f"{strike:.3f} {dip_w:.3f}  {nst} {ndi}   0.00")
    for i in range(len(d)):
        w(f"   {xl[i]:8.4f} {yl[i]:8.4f}  {ss[i]:9.4f} {ds[i]:9.4f}   0.0000")
    w("#==========================================end of input=================")

    Path(args.out).write_text("\n".join(L) + "\n")
    print(f"wrote: {args.out}  ({len(d)} patches, obs grid {args.nlat}x{args.nlon}={args.nlat*args.nlon})")


if __name__ == "__main__":
    main()
