# Driving Distiller from the command line

Running `MascotDistiller.exe` from a script rather than the GUI: the version
gate, the full switch reference, the behaviours that cost time to discover, and
how to build a batch around it that survives being killed.

Two kinds of material live here, and the difference matters:

- **Verified** — switches and behaviours exercised on Distiller 2.9.241–2.9.242
  (marked as such).
- **Documented** — the full 2.9.240+ switch list from the Distiller help. Most
  of it is reliable, but at least one documented behaviour (`-rawFile` creating
  a project) does not work; see [Creating a `.rov` headlessly](#creating-a-rov-headlessly).

> Switch syntax follows DOS / MFC conventions: `-switch` and `/switch` are
> interchangeable. Run `MascotDistiller.exe /?` for what your build accepts.

## Contents

1. [Check the version first](#check-the-version-first)
2. [Licensing](#licensing)
3. [Invocation](#invocation)
4. [Verified switches (2.9.241–2.9.242)](#verified-switches-2924129242)
5. [Full switch reference (2.9.240+)](#full-switch-reference-29240)
6. [Exit codes](#exit-codes)
7. [Getting a Mascot search out of a project](#getting-a-mascot-search-out-of-a-project)
8. [Creating a `.rov` headlessly](#creating-a-rov-headlessly)
9. [Peak lists for third-party tools](#peak-lists-for-third-party-tools)
10. [Project integrity and resumable batches](#project-integrity-and-resumable-batches)
11. [Scheduling and resource contention](#scheduling-and-resource-contention)
12. [DIA precursor peak-picking overrides](#dia-precursor-peak-picking-overrides)
13. [Where this fits](#where-this-fits)

---

## Check the version first

The full set of command-line processing options is only available on
**Distiller 2.9.240 or above** (the 3.0 line). Older builds accept a much
smaller subset, so a tool-chain that shells out to `MascotDistiller.exe` must
check the version first and fall back to the GUI / MDXE path when the build is
too old.

**Always gate on the version.** Do not emit or run the command-line
processing options below unless the installed Distiller is `>= 2.9.240`.

### Preferred: read the executable's file version (does not launch Distiller)

```powershell
# <DISTILLER_INSTALL> resolved during first-time setup (see SETUP.md)
$exe = Join-Path $DistillerInstall 'MascotDistiller.exe'
$raw = (Get-Item $exe).VersionInfo.ProductVersion   # e.g. "2.9.240.0"

# Keep only the leading numeric dotted portion, then compare as a Version
$clean = ($raw -replace '[^0-9.].*$', '').Trim('.')
$cmdLineOptionsAvailable = [version]$clean -ge [version]'2.9.240'

if ($cmdLineOptionsAvailable) {
    "Distiller $clean — command-line processing options available"
} else {
    "Distiller $clean — too old; use the GUI or MDXE.pl (see BATCH_TESTING.md)"
}
```

This is the robust check: it reads the PE version resource off disk, so it
never starts the application and never blocks.

### Alternative: `-version` switch (note the console gotcha)

```powershell
& $exe -version > version.txt   # MUST redirect
$raw = (Get-Content version.txt -Raw).Trim()        # e.g. "2.3.000.0"
```

`MascotDistiller.exe -version` writes to **STDOUT but does not display in
the console** — you have to redirect to a file (`> version.txt`) and read it
back. Because this actually launches the executable, prefer the file-version
method above unless you specifically need the app's self-reported string.

### Version comparison notes

- `.NET [version]` treats `2.9.240` as `2.9.240` (revision unset) and
  `2.9.240.0` as revision `0`, so `[version]'2.9.240.0' -ge [version]'2.9.240'`
  is `$true`. Both `2.9.240` and any `3.x` satisfy the gate; `2.9.239.x` and
  earlier `2.9`/`2.8` builds do not.
- If `ProductVersion` ever comes back non-numeric or empty, treat the gate as
  **not satisfied** (fail closed) rather than assuming availability.

---

## Licensing

The single most relevant option for report development is **`-quantreport`**:
it runs a custom Python report (the kind this skill builds) against a project
in batch mode and writes the HTML/CSV output — the headless equivalent of
running the report through the wizard. That makes it a lightweight
alternative to `MDXE.pl` for a smoke test (see
[BATCH_TESTING.md](BATCH_TESTING.md)), and it is only dependable on 2.9.240+.

**No Distiller SDK licence required.** Unlike MDRO (the COM SDK the
`mascot-mdro` skill drives, which is a separately-licensed paid product),
these command-line options are part of the base Distiller executable. That is
why they belong in *this* skill: any Distiller 2.9.240+ user can run them,
whereas MDRO-based features only run for the SDK-licensed subset. Individual
switches do still need the relevant **licence toolboxes** on top of base
Distiller:

| Capability | Requires |
|------------|----------|
| Batch quantitation, running reports (`-quantreport`) | Quantitation Toolbox |
| Peak picking (`-runPeakPicking`), search submission (`-submitSearch`) | Daemon Toolbox |
| Mascot / de novo searches from the CLI | Daemon + Search Toolboxes |

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

**Return immediately ≠ finished.** After you press Enter you are handed
straight back to the prompt; Distiller keeps processing in the background.
Determine completion by checking the return code, tailing a log file, or
attaching a console (`-showConsole`).

---

## Verified switches (2.9.241–2.9.242)

| Switch | Meaning |
|---|---|
| `/batch` | No GUI. Required for unattended runs. |
| `/denovo <0\|1\|2>` | De novo over the whole project (`0`), a scan range (`1`), or (documented) only peak lists unassigned in the loaded Mascot result (`2`). See [DE_NOVO.md](DE_NOVO.md). |
| `/denovo_start_scan <n>`, `/denovo_end_scan <n>` | Range bounds for `/denovo 1`. Raw scan numbers, not peak-list indices. |
| `/denovoout <path.csv>` | De novo output CSV. |
| `/outputProgress` | Progress lines in the log. Worth it on anything multi-hour. |
| `/e <path.txt>` | Status/error file. Documented as "last error if the return code is non-zero; ignored if the file already exists" (so delete it before each run). Observed: written even on success, often empty — an empty file is not evidence of failure, and a non-empty one is worth printing. |
| `/logfile <path>` | Log destination. |
| `/loglevel <mask>` | **Bitmask**, not a 0–4 scale: sum of `1` Error, `2` Warning, `4` Information, `8`/`16`/`32` Debug 1–3. Verified 2.9.242: `4` logs Information *without* errors, `7` logs both. Use `7` for unattended runs, `3` (Error + Warning) for quiet ones. Turning logging up is also how you see the **properties CSV** a custom report receives (see SKILL.md, *Creating a New Report*). |
| `/s <preferences.rst>` | Documented, but **ignored for de novo parameters** — a deliberately malformed file still produces normal output. Don't rely on it. |
| `/submitSearch` | Submit a Mascot search from the project. Requires the **Daemon Toolbox licence** — see [below](#getting-a-mascot-search-out-of-a-project). |

---

## Full switch reference (2.9.240+)

From the Distiller help. General form — process a project file according to
the switches that follow (the project path may also go last, as in the
verified examples):

```
MascotDistiller.exe <project.rov> [switches...]
```

### Informational

| Switch | Effect |
|--------|--------|
| `-version` | Write executable version to STDOUT (redirect to a file to capture — see above) |
| `-?`, `-help` | Brief help |
| `-features` | Comma-separated list of enabled licence features, e.g. `2.1.0,2.1.1,...` |
| `-getReportList <protocol>` | Comma-separated list of report files for `<protocol>` (empty = all) |

### Batch run / quantitation

| Switch | Effect |
|--------|--------|
| `-batch` | Run with no GUI: load search by `task_id`, quantitate the hit range, save the project. Omit to just open the project on the desktop. |
| `-task_id <id>` | Load results for the given Mascot Server task ID (not needed if re-using the search saved in the project). |
| `-quantitate <range>` | Range of protein hits to quantify; empty = all hits. |
| `-quantout <file>` | Destination for quantitation output (XML if no `-quantreport`). |
| `-quantreport <report>` | Save an HTML report using the named Python report (a filename in the reports dir, or a fully-qualified path). **Runs a report of the kind this skill builds.** |
| `-completeReport <0\|1>` | With `-quantout` and no `-quantreport`: `0` = abbreviated XML, `1` = complete (default `1`). |
| `-exportTimeAlignment <0\|1>` | With `-quantout`, no `-quantreport`, `-completeReport 1`: include Replicate time-alignment data in the XML (default `0` = exclude; inclusion can bloat the file). |

### De novo

| Switch | Effect |
|--------|--------|
| `-denovo <option>` | `0` = all peaklists; `1 <range>` = specified range only; `2` = unassigned peaklists from the loaded Mascot result. |
| `-denovoout <path>` | Export de novo results to `<path>` as CSV. |

### Creating a project from a raw file

| Switch | Effect |
|--------|--------|
| `-rawFile <path>` | Create a new `<project.rov>` for this raw file, overwriting any existing project. |
| `-rawFileType <type>` | File type of `-rawFile`. See the type table below. |
| `-rstExperimentType <type>` | `0` = DDA (default), `1` = DIA. Used with `-rawFile`. |
| `-multifileDirectory <path>` | If `<project.rov>` doesn't exist, build a memory-efficient multifile master project from this directory (designed for a Mascot Daemon task cache dir), attempting a merged search result from the first sub-project's settings. |

`-rawFileType` values: `0` Text · `1` Sciex Analyst (.wiff) · `2` Waters
MassLynx (.raw) · `3` Sciex Data Explorer · `4` Thermo Xcalibur (.raw) ·
`5` Bruker XMASS/XTOF · `6` Bruker Data/Flex Analysis (yep) · `7` Kratos
Axima · `8` Shimadzu LCMS-IT-TOF · `9` Agilent LC/MSD Trap · `10` mzXML ·
`12` Bruker Data/Flex Analysis (baf) · `13` Agilent QTOF · `14` mzML ·
`15` Waters MassLynx MS^E · `16` Bruker timsTOF.

### Peak picking & search submission (Daemon Toolbox)

| Switch | Effect |
|--------|--------|
| `-runPeakPicking <range>` | Peak-pick the given scan range (blank = all scans). |
| `-submitSearch <.par path>` | Submit a search using the given Daemon `.par` options (optional — falls back to project defaults). |
| `-searchType <type>` | Type for `-submitSearch` when no `.opt` path was given: `1` PMF · `2` SEQ · `3` MSMS (default). |

### Logging, auth & process control

`-loglevel` is a bitmask — see the verified table above.

| Switch | Effect |
|--------|--------|
| `-logfile <path>` | Write a log file. |
| `-loglevel <level>` | Sum of: `1` Error · `2` Warning · `4` Information · `8` Debug1 · `16` Debug2 · `32` Debug3 (e.g. `7` = first three). |
| `-s <preferences.rst>` | Path to a Distiller preferences file. |
| `-e <error file>` | Write the last error to this file if the return code is non-zero (`-loglevel` must include Error; ignored if the file already exists). |
| `-username` / `-password` | Mascot security credentials. |
| `-webServerUsername` / `-webServerPassword` | Web-server auth credentials. |
| `-showConsole <0\|1\|2>` | Attach a console in batch mode: `0` none (default) · `1` attach, auto-close · `2` attach, wait for keypress. |
| `-outputProgress <0\|1>` | `1` = write progress to STDOUT (default `0`). |
| `-setProcessorAffinity <list>` | Sticky zero-based CPU list (e.g. `0,1,2,3`); call with no value to clear. |
| `-daemonMGFIonMobilityParam <0\|1>` | Default for including ion-mobility values in the Daemon-exported MGF (`0` exclude, `1` include). **Must run from an elevated prompt as an administrator.** |

### Example

```
MascotDistiller.exe C:\mdro_test\sample.rov -batch -quantitate -e error.txt -loglevel 1
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Completed. **Still check the output file exists** — some failures exit 0. |
| `3` | Fatal error before processing — e.g. the project path doesn't exist (verified 2.9.242: `Unable to open MDRO project file`). |
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

## Creating a `.rov` headlessly

What actually works — verified 2026-08-05 on Distiller 2.9.242.9.

> **`-rawFile` does not create a project.** The documentation says it will, but
> `MascotDistiller.exe` **opens `<project.rov>` before processing any other switch**, so a
> non-existent project fails with `Unable to open MDRO project file (The system cannot find
> the file specified)` and `-rawFile` / `-runPeakPicking` never run. Verified across six
> invocations including the two-step create-then-pick form.

Build the project over COM instead, then peak pick from the command line.

### 1. Create the project (COM)

```python
import win32com.client as w
dsc  = w.Dispatch('MDRO.DataSourceCollection')
spec = w.Dispatch('MDRO.DataSourceSpec')
spec.Format = 4          # Thermo Xcalibur; 14 = mzML, 16 = Bruker timsTOF
spec.Path   = RAW
spec.Sample = 1
dsc.Open2(spec)          # MUST be opened - an empty collection is rejected

pm   = w.Dispatch('MDRO.MDROProjectManager')
proj = pm.Create(rov_path, 0, dsc)   # (BSTR sPath, long lFlags, IDataSourceCollection*, [VARIANT viMon])
proj.Save(); proj.Close()
```

Signature confirmed in `SDK/inc/mdro_api_i.h`. Argument 3 rejects `None`,
`DataSourceSpec`, `DataSourceSpecCollection` and `CompositeMonitor` with *Type mismatch* —
it must be an **opened** `DataSourceCollection`. Writes a ~950-byte project.

### 2. Add the processing-options stream (ZIP surgery)

A COM-created `.rov` holds only `mdro_project_<UUID>` and an empty `___zip_storage_*`.
Peak picking then dies with `Stream does not exist`. Add `mdro_proc_opts` (a `.opt` file's
XML verbatim — see [ROV_FILE_FORMAT.md](ROV_FILE_FORMAT.md)) **and register it** in the
project XML, replacing `<projectStreams count="0"/>` with:

```xml
<projectStreams count="1">
    <projectStream id="0">
        <streamType>0</streamType>
        <segmentNum>0</segmentNum>
        <name>mdro_proc_opts</name>
    </projectStream>
</projectStreams>
```

Injecting the stream **without** registering it still fails — the registry is what the
application reads. Stream types, from a Distiller-made `.rov`: `0` = `mdro_proc_opts`,
`1` = `mdro_pkl`, `2` = `mdro_search_status(+N)`, `4` = `rover_data(+N)`.

### 3. Peak pick

```
MascotDistiller.exe caco.rov -batch -runPeakPicking -logfile pp.log -loglevel 7
```

Returns `rc=0`; the project grows from ~2 KB to tens of MB. `Failed to get HTTP proxy` in
the log is benign.

### De novo on a COM-created project

`-denovo 0` straight after steps 1–3 failed per-peaklist with
`preparePeakListForDenovo call failed`: the de novo settings live in the
**`rover_data`** stream (`<denovotagTab>`), which a fresh project lacks. The
seed → patch → run sequence in [DE_NOVO.md](DE_NOVO.md) exists to create and fill
`rover_data` on a fresh project; it was developed on Distiller-made projects and
is **untested on a COM-created one**. If the seed run also fails there, graft
`rover_data` from a Distiller-made `.rov`, or save one project from the GUI and
reuse it as a template.

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

---

## DIA precursor peak-picking overrides

Global and sticky — these persist across runs until reset.

For DIA precursor detection there are values that are **not** part of the
normal processing options and can be reset globally from the command line.
Changing any of these requires restarting **both** Mascot Distiller and
Mascot Daemon (including the service) before they take effect.

| Switch | Effect (default) |
|--------|------------------|
| `-DIAMSMSPrecursorCountThreshold <n>` | Survey-scan precursor count in the DIA isolation window at/below which the MS/MS scan is searched for precursors (default `1`, `>= 0`). |
| `-DIAIsolationWindowTolerance <Da>` | Extend (+) or contract (−) the isolation window, in Da (default `0`). |
| `-DIAMSMSPrecursorTolPPM <ppm>` | Precursor grouping tolerance for fragment-ion-pair precursor determination (default `40`, positive). |
| `-DIAMSMSPrecursorMax <n>` | Max precursors to take from the MS/MS fragment-ion pairs (default `10`). |

---

## Where this fits

- For a **report smoke test** on 2.9.240+, `-quantreport` is the quickest
  headless run. For richer regression testing (config-driven, output diffing)
  use `MDXE.pl` — see [BATCH_TESTING.md](BATCH_TESTING.md).
- For discovery of `<DISTILLER_INSTALL>` and `MascotDistiller.exe`, see
  [SETUP.md](SETUP.md).
- For raw-data scripting (peak lists, spectra, TICs) outside the report
  context, use the companion **`mascot-mdro`** skill.
