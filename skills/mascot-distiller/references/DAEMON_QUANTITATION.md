# Quantitation through Mascot Daemon — MS1 and MS2 examples

Mascot Daemon can batch-drive Distiller per raw file: peak pick → Mascot
search → import results into a Distiller project → **quantitate**. The
resulting `.rov` projects are exactly what a custom report (this skill) runs
against, so knowing how Daemon produces them saves a lot of "why is my report
empty" debugging.

> Sources: Mascot Daemon help (*Data Import Filters → Mascot Distiller*),
> Mascot Distiller help (*Multi-file Quantitation*), and real `.par` files /
> Daemon TaskDB rows from a working Daemon 3.x + Distiller 2.9.242 install.
> For the TaskDB columns themselves see the **`mascot-daemon`** skill.

---

## 1. What has to line up

Three things decide whether Daemon produces quantitation:

| Where | Setting | Required value |
|-------|---------|----------------|
| Parameter set (`.par` / `mascot_daemon_parameters.quantitation`) | `QUANTITATION=` | A method name from the server's `quantitation.xml` that Distiller supports |
| Task `filter_options` field 9 | Peak list format | `0` = **MGF** (mzData makes quantitation fail) |
| Task `filter_options` field 10 | Save Distiller project | `1` (the Quantitate control is disabled without it) |
| Task `filter_options` field 11 | Quantitate hits | `0` = all, `-1` = none, or `N-M` range |

Plus licensing: Distiller needs the **Daemon Toolbox** (to be a Daemon import
filter) and the **Search + Quantitation Toolboxes** (for the Quantitate step).
Daemon and Distiller must be on the same PC.

`filter_options` is the 16-field comma string described in the
`mascot-daemon` skill. A real quantitating task:

```
C:\ProgramData\Matrix Science\Mascot Distiller\processing options\default.ThermoXcalibur.opt,4,False,False,,,1,1,0,0,1,0,True,0,Default,0
```

| Index | Value | Meaning |
|-------|-------|---------|
| 0 | `...\default.ThermoXcalibur.opt` | Processing options |
| 1 | `4` | Thermo Xcalibur |
| 9 | `0` | MGF peak list |
| 10 | `1` | Save Distiller project |
| 11 | `0` | Quantitate all hits (`-1` = none — the usual value for search-only tasks) |
| 12 | `True` | Intensity = area (`False` = S/N) |

---

## 2. Which protocols Daemon can quantitate

| Protocol | Level (msparser class) | Example method | Daemon can quantitate per file? | Who makes the quant report |
|----------|-------|----------------|-------------------------------|----------------------------|
| `reporter` | MS2 (`ms_ms2quantitation`) | `TMT 10plex`, `TMTpro 16plex`, `iTRAQ 8plex` | **Yes** | Mascot Server (in the search result) *and* Distiller (`.rov`, MS2 quant cache) |
| `multiplex` | Search-time, handled as MS2 (`ms_ms2quantitation`) | `SILAC K+6 R+6 multiplex`, `18O multiplex` | **Yes** | Mascot Server / Distiller |
| `average` | MS1 (`ms_ms1quantitation`) | `Average [MD]` (label-free, top-N, single file) | **Yes** | Distiller only |
| `precursor` | MS1 (`ms_ms1quantitation`) | `SILAC K+6 R+6 [MD]`, `15N Metabolic [MD]`, `Dimethylation [MD]` | **Yes** | Distiller only |
| `replicate` | MS1 (`ms_ms1quantitation`) | `Label-free [MD]`, `DIA Label-free [MD]` | **No** — needs all runs together | Distiller multi-file project |

The `[MD]` suffix is the convention for "requires Mascot Distiller".
Replicate is the trap: Daemon operates on one raw file at a time, while
replicate needs global time alignment / match-between-runs across every
component file (see §5).

In the report, the protocol arrives as `qMethod.getProtocol()` →
`reporter`/`multiplex` ⇒ `ms_ms2quantitation`, everything else ⇒
`ms_ms1quantitation` (see [QUANT_PROTOCOL_HELPER.md](QUANT_PROTOCOL_HELPER.md)).

---

## 3. Example A — MS2 quantitation: TMT

### Parameter set (`OrbiTrap Human TMTpro 16plex.par`)

```ini
COM=<taskname> (<parameters>), submitted from Daemon on <localhost>
TOL=10
TOLU=ppm
ITOL=0.3
ITOLU=Da
PFA=1
DB=Uniprot_Human
MODS=Carbamidomethyl (C)
IT_MODS=Oxidation (M)
MASS=Monoisotopic
CLE=Trypsin
SEARCH=MIS
CHARGE=2+ and 3+
REPORT= AUTO
FORMAT=Mascot generic
TAXONOMY=All entries
INSTRUMENT=ESI-TRAP
QUANTITATION=TMTpro 16plex
```

