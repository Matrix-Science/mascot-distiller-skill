##############################################################################
# run_denovo                                                                 #
##############################################################################
# COPYRIGHT NOTICE                                                           #
# Copyright 2026 Matrix Science Limited  All Rights Reserved.                #
##############################################################################
"""Run Mascot Distiller de novo sequencing over a .rov project, with parameters
appropriate to the data rather than Distiller's generic defaults.

De novo parameters live inside the project, not in the preferences file and not
on the command line (see patch_rov_denovo.py and references/DE_NOVO.md). The
project does not contain them until Distiller has done de novo work on it at
least once. So the working sequence is:

    1. SEED   a tiny de novo run   -> makes Distiller materialise `rover_data`
    2. PATCH  the parameters       -> and drop any cached solutions
    3. RUN    de novo for real

Usage:
    python run_denovo.py --rov project.rov --out denovo.csv \
        --seed-start 5 --seed-end 400 --frag-tol 0.02 --pep-tol 10

    # or let the seed window come from a peak-list manifest CSV that has a
    # "first_scan" column (as produced by an MDRO peak-picking script):
    python run_denovo.py --rov project.rov --out denovo.csv \
        --manifest project_manifest.csv
"""

__version__ = "1.0.0"

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import patch_rov_denovo

DENOVO_ALL = "0"
DENOVO_RANGE = "1"

ACCESS_VIOLATION = 3221225477      # 0xC0000005


def find_distiller() -> Path:
    """Locate MascotDistiller.exe.

    Order: MASCOT_DISTILLER_INSTALL, then the usual Program Files locations.
    """
    env = os.environ.get("MASCOT_DISTILLER_INSTALL")
    candidates = []
    if env:
        candidates.append(Path(env))
    for var in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(var)
        if base:
            candidates.append(Path(base) / "Matrix Science" / "Mascot Distiller")
    for c in candidates:
        if (c / "MascotDistiller.exe").exists():
            return c
    raise SystemExit(
        "MascotDistiller.exe not found. Set MASCOT_DISTILLER_INSTALL to the "
        "Mascot Distiller installation directory.")


def distiller(install: Path, args, label: str) -> int:
    """Run Distiller with cwd set to its own directory (it resolves sibling
    DLLs and config relative to there)."""
    t0 = time.time()
    proc = subprocess.run([str(install / "MascotDistiller.exe"), *args],
                          cwd=str(install), capture_output=True, text=True)
    print(f"  {label}: exit={proc.returncode} elapsed={time.time()-t0:.0f}s")
    return proc.returncode


