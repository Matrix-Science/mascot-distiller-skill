##############################################################################
# patch_rov_denovo                                                           #
##############################################################################
# COPYRIGHT NOTICE                                                           #
# Copyright 2026 Matrix Science Limited  All Rights Reserved.                #
##############################################################################
"""Set the de novo search parameters stored inside a Mascot Distiller .rov.

Distiller's de novo engine takes instrument, enzyme, tolerances and
modifications from a `<denovotagTab>` section -- but from a copy held *inside
the project*, not from the live preferences file. The project snapshots that
section when it is created, which is why editing Distiller.rst afterwards has
no effect and why the documented /s <preferences> switch changes nothing.

A .rov is a ZIP. Its `rover_data` member is a <distillerProject> XML document
containing the embedded <denovotagTab>. Patching that member sets the
parameters the de novo run will actually use.

Numeric fields are base64-encoded little-endian IEEE-754 doubles, matching the
preferences format.

`rover_data` does not exist in a freshly created project -- Distiller writes it
the first time it does de novo work. Run a short seeding de novo pass first
(run_denovo.py does this for you).

Usage:
    python patch_rov_denovo.py --rov project.rov --frag-tol 0.02 --pep-tol 10 \
        --fixed-mod "Carbamidomethyl (C)" --var-mod "Oxidation (M)"

See references/DE_NOVO.md for the full workflow and failure modes.
"""

__version__ = "1.0.0"

import argparse
import base64
import re
import shutil
import struct
import zipfile
from pathlib import Path

ROVER_MEMBER = "rover_data"


def encode_double(value: float) -> str:
    return base64.b64encode(struct.pack("<d", float(value))).decode()


def decode_double(b64: str) -> float:
    return struct.unpack("<d", base64.b64decode(b64))[0]


def patch_denovo_block(xml: str, frag_tol: float, pep_tol: float,
                       instrument: str, enzyme: str, solutions: int,
                       fixed_mods: list, var_mods: list):
    """Rewrite the <denovotagTab> element of a distillerProject document.

    Returns (patched_xml, previous_values).
    """
    start = xml.find("<denovotagTab")
    if start < 0:
        raise ValueError("no <denovotagTab> in rover_data")
    end = xml.find("</denovotagTab>", start)
    if end < 0:
        raise ValueError("unterminated <denovotagTab>")
    end += len("</denovotagTab>")
    block = xml[start:end]

    # Decode before overwriting -- the cheapest check that the attribute being
    # patched is the one that was meant.
    before = {
        "FragTol": decode_double(re.search(r'FragTol="([^"]*)"', block).group(1)),
        "PepTol": decode_double(re.search(r'PepTol="([^"]*)"', block).group(1)),
    }

    def set_attr(b, attr, value):
        pat = re.compile(rf'{attr}="[^"]*"')
        return pat.sub(f'{attr}="{value}"', b, count=1) if pat.search(b) else b

    block = set_attr(block, "FragTol", encode_double(frag_tol))
    block = set_attr(block, "PepTol", encode_double(pep_tol))
    block = set_attr(block, "FragUnit", "Da")
    block = set_attr(block, "PepUnit", "ppm")
    block = set_attr(block, "Instrument", instrument)
    block = set_attr(block, "Enzyme", enzyme)
    block = set_attr(block, "DenovoSolutions", str(solutions))

    mods = "".join(f'<Mod Name="{m}" type="fix" />' for m in fixed_mods)
    mods += "".join(f'<Mod Name="{m}" type="var" />' for m in var_mods)
    if mods:
        # The element may be empty and self-closing (<Modifications ICAT="0" />)
        # in a stock project, or already populated. Handle both.
        if re.search(r'<Modifications([^>]*)/>', block):
            block = re.sub(r'<Modifications([^>]*)/>',
                           rf'<Modifications\1>{mods}</Modifications>',
                           block, count=1)
        else:
            block = re.sub(r'<Modifications([^>]*)>.*?</Modifications>',
                           rf'<Modifications\1>{mods}</Modifications>',
                           block, count=1, flags=re.S)

    return xml[:start] + block + xml[end:], before


