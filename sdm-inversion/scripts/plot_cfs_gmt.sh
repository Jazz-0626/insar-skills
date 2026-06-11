#!/bin/bash
# plot_cfs_gmt.sh — GMT6 multi-depth coseismic dCFS (CFS_Mas) maps from PSCMP
# snapshot outputs. Generic: configure via env vars. Red = loading, blue = shadow.
#
# REQUIRED env:
#   R        GMT region, e.g. R=86.9/88.2/28.0/29.3  (must lie within PSGRN r2!)
# OPTIONAL env:
#   DEPTHS   list of depth tags, default "00 05 10 15 20"
#   DATPAT   per-depth snapshot path pattern with %s placeholder,
#            default "output_%skm/coulomb.dat"   (relative to cwd)
#   I        grid spacing [deg], default 0.01 (match your PSCMP obs grid!)
#   CLIP     colour saturation [bar], default 5  (1 bar = 0.1 MPa)
#   TRACE    fault surface-trace file (lon lat), drawn as black line (optional)
#   EPI      epicenter file (lon lat), drawn as yellow star (optional)
#   OUTNAME  figure name (no ext), default cfs_5depths -> figs/<OUTNAME>.{png,pdf}
#   ANNOT    one-line annotation for the legend slot (receiver mech etc.)
#
# Data: PSCMP snapshot col1=lat col2=lon col18=CFS_Mas[Pa] (icfs=1, insar=0).
# NOTE: GMT 6.3.0 subplot has a frame-synthesis bug with custom -B/+t (errors
# like "Offending option -BWrtS" you never wrote) — this script uses classic
# -X/-Y shifts instead. 3 panels per row; colorbar+annotation in the next slot.
set -e

: "${R:?set R=lonmin/lonmax/latmin/latmax}"
DEPTHS=${DEPTHS:-"00 05 10 15 20"}
DATPAT=${DATPAT:-output_%skm/coulomb.dat}
I=${I:-0.01}
CLIP=${CLIP:-5}
OUTNAME=${OUTNAME:-cfs_5depths}
W=8c; DX=9.6c; DY=11.2c

mkdir -p figs
gmt begin figs/$OUTNAME png,pdf E300
  gmt set FONT_TITLE 12p,Helvetica-Bold FONT_LABEL 10p FONT_ANNOT_PRIMARY 9p
  gmt set MAP_FRAME_TYPE plain MAP_TITLE_OFFSET 4p
  gmt makecpt -Cpolar -T-$CLIP/$CLIP/0.1 -Z -D

  n=0
  for Z in $DEPTHS; do
    ZLAB=$(echo $Z | sed 's/^0\([0-9]\)/\1/')
    if [ $n -eq 0 ]; then SHIFT="-X2.2c -Y26c"
    elif [ $((n % 3)) -eq 0 ]; then SHIFT="-X-19.2c -Y-${DY}"
    else SHIFT="-X${DX}"; fi
    DAT=$(printf "$DATPAT" "$Z")
    awk 'NR>1{printf "%.5f %.5f %.4f\n",$2,$1,$18/1e5}' "$DAT" \
      | gmt xyz2grd -R$R -I$I -Gtmp_$Z.grd
    gmt grdimage tmp_$Z.grd -R$R -JM$W -C $SHIFT \
        -Bxa0.4f0.2 -Bya0.4f0.2 -BWSen+t"Depth ${ZLAB} km"
    gmt grdcontour tmp_$Z.grd -C+0.0001 -W0.4p,40/40/40,2_2 -S8
    [ -n "$TRACE" ] && gmt plot "$TRACE" -W1.6p,black
    [ -n "$EPI" ]   && gmt plot "$EPI" -Sa0.45c -Gyellow -W0.8p,black
    rm -f tmp_$Z.grd
    n=$((n+1))
  done

  # colorbar (+ optional annotation) in the next free slot
  if [ $((n % 3)) -eq 0 ]; then SHIFT="-X-19.2c -Y-${DY}"; else SHIFT="-X${DX}"; fi
  gmt basemap -R0/1/0/1 -JX8c/8.5c $SHIFT -B+n
  gmt colorbar -C -Dx0.7c/5.2c+w6.6c/0.45c+h -Bxa2f1+l"@~D@~CFS (bar)"
  [ -n "$ANNOT" ] && echo "0.02 0.30 $ANNOT" | gmt text -F+f9p+jML -N
  echo "0.02 0.18 Colour clip \261${CLIP} bar; dashed = 0 contour" | gmt text -F+f9p+jML -N
gmt end

echo "[saved] figs/${OUTNAME}.png / .pdf"
