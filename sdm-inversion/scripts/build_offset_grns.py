#!/usr/bin/env python3
"""
build_offset_grns.py — build the corrgrn file for ENU constant-offset corrections.

Each SDM data point gets one row; the columns are the offset basis vectors.
For ENU constant offsets (3 params N,E,U): points of the N dataset -> (1,0,0),
E dataset -> (0,1,0), U dataset -> (0,0,1). Row order MUST match the data-set
order declared in the inp (so pass the .dat files in that same order).

Usage:
  build_offset_grns.py ns.dat ew.dat up.dat > offset_grns.dat
Generalises: pass N .dat files -> N-column identity blocks in file order.
"""
import sys


def main():
    files = sys.argv[1:]
    if len(files) < 2:
        sys.exit("usage: build_offset_grns.py file1.dat file2.dat [file3.dat ...] > offset_grns.dat")
    counts = []
    for f in files:
        with open(f) as fh:
            counts.append(sum(1 for ln in fh if ln.strip()))
    n = len(files)
    sys.stdout.write(f"# offset Greens function: {n} columns, identity blocks per dataset in order {files}\n")
    for i in range(n):
        row = " ".join("1.0" if j == i else "0.0" for j in range(n)) + "\n"
        for _ in range(counts[i]):
            sys.stdout.write(row)
    sys.stderr.write(f"offset_grns: {n} cols, rows per dataset = {counts}, total = {sum(counts)}\n")


if __name__ == "__main__":
    main()