def patch_rov(rov: Path, frag_tol: float = 0.02, pep_tol: float = 10.0,
              instrument: str = "ESI-TRAP", enzyme: str = "Trypsin/P",
              solutions: int = 10, fixed_mods=None, var_mods=None,
              backup: bool = True, keep_results: bool = False,
              verbose: bool = True) -> dict:
    """Patch a project's de novo parameters in place. Returns a summary dict."""
    rov = Path(rov)
    fixed_mods = ["Carbamidomethyl (C)"] if fixed_mods is None else fixed_mods
    var_mods = ["Oxidation (M)"] if var_mods is None else var_mods

    if not rov.exists():
        raise SystemExit(f"not found: {rov}")

    if backup:
        pristine = rov.with_suffix(".rov.orig")
        if not pristine.exists():
            shutil.copy2(rov, pristine)
            if verbose:
                print(f"backup -> {pristine.name}")

    with zipfile.ZipFile(rov) as zf:
        members = zf.infolist()
        blobs = {m.filename: zf.read(m.filename) for m in members}
        compress = {m.filename: m.compress_type for m in members}

    if ROVER_MEMBER not in blobs:
        raise SystemExit(
            f"{ROVER_MEMBER} not present in {rov.name} -- the project has "
            f"never had de novo run on it. Seed it first (see run_denovo.py).")

    xml = blobs[ROVER_MEMBER].decode("utf-8", errors="surrogateescape")
    patched, before = patch_denovo_block(xml, frag_tol, pep_tol, instrument,
                                         enzyme, solutions, fixed_mods,
                                         var_mods)

    # Purge cached de novo solutions. Distiller stores them in separate zip
    # members named "rover_data+N", referenced from the project XML by
    # <DenovoResult Segment="N" />. If they survive, /denovo simply re-exports
    # the old results and silently ignores the new parameters -- the run looks
    # like it succeeded and the exported header even shows the new tolerances.
    dropped = []
    if not keep_results:
        segments = re.findall(r'<DenovoResult\s+Segment="(\d+)"\s*/?>', patched)
        patched = re.sub(r'<DenovoResult\s+Segment="\d+"\s*/>', "", patched)
        for seg in segments:
            name = f"{ROVER_MEMBER}+{seg}"
            if blobs.pop(name, None) is not None:
                dropped.append(name)

    blobs[ROVER_MEMBER] = patched.encode("utf-8", errors="surrogateescape")

    tmp = rov.with_suffix(".rov.tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        for m in members:
            if m.filename not in blobs:
                continue
            zf.writestr(m.filename, blobs[m.filename],
                        compress_type=compress[m.filename])
    tmp.replace(rov)

    summary = {
        "frag_tol_before": before["FragTol"], "frag_tol": frag_tol,
        "pep_tol_before": before["PepTol"], "pep_tol": pep_tol,
        "instrument": instrument, "enzyme": enzyme, "solutions": solutions,
        "fixed_mods": list(fixed_mods), "var_mods": list(var_mods),
        "purged": dropped,
    }
    if verbose:
        print(f"patched {rov.name}")
        print(f"  fragment tolerance : {before['FragTol']} -> {frag_tol} Da")
        print(f"  peptide tolerance  : {before['PepTol']} -> {pep_tol} ppm")
        print(f"  instrument         : {instrument}")
        print(f"  enzyme             : {enzyme}")
        print(f"  solutions          : {solutions}")
        print(f"  fixed mods         : {', '.join(fixed_mods) or '-'}")
        print(f"  variable mods      : {', '.join(var_mods) or '-'}")
        print(f"  purged results     : {', '.join(dropped) or 'none cached'}")
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rov", required=True, type=Path)
    ap.add_argument("--frag-tol", type=float, default=0.02)
    ap.add_argument("--pep-tol", type=float, default=10.0)
    ap.add_argument("--instrument", default="ESI-TRAP")
    ap.add_argument("--enzyme", default="Trypsin/P")
    ap.add_argument("--solutions", type=int, default=10)
    ap.add_argument("--fixed-mod", action="append", default=None,
                    help="repeatable; default Carbamidomethyl (C)")
    ap.add_argument("--var-mod", action="append", default=None,
                    help="repeatable; default Oxidation (M). Phospho datasets "
                         "need Phospho (ST) and Phospho (Y) here or de novo "
                         "cannot place the modification at all.")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--keep-results", action="store_true",
                    help="do not purge cached de novo solutions (rarely what "
                         "you want -- see the note in patch_rov)")
    args = ap.parse_args()

    patch_rov(args.rov, args.frag_tol, args.pep_tol, args.instrument,
              args.enzyme, args.solutions, args.fixed_mod, args.var_mod,
              backup=not args.no_backup, keep_results=args.keep_results)


if __name__ == "__main__":
    main()