Note that **`MODS=` does not list the TMT label.** The method in
`quantitation.xml` carries it:

```xml
<method name="TMTpro 16plex" protein_ratio_type="median" ...>
  <modifications mode="fixed" name="TMT fixed" required="false">
    <mod_file>TMTpro (N-term)</mod_file>
    <mod_file>TMTpro (K)</mod_file>
  </modifications>
  <component name="126"><moverz monoisotopic="126.127726" .../></component>
  ...
  <protocol><reporter .../></protocol>
```

Mascot adds the method's fixed mods to the search. Listing them in `MODS=`
as well is harmless but redundant. Use `TMT6plex (N-term)/(K)` methods
(`TMT 10plex`, `TMT 11plex`) with TMT 10/11plex reagents, and `TMTpro` methods
with 16/18plex. Mixing them up gives near-zero matches, not an error.

### Task (TaskDB row, abbreviated — real task 592)

```text
parameter_set    = TPP_Lopez_CIDHCD                  -- QUANTITATION=TMT 10plex
import_filter    = Mascot Distiller
filter_options   = ...\CID_HCD_reporter.ThermoXcalibur.opt,4,False,False,,,1,1,0,0,1,0,True,0,Default,0
merge_data_files = 0
```

- **Field 12 (intensity) matters for reporter ions.** `True` = isotope-cluster
  area (default), `False` = S/N (∝ peak height). The Daemon help suggests
  trying both for TMT/iTRAQ accuracy.
- Use a processing-options file that keeps the low-m/z reporter region
  (a dedicated `*reporter*.opt` like the one above), otherwise reporter ions
  can be filtered out at peak picking.

### What lands in the cache folder

`<Daemon MGF root>\<task_uid> <task_label>\`:

```
2522e76de8fc5820___Zero_cAMP_F1_1_5uL-05.raw.-1.mgf          peak list submitted to Mascot
2522e76de8fc5820___Zero_cAMP_F1_1_5uL-05.raw.-1.rov          Distiller project with search + MS2 quant
2522e76de8fc5820___Zero_cAMP_F1_1_5uL-05.raw.-1.rov.import.log  Distiller's log for this file (see LOGGING.md)
```

The import log for an MS2 task shows the quant step explicitly:

```
LVL_INFO  PURIFIER_API  Extracting required peaklist information required for MS2 quantitation
LVL_INFO  PURIFIER_API  Creating ms2 quantitation cache file(s)
LVL_INFO  PURIFIER_API  Search.cs  Save search 1
LVL_INFO  PURIFIER_API  PurifierCommandlineApplication.cs  Done!
```

### Running a custom report against it (Distiller 2.9.240+)

```
MascotDistiller.exe "<cache dir>\<hash>___<raw>.-1.rov" -batch ^
    -quantreport my-tmt-report.py -quantout tmt-out.html ^
    -logfile tmt-report.log -loglevel 7
```

`-quantreport` takes a file name in the reports directory or a full path.
The full command-line option set (`-quantreport`, `-quantout`) needs
**Distiller 2.9.240 or later**, so check `MascotDistiller.exe`'s file version
first (see [COMMAND_LINE.md](COMMAND_LINE.md#check-the-version-first)). On older builds,
open the `.rov` in Distiller Workstation (Daemon's status tab hyperlinks it)
and run the report from the wizard.

---

## 4. Example B — MS1 label-free, single file: `Average [MD]`

The Average protocol (top-N peptides per protein, Silva/Hi3 style) gives a
per-file absolute abundance, so it **does** work file-by-file in Daemon.

### Parameter set (`PXD28735 Average.par`)

```ini
COM=<taskname> (<parameters>), submitted from Daemon on <localhost>
TOL=30
TOLU=ppm
ITOL=20
ITOLU=ppm
PFA=2
DB=UP2311_S_cerevisiae,UP5640_H_sapiens,UP625_E_coli_K12
MODS=Carbamidomethyl (C)
IT_MODS=Acetyl (Protein N-term)@Oxidation (M)
MASS=Monoisotopic
CLE=Trypsin/P
SEARCH=MIS
CHARGE=2+ and 3+
REPORT= AUTO
FORMAT=Mascot generic
TAXONOMY=All entries
INSTRUMENT=ETD-TRAP
DECOY=1
QUANTITATION=Average [MD]
TARGET_FDR_PERCENT=1
PERCOLATE=1
ML_ADAPTER_PARAM="MS2Rescore.ms2pip_model=HCD2019"
```

The method (from `quantitation.xml`):

```xml
<method name="Average [MD]" protein_ratio_type="average" ...>
  <quality pep_threshold_type="at least homology" pep_threshold_value="0.05" .../>
  <integration method="simpsons" source="survey" xic_threshold="0.1" .../>
  <protocol>
    <average num_peptides="3" reference_accession="" reference_amount="1.0"
             selection="unique_sequence"/>
  </protocol>
