# De novo sequencing with Mascot Distiller

Distiller can sequence a spectrum without a database. From the GUI it is
**Analysis → De novo**; unattended it is `MascotDistiller.exe /batch /denovo`.
This page covers the unattended path, because that is where the parameters go
somewhere non-obvious and a silent-wrong-answer failure mode lives.

Verified against **Distiller 2.9.241.58** on Windows.

## Contents

1. [The one thing to know first](#the-one-thing-to-know-first)
2. [Command line](#command-line)
3. [The working sequence: seed → patch → run](#the-working-sequence-seed--patch--run)
4. [Parameters: the `<denovotagTab>` block](#parameters-the-denovotagtab-block)
5. [Choosing parameters for the instrument](#choosing-parameters-for-the-instrument)
6. [Output CSV format](#output-csv-format)
7. [Sequence notation](#sequence-notation)
8. [What the score does and does not tell you](#what-the-score-does-and-does-not-tell-you)
9. [Failure modes](#failure-modes)
10. [Throughput](#throughput)

---

## The one thing to know first

**De novo parameters are read from a copy stored inside the `.rov` project, not
from the preferences file and not from the command line.**

Three consequences, each of which looks like something else when you hit it:

| What you'd expect | What actually happens |
|---|---|
| Edit `Distiller.rst` (live preferences) between runs | No effect. The project snapshotted its own copy when it was created. |
| Pass `/s <preferences>` — it's a documented switch | Accepted and ignored for de novo. A deliberately **malformed** preferences file still produces normal output, which is how you can prove it isn't being read. |
| Set new parameters, re-run, read the output header | The header shows your new tolerances **and the solutions are the old ones**, re-exported from cache. See [failure modes](#failure-modes). |

So to change de novo parameters you patch `rover_data` inside the `.rov`.
The `.rov` is a ZIP — see [ROV_FILE_FORMAT.md](ROV_FILE_FORMAT.md) for the
container layout.

---

## Command line

`MascotDistiller.exe` lives in `<DISTILLER_INSTALL>`. Run it with
`cwd=<DISTILLER_INSTALL>` — it resolves sibling DLLs and config relative to its
own directory.

| Switch | Meaning |
|---|---|
| `/batch` | No GUI. Required for unattended use. |
| `/denovo <mode>` | `0` = every spectrum in the project, `1` = a scan range. |
| `/denovo_start_scan <n>` / `/denovo_end_scan <n>` | Range bounds, used when `/denovo 1`. **Raw scan numbers**, not peak-list indices. |
| `/denovoout <path.csv>` | Where to write the solutions CSV. |
| `/outputProgress` | Emit progress lines to the log — worth having on a multi-hour run. |
| `/e <path.txt>` | Error/status file. Written even on success (often empty). |
| `/logfile <path>` / `/loglevel <0-4>` | Log destination and verbosity; `3` is a useful default. |
| `<project.rov>` | The project, given last as a positional argument. |

```powershell
& "$env:PROGRAMFILES\Matrix Science\Mascot Distiller\MascotDistiller.exe" `
    /batch /denovo 0 /denovoout out.csv /outputProgress `
    /e status.txt /logfile denovo.log /loglevel 3 project.rov
```

Exit code `0` means the run completed. **`3221225477` (0xC0000005) is an access
violation** — the engine crashed; see [failure modes](#failure-modes).

---

## The working sequence: seed → patch → run

`rover_data` **does not exist in a freshly created project.** Distiller writes
it the first time it does de novo work. So a first-run patch has nothing to
patch. The sequence that works:

```
1. SEED   /denovo 1 over a short scan window   → makes Distiller create rover_data
2. PATCH  rewrite <denovotagTab> in rover_data → sets the real parameters
          + delete cached rover_data+N members → forces recomputation
3. RUN    /denovo 0 over the whole project     → the run you actually wanted
```

**Seed over a window of scans, not one.** If the single seeded spectrum yields
no de novo solution, the run still exits `0`, `rover_data` is never created, and
the patch step fails with `rover_data not present`. 25 leading scans costs
seconds and makes that outcome very unlikely.

A ready-to-run implementation of all three steps ships with this skill:
`templates/denovo-cli/` (`run_denovo.py` drives it, `patch_rov_denovo.py` does
the patching and can also be used standalone).

---

## Parameters: the `<denovotagTab>` block

Same element in the live preferences (`%APPDATA%\Matrix Science\Mascot
Distiller\Distiller.rst`) and inside the project's `rover_data`:

```xml
<denovotagTab MissOnePeak="0" DenovoSolutions="10" ShowComplement="0"
              EnzymeType="1" ErrorTag="0" UseJCode="0" UseOCode="0" UseUCode="0"
              MaxModResiduesPerSolution="1" DenovoSigThreshold="0.05">
  <SearchOptions PepUnit="ppm" PepTol="AAAAAAAAJEA="
                 FragUnit="Da"  FragTol="exSuR+F6lD8="
                 Instrument="ESI-TRAP" Enzyme="Trypsin/P" Missed="2"
                 ErrorTolerant="0" PepIsotopeError="0" Decoy="0"
                 Database="" Quantitation="None">
    <Modifications ICAT="0">
      <Mod Name="Carbamidomethyl (C)" type="fix" />
      <Mod Name="Oxidation (M)" type="var" />
    </Modifications>
  </SearchOptions>
</denovotagTab>
```

### Numeric fields are base64 little-endian IEEE-754 doubles

`PepTol`, `FragTol` and friends are **not** decimal text:

```python
import base64, struct

def encode_double(v):  # 0.02 -> 'exSuR+F6lD8='
    return base64.b64encode(struct.pack("<d", float(v))).decode()

def decode_double(b64):
    return struct.unpack("<d", base64.b64decode(b64))[0]
```

Always **decode and print the old value** before overwriting — it's the only
cheap check that you patched the attribute you meant to.

### Attributes worth setting

| Attribute | Notes |
|---|---|
| `FragTol` + `FragUnit` | The one that matters most. See [below](#choosing-parameters-for-the-instrument). |
| `PepTol` + `PepUnit` | Precursor tolerance; `ppm` for Orbitrap-class instruments. |
| `Instrument` | Selects the ion series considered — `ESI-TRAP`, `ESI-QUAD-TOF`, etc. Must match the fragmentation. |
| `Enzyme` + `EnzymeType` | Drives the `EnzymeSpecific` output column. Not a hard constraint on the sequence. |
| `DenovoSolutions` | How many solutions per spectrum to emit (10 is the stock value). Ranked by score. |
| `DenovoSigThreshold` | Significance threshold behind the `Significant` column. `0.05` by default. |
| `MaxModResiduesPerSolution` | Caps modified residues per solution. Raising it explodes the search space. |
| `<Modifications>` | `type="fix"` / `type="var"`, names exactly as Unimod/Mascot spells them, e.g. `Phospho (ST)`. |

The `<Modifications>` element may be **empty and self-closing**
(`<Modifications ICAT="0" />`) in a stock project, so a patcher has to handle
both that and the populated form.

---

## Choosing parameters for the instrument

**The stock 0.300 Da fragment tolerance is wrong for Orbitrap MS2 by more than
an order of magnitude, and it degrades the answer visibly rather than subtly.**
Too many residue compositions fit each unexplained mass gap, so Distiller emits
sprawling alternative lists:

```
0.30 Da :  [YSP|VTF|TMD|SME|PFC|FEA|EDC|YAi|SFi|PHi|MCi]
0.02 Da :  [VA|Gi]
```

Both are *correct* — every listed composition really does fit the gap at that
tolerance. But the first is unusable and the second is nearly an answer. Set the
tolerance to what the data supports before judging de novo output.

Keep de novo parameters **in step with the database search** you are comparing
against. If the Mascot search ran at 10 ppm / 0.02 Da, run de novo at 10 ppm /
0.02 Da, and compare sequences at those same tolerances.

### Modifications: fewer is better

Counter-intuitively, **adding variable modifications makes de novo worse**.
Measured on a Q Exactive dataset, adding carbamylation and deamidation to the
stock Carbamidomethyl/Oxidation set *reduced* the number of spectra sequenced
correctly. A database search prunes the mod search space with the sequence; de
novo has no such constraint, so each extra variable mod multiplies the
candidates competing for the same peaks.

Add a variable mod when the chemistry demands it — a phosphoproteomics dataset
needs `Phospho (ST)` and `Phospho (Y)` or de novo cannot place the modification
at all — and not as a hedge.

---

## Output CSV format

A header block, then the solution table. Header lines are `Key,"Value"` pairs;
solution rows begin with a **numeric** `PeakListIndex`, which is the reliable
way to tell them apart:

```
Mascot Distiller Version,"2.9.241.58"
Instrument Type,"ESI-TRAP"
Enzyme,"Trypsin/P"
Peptide Mass Tolerance,10.000
Peptide Mass Tolerance Units,"ppm"
Fragment Mass Tolerance,0.020
Fragment Mass Tolerance Units,"Da"
Fixed Modifications,"Carbamidomethyl (C)"
Variable Modifications,"Oxidation (M)"
Significance Threshold,"0.05"

Fixed Modifications,"---------------------------------"
Identifier,Name,Delta,Neutral loss(es)
1,"Carbamidomethyl (C)",57.0215,0

Variable Modifications,"---------------------------------"
Identifier,Name,Delta,Neutral loss(es)
1,"Oxidation (M)",15.9949,0,63.9983

Denovo Solutions,"---------------------------------"
PeakListIndex,PeakListTitle,Charge,ObsMOverZ,Score,Expect,Significant,EnzymeSpecific,Sequence,FullSequence
4,"4: Scan 41 (rt=6.36839)",3,522.256,81,"1.42907592709245E-05","yes","yes","KiAEKDEEMEQAK","KiAEKDEEM(Oxidation)EQAK"
4,"4: Scan 41 (rt=6.36839)",3,522.256,63,"0.000901685952018825","yes","yes","Ki[YT]QDEE[TQ][RPG]","Ki[YT]QDEE[TQ][RPG]"
```

| Column | Notes |
|---|---|
| `PeakListIndex` | 1-based index into the project's peak lists. Repeats — one row per solution. |
| `PeakListTitle` | `"<index>: Scan <n> (rt=<min>)"`. **This is where the raw scan number is**, and the join key to an MGF or a Mascot search. |
| `Charge`, `ObsMOverZ` | Precursor as Distiller assigned it. |
| `Score` | De novo score, higher is better. Read the [caveat](#what-the-score-does-and-does-not-tell-you). |
| `Expect` | Expectation value for the score. |
| `Significant` | `yes`/`no` against `DenovoSigThreshold`. |
| `EnzymeSpecific` | `yes`/`no` against the configured enzyme. |
| `Sequence` | **Lossy.** Collapses unexplained mass gaps to `-`. |
| `FullSequence` | **Use this one.** Keeps the candidate compositions for each gap. |

Rows for a spectrum arrive best-score-first, but sort defensively if you depend
on it.

```python
import csv

def parse_denovo(path):
    """Every solution per spectrum, keyed by peak-list index."""
    out = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.reader(fh):
            if len(row) < 10 or not row[0].strip().isdigit():
                continue                      # header block or blank line
            out.setdefault(int(row[0]), []).append({
                "title":      row[1],
                "charge":     int(row[2]),
                "score":      float(row[4]),
                "expect":     float(row[5]),
                "significant": row[6].strip().lower() == "yes",
                "sequence":   row[9].strip(),  # FullSequence, not row[8]
            })
    for k in out:
        out[k].sort(key=lambda s: s["score"], reverse=True)
    return out
```

---

## Sequence notation

Distiller states its uncertainty rather than hiding it. Anything consuming these
sequences has to handle four constructs.

| Construct | Meaning | Example |
|---|---|---|
| `i` (lowercase) | **Ile or Leu.** Isobaric (113.084 either way), so no evidence can separate them. | `KiAEK` |
| `q` (lowercase) | **Lys or Gln.** 128.095 vs 128.059 — a *real* mass difference, unresolved at the working tolerance. Not the same kind of ambiguity as `i`. | `qVDER` |
| `[ABC]` | A run of residues whose **composition is known but whose order is not**. | `[HG]GYKPTDK` |
| `[AB\|CD\|EF]` | **Alternative compositions** for one mass gap, `\|`-separated. Combines with the above — each alternative is itself unordered. | `K[VA\|Gi]PTDK` |
| `(Name)` | A modification on the preceding residue, by Mascot/Unimod name. | `...DEEM(Oxidation)EQAK` |
| `-` | An unexplained gap — **only in the `Sequence` column**. `FullSequence` has the compositions. | `K-PTDK` |

Converting to a plain string for comparison:

```python
import re

def from_distiller(seq):
    seq = re.sub(r"\(([^)]+)\)", "", seq)   # drop mod names (or map to deltas)
    seq = seq.replace("i", "L")             # Ile/Leu are indistinguishable
    seq = seq.replace("q", "[K|Q]")         # keep as an alternative — it is one
    return seq                              # [..] / | still need expanding
```

**Do not silently pick the first option.** How much of Distiller's output is
fully determined is a real property of the tool, and flattening it overstates
the tool considerably. On one 2.4M-spectrum benchmark only **27.8%** of
Distiller's correct answers named a single sequence outright. Whatever a report
does with ambiguity — expand, take the first, or drop — say so in the output.

An unbounded expansion is also a trap: a solution with several multi-residue
alternative groups can expand to thousands of concrete sequences, and matching
any-of-thousands against a database will match something by chance. Cap the
block size (3 residues is a workable ceiling) or count expansions and refuse
above a threshold.

---

## What the score does and does not tell you

The de novo `Score` column ranks solutions **within one spectrum** — the ordering
is meaningful and the top solution is the one to report.

**It does not rank spectra against each other for correctness.** Measured over
2.4M spectra against a Mascot baseline, the wrong-answer rate by score quintile
ran 50.0 / 48.6 / 49.1 / 50.0 / 54.5% — flat, and marginally *inverted*. A
machine-learning de novo engine on the same spectra ran 96.9% → 12.3% across its
own score range. The same measurement expressed as an AUC for "does this peptide
map to the proteome at all": Distiller 0.753, Casanovo 0.974.

Practical consequences for a report:

- **Do not build a score cutoff** to separate good from bad Distiller de novo
  results across a dataset. It will not separate them. Use the `Significant`
  column (which is a per-spectrum expectation test) or an external criterion.
- **Do not draw a precision–coverage curve ranked by this score** and read it as
  a quality curve — it comes out near-horizontal by construction.
- **Do not compare scores across engines.** Mascot and Distiller share an ions
  score scale; other de novo tools have their own. Ranking within a tool is
  fine; a shared axis is not.
- The thing Distiller's de novo output *does* offer over an ML engine is the
  explicit ambiguity above: you know which residues are determined. Consensus
  with an orthogonal tool is a far better filter than the score — on that
  benchmark, agreement between Distiller and Casanovo was 98.1% precise.

---

## Failure modes

### 1. Stale cached results, reported as fresh (worst one)

Once a project has de novo results, Distiller caches them in ZIP members named
`rover_data+N`, referenced from the project XML by `<DenovoResult Segment="N"/>`.
A later `/denovo` run **re-exports the cache instead of recomputing** — and the
exported header reflects your *new* parameters. Exit code 0, plausible file, right
header, wrong solutions.

Purge them as part of the patch:

```python
segments = re.findall(r'<DenovoResult\s+Segment="(\d+)"\s*/?>', rover_xml)
rover_xml = re.sub(r'<DenovoResult\s+Segment="\d+"\s*/>', "", rover_xml)
for seg in segments:
    blobs.pop(f"rover_data+{seg}", None)   # drop the cached member too
```

### 2. `rover_data not present`

Either the project has never had de novo run on it (seed it — see
[the working sequence](#the-working-sequence-seed--patch--run)), or the seeding
run produced no solutions at all, or the `.rov` is incomplete.

### 3. Incomplete `.rov` that still opens

A project left half-written by a hard kill is a **valid ZIP of roughly the right
size** and passes every size check, but can be missing `mdro_proc_opts`.
Distiller then does no de novo work at all: exit 0, no `rover_data`, and the
patch fails. Check the member list — it costs milliseconds:

```python
def rov_is_complete(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (OSError, zipfile.BadZipFile):
        return False
    return {"mdro_pkl", "mdro_proc_opts"} <= names
    # rover_data deliberately NOT required — a fresh project has none yet
```

More generally: **a stage's output file existing is not evidence the stage
finished.** A process killed mid-write leaves a megabyte-scale truncated file
that sails past any size floor. Record exit codes and trust only `0`.

### 4. Access violation at tight fragment tolerances

The de novo engine can crash with `0xC0000005` (exit `3221225477`) at tight
fragment tolerances on some data. Measured on a Fusion Lumos phosphoproteomics
file: **0.02 and 0.03 Da crashed within ~70 s; 0.04, 0.05, 0.1 and 0.3 all
completed.** The same 0.02 Da setting is fine on Q Exactive data, so it is
data-dependent, not a flat limit.

Don't give up the tight tolerance everywhere. Ask for it, back off through a
ladder on crash, and **record which tolerance actually produced the output** —
re-patching from a pristine copy of the `.rov` each attempt so a crashed run
can't leave partial state behind.

### 5. Distiller holds the project open

While a de novo run is in flight the `.rov` is locked. Anything else that needs
the same project — a Mascot submission via `/submitSearch`, a report — has to
wait or use a different route. See [COMMAND_LINE.md](COMMAND_LINE.md).

---

## Throughput

De novo is the slow stage, and it is **I/O bound rather than CPU bound**:
measured at ~22% of 32 threads, and running three instances concurrently gave
only a **1.22× throughput gain**. Don't size a batch around de novo parallelism;
overlap it with other stages instead.

Reference timings for one ~24k-spectrum Q Exactive file (Ryzen 9 5950X):

| Stage | Time |
|---|---|
| Distiller peak picking | ~2 min |
| Mascot search | ~2 min |
| **Distiller de novo** | **~77 min** |

Because Distiller is CPU-bound work on the host, it can be overlapped with
GPU-bound tools (an ML de novo engine, say) at essentially no cost.
