# Driving Distiller from the command line

Running `MascotDistiller.exe` from a script rather than the GUI: the version
gate, the full switch reference, the behaviours that cost time to discover, and
how to build a batch around it that survives being killed.

Two kinds of material live here, and the difference matters:

- **Verified** — switches and behaviours exercised on Distiller 2.9.241–2.9.242
  (marked as such).
- **Documented** — the full switch list, checked against the `-?` output of
  Distiller 2.9.242.16. Run `MascotDistiller.exe -?` for what your build accepts.

> **Use `-switch`, not `/switch`.** Distiller accepts both, but Git Bash (MSYS)
> rewrites a leading-`/` argument such as `/batch` into a Windows path, and
> Distiller then exits at once with no log. The `-` form works in every shell.
> `-help` and `-?` print help; `--help` (double dash) opens the GUI instead.

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
10. [Headless reports (`-quantreport`)](#headless-reports--quantreport)
11. [Project integrity and resumable batches](#project-integrity-and-resumable-batches)
12. [Scheduling and resource contention](#scheduling-and-resource-contention)
13. [DIA precursor peak-picking overrides](#dia-precursor-peak-picking-overrides)
14. [Where this fits](#where-this-fits)

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
This is the form the `-?` usage line gives (`/Options <rov file>`), and every
verified run used it. (The CHM help's own example puts the project first.)

**Pass absolute paths, and run one instance at a time.** Exit code
`3762504530` (`0xE0434352`, an unhandled .NET exception) within about a second
has two known causes:

- A relative `.rov`, raw-file or output path. The working directory is the
  install directory, so the path resolves *there*. Resolve every path before
  building the command.
- Another Distiller instance already running. Check with
  `tasklist | grep -i -E "MascotDistiller|DistillerGUIApplication"` before
  retrying.

**Return immediately ≠ finished.** After you press Enter you are handed
straight back to the prompt; Distiller keeps processing in the background.
Determine completion by checking the return code, tailing a log file, or
attaching a console (`-showConsole`).

**If a Distiller window opens, the switches were not received.** On 3.0 beta
builds (2.9.242.22) `MascotDistiller.exe` starts the WPF application
`DistillerGUIApplication.exe`. A window plus exit `0` within a second means it
fell back to the GUI: usually a mangled `/batch`, or the project path given
first. Stop that process if you started it, and fix the command. In a correct
`-batch` run the exit code is meaningful.

---

## Verified switches (2.9.241–2.9.242)

| Switch | Meaning |
|---|---|
| `-batch` | No GUI. Required for unattended runs. |
| `-denovo <0\|1\|2>` | De novo over the whole project (`0`), a scan range (`1`), or (documented) only peak lists unassigned in the loaded Mascot result (`2`). See [DE_NOVO.md](DE_NOVO.md). |
| `-denovo_start_scan <n>`, `-denovo_end_scan <n>` | Range bounds for `-denovo 1`. Raw scan numbers, not peak-list indices. |
| `-denovoout <path.csv>` | De novo output CSV. |
| `-outputProgress` | Progress lines in the log. Worth it on anything multi-hour. |
| `-e <path.txt>` | Status/error file. Documented as "last error if the return code is non-zero; ignored if the file already exists" (so delete it before each run). Observed: written even on success, often empty — an empty file is not evidence of failure, and a non-empty one is worth printing. |
| `-logfile <path>` | Log destination. |
| `-loglevel <mask>` | **Bitmask**, not a 0–4 scale: sum of `1` Error, `2` Warning, `4` Information, `8`/`16`/`32` Debug 1–3. Verified 2.9.242: `4` logs Information *without* errors, `7` logs both. Use `7` for unattended runs, `3` (Error + Warning) for quiet ones. Turning logging up is also how you see the **properties CSV** a custom report receives (see SKILL.md, *Creating a New Report*). |
| `-s <preferences.rst>` | Documented, but **ignored for de novo parameters** — a deliberately malformed file still produces normal output. Don't rely on it. |
| `-submitSearch <par>` | Submit a Mascot search from the project. Requires the **Daemon Toolbox licence** — see [below](#getting-a-mascot-search-out-of-a-project). |
| `-rawFile <raw> -rawFileType <n> -optFile <opt> -runPeakPicking` | Create **and** peak-pick a new project in one call (2.9.242.16 Thermo `.raw` DIA; 2.9.242.22 mzXML/mzML). Needs `-rawFileType` and the project path last. See [Creating a `.rov` headlessly](#creating-a-rov-headlessly). |
| `-multifileDirectory <dir>` | Builds a multi-file master `.rov` from a directory of sub-projects (2.9.242.16, 8-run masters). See [DAEMON_QUANTITATION.md](DAEMON_QUANTITATION.md). |
| `-quantitate -quantreport <report> -quantout <file>` | Headless report run. **Takes the report's XML wizard defaults**; see [Headless reports](#headless-reports--quantreport). |

---

## Full switch reference (2.9.240+)

Checked against the `-?` output of Distiller 2.9.242.16. General form:

```
MascotDistiller.exe [switches...] <project.rov>
```

### Informational

| Switch | Effect |
|--------|--------|
| `-version` | Write executable version to STDOUT (redirect to a file to capture — see above) |
| `-?`, `-help` | Brief help (`--help` opens the GUI instead) |
| `-features` | Comma-separated list of enabled licence features, e.g. `2.1.0,2.1.1,...` |
| `-getReportList <protocol>` | Comma-separated list of report files for `<protocol>` (empty = all). `-getXsltList` is a deprecated alias. |

### Batch run / quantitation

| Switch | Effect |
|--------|--------|
| `-batch` | Run with no GUI: load search by `task_id`, quantitate the hit range, save the project. Omit to just open the project on the desktop. |
| `-task_id <id>` | Load results for the given Mascot Server task ID (not needed if re-using the search saved in the project). |
| `-quantitate <range>` | Range of protein hits to quantify; empty = all hits. |
| `-quantout <file>` | Destination for quantitation output: the XML if there is no `-quantreport`, otherwise the report's output. |
| `-quantreport <report>` | Run the named Python report (a filename in the reports dir, or a full path). **Runs a report of the kind this skill builds.** The output format is whatever the report writes (HTML, CSV, XLSX, ...); the `-quantout` extension does not change it. |
| `-completeReport <0\|1>` | With `-quantout` and no `-quantreport`: `0` = abbreviated XML, `1` = complete (default `1`). |
| `-exportTimeAlignment <0\|1>` | With `-quantout`, no `-quantreport`, `-completeReport 1`: include Replicate time-alignment data in the XML (default `0` = exclude; inclusion can bloat the file). |

### De novo

| Switch | Effect |
|--------|--------|
| `-denovo <option>` | `0` = all peaklists; `1 <range>` = specified range only; `2` = unassigned peaklists from the loaded Mascot result. |
| `-denovoout <path>` | Export de novo results to `<path>` as CSV. |
| `-denovo_start_scan <n>` / `-denovo_end_scan <n>` | Range bounds for `-denovo 1` (raw scan numbers). |

### Creating a project from a raw file

| Switch | Effect |
|--------|--------|
| `-rawFile <path>` | Create a new `<project.rov>` for this raw file, overwriting any existing project. Works only with `-rawFileType` and the project path last; see [Creating a `.rov` headlessly](#creating-a-rov-headlessly). |
| `-rawFileType <type>` | File type of `-rawFile`. See the type table below. |
| `-rstExperimentType <type>` | `1` = DDA (default), `2` = DIA. Used with `-rawFile`. |
| `-optFile <path>` | Processing options (`.opt`) for the new project. Pass it every time: the defaults are not the GUI's. |
| `-sampleIndex <n>` | Sample index, for multi-sample raw files, when creating a new project. |

> The CHM help page gives `-rstExperimentType` as 0/1, `-searchType` as 1/2/3 and
> `-outputProgress <0|1>`. The executable's own `-?` (2.9.242.16), and a working
> DIA run with `-rstExperimentType 2`, say 1/2, 0/1/2 and no value. Trust `-?`.
| `-multifileDirectory <path>` | If `<project.rov>` doesn't exist, build a memory-efficient multifile master project from this directory (designed for a Mascot Daemon task cache dir), attempting a merged search result from the first sub-project's settings. Verified 2.9.242.16 on a Daemon cache, on a folder of CLI-made `.rov` files, and on a staging folder of hard links to `.rov`+`.mgf` pairs from two task caches. |

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
| `-searchType <type>` | Search type when `-submitSearch` has no `.par` file: `0` PMF · `1` SEQ · `2` MSMS (default). |

### Logging, auth & process control

`-loglevel` is a bitmask — see the verified table above.

| Switch | Effect |
|--------|--------|
| `-logfile <path>` | Write a log file. |
| `-loglevel <level>` | Sum of: `1` Error · `2` Warning · `4` Information · `8` Debug1 · `16` Debug2 · `32` Debug3 (e.g. `7` = first three). |
| `-s <preferences.rst>` | Path to a Distiller preferences file. |
| `-cacheFileDirectory <path>` | Override the default directory for msparser and msquantlib cache files. |
| `-e <error file>` | Full path for the batch-mode return status. Must be a new file, so delete it before each run. |
| `-username` / `-password` | Mascot security credentials. |
| `-sessionID <id>` | Mascot Server security session ID, instead of a username and password. |
| `-webServerUsername` / `-webServerPassword` | Web-server auth credentials. |
| `-showConsole <0\|1\|2>` | Attach a console in batch mode: `0` none (default) · `1` attach, auto-close · `2` attach, wait for keypress. |
| `-outputProgress` | Write progress for quantitation, de novo or report generation to STDOUT. Takes no value. |
| `-setProcessorAffinity <list>` | Sticky zero-based CPU list (e.g. `0,1,2,3`); call with no value to clear. |
| `-enableSciexTOFDIANoiseFiltering <0\|1>` | Noise filtering of SCIEX TOF DIA raw spectra (default on). **Elevated prompt as an administrator; restart Distiller after changing.** |
| `-daemonMGFIonMobilityParam <0\|1>` | Default for including ion-mobility values in the Daemon-exported MGF (`0` exclude, `1` include). **Must run from an elevated prompt as an administrator.** |

### Example

```
MascotDistiller.exe -batch -quantitate -e C:\work\error.txt -logfile C:\work\run.log -loglevel 7 C:\work\sample.rov
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Completed. **Still check the output file exists** — some failures exit 0. |
| `3` | Fatal error before processing — e.g. the project path doesn't exist and you didn't ask for one to be created (verified 2.9.242: `Unable to open MDRO project file`), or `-rawFile` couldn't read the raw file. |
| `2` | Quantitation or report refused the project; the reason is in the `-e` file. Seen: `Replicate Label-free quantitation requires 2 or more samples. Use the 'Average' method for single files`. |
| `154` | Seen when the project's raw files have moved: the `-e` file shows only a `NullReferenceException`. The real cause, `Cannot find raw file ... or Project directory`, is an `LVL_ERROR` line in the log (any `-loglevel` that includes `1`), not in the `-e` file. Put the raw files back, or point a directory junction at their new home. |
| `3221225477` | `0xC0000005`, access violation — the engine crashed. Common at tight de novo fragment tolerances on some data; back off and retry. |
| `3762504530` | `0xE0434352`, unhandled .NET exception, within about a second. A relative path, or another Distiller instance already running; see [Invocation](#invocation). |

An exit code of 0 with **no output file**, or with output but no `rover_data`
created, means Distiller decided there was nothing to do. That is usually a
malformed or incomplete project rather than a bug.

---

## Getting a Mascot search out of a project

Two routes, and the choice is not obvious.

### `-submitSearch` — Distiller submits

Uses the project's own `<mascotSearchTab>` settings and imports the results back
into the project, which is what you want if downstream work is quantitation.

Two constraints:

- It needs the **Daemon Toolbox licence**, which is separate from base Distiller.
- It **holds the `.rov` open**. Anything else touching the same project — a de
  novo run in particular — contends for it.

**Writing the `.par` file.** `-submitSearch` reads a Daemon `.par`, but it does
not parse it the way Daemon does:

- **Variable mods: use commas, not `@`.** Daemon splits
  `IT_MODS=Acetyl (Protein N-term)@Oxidation (M)` itself. `-submitSearch` sends
  it as one modification name, and Mascot rejects the search with `[M00135]`.
- **All databases on one comma-separated `DB=` line**, e.g.
  `DB=UP5640_H_sapiens,cRAP_Uniprot`. Two `DB=` lines are not an error: the
  last one wins, and the search silently runs against that database only, with
  exit code 0. Check `search__databases` in the first result before letting a
  batch continue (see [ROV_FILE_FORMAT.md](ROV_FILE_FORMAT.md)).
- The search goes to the default server in `Distiller.rst` `<MascotServers>`;
  there is no switch for it (not fully verified).

**A crashed search still exits 0.** If Mascot Server kills the job, Distiller
writes `Search Crashed` to the `-e` file and the log, and returns 0. The `.rov`
it leaves has no `<resultsFile>`. Check the `-e` file and the project's
`mdro_search_status`, not the exit code. Move the bad `.rov` aside and rerun the
file from scratch.

**An idle Distiller during a search is not hung.** While the server searches,
Distiller uses about 0% CPU, holds an open connection to the Mascot host on
port 80, and writes nothing to its log or `-e` file. Mascot Server's search log
does not list the search until it finishes, so "no new F-number" isn't evidence
of failure either. Search time grows steeply with variable mods: on one 543 MB
DIA file, 3 variable mods took 12 minutes and 5 took 67. A healthy search was
once killed at 40 minutes for looking hung.

**`-task_id` with an expired task loops.** If the Mascot task ID has aged out of
the server, Distiller retries `unknown_id` forever. Use a timeout.

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

### The command line (preferred)

One call creates the project, peak-picks it and, optionally, searches it:

```
MascotDistiller.exe -batch -rawFile <raw> -rawFileType <n> -optFile <opt>
    -runPeakPicking [-rstExperimentType 2] [-submitSearch <par>]
    -e <abs err.txt> -logfile <abs run.log> -loglevel 7 <abs new.rov>
```

(One command line; wrapped here for reading.)

Verified:

- 2.9.242.16, Thermo `.raw` (`-rawFileType 4`), DIA with
  `default.ThermoXcalibur.dia.opt`, peak-picked and searched in one call.
  Used for 12 files in one project and 17 in another with no failures.
- 2.9.242.22, mzXML (`10`) and non-indexed mzML (`14`) from Bruker MALDI LIFT
  spots, with a custom `.opt`. Used for 15 projects, one of 195 spectra.

What makes it work:

- **`-rawFileType` is required.** Without it, Distiller tries to open the
  named `.rov` instead of creating it, and fails with `Unable to open MDRO
  project file (The system cannot find the file specified)`. The value is the
  `mdroDataSourceFormat_e` number from the table above. It is also the first
  field after the `.opt` path in a Daemon task's `filter_options`.
- **The project path goes last.** Every verified run did this. Every failed
  attempt put it first, but each also lacked `-rawFileType` or `-optFile`, so
  the order alone isn't proven to be the cause. Put it last and pass both.
- **Pass `-optFile`.** Engine defaults are not the GUI defaults.
- **`-rstExperimentType 2` for DIA.** `1` (DDA) is the default.
- **Absolute paths** everywhere (see [Invocation](#invocation)).

Raw-format problems seen with `-rawFile`:

| Input | Result | Workaround |
|---|---|---|
| Bruker flex `fid` as type `5` or `6` | Exit 3: "not in the specified format", or "Object reference not set" | Convert with msconvert first |
| msconvert indexed mzML | Rejected: empty `offset` content | `msconvert --mzML --noindex` |
| msconvert mzXML 3.x | Rejected: wants mzXML schema 2.0 | Use non-indexed mzML instead |
| Merged mzML | Needs unique `sourceFile` and spectrum ids, and a `defaultDataProcessingRef` | Fix the merge, or make one project per file |
| MGF (type `0`) | Crashed in `openProjectFile` (seen once) | Use mzML |

If your build still can't create a project this way, build it over COM as below.

### Fallback: COM plus ZIP surgery

Verified 2026-08-05 on Distiller 2.9.242.9, before the command-line form above
was found to work. It needs the MDRO SDK licence.

#### 1. Create the project (COM)

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

#### 2. Add the processing-options stream (ZIP surgery)

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

#### 3. Peak pick

```
MascotDistiller.exe -batch -runPeakPicking -logfile C:\work\pp.log -loglevel 7 C:\work\caco.rov
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

There is no command-line switch to export a peak list. Two routes:

- **With the SDK licence:** the companion **`mascot-mdro`** skill covers
  `PeakListFormatOptions`, `ExportPeakLists`, and a manifest that maps MGF
  position to raw scan number.
- **Without it:** read the `mdro_pkl` stream out of the `.rov`. It is XML
  (`peakListArchive`, namespace `.../mdro_pkl_archive_2`) whose numeric arrays
  are base64 little-endian doubles. This reproduced Daemon's own MGF exactly on
  MALDI LIFT data (68 of 68 peaks); check it against a Daemon MGF on your data.

```python
import base64, struct, zipfile, xml.etree.ElementTree as ET
NS = "{http://www.matrixscience.com/xmlns/schema/mdro_pkl_archive_2}"
PROTON = 1.007276

def doubles(text):
    raw = base64.b64decode(text or "")
    return struct.unpack(f"<{len(raw) // 8}d", raw)

def rov_peaklists(rov):
    """Yield (precursor_mz, precursor_intensity, charge, [(MH+, area)])."""
    with zipfile.ZipFile(rov) as z:
        root = ET.fromstring(z.read("mdro_pkl"))
    lists = {pl.get("id"): pl for pl in root.iter(NS + "peakList")}
    for pd in root.iter(NS + "peakData"):
        prec = lists[pd.get("pklId")].find(f"{NS}precursors/{NS}precursor")
        mz = doubles(pd.findtext(NS + "mz"))
        area = doubles(pd.findtext(NS + "area"))
        z = [int(c) for c in pd.findtext(NS + "charge").split()]
        ignore = [c != "0" for c in pd.findtext(NS + "ignore", "").split()] or [False] * len(mz)
        # Distiller writes multiply charged fragments as MH+, intensity = area
        peaks = [(m * c - (c - 1) * PROTON, a)
                 for m, a, c, ig in zip(mz, area, z, ignore) if not ig]
        yield (doubles(prec.get("mz"))[0], doubles(prec.get("intensity"))[0],
               int(prec.get("charges").split()[0]), peaks)
```

Write an MGF block per peak list, skipping lists with no peaks. The
`PeakListIndex` Distiller reports skips empty spectra, so it drifts away from
the raw scan order. Join on the `Scan N` part of the title, not on position.

---

## Headless reports (`-quantreport`)

- **The wizard isn't shown, so every parameter takes its XML default** (the
  option marked `selected="true"`). Two shipped reports can have opposite
  defaults for the same choice: one past export dropped modified peptides
  because of this. To run with other values, copy the `.py` and `.py.xml` pair
  (and any helpers it imports) out of `reports` to a writable folder, change
  `selected="true"` in the copy, and pass the copy's full path to
  `-quantreport`. Never edit the shipped files in place.
- **The output format comes from the report.** A `-quantout out.csv` can
  contain XLSX, with exit code 0. Check what the report writes.
- **Replicate quantitation needs 2 or more files.** On a single-file project it
  exits `2` with "requires 2 or more samples"; use the Average method instead.
- **For a multi-file master, the quant flags that worked:**
  `-quantitate "" -quantout <file.xml> -completeReport 1 -exportTimeAlignment 1`.
  Building the master with `-multifileDirectory` rewrites the sub-project
  `.rov` files, so hard-linked copies change too.
- These XSD messages in the log are harmless: `no declaration found for
  element 'quantitation'` and `Failed to load quantitation configuration file`.
- **CSV layout of the shipped `table-*` reports** (other reports differ). About 190 preamble lines, some with embedded newlines,
  come before the data, so find the line starting `Primary key,` rather than
  using a fixed `skiprows`. Protein ratio columns are named `Ref`, `C1`, ... in
  raw-file order. In the stacked layout the protein block comes first, then the
  peptide block.
- For runs longer than a tool's timeout (an MCP call may be dropped after about
  30 minutes while Distiller keeps going), run the command line in the
  background and poll the log and output file.

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
| `-DIAMSMSPrecursorsIsolationWindowCutoff <Da>` | Isolation-window width below which the MS/MS precursor strategy is not used, even when the survey scan has few precursors (default `1.6`). |

---

## Where this fits

- For a **report smoke test** on 2.9.240+, `-quantreport` is the quickest
  headless run. For richer regression testing (config-driven, output diffing)
  use `MDXE.pl` — see [BATCH_TESTING.md](BATCH_TESTING.md).
- For discovery of `<DISTILLER_INSTALL>` and `MascotDistiller.exe`, see
  [SETUP.md](SETUP.md).
- For raw-data scripting (peak lists, spectra, TICs) outside the report
  context, use the companion **`mascot-mdro`** skill.
