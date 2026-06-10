#!/bin/bash
# checker_run.sh — generic resolution-test runner (one case):
#   make synthetic "true" slip -> SDM forward (niter=0) -> add noise -> SDM invert.
# Geometry/smoothing come from your forward/invert inp (copies of the production
# DMCF inp with nusrp=0 and niter 0 / N respectively — see templates/).
#
# REQUIRED env (export before calling):
#   SDM    sdm2025 executable (third-party, R. Wang — see SKILL.md for source)
#   PY     python with numpy/matplotlib (e.g. a conda env)
#   SRC    real-inversion slip_model.dat (the mesh to overwrite)
#   FWD    forward inp (reads slip_dmcf_runtime.dat, writes fwd_*; niter=0)
#   INV    invert  inp (reads *_synth.dat, writes slip_dmcf_inverted.dat; niter>0)
#   NOISE  args for checker_add_noise.py, e.g. "--map un:ns:0.107 --map ue:ew:0.023 --map uz:up:0.018"
# OPTIONAL:
#   SKILL  this skill's scripts dir (default: dir of this script)
#
# Usage:
#   checker_run.sh <CASE_DIR> block --xmin 0 --xmax 30 --zmin 0 --zmax 10
#   checker_run.sh <CASE_DIR> cells --cell 8 --amp 2.0
set -e
SKILL="${SKILL:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
: "${SDM:?set SDM=path/to/sdm2025 executable}"
: "${PY:?set PY=path/to/python (numpy+matplotlib)}"
: "${SRC:?set SRC=path/to/real slip_model.dat}"
: "${FWD:?set FWD=path/to/forward inp}"
: "${INV:?set INV=path/to/invert inp}"
: "${NOISE:?set NOISE=checker_add_noise.py args, e.g. --map un:ns:0.107 ...}"

CASE="${1:?need CASE_DIR}"; shift
MODE="${1:?need mode: block|cells}"; shift   # remaining args -> make_slip

echo "================ resolution test: $CASE  ($MODE $*) ================"
mkdir -p "$CASE"
cp "$FWD" "$CASE/sdm_checker_forward.inp"
cp "$INV" "$CASE/sdm_checker_invert.inp"
( cd "$CASE"
  $PY "$SKILL/checker_make_slip.py" "$MODE" --src "$SRC" --out slip_dmcf_true.dat "$@"
  cp slip_dmcf_true.dat slip_dmcf_runtime.dat
  echo 'sdm_checker_forward.inp' | "$SDM" > stdout_forward.log 2>&1
  $PY "$SKILL/checker_add_noise.py" $NOISE
  echo 'sdm_checker_invert.inp'  | "$SDM" > stdout_invert.log  2>&1
  grep -E 'derived moment|data-model correlation' stdout_invert.log | sed 's/^/    /'
)
echo "DONE: $CASE"