def seed_range_from_manifest(manifest: Path, count: int):
    """First and last scan of a short seeding window.

    The seed exists only to make Distiller materialise `rover_data`, which it
    writes the first time it actually does de novo work. A single scan is not
    enough: if that one spectrum yields no de novo result the run still exits
    0, no rover_data appears, and the patch step then fails with
    "rover_data not present". A window of scans makes that outcome far less
    likely while still costing seconds.
    """
    scans = []
    with open(manifest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            scans.append(int(row["first_scan"]))
            if len(scans) >= count:
                break
    if not scans:
        raise SystemExit(f"empty manifest: {manifest}")
    return scans[0], scans[-1]


def read_header(csv_path: Path) -> dict:
    """Parse the Key,"Value" header block above the solution table."""
    header = {}
    with open(csv_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("PeakListIndex"):
                break
            parts = [p.strip().strip('"')
                     for p in line.rstrip("\n").split(",", 1)]
            if len(parts) == 2 and parts[0]:
                header[parts[0]] = parts[1]
    return header


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rov", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--manifest", type=Path,
                    help="peak-list manifest CSV with a first_scan column; "
                         "used to pick the seeding window")
    ap.add_argument("--seed-start", type=int,
                    help="first raw scan of the seeding window")
    ap.add_argument("--seed-end", type=int,
                    help="last raw scan of the seeding window")
    ap.add_argument("--seed-scans", type=int, default=25,
                    help="how many leading manifest rows the seeding window "
                         "covers when --manifest is used")
    ap.add_argument("--frag-tol", type=float, default=0.02)
    ap.add_argument("--frag-tol-fallbacks", default="0.04,0.05,0.1",
                    help="comma-separated tolerances to fall back to if the "
                         "engine crashes at the requested one")
    ap.add_argument("--pep-tol", type=float, default=10.0)
    ap.add_argument("--instrument", default="ESI-TRAP")
    ap.add_argument("--enzyme", default="Trypsin/P")
    ap.add_argument("--solutions", type=int, default=10)
    ap.add_argument("--fixed-mod", action="append",
                    help="repeatable; default Carbamidomethyl (C)")
    ap.add_argument("--var-mod", action="append",
                    help="repeatable; default Oxidation (M). Phospho datasets "
                         "need Phospho (ST) and Phospho (Y) adding here or de "
                         "novo cannot place the modification at all. Do not "
                         "add mods speculatively -- each one costs accuracy.")
    args = ap.parse_args()

    install = find_distiller()
    if not args.rov.exists():
        sys.exit(f"not found: {args.rov}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    status = args.out.with_name(args.out.stem + "_status.txt")
    log = args.out.with_name(args.out.stem + ".log")
    seed_out = args.out.with_name(args.out.stem + "_seed.csv")
    for stale in (args.out, status, log, seed_out):
        stale.unlink(missing_ok=True)

    if args.seed_start and args.seed_end:
        lo, hi = args.seed_start, args.seed_end
    elif args.manifest:
        lo, hi = seed_range_from_manifest(args.manifest, args.seed_scans)
    else:
        sys.exit("give either --manifest or both --seed-start and --seed-end")

    # 1. Seed: smallest useful de novo run, purely to make Distiller
    #    materialise the rover_data member we need to patch.
    print(f"[1/3] seeding project (scans {lo}-{hi})")
    distiller(install, ["/batch", "/denovo", DENOVO_RANGE,
                        "/denovo_start_scan", str(lo),
                        "/denovo_end_scan", str(hi),
                        "/denovoout", str(seed_out),
                        "/e", str(status), "/logfile", str(log),
                        "/loglevel", "3", str(args.rov)], "seed")

    # 2 & 3. Patch parameters, then run -- retrying at a looser fragment
    # tolerance if the engine dies.
    #
    # Distiller's de novo engine can segfault (0xC0000005) on some data at
    # tight fragment tolerances. Measured on a Fusion Lumos phosphoproteomics
    # file: 0.02 and 0.03 Da crash within ~70s, while 0.04, 0.05, 0.1 and 0.3
    # all complete normally. The same 0.02 Da setting is fine on Q Exactive
    # data, so it is data-dependent rather than a flat limit. Rather than give
    # up the tight tolerance everywhere, ask for it and back off only where
    # needed, recording what was actually used.
    backoff = [args.frag_tol]
    for v in args.frag_tol_fallbacks.split(","):
        v = v.strip()
        if v and float(v) > args.frag_tol:
            backoff.append(float(v))

    pristine = args.rov.with_suffix(".rov.orig")
    rc, used_tol = 1, None
    for i, tol in enumerate(backoff, 1):
        if pristine.exists():
            # Start each attempt from the pre-patch project so a crashed run
            # cannot leave partial state behind.
            shutil.copy2(pristine, args.rov)
        print(f"[2/3] patching de novo parameters "
              f"(fragment tolerance {tol} Da, attempt {i}/{len(backoff)})")
        patch_rov_denovo.patch_rov(
            args.rov, frag_tol=tol, pep_tol=args.pep_tol,
            instrument=args.instrument, enzyme=args.enzyme,
            solutions=args.solutions, fixed_mods=args.fixed_mod,
            var_mods=args.var_mod)

        print("[3/3] de novo sequencing all spectra")
        args.out.unlink(missing_ok=True)
        rc = distiller(install, ["/batch", "/denovo", DENOVO_ALL,
                                 "/denovoout", str(args.out),
                                 "/outputProgress",
                                 "/e", str(status), "/logfile", str(log),
                                 "/loglevel", "3", str(args.rov)], "denovo")
        if rc == 0 and args.out.exists():
            used_tol = tol
            break
        print(f"  failed at {tol} Da (exit {rc})"
              + (" -- access violation" if rc == ACCESS_VIOLATION else ""))

    if used_tol is not None and used_tol != args.frag_tol:
        print(f"  NOTE: fell back to {used_tol} Da fragment tolerance")

    if status.exists() and status.read_text().strip():
        print("status:", status.read_text().strip()[:300])
    if not args.out.exists():
        sys.exit(f"no de novo output produced (exit {rc})")

    # Echo what the run actually used. Worth reading every time: the header
    # reflects the patched parameters even when cached results were re-exported,
    # so treat it as confirmation of intent, not proof of recomputation.
    header = read_header(args.out)
    for k in ("Instrument Type", "Enzyme", "Peptide Mass Tolerance",
              "Fragment Mass Tolerance", "Fixed Modifications",
              "Variable Modifications"):
        if k in header:
            print(f"  {k}: {header[k]}")
    seed_out.unlink(missing_ok=True)
    print(f"wrote {args.out} ({args.out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