</method>
```

### Task

```text
import_filter    = Mascot Distiller
filter_options   = ...\default.ThermoXcalibur.opt,4,False,False,,,1,1,0,0,1,0,True,0,Default,0
merge_data_files = 0        -- one search + one .rov per raw file
```

Each raw file gets its own `.rov` with Average quant done. Compare files
with Daemon's **Quantitation Summary** (status tab → right-click the task →
*Quantitation Summary → New sample map*), or build a multi-file project from
the `.rov`s, or run your report on each `.rov` in turn.

- Percolator / ML rescoring in the parameter set is **ignored by Distiller
  ≤ 2.8** when it quantitates. 2.9+ honours it (the import log shows
  `IsPercolator=True`).
- In the report this is MS1 with `typeStr == 'average'` — iterate via the
  Average branch, not `getNumberOfMatches()` (see SKILL.md gotchas and
  [QUANT_PROTOCOL_HELPER.md](QUANT_PROTOCOL_HELPER.md)).

---

## 5. Example C — MS1 label-free across runs: `Label-free [MD]` (replicate)

### The method — components map to files

```xml
<method name="Label-free [MD]" protein_ratio_type="median" ...>
  <component name="C1"><file_index>1</file_index></component>
  <component name="C2"><file_index>2</file_index></component>
  <component name="Ref"><file_index>3</file_index></component>
  <report_ratio name="C1/Ref"> ... </report_ratio>
  <report_ratio name="C2/Ref"> ... </report_ratio>
  <integration allow_elution_shift="true" elution_time_delta="500.0"
               elution_time_delta_unit="seconds" matched_rho="0.8" .../>
  <protocol><replicate/></protocol>
</method>
```

`file_index` is the position of the raw file **in the multi-file project**.
Getting the order wrong silently swaps your conditions — check it in the report
(SKILL.md gotcha 14: one component == one sample).

### Parameter set (`Clarkson University Human.par`, abbreviated)

```ini
DB=UP5640_H_sapiens
IT_MODS=Acetyl (Protein N-term)@Oxidation (M)
SEARCH=MIS
INSTRUMENT=ESI-QUAD-TOF
DECOY=1
QUANTITATION=Label-free [MD]
PERCOLATE=1
```

### Daemon can only do the per-file half

Recommended workflow (Distiller help, *Multi-file Quantitation*):

1. **Daemon task, one `.rov` per raw file.** Save project = `1`, quantitate
   = `0` (**all hits** — hit 1 in a single file is not hit 1 in the
   combined result, so a partial range forces re-quantitation later),
   `merge_data_files = 0`.
2. **Combine the projects** into a memory-efficient multi-file project, in
   `file_index` order:
   - Distiller Workstation: *File → New multi-file project*, select the `.rov`s
     from the cache folder, then *Process and Search* and *Quantitate All*
     (fast — peak picking and per-file search are already done), **or**
   - Command line (2.9.240+): `MascotDistiller.exe new_master.rov -batch
     -multifileDirectory "<Daemon cache dir>" -quantitate` — documented as
     "designed to be used on the cache directory from a Mascot Daemon task".
     **Not verified here.** Note that `-rawFile` fails because the
     executable opens `<project.rov>` before handling other switches, so a
     missing project can fail the same way. Test this on a small task before you
     rely on it, **or**
   - Daemon 3.0+ **Quantitation Summary** with a sample map.
3. Run your report against the **master** `.rov`.

### Do not set "Merge MS/MS files"

Real task 593 used `Label-free [MD]` (DIA variant) with `merge_data_files=1`:
Daemon concatenated the peak lists into `mascot_daemon_merge.mgf` and ran
**one** search (result OK), but there was no per-file project and no
`distiller_project` in the result row, so there was nothing to quantitate.
Merging is for identification depth, not label-free quantitation.

---

## 6. Gotchas checklist

| Symptom | Cause |
|---------|-------|
| Search fine, no quant in `.rov` | `QUANTITATION=None`/missing in the parameter set, or save project = `0`, or quantitate = `-1` |
| Quant fails, MGF absent | Peak list format set to mzData/Comprehensive (field 9 ≠ 0) |
| Replicate method, no ratios | Daemon can't do replicate per file; build a multi-file project (§5) |
| Merged task has no project link | Expected: merged searches have no per-file project hyperlink |
| TMT search nearly empty | TMT6plex vs TMTpro method/reagent mismatch |
| Reporter ions missing | Processing options trim low m/z; use a reporter `.opt` |
| Distiller "server busy" lock-ups on `.wiff` | Daemon service account ≠ the Windows user running Distiller. Run the Daemon engine in the tray as the same user (the Distiller help recommends tray over service) |
| Combined project slow to open | Per-file tasks quantitated a hit *range*, not all hits |

When any of these happen, the first place to look is the per-file
`*.rov.import.log` — see [LOGGING.md](LOGGING.md).
