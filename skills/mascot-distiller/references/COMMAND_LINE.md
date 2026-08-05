# Driving Distiller unattended

Notes on running `MascotDistiller.exe` from a script rather than the GUI, and on
building a batch around it that survives being killed.

This is **not** a complete switch reference — it is the set verified in anger on
Distiller 2.9.241.58, plus the behaviours that cost time to discover. Run
`MascotDistiller.exe /?` for the full list your build supports.

## Contents

1. [Invocation](#invocation)
2. [Verified switches](#verified-switches)
3. [Exit codes](#exit-codes)
4. [Getting a Mascot search out of a project](#getting-a-mascot-search-out-of-a-project)
5. [Peak lists for third-party tools](#peak-lists-for-third-party-tools)
6. [Project integrity and resumable batches](#project-integrity-and-resumable-batches)
7. [Scheduling and resource contention](#scheduling-and-resource-contention)

---

## Invocation

```python
subprocess.run([str(DISTILLER_EXE), *args],
               cwd=str(DISTILLER_DIR),          # <- matters
               capture_output=True, text=True)
```

Set the working directory to `<DISTILLER_INSTALL>`. Distiller resolves sibling
DLLs and configuration relative to its own directory, and running it from
elsewhere is an avoidable source of odd failures.

The project path goes **last**, as a positional argument, after all switches.

---

## Verified switches

| Switch | Meaning |
|---|---|
| `/batch` | No GUI. Required for unattended runs. |
| `/denovo <0\|1>` | De novo over the whole project (`0`) or a scan range (`1`). See [DE_NOVO.md](DE_NOVO.md). |
| `/denovo_start_scan <n>`, `/denovo_end_scan <n>` | Range bounds for `/denovo 1`. Raw scan numbers, not peak-list indices. |
| `/denovoout <path.csv>` | De novo output CSV. |
| `/outputProgress` | Progress lines in the log. Worth it on anything multi-hour. |
| `/e <path.txt>` | Status/error file. Written even on success, often empty — an empty file is not evidence of failure, and a non-empty one is worth printing. |
| `/logfile <path>` | Log destination. |
| `/loglevel <0-4>` | Verbosity; `3` is a good default. Turning logging up is also how you see the **properties CSV** a custom report receives (see SKILL.md, *Creating a New Report*). |
| `/s <preferences.rst>` | Documented, but **ignored for de novo parameters** — a deliberately malformed file still produces normal output. Don't rely on it. |
| `/submitSearch` | Submit a Mascot search from the project. Requires the **Daemon Toolbox licence** — see [below](#getting-a-mascot-search-out-of-a-project). |

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Completed. **Still check the output file exists** — some failures exit 0. |
| `3221225477` | `0xC0000005`, access violation — the engine crashed. Common at tight de novo fragment tolerances on some data; back off and retry. |

An exit code of 0 with **no output file**, or with output but no `rover_data`
created, means Distiller decided there was nothing to do. That is usually a
malformed or incomplete project rather than a bug.

---

## Getting a Mascot search out of a project

Two routes, and the choice is not obvious.

### `/submitSearch` — Distiller submits

Uses the project's own `<mascotSearchTab>` settings and imports the results back
into the project, which is what you want if downstream work is quantitation.

Two constraints:

- It needs the **Daemon Toolbox licence**, which is separate from base Distiller.
- It **holds the `.rov` open**. Anything else touching the same project — a de
  novo run in particular — contends for it.

### Submitting the peak list over HTTP — you submit

Export the peak list once and POST it to `nph-mascot.exe` yourself. This gives an
identical search when the parameters match, needs no extra licence, and does not
touch the project, so it can run **concurrently** with a de novo run on the same
`.rov`.

```python
params = {
    "SEARCH": "MIS", "COM": title, "USERNAME": user, "USEREMAIL": email,
    "DB": "SwissProt", "TAXONOMY": ". . Homo sapiens (human)",
    "CLE": "Trypsin/P", "PFA": "2",
    "MODS":    ",".join(fixed_mods),      # comma-separated, fixed
    "IT_MODS": ",".join(variable_mods),   # comma-separated, variable
    "TOL": "10",   "TOLU": "ppm",         # precursor
    "ITOL": "0.02", "ITOLU": "Da",        # fragment
    "CHARGE": "2+, 3+ and 4+", "INSTRUMENT": "ESI-TRAP",
    "FORMAT": "Mascot generic", "REPORT": "AUTO",
    "DECOY": "1", "PEP_ISOTOPE_ERROR": "0", "MASS": "Monoisotopic",
    "INTERMEDIATE": "", "PRECURSOR": "", "FORMVER": "1.01",
}
with open(mgf, "rb") as fh:
    resp = requests.post(f"{server}/nph-mascot.exe?1", data=params,
                         files={"FILE": (mgf.name, fh,
                                         "application/octet-stream")})
```

Add `ERRORTOLERANT: "1"` for an automatic error-tolerant second pass, optionally
narrowed with `ET_CLASSIFICATIONS` (repeat the field; an empty value means the
whole ~2000-entry Unimod list, which is slow).

**Recovering the result file.** Success returns a page whose useful content is a
JavaScript redirect:

```
location.replace("../cgi/master_results_2.pl?file=../data/20260730/F002365.msr")
```

Modern Mascot writes `.msr` (compressed); older versions write `.dat`. To read
the result locally with msparser, fetch it through `export_dat_2.pl` with
`export_format=MascotDAT` — and **name the local copy `.dat`**. The endpoint
returns DAT content regardless of the server-side extension, and saving it as
`.msr` yields a file whose contents don't match its name, which
`ms_mascotresfile_dat` will refuse to open.

---

## Peak lists for third-party tools

If the MGF is going anywhere other than Mascot, two Distiller defaults will
break it:

1. **`ProcessingOptionsHeader`** prefixes the file with a `#`-commented dump of
   the processing options. Mascot ignores it; parsers that sniff the format by
   requiring the first line to be `BEGIN IONS` (depthcharge, and hence Casanovo)
   reject the whole file as an unknown format. Set it `False`.
2. Even with the header suppressed, Distiller emits a **leading blank line** —
   enough on its own to fail that same sniff test. Strip leading whitespace from
   the exported file.

Also set `AddMGFScansParameter = True` so each peak list carries a `SCANS=` line.
Without it the only link back to the raw scan is the title string, and the join
between tools becomes guesswork.

Peak-list export is MDRO SDK territory — see the companion **`mascot-mdro`**
skill for `PeakListFormatOptions`, `ExportPeakLists`, and building a manifest
that maps MGF position ↔ raw scan number.

---

## Project integrity and resumable batches

Two rules, both learned by having a batch quietly score garbage.

**1. A file existing is not evidence a stage finished.** A process killed
mid-write leaves a megabyte-scale truncated file that passes any size floor and
is then read as a whole result. The exit code is the only reliable signal:
persist it per stage, and on resume delete any output whose tool is not recorded
as having returned `0`.

**2. A `.rov` can be a valid ZIP and still be unusable.** Check the member list
rather than the size:

```python
def rov_is_complete(path):
    """True if the project has what de novo needs."""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (OSError, zipfile.BadZipFile):
        return False
    return {"mdro_pkl", "mdro_proc_opts"} <= names
```

A project missing `mdro_proc_opts` opens cleanly, is close to full size, and
causes Distiller to do **no de novo work at all** — exit 0, no `rover_data`, and
a confusing `rover_data not present` two steps later.

`rover_data` is deliberately not in that set: a freshly created project has none
yet, and the de novo seeding run exists to produce it.

For the full stream layout see [ROV_FILE_FORMAT.md](ROV_FILE_FORMAT.md).

---

## Scheduling and resource contention

- **De novo is I/O bound, not CPU bound** — ~22% of 32 threads, and three
  concurrent instances gave only a 1.22× throughput gain. Keep the file-level
  worker count low and win by overlapping *different* stages instead.
- **Distiller is CPU work**, so it overlaps with GPU-bound tools at essentially
  no cost. Serialise GPU consumers against each other with a lock; let Distiller
  run alongside them.
- **Rewrite batch state after every stage**, not at the end. A batch that
  persists progress per stage can be killed and restarted at any point.
- **Windows scheduled tasks**: `/rl highest` requires elevation to register, and
  `schtasks /create` without `/np` or stored credentials will block on a password
  prompt — which looks like a hang in a captured-output subprocess. Verify the
  task exists with `schtasks /query` afterwards rather than trusting the exit
  code alone.
