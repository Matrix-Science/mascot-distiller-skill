---
name: mascot-distiller
description: Create and develop Mascot Distiller custom quantitative proteomics reports, and drive Distiller unattended. Use when creating or editing reports, working with the msparser SDK for quantitation analysis, running Distiller de novo sequencing from the command line, or working with .rov project files.
---

# Mascot Distiller Report Development Skill

Build custom quantitative proteomics reports for Mascot Distiller using the msparser SDK, and drive Distiller itself from the command line.

## Contents

1. [Overview](#overview)
2. [First-time setup](#first-time-setup)
3. [Two-File Report Pattern](#two-file-report-pattern)
4. [Execution Flow](#execution-flow)
5. [Creating a New Report](#creating-a-new-report)
6. [Python Script Structure](#python-script-structure)
7. [XML Definition Structure](#xml-definition-structure)
8. [Properties CSV Format](#properties-csv-format)
9. [msparser API Quick Reference](#msparser-api-quick-reference)
10. [Common Patterns](#common-patterns)
11. [Quantitation Methods](#quantitation-methods)
12. [Helper Modules](#helper-modules)
13. [Deployment and Testing](#deployment-and-testing)
14. [De novo sequencing and the batch CLI](#de-novo-sequencing-and-the-batch-cli)
15. [Critical Gotchas](#critical-gotchas)
16. [Reference Files](#reference-files)

---

## Overview

Mascot Distiller reports are Python scripts executed by Mascot Distiller to produce custom quantitative proteomics analysis outputs (CSV, HTML, SVG, PNG). Each report is a paired `.py` + `.py.xml` file deployed to Distiller's reports directory.

This skill uses two machine-specific paths that must be resolved before doing any real work:

| Placeholder | What it is | How to find it |
|-------------|------------|----------------|
| `<WORKSPACE>` | Your local checkout of the report-building project (contains `reports/`, `dev-reports/`, `msparser/`, `scripts/`, `Documentation/`) | Wherever you cloned/copied the project |
| `<DISTILLER_INSTALL>` | The Mascot Distiller installation directory (contains `reports\` subdirectory and `MascotDistiller.exe`) | Default: `C:\Program Files\Matrix Science\Mascot Distiller` |

See [First-time setup](#first-time-setup) for how to resolve these.

**Key subdirectories under `<WORKSPACE>`** (relative paths):
- `reports/` - Reference reports and shared helper modules (read-only)
- `dev-reports/` - Development workspace for custom reports
- `dev-reports/templates/` - Starter templates
- `scripts/` - Deployment and testing PowerShell scripts
- `msparser/example_python/` - 30+ msparser SDK examples
- `Documentation/` - Schema files and API documentation

**Distiller deployment target**: `<DISTILLER_INSTALL>\reports\`

---

## First-time setup

Before generating, deploying, or testing a report, Claude must know the values of `<WORKSPACE>` and `<DISTILLER_INSTALL>` for this machine. Resolve them in this order:

1. **Check project memory.** Look for `mascot_distiller_paths.md` in the current project's memory directory. If present, use the values it records. Skip steps 2–4.

2. **Check environment variables.** If `MASCOT_DISTILLER_WORKSPACE` and/or `MASCOT_DISTILLER_INSTALL` are set in the user's shell, use those.

3. **Probe defaults** (Windows):
   - `<DISTILLER_INSTALL>` candidates, in order:
     - `%PROGRAMFILES%\Matrix Science\Mascot Distiller`
     - `%PROGRAMFILES(X86)%\Matrix Science\Mascot Distiller`
     - Registry: `HKLM\SOFTWARE\Matrix Science\Mascot Distiller\InstallDir` (read with PowerShell)
   - `<WORKSPACE>` candidates: the current working directory if it contains `reports/` and `dev-reports/`; otherwise the user must provide it.
   - Verify each candidate exists and contains the expected subdirectories (`reports/`, plus `MascotDistiller.exe` for the install dir) before trusting it.

4. **Ask the user.** If steps 1–3 don't resolve a path, ask once: *"Where is your Mascot Distiller report-building workspace?"* and *"Where is Mascot Distiller installed?"* (offer the probed defaults).

5. **Save to project memory.** Once resolved, write `mascot_distiller_paths.md` (a `reference`-type memory) so future sessions skip discovery. Template:

   ```markdown
   ---
   name: Mascot Distiller paths
   description: Workspace and install paths for the mascot-distiller skill on this machine
   type: reference
   ---

   - `<WORKSPACE>` = `C:\path\to\Mascot Distiller report building`
   - `<DISTILLER_INSTALL>` = `C:\Program Files\Matrix Science\Mascot Distiller`

   Verified <YYYY-MM-DD> by reading the directory contents.
   ```

   Then add to `MEMORY.md`: `- [Mascot Distiller paths](mascot_distiller_paths.md) — workspace and install dir`.

For deeper discovery details (registry queries, non-Windows Distiller, etc.) see [references/SETUP.md](references/SETUP.md).

---

## Two-File Report Pattern

Every report consists of exactly TWO paired files:

| File | Purpose |
|------|---------|
| `report-name.py` | Python script with all report logic and data processing |
| `report-name.py.xml` | XML definition for parameters, wizard UI, and quantitation protocol support |

Both files must share the same base name and be deployed together.

---

## Execution Flow

```
User opens Distiller GUI -> Selects custom report
    -> Distiller reads .py.xml to generate wizard UI
    -> User provides inputs through wizard pages
    -> Distiller creates "properties.csv" with all settings
    -> Distiller executes Python script: python report.py <properties.csv path>
    -> Python script processes data and generates output file
    -> Report appears in Distiller results
```

The properties CSV path is passed as `sys.argv[1]`.

---

## Creating a New Report

### Step 1: Create report directory

```
dev-reports/
  └── my-report/
      ├── my-report.py
      └── my-report.py.xml
```

### Step 2: Start from template

Three starting points, in order of preference:

1. **Skill template** (recommended) — `templates/quant-report-template/` in this skill. Copy `report-name.py` + `report-name.py.xml` + `README.md` into your new dev-report directory and rename. Has the copyright banner, `__version__`, the logger GC pattern, and the standard property-subset extraction baked in.
2. **Workspace template** — `<WORKSPACE>/dev-reports/templates/template-simple.py` for a more bare-bones starting point.
3. **Existing report** — `<WORKSPACE>/reports/top-3.py` if you want a complete worked example to crib from.

**Debugging what Distiller passes in**: you don't need a dedicated report to see the properties CSV. Distiller logs the full properties file when logging verbosity is turned up — enable it in Distiller's logging options and the file contents appear in the Distiller log. That's the shortest path to seeing exactly what wizard inputs and project metadata your report will receive.

### Step 3: Edit the XML (defines wizard UI)

### Step 4: Edit the Python (report logic)

### Step 5: Run the pre-deploy checklist

See [references/CHECKLIST.md](references/CHECKLIST.md) — encoding, schema, parse, logger, no hard-coded paths. One-shot Bash audit included.

### Step 6: Deploy and test

```powershell
.\scripts\deploy-report.ps1 -ReportName "my-report"
```

---

## Python Script Structure

### Minimal template

```python
import sys
import CreateQuantDataFrames
import pandas
import msparser
import io
import WriteReports
import LoadQuantitation

mylogger_ = msparser.ms_stdout_logger()

def main():
    if len(sys.argv) < 2:
        sys.exit('Must specify properties filename as parameters')

    propsPath = sys.argv[1]
    props_csv = pandas.read_csv(propsPath, delimiter=',', header=0,
                                keep_default_na=False, quotechar="\"")

    # Standard property subsets
    props_logging = props_csv[props_csv.Identifier == 'LoggingOptions']
    props_options = props_csv[props_csv.Identifier == 'PathOptions']
    props_header = props_csv[props_csv.Identifier == 'ReportHeader']
    props_rawfiles = props_csv[props_csv.Identifier == 'RawFile']

    savePath = props_options.Input2.iloc[0]

    # Extract custom wizard parameters
    # props_custom = props_csv[props_csv.Identifier == 'myParamName']
    # myValue = props_custom.Input1.iloc[0]

    # Initialise logging
    mylogger_.setColsToOutput(int(props_logging.Input2.iloc[0]))
    msparser.ms_loggingmonitor.getDefaultMonitor().setLogMask(
        int(props_logging.Input1.iloc[0]))
    msparser.ms_loggingmonitor.getDefaultMonitor().addLogEventsHandler(mylogger_)

    # Load results
    loadRes = LoadQuantitation.DoLoad(propsPath)

    # Generate report
    CreateReport(loadRes, savePath, props_header, props_rawfiles)

    # Prevent garbage collection of logger
    mylogger_.setColsToOutput(1)


def CreateReport(loadedResults, savePath, props_header, props_rawfiles):
    if len(loadedResults) == 0:
        sys.exit("No Results Parameters Supplied")

    isMS1 = loadedResults[0].isMS1
    quant = loadedResults[0].qObj
    pepSum = loadedResults[0].pepSum
    qMethod = loadedResults[0].qMethod

    proteins = CreateQuantDataFrames.pullProteinsFrom(pepSum)

    data = []
    for i, protein in enumerate(proteins):
        WriteReports.OutputProgress('Processing proteins', i + 1, len(proteins))
        row = [
            protein.getHitNumber(),
            protein.getAccession(),
            pepSum.getProteinDescription(protein.getAccession()),
        ]
        # Add your calculations here
        data.append(row)

    header = ['Hit Number', 'Accession', 'Description']
    df = pandas.DataFrame(data, None, header)
    df.to_csv(savePath, index=False)
    WriteReports.OutputProgress('Report complete', 1, 1)


if __name__ == "__main__":
    sys.exit(main())
```

---

## XML Definition Structure

### Minimal template

```xml
<?xml version="1.0" encoding="utf-8"?>
<DistillerReport majorVersion="1" minorVersion="0"
    title="Your Report Title" grouping="Custom"
    xmlns="http://www.matrixscience.com/xmlns/schema/distiller_report_definition_1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.matrixscience.com/xmlns/schema/distiller_quantitation_2
        distiller_report_definition_1.xsd">

    <Description>Tooltip description of the report</Description>

    <Supports average="true" precursor="true" replicate="true"
             reporter="true" multiplex="true"/>

    <Inputs>
        <ReportConfiguration>
            <Parameter name="exportFormat" label="Format" value="CSV"
                       type="text" mapsTo="ExportFileType"/>
        </ReportConfiguration>

        <Wizard>
            <WelcomeText>Introduction shown on first wizard page.</WelcomeText>

            <!-- Add wizard pages here -->

            <CompletionText>Click 'Finish' to run the report.</CompletionText>
        </Wizard>
    </Inputs>
</DistillerReport>
```

### Key XML attributes

- `title` - Report name displayed in Distiller GUI
- `grouping` - Menu folder path (e.g. `"Custom"`, `"Custom/Intensity"`)

### Supported quantitation protocols

Set each to `"true"` or `"false"` in the `<Supports>` element:
- `average` - Isotope labeling (SILAC, 15N) - MS1
- `precursor` - Label-free precursor intensity - MS1
- `replicate` - Replicate ratios
- `reporter` - Isobaric tags (iTRAQ, TMT) - MS2
- `multiplex` - Multiplexed protocols

### Wizard parameter types

| Type | Description |
|------|-------------|
| `select` | Dropdown menu |
| `multiSelect` | Multi-select dropdown |
| `radio` | Radio buttons |
| `text` | Text input |
| `integer` | Integer input |
| `floatingPoint` | Decimal input |
| `checkbox` | Checkbox |
| `file` | File browser |
| `autocomplete` | Text with autocomplete |

### Wizard page example

```xml
<Page title="Report Options">
    <HelpText>Configure your analysis options.</HelpText>
    <Parameter name="selectionType" label="Selection type" type="select">
        <Option value="unique_sequence" displayString="Unique sequence" selected="true"/>
        <Option value="unique_mr" displayString="Unique Mr"/>
        <Option value="unique_mz" displayString="Unique M/Z"/>
    </Parameter>
</Page>
```

### Conditional page skipping

```xml
<Page title="Optional Page">
    <SkipIf>
        <SkipIfParameter name="databaseCount" value="1"/>
    </SkipIf>
    <!-- page content -->
</Page>
```

### Auto-generated options from Distiller

```xml
<Parameter name="excludeDatabase" type="select" label="Database" mapsTo="AnalysisInputs">
    <AutoGenerateOptions>databases</AutoGenerateOptions>
    <Option value="" displayString="" selected="true"/>
</Parameter>
```

### Distiller variable substitution

Use `@{VariableName}` in ReportConfiguration values:
```xml
<Parameter name="databaseCount" label="no databases" type="integer"
           value="@{DatabaseNames.Count}"/>
```

---

## Properties CSV Format

The properties CSV has columns: `Identifier`, `Input1` through `Input9`.

| Identifier | Key Fields | Purpose |
|------------|------------|---------|
| `LoggingOptions` | Input1=log mask, Input2=columns | Logging config |
| `PathOptions` | Input1=working dir, Input2=save path, Input3=mascot.dat | File paths |
| `ReportHeader` | Input2=project file, Input3=dat files | Metadata |
| `RawFile` | Input1=file paths | Raw MS data files |
| `Results` | Input1=dat, Input2=xml, Input3=cdb, Input5=samples, Input6=replicates, Input7=ratios, Input9=cache | Result files |
| `AnalysisInputs` | Input1-5 | Custom analysis params |
| `ActionOptions` | Input1-5 | Output format options |
| `ExportFileType` | Input1 | CSV, HTM, etc. |
| `Schema` | Input1-4 | XML schema paths |
| `SummaryInputs` | Input1-9 | Peptide summary params |
| `Imputation` | Various | Data imputation settings |
| `Debug` | Various | Debug options |
| *Custom* | As defined in XML | Your wizard parameters |

### Accessing custom parameters in Python

```python
props_csv = pandas.read_csv(propsPath, delimiter=',', header=0,
                            keep_default_na=False, quotechar="\"")
# Parameter name from XML: <Parameter name="selectionType" ...>
props_selection = props_csv[props_csv.Identifier == 'selectionType']
value = props_selection.Input1.iloc[0]
```

---

## msparser API Quick Reference

See [references/MSPARSER_API.md](references/MSPARSER_API.md) for the complete API reference.

### Core classes

| Class | Purpose |
|-------|---------|
| `ms_mascotresfilebase` | Load results files (.dat) |
| `ms_peptidesummary` | Protein/peptide hits from search |
| `ms_quant_method` | Quantitation method definition |
| `ms_ms1quantitation` | Precursor-level (MS1) quantitation |
| `ms_ms2quantitation` | Fragment-level (MS2) quantitation |
| `ms_stdout_logger` | Console logging |
| `ms_loggingmonitor` | Logging management |

### Key methods

```python
# Load results
resFile = msparser.ms_mascotresfilebase.createResfile(filepath, flags)

# Get proteins
proteins = CreateQuantDataFrames.pullProteinsFrom(pepSum)
protein.getHitNumber()
protein.getAccession()
protein.getDB()
protein.getMemberNumber()
protein.getScore()
protein.getNumPeptides()

# Get protein description
pepSum.getProteinDescription(accession)

# Get peptide from query/rank
peptide = pepSum.getPeptide(query, rank)
peptide.getPeptideStr()
peptide.getCharge()
peptide.getIonsScore()

# MS2 quantitation
peptideKeys = quant.getPeptideQuantKeys(accession, db)
intensities = quant.getComponentIntensities(peptideKeys.get(i))
proteinRatio = quant.getProteinRatio(accession, db, ratioName)

# MS1 quantitation
matchesCount = quant.getNumMatchesForHit(hitNumber, memberNumber)
match = quant.getMatchForHit(i, hitNumber, memberNumber)  # 1-based!
component = match.getComponent(componentName)
component.getAbsoluteValue()

# Average quantitation
intensity = quant.getAveragePeptideIntensity(accession, db, include, exclude)
# Returns (bool success, float intensity)

# Components
qMethod.getNumberOfComponents()
qMethod.getComponentByNumber(i).getName()  # 0-based
qMethod.getNumberOfReportRatios()
```

---

## Common Patterns

### Iterate over proteins

```python
proteins = CreateQuantDataFrames.pullProteinsFrom(pepSum)
for i, protein in enumerate(proteins):
    WriteReports.OutputProgress('Processing proteins', i + 1, len(proteins))
    hitNo = protein.getHitNumber()
    accession = protein.getAccession()
    description = pepSum.getProteinDescription(accession)
```

### Get component names

```python
componentNames = []
if isAverage:
    componentNames.append('Avg')
else:
    for c in range(0, qMethod.getNumberOfComponents()):
        componentNames.append(qMethod.getComponentByNumber(c).getName())
```

### MS2 peptide intensities (Reporter/Multiplex)

```python
peptideKeys = quant.getPeptideQuantKeys(protein.getAccession(), protein.getDB())
for i in range(peptideKeys.size()):
    intensities = quant.getComponentIntensities(peptideKeys.get(i))
    ok, query, rank = peptideKeys.get(i).getQueryAndRank()
    peptide = pepSum.getPeptide(query, rank)
    # intensities[componentIndex] gives intensity for that component
```

### MS1 peptide matches (Precursor)

```python
matchesCount = quant.getNumMatchesForHit(protein.getHitNumber(), protein.getMemberNumber())
for i in range(1, matchesCount + 1):  # 1-based!
    match = quant.getMatchForHit(i, protein.getHitNumber(), protein.getMemberNumber())
    component = match.getComponent(componentName)
    value = component.getAbsoluteValue()
```

### Average method intensity

```python
qMethod.getProtocol().getAverage().setSelection(peptideSelectionType)
qMethod.getProtocol().getAverage().setNumPeptides(3)
include = msparser.ms_peptide_quant_key_vector()
exclude = msparser.ms_peptide_quant_key_vector()
result = quant.getAveragePeptideIntensity(protein.getAccession(), protein.getDB(),
                                           include, exclude)
if result[0]:  # success
    intensity = result[1]
```

### Disable normalisation for MS2

```python
if not isMS1:
    quant.getQuantitationMethod().dropNormalisation()
```

### Extract XIC for every identified peak (MS1 only)

XIC = extracted ion chromatogram. The integrated trace per identified peptide. Reachable from MS1 match components only — MS2 (reporter/multiplex) protocols have no XIC.

```python
# Per-protein, per-match, per-component, per-file XIC iteration
for i in range(1, quant.getNumMatchesForHit(hitNo, memberNo) + 1):
    match = quant.getMatchForHit(i, hitNo, memberNo)
    for c in range(qMethod.getNumberOfComponents()):
        compName = qMethod.getComponentByNumber(c).getName()
        if not match.hasComponent(compName):
            continue
        component = match.getComponent(compName)

        # Multifile: enumerate contributing raw files
        n_files = component.getNumFileIndexesMatched()
        file_indexes = [component.getFileIndex(k) for k in range(n_files)] or [-1]

        for file_index in file_indexes:
            try:
                xic = component.getXic(file_index)
            except Exception:
                continue
            if xic is None or xic.getNumPoints() == 0:
                continue

            # Peak/region bounds in seconds
            rt_peak_start = xic.getRtPeakStart()
            rt_peak_end = xic.getRtPeakEnd()
            peak_state = xic.getPeakState()  # 1=OK, 3=DISCARD, 0=UNKNOWN

            # Trace points (1-based!)
            for p in range(1, xic.getNumPoints() + 1):
                rt, scan_id, intensity = xic.getPoint(p)
                # ... write a row, append to plot, etc.
```

For a complete XIC report (CSV trace + Plotly HTML per peptide), see [REPORT_EXAMPLES.md Example 6](references/REPORT_EXAMPLES.md). For the full XIC API see [MSPARSER_API.md](references/MSPARSER_API.md#xic-extracted-ion-chromatogram).

### CSV output with optional header

```python
df = pandas.DataFrame(data, None, header)
if exportHeader:
    s = io.StringIO()
    csvRow = '{0},{1}\n'
    s.write(csvRow.format('Project file', props_header.Input2.iloc[0]))
    s.write('\n')
    df.to_csv(s, index=False)
    with open(savePath, 'w', encoding='utf-8') as f:
        f.write(s.getvalue())
else:
    df.to_csv(savePath, index=False)
```

### Report progress

```python
WriteReports.OutputProgress('Processing proteins', current, total)
# Outputs: "Progress","5","100","Processing proteins"
```

---

## Quantitation Methods

| Protocol | Type | API Class | Description |
|----------|------|-----------|-------------|
| `average` | MS1 | `ms_ms1quantitation` | Isotope labeling (SILAC, 15N) |
| `precursor` | MS1 | `ms_ms1quantitation` | Label-free precursor intensity |
| `replicate` | MS1 | `ms_ms1quantitation` | Replicate ratios |
| `reporter` | MS2 | `ms_ms2quantitation` | Isobaric tags (iTRAQ, TMT) |
| `multiplex` | MS2 | `ms_ms2quantitation` | Multiplexed protocols |

### Determining quantitation type

```python
quantProtocol = qMethod.getProtocol()
typeStr = quantProtocol.getType()
isMS1 = typeStr not in ['reporter', 'multiplex']

isAverage = False
if isMS1:
    isAverage = qMethod.getProtocol().getAverage() is not None
```

---

## Helper Modules

All in `reports/` directory, automatically available in Distiller.

| Module | Key Function | Purpose |
|--------|-------------|---------|
| `LoadQuantitation` | `DoLoad(propsPath)` | Load search & quantitation results. Returns list of `LoadObjs` namedtuples |
| `WriteReports` | `OutputProgress(msg, cur, tot)` | Progress reporting and report writing |
| `CreateQuantDataFrames` | `pullProteinsFrom(pepSum)` | Extract proteins; create DataFrames from quant data |
| `reportHeader` | `createReportHeader(...)` | Generate standard report headers |
| `CreateGraphs` | Various | Graph/visualization generation (Plotly, SVG, PNG) |
| `StatisticsOperations` | Various | PCA, K-means, ANOVA, Volcano plots |
| `FormatDataFrames` | Various | Data formatting utilities |
| `Imputation` | Various | Missing data imputation |

### LoadObjs namedtuple

```python
LoadObjs = namedtuple('LoadObjs', [
    'isMS1',     # bool: MS1 or MS2 quantitation
    'qObj',      # ms_ms1quantitation or ms_ms2quantitation
    'pepSum',    # ms_peptidesummary (protein hits)
    'qMethod',   # ms_quant_method (method definition)
    'resFile',   # ms_mascotresfilebase (keep reference to prevent GC!)
    'subsets'    # [samples, replicates, ratios]
])
```

---

## Deployment and Testing

Run these from `<WORKSPACE>` (resolved during [First-time setup](#first-time-setup)).

### Deploy to Distiller

```powershell
.\scripts\deploy-report.ps1 -ReportName "my-report"
# Copies .py and .py.xml to <DISTILLER_INSTALL>\reports\
# Creates timestamped backups of existing files
# Requires elevated PowerShell (writes under Program Files)
```

### Test from command line

```powershell
.\scripts\test-report.ps1 -ReportName "my-report" -RovFile "path\to\file.rov"
# Runs Distiller in batch mode with the report
```

### Test in Distiller GUI

1. Deploy report
2. Open Distiller, load a `.rov` project file
3. Go to **Analysis -> Reports -> [grouping] -> [title]**
4. Run through wizard and verify output

---

## De novo sequencing and the batch CLI

Everything above is *post-search reporting*. Distiller can also be driven
directly — `MascotDistiller.exe /batch ...` — to sequence spectra without a
database, submit searches, and run reports unattended.

### The one thing to know about de novo

**De novo parameters are read from a copy stored inside the `.rov` project**,
not from the preferences file and not from the command line. Editing
`Distiller.rst` between runs has no effect, and the documented `/s <preferences>`
switch is accepted and ignored — a deliberately malformed preferences file still
produces normal output.

Worse, once a project has de novo results Distiller caches them in
`rover_data+N` ZIP members and a later run **re-exports the cache instead of
recomputing**. The run exits 0, the file looks right, and the exported header
shows your *new* tolerances over the *old* solutions.

The sequence that works:

```
1. SEED   /denovo 1 over a short scan window   -> makes Distiller create rover_data
                                                  (a fresh project has none)
2. PATCH  rewrite <denovotagTab> in rover_data -> sets the real parameters
          + delete cached rover_data+N members -> forces recomputation
3. RUN    /denovo 0 over the whole project
```

```powershell
python templates/denovo-cli/run_denovo.py --rov project.rov --out denovo.csv `
    --seed-start 5 --seed-end 400 --frag-tol 0.02 --pep-tol 10
```

### Two parameter traps

- **The stock 0.300 Da fragment tolerance is more than an order of magnitude too
  loose for Orbitrap MS2.** Too many compositions fit each mass gap, so Distiller
  emits `[YSP|VTF|TMD|SME|PFC|FEA|EDC|YAi|SFi|PHi|MCi]` where 0.02 Da gives
  `[VA|Gi]`. Set the tolerance before judging the output.
- **Adding variable modifications makes de novo worse.** A database search prunes
  the mod space with the sequence; de novo has no such constraint. Add
  `Phospho (ST)`/`Phospho (Y)` when the sample demands it, not as a hedge.

### Reading the output

The de novo CSV states its uncertainty rather than hiding it: lowercase `i`
(Ile-or-Leu) and `q` (Lys-or-Gln), `[ABC]` for a known composition in unknown
order, `[AB|CD]` for alternative compositions. Use the **`FullSequence`** column,
not `Sequence` — the latter collapses gaps to `-`.

Do not flatten that ambiguity silently. On a 2.4M-spectrum benchmark only 27.8%
of Distiller's correct answers named a single sequence outright, so taking the
first option and reporting it as *the* answer overstates the tool considerably.

**The de novo score ranks solutions within one spectrum, not spectra against
each other.** Measured across 2.4M spectra the wrong-answer rate by score
quintile was flat (50.0 / 48.6 / 49.1 / 50.0 / 54.5%). Don't build a
cross-dataset score cutoff on it, and don't draw a precision–coverage curve
ranked by it and read the result as quality.

Full detail — switches, output format, notation, failure modes, throughput:
[references/DE_NOVO.md](references/DE_NOVO.md) and
[references/COMMAND_LINE.md](references/COMMAND_LINE.md).

### Comparing engines?

For de novo work that isn't Distiller-specific — running other engines,
joining results by scan number, isobaric-aware sequence comparison, mapping
peptides to a proteome, FDR control — see the separate **de novo sequencing**
skill. This skill covers the Distiller side only.

---

## Critical Gotchas

### 1. Garbage collection - KEEP REFERENCES

Always keep a reference to the logger and result file objects. The logger must have a final call at the end of `main()`:

```python
mylogger_ = msparser.ms_stdout_logger()  # Module-level!

def main():
    # ... all your code ...
    mylogger_.setColsToOutput(1)  # Prevent GC - MUST be last line
```

The `resFile` is stored in `LoadObjs` for the same reason.

### 2. Modifications API uses 1-based indexing

```python
params = res_file.params()  # NOT msparser.ms_searchparams(res_file)
i = 1
while True:
    mod_name = params.getFixedModsName(i)  # 1-based!
    if not mod_name:
        break
    residues = params.getFixedModsResidues(i)
    i += 1
```

### 3. Use `res_file.params()` for search parameters

```python
# CORRECT
params = res_file.params()
mod_name = params.getFixedModsName(1)

# WRONG - ms_searchparams doesn't have getFixedModsName
search_params = msparser.ms_searchparams(res_file)
```

### 4. MS1 match iteration is 1-based

```python
for i in range(1, matchesCount + 1):  # Starts at 1!
    match = quant.getMatchForHit(i, hitNumber, memberNumber)
```

### 5. Component indexing is 0-based

```python
for c in range(0, qMethod.getNumberOfComponents()):  # Starts at 0
    name = qMethod.getComponentByNumber(c).getName()
```

### 6. Always test with a real Distiller batch job

Unit tests can pass even when msparser rejects out-of-range query requests. When touching query/file-mapping logic, always run at least one full Distiller batch job.

### 7. Available Python environment in Distiller

Python 3.6+ with: pandas, numpy, matplotlib, plotly, scipy, scikit-learn, seaborn, statsmodels, msparser.

### 8. Release checklist

Before release:
- Add Matrix Science copyright banner and explicit `__version__`
- Strip experimental debug code
- Run unit tests and at least one Distiller integration test

### 9. File encoding: Distiller requires UTF-8

Distiller's embedded Python interpreter expects **UTF-8** encoded `.py` files. If your development file is UTF-16 (common when editing on Windows), you **must** convert to UTF-8 before deploying:

```python
# Convert UTF-16 → UTF-8 for deployment
with open('report.py', 'r', encoding='utf-16-le') as f:
    content = f.read()
content = content.lstrip('\ufeff')  # strip BOM
with open('report.utf8.py', 'w', encoding='utf-8') as f:
    f.write(content)
```

Symptom: `SyntaxError: Non-UTF-8 code starting with '\xff'` on line 1.

### 10. Multifile projects: query numbering mismatch (CRITICAL)

In multifile projects, there are **two query numbering systems**:
- **Merged/global numbering** - used by the merged `ms_mascotresfilebase` and the main `ms_peptidesummary`. Queries numbered 1 to N across all files (e.g. file 1 has queries 1-30000, file 2 has 30001-60000, file 3 has 60001-90000).
- **Local/file-specific numbering** - used by individual sub-resfiles from `resFile.getResfile(file_id)` and any `ms_peptidesummary` built from them. Each starts at query 1.

**`ms_peptidesummary.getPeptide(query, rank)` will crash the entire process (access violation, ec=-1073741819 / 0xC0000005) if passed an out-of-range query number.** This is a C++ crash that Python's `except Exception` **cannot catch**.

**Rule**: Never pass merged query numbers to file-specific summaries. Use `getSrcQueryAndFileIdForMultiFile()` to translate:

```python
# Get the local query number for a merged query
result = resFile.getSrcQueryAndFileIdForMultiFile(merged_query)
# result contains (file_id, source_query) pairs
# Use source_query with file-specific summaries
# Use merged_query only with the merged pep_sum
```

### 11. Multifile API methods

```python
# Count sub-resfiles in a multifile project
num_files = resFile.getNumberOfResfiles()

# Get individual sub-resfile (1-based file_id)
sub_res = resFile.getResfile(file_id)

# Get local query count for a sub-resfile
sub_queries = sub_res.getNumQueries()

# Map merged query → (file_id, source_query)
result = resFile.getSrcQueryAndFileIdForMultiFile(merged_query)

# Build a file-specific summary (for per-file peptide lookups)
res_params = msparser.ms_mascotresults_params()
# ... configure res_params ...
file_summary = msparser.ms_peptidesummary(sub_res, res_params)
# ONLY pass local query numbers to file_summary.getPeptide()
```

### 12. `grouping=""` in the root `<DistillerReport>` element

Every report in the reference `reports/` directory (`top-3`, `proteins_ibaq`, `table-peptides-int-all`, `anova`, ...) sets `grouping=""`. Distiller files empty-grouping reports under **Analysis → Reports → Custom** automatically.

Setting `grouping="Custom"` — even though it looks correct and matches the skill's old template — creates a nested **Custom/Custom/** sub-folder that buries the report, and on some Distiller builds makes it not appear in the menu at all. XML schema validation catches neither case. Always use `grouping=""` unless you deliberately want a sub-folder, in which case use `grouping="Custom/Something"`.

### 13. `mapsTo="AnalysisInputs"` slot is bound by parameter name, not XML order

`AnalysisInputs` has a fixed column schema baked into `reports/LoadQuantitation.py`:

| Slot     | Required parameter `name=` |
|----------|----------------------------|
| `Input1` | `signifThreshold`          |
| `Input2` | `filterSignif`             |
| `Input3` | `maxRatio`                 |
| `Input4` | `useProtein`               |
| `Input5` | `excludeDatabase`          |

If your wizard parameter has `mapsTo="AnalysisInputs"` but a name other than one of the five above, **Distiller silently drops the value** — the wizard page renders, the user selects something, and `props_analysis.InputN` is empty. The database drop-down via `<AutoGenerateOptions>databases</AutoGenerateOptions>` *only* works when the parameter is named `excludeDatabase`. If you want "flag as contaminant" rather than "exclude", keep the name `excludeDatabase` and reinterpret the value in Python — or drop `mapsTo` entirely and use your own Identifier (see [WIZARD_COOKBOOK.md](references/WIZARD_COOKBOOK.md) for the `mapsTo` deep-dive, including the full magic-name table).

### 14. Label-free MS1: one quant component == one sample — emit one row per component

In precursor/replicate label-free MS1 quant, each component of a `match`
corresponds to one sample (usually one raw file). Iterate the match's components
and emit **one row per component**, mapped to the file that component matched.

Do **NOT** loop over every raw file calling `getAbsoluteValue(file_index)` for
each: when a component only has data for one file, `getAbsoluteValue(<other index>)`
returns the component's aggregate value anyway, so you get one duplicate row per
file — a 10-file project produced 10× every match. (Same rule, stated for XICs, in
[REPORT_EXAMPLES.md](references/REPORT_EXAMPLES.md): "use `component.getFileIndex(k)`
for the indexes this specific component actually saw".)

### 15. Two different "component" objects — don't use the quant-method one for sample/run mapping

There are two component objects and they are **not** interchangeable for working
out which sample/run a value belongs to:

- `match.getComponent(name)` — *this measurement's* component. Its
  `getFileIndex(k)` (`k` in `0 .. getNumFileIndexesMatched()-1`) gives the files
  this component actually matched. **Use this** for per-file values and `Run`
  labelling.
- `qMethod.getComponentByNumber(i)` — the component *definition*. Its
  `getFileIndex(f).getContent()` does **NOT** reliably map a component to a single
  sample/run in multifile projects: in a multi-file DIA project it returned
  scrambled content, mismapping components to the wrong runs and dropping some runs
  entirely (one component's value landed under another sample's name).

When components are named after their samples/files, matching the component name to
the run name (unique trailing match, e.g. component `N4` → run `..._N4`) is a
reliable fallback. **Always confirm the component→run mapping on a real multifile
project**: every component should map to exactly one expected run, with no reuse and
none dropped.

### 16. A `.rov` can be a valid ZIP and still be unusable

A project left half-written by a hard kill opens cleanly and is close to full
size, but can be missing `mdro_proc_opts`. Distiller then does **no de novo work
at all** — exit 0, no `rover_data` created, and a confusing `rover_data not
present` two steps later. Size and ZIP validity both pass; check the member list:

```python
def rov_is_complete(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
    except (OSError, zipfile.BadZipFile):
        return False
    return {"mdro_pkl", "mdro_proc_opts"} <= names
    # rover_data deliberately NOT required -- a fresh project has none yet
```

### 17. An output file existing is not evidence the stage finished

A Distiller process killed mid-write — by a forced reboot, say — leaves a file
that is megabytes long and still truncated, which sails past any size floor and
is then read as though it were a whole result. **The exit code is the only
reliable signal.** In a resumable batch, persist the exit code per stage and on
restart delete any output whose stage is not recorded as having returned 0.

Note also that exit 0 with *no* output file is a real outcome: it usually means
Distiller decided there was nothing to do, which points at the project rather
than at Distiller.

---

## Reference Files

| File | Contents |
|------|----------|
| [SETUP.md](references/SETUP.md) | First-time path discovery: workspace, Distiller install, msparser SDK location |
| [MSPARSER_API.md](references/MSPARSER_API.md) | Complete msparser API (post-search results / quantitation) — XICs from quant cache |
| [XML_SCHEMA.md](references/XML_SCHEMA.md) | Raw XML definition schema — types and grammar |
| [WIZARD_COOKBOOK.md](references/WIZARD_COOKBOOK.md) | Wizard XML idioms (AutoGenerateOptions, SkipIf, mapsTo, @{Var}, full-page patterns) |
| [REPORT_EXAMPLES.md](references/REPORT_EXAMPLES.md) | Annotated examples of complete msparser-based reports (top-3, multiple output formats, headers, database filtering, integrated XIC) |
| [VISUALIZATIONS.md](references/VISUALIZATIONS.md) | Plot recipes: Plotly embedding, XIC overlays, annotated MS2, heatmaps, rank-abundance |
| [QUANT_PROTOCOL_HELPER.md](references/QUANT_PROTOCOL_HELPER.md) | Drop-in helper for MS1/MS2/Average branching — single dispatch instead of copy-pasted branches |
| [CHECKLIST.md](references/CHECKLIST.md) | Pre-deploy and release checklists (encoding, schema, logger, etc.) |
| [BATCH_TESTING.md](references/BATCH_TESTING.md) | MDXE-driven regression testing; fixture design; CI considerations |
| [PROCESSING_OPTIONS.md](references/PROCESSING_OPTIONS.md) | `*.opt` (peak-detection) schema versions and `downgrade-opt-to-1.6.ps1` for sending files back to customers on older Distiller builds |
| [ROV_FILE_FORMAT.md](references/ROV_FILE_FORMAT.md) | `.rov` is a ZIP container — stream layout, why msparser can't open it natively, the `open_rov_resfile()` extract-then-`createResfile()` pattern, where peak detection options + quant method + embedded `.dat` actually live |
| [DE_NOVO.md](references/DE_NOVO.md) | Distiller de novo sequencing: why parameters live in the `.rov`, the seed→patch→run sequence, `<denovotagTab>` attributes, output CSV format, the ambiguity notation, what the score does and does not tell you, crash backoff |
| [COMMAND_LINE.md](references/COMMAND_LINE.md) | Driving Distiller unattended: verified `/batch` switches, exit codes, `/submitSearch` vs HTTP submission to `nph-mascot.exe`, MGF export for third-party tools, resumable-batch rules |

**Templates** (in `templates/` — copy into `<WORKSPACE>/dev-reports/<your-name>/`):
- `quant-report-template/` — recommended starting point with banner, `__version__`, logger GC, standard property extraction
- `denovo-cli/` — `run_denovo.py` + `patch_rov_denovo.py`: unattended de novo with parameters that actually take effect (plain Python, no msparser needed)
- `lint-report.sh` — one-shot pre-deploy audit; copy into `<WORKSPACE>/scripts/`
- `downgrade-opt-to-1.6.ps1` — convert schema 1.7+ processing-options files to 1.6 (see [PROCESSING_OPTIONS.md](references/PROCESSING_OPTIONS.md))

### Need raw-data access? Use the `mascot-mdro` skill

This skill is strictly for post-search reports driven by `msparser` and the `.dat` results file. If you need to reach back to the raw vendor data — peak detection, TICs, spectra, peak list export (MGF/DTA/PKL), or an XIC at an arbitrary m/z — use the companion **`mascot-mdro`** skill, which covers the COM-based Mascot Distiller SDK. MDRO can also be invoked **inside** a custom report (e.g. to overlay a raw XIC on top of msparser's integrated XIC); the bridging example and its gotchas live in `mascot-mdro`'s `REPORT_EXAMPLES.md`.

> **Licence note**: the Mascot Distiller SDK is a **paid product**, separate from the base Distiller application. A report that calls MDRO only runs for users with an active SDK licence — don't design a headline feature around MDRO unless your target users have the licence. Deliver an msparser-only version if you need wider reach.

---

## Key Reference Reports

- **`reports/top-3.py`** + `top-3.py.xml` - Recommended starting point. Demonstrates all quantitation methods (Average, MS1, MS2), wizard parameters, conditional pages, and CSV output with optional header.
- **`dev-reports/templates/template-simple.py`** + `.py.xml` - Minimal working template.
- **`reports/proteins.py`** / `peptides.py` - Standard protein/peptide reports.
- **`reports/quality.py`** - Quality control report.
