# msparser API Reference

Complete reference for the msparser Python SDK used in Mascot Distiller reports.

## File Loading

### ms_mascotresfilebase

Factory class for loading Mascot results files.

```python
# Load a .dat file (standard with cache)
resFile = msparser.ms_mascotresfilebase.createResfile(
    filepath,           # Path to .dat file
    0,                  # Reserved
    "<!-- %d seconds-->\n",  # Comment template
    int(msparser.ms_mascotresfilebase.RESFILE_USE_CACHE),  # Flags
    cacheDir            # Cache directory path
)

# Load without cache
resFile = msparser.ms_mascotresfilebase.createResfile(
    filepath, 0, "<!-- %d seconds-->\n",
    int(msparser.ms_mascotresfilebase.RESFILE_NOFLAG), cacheDir
)

# Multifile projects - append additional dat files
resFile.appendResfile(additionalDatPath)

# Multifile projects - access sub-resfiles and query mapping
numFiles = resFile.getNumberOfResfiles()       # int - count of sub-resfiles
subRes = resFile.getResfile(file_id)           # sub-resfile (1-based file_id)
subQueries = subRes.getNumQueries()            # query count for this sub-file
totalQueries = resFile.getNumQueries()         # total merged query count

# CRITICAL: Map merged query number → (file_id, source_query)
# Merged queries use global numbering (1..N across all files).
# Sub-resfiles use LOCAL numbering (1..M per file).
# NEVER pass merged query numbers to file-specific ms_peptidesummary objects.
# getPeptide() will CRASH (access violation) on out-of-range queries.
result = resFile.getSrcQueryAndFileIdForMultiFile(merged_query)

# Set schema paths (required for quantitation)
resFile.setXMLschemaFilePath(
    msparser.ms_mascotresfilebase.XML_SCHEMA_QUANTITATION, quantSchemaPath)
resFile.setXMLschemaFilePath(
    msparser.ms_mascotresfilebase.XML_SCHEMA_UNIMOD, unimodSchemaPath)

# Validation
resFile.isValid()              # bool
resFile.getLastErrorString()   # str
resFile.getLastError()         # error code
resFile.getNumberOfErrors()    # int
resFile.getErrorNumber(i)      # error code at index i (1-based)
resFile.getErrorString(i)      # error string at index i (1-based)
resFile.clearAllErrors()

# Cache
resFile.getCacheFileName()
resFile.getCacheDirectory()

# Search parameters
params = resFile.params()      # Returns ms_searchparams-like object
resFile.getQuantitationMethod(qMethod)  # Populates ms_quant_method

# Percolator
resFile.setPercolatorFeatures(mascotOptions, "")
```

### Resfile flags

```python
msparser.ms_mascotresfilebase.RESFILE_NOFLAG
msparser.ms_mascotresfilebase.RESFILE_USE_CACHE
```

---

## Search Parameters

Access via `resFile.params()`, NOT via `ms_searchparams` constructor.

```python
params = resFile.params()

# Fixed modifications (1-BASED indexing!)
i = 1
while True:
    name = params.getFixedModsName(i)
    if not name:
        break
    residues = params.getFixedModsResidues(i)
    delta = params.getFixedModsDelta(i)
    neutralLoss = params.getFixedModsNeutralLoss(i)
    i += 1

# Variable modifications (1-BASED indexing!)
i = 1
while True:
    name = params.getVarModsName(i)
    if not name:
        break
    i += 1
```

---

## Peptide Summary

### ms_peptidesummary

Created via `LoadQuantitation.DoLoad()` or manually:

```python
# Manual creation (normally handled by LoadQuantitation)
resParams = msparser.ms_mascotresults_params()
resFile.get_ms_mascotresults_params(opts, resParams)
pepSum = msparser.ms_peptidesummary(resFile, resParams)
```

**Key methods:**

```python
# Get protein hit (1-based hit number)
protein = pepSum.getHit(hitNumber)

# Get protein description
description = pepSum.getProteinDescription(accession)

# Get peptide match
peptide = pepSum.getPeptide(queryNumber, rank)

# Get readable variable modifications
readableMods = pepSum.getReadableVarMods(queryNumber, rank)
```

---

## Protein Object (ms_protein)

Returned by `pepSum.getHit()` or `pullProteinsFrom()`.

```python
protein.getHitNumber()       # int - hit index
protein.getAccession()       # str - UniProt/database accession
protein.getDB()              # int - database ID
protein.getMemberNumber()    # int - isoform (0 = main protein)
protein.getScore()           # float - protein score
protein.getNumPeptides()     # int - number of peptides
protein.getPeptideQuery(i)   # int - query number for peptide i
protein.getPeptideP(i)       # int - rank for peptide i
```

---

## Peptide Object (ms_peptide)

Returned by `pepSum.getPeptide(query, rank)`.

```python
peptide.getPeptideStr()      # str - sequence (with modifications)
peptide.getCharge()          # int - charge state
peptide.getIonsScore()       # float - ions score
peptide.getCalcMr()          # float - calculated molecular mass
```

---

## Quantitation Method (ms_quant_method)

```python
# Protocol
protocol = qMethod.getProtocol()
typeStr = protocol.getType()   # 'average', 'precursor', 'replicate',
                                # 'reporter', 'multiplex', 'null'

# Components (0-based indexing)
numComponents = qMethod.getNumberOfComponents()
for c in range(numComponents):
    name = qMethod.getComponentByNumber(c).getName()

# Report ratios
numRatios = qMethod.getNumberOfReportRatios()
for r in range(numRatios):
    ratioName = qMethod.getReportRatioByNumber(r).getName()

# Average method settings
avg = protocol.getAverage()  # None if not average method
if avg:
    avg.setSelection(selectionType)  # 'unique_sequence', 'unique_mr', 'unique_mz'
    avg.setNumPeptides(3)

# Quality thresholds
quality = qMethod.getQuality()
quality.isIsolatedPrecursor()
quality.getIsolatedPrecursorThreshold()
quality.isTotalIntensity()
quality.getTotalIntensityThreshold()

# Integration
integration = qMethod.getIntegration()
matchedRho = float(integration.getMatchedRho())

# Normalisation
qMethod.dropNormalisation()  # Disable normalisation
```

---

## MS1 Quantitation (ms_ms1quantitation)

For average, precursor, and replicate protocols.

```python
quant = msparser.ms_ms1quantitation(pepSum, qMethod)

# Validation
quant.isValid()
quant.getLastErrorString()

# Load data
quant.loadXmlFile(xmlPath, schemaPath)
quant.loadCdbFile(cdbPath, cachePath, False)  # False = don't re-evaluate thresholds

# Get updated method
qMethod = quant.getQuantitationMethod()

# Protein matches (1-BASED indexing!)
matchesCount = quant.getNumMatchesForHit(hitNumber, memberNumber)
for i in range(1, matchesCount + 1):
    match = quant.getMatchForHit(i, hitNumber, memberNumber)

# Average method specific
include = msparser.ms_peptide_quant_key_vector()
exclude = msparser.ms_peptide_quant_key_vector()
result = quant.getAveragePeptideIntensity(accession, db, include, exclude)
# result = (bool success, float intensity)
if result[0]:
    intensity = result[1]
```

### MS1 Match Object

```python
match.getPeptideString()
match.getReadableLabelFreeVarMods()
match.getChargeState()
match.getComponent(componentName)     # Returns component object
match.getChargeStateData()

# XIC scan range processed for this match (across all components)
match.getFirstXicScanId()
match.getLastXicScanId()
match.getDisplayIntensity()           # Total intensity across XIC peak

# Component
component.getAbsoluteValue()          # Unnormalised intensity

# Charge state data
csData = match.getChargeStateData()
csData.getMatchedFraction()
csData.getTotalIntensity()
csData.getMatchedRho()
```

---

## XIC (Extracted Ion Chromatogram)

Per-peptide chromatogram traces are reachable from MS1 match components.

### Get an XIC from a match component

```python
match = quant.getMatchForHit(i, hitNumber, memberNumber)  # 1-based!
component = match.getComponent(componentName)

# Single-file project (or aggregate across all files)
xic = component.getXic()              # default file_index = -1 (not set)

# Multifile project (1-based file_index)
xic = component.getXic(file_index)

# Discover which raw files contributed to this component
n = component.getNumFileIndexesMatched()
for idx in range(n):
    file_index = component.getFileIndex(idx)   # 1-based
    xic_for_file = component.getXic(file_index)
```

`file_index` defaults to the sentinel `ms_quant_file_index::file_index_value_not_set` (= -1). Pass an explicit 1-based file index for multifile projects.

**Component object caveat (multifile):** the per-file methods above are on the
**match** component (`match.getComponent(name)`). The quant-*method* component
(`qMethod.getComponentByNumber(i)`) is the component *definition*; its
`getFileIndex(f).getContent()` is **not** a reliable component→sample/run map in
multifile projects (it can scramble — components mapped to the wrong runs). Use the
match component's matched file indexes, or match the component name to the run name.
See SKILL.md Critical Gotcha #15.

### ms_xic API

```python
# Peak state
xic.getPeakState()                    # PEAK_STATE_OK | PEAK_STATE_DISCARD | PEAK_STATE_UNKNOWN
msparser.ms_xic.PEAK_STATE_OK         # 1
msparser.ms_xic.PEAK_STATE_DISCARD    # 3
msparser.ms_xic.PEAK_STATE_UNKNOWN    # 0

# Retention time bounds (seconds)
xic.getRtPeakStart()                  # RT of integrated peak start
xic.getRtPeakEnd()                    # RT of integrated peak end
xic.getRtRegionStart()                # RT of wider search region start
xic.getRtRegionEnd()                  # RT of wider search region end

# Scan ID bounds
xic.getStartScanId()                  # First scan in chromatogram
xic.getEndScanId()                    # Last scan in chromatogram
xic.getPeakStartScanId()              # First scan of integrated peak
xic.getPeakEndScanId()                # Last scan of integrated peak
xic.getRegionStartScanId()
xic.getRegionEndScanId()

# Index bounds (only valid when hasIndexes() is True)
xic.hasIndexes()
xic.getStartIndex()
xic.getEndIndex()
xic.getPeakStartIndex()
xic.getPeakEndIndex()
xic.getRegionStartIndex()
xic.getRegionEndIndex()

# Time alignment
xic.getUseTimeShift()                 # bool - aligned by time vs. by scan
xic.getElutionTimeShift()             # seconds

# Trace points (1-based!)
n = xic.getNumPoints()
for i in range(1, n + 1):
    rt, scanId, intensity = xic.getPoint(i)   # SWIG returns 3-tuple
```

### Notes and gotchas

- **Empty XIC**: `getNumPoints()` may return 0 for unidentified or discarded peaks. Always guard.
- **PEAK_STATE_DISCARD**: present in the data but excluded from quantitation; surface this in the report.
- **getPoint() is 1-based** like other msparser iteration. Use `range(1, n + 1)`.
- **getXic() can throw** if the underlying XIC data wasn't cached. Wrap in try/except when iterating large protein lists.
- **Multifile**: a component without per-file XIC data may only return a sensible result for `file_index = -1` (aggregate). Try the file-specific call first, fall back to the aggregate.
- **MS2 protocols (reporter/multiplex) do not produce XICs** — `getXic` is only on `ms_ms1quant_match_component`. For MS2 reports, the chromatogram is implicit in the precursor; report scan/RT from the peptide query instead.

### Robust XIC accessor pattern

```python
def safe_get_xic(component, file_index=None):
    method = getattr(component, "getXic", None)
    if method is None:
        return None
    try:
        return method(file_index) if file_index is not None else method()
    except Exception:
        return None

def xic_to_arrays(xic):
    if xic is None:
        return [], [], []
    rts, scans, ints = [], [], []
    for i in range(1, xic.getNumPoints() + 1):
        rt, scan, inten = xic.getPoint(i)
        rts.append(rt); scans.append(scan); ints.append(inten)
    return rts, scans, ints
```

---

## MS2 Quantitation (ms_ms2quantitation)

For reporter and multiplex protocols.

```python
quant = msparser.ms_ms2quantitation(pepSum, qMethod)

# Validation
quant.isValid()
quant.getLastErrorString()

# Load data
quant.loadXmlFile(xmlPath, schemaPath)
quant.loadCdbFile(cdbPath)

# Get updated method
qMethod = quant.getQuantitationMethod()

# Peptide quantitation keys
peptideKeys = quant.getPeptideQuantKeys(accession, db)
for i in range(peptideKeys.size()):
    key = peptideKeys.get(i)

    # Get intensities array (indexed by component number, 0-based)
    intensities = quant.getComponentIntensities(key)

    # Get query and rank
    ok, query, rank = key.getQueryAndRank()

# Protein ratio
proteinRatio = quant.getProteinRatio(accession, db, ratioName)
ratioValue = proteinRatio.getValue()

# Normalisation
quant.normaliseIntensities()
quant.normalisePeptideRatios()
```

---

## Logging

```python
# Create logger (module-level to prevent GC)
mylogger_ = msparser.ms_stdout_logger()

# Configure
mylogger_.setColsToOutput(int(props_logging.Input2.iloc[0]))

# Set up monitor
monitor = msparser.ms_loggingmonitor.getDefaultMonitor()
monitor.setLogMask(int(props_logging.Input1.iloc[0]))
monitor.addLogEventsHandler(mylogger_)

# Log a message
monitor.logMessage(
    msparser.ms_loggingmonitor.LVL_DEBUG1,  # Level
    msparser.ms_loggingmonitor.SRC_APPLICATION,  # Source
    0,                                        # Code
    'Your message',                           # Message
    'your-script.py',                         # File
    sys._getframe().f_lineno                  # Line number
)

# Log levels
msparser.ms_loggingmonitor.LVL_DEBUG1
msparser.ms_loggingmonitor.LVL_DEBUG2
msparser.ms_loggingmonitor.LVL_DEBUG3
msparser.ms_loggingmonitor.LVL_WARNING

# Source constants
msparser.ms_loggingmonitor.SRC_APPLICATION
msparser.ms_loggingmonitor.SRC_PURIFIERAPP
```

---

## Configuration

```python
# Mascot.dat configuration
mascotDotDat = msparser.ms_datfile(mascotDatPath)
mascotOptions = mascotDotDat.getMascotOptions()

# Quantitation configuration from file
qConfigFile = msparser.ms_quant_configfile(quantXmlPath, quantSchemaPath)
qMethod = qConfigFile.getMethodByNumber(0)
```

---

## Error Handling

```python
# Check errors on error handler
def dumpWarnings(errorsIn):
    if errorsIn.getNumberOfErrors() > 0:
        for i in range(errorsIn.getNumberOfErrors()):
            msg = "Warning: %s" % errorsIn.getErrorString(i)
            msparser.ms_loggingmonitor.getDefaultMonitor().logMessage(
                msparser.ms_loggingmonitor.LVL_WARNING,
                msparser.ms_loggingmonitor.SRC_APPLICATION,
                0, msg, 'script.py', sys._getframe().f_lineno)

# Check resfile errors
def checkErrors(resfile):
    if resfile.getLastError():
        for i in range(1, 1 + resfile.getNumberOfErrors()):
            sys.stderr.write("Error number: %s: %s" %
                           (resfile.getErrorNumber(i), resfile.getErrorString(i)))
    bIsValid = resfile.isValid()
    resfile.clearAllErrors()
    return bIsValid
```

---

## Schema Path Construction

```python
# Standard schema path format
quant_schema = ''.join([
    "http://www.matrixscience.com/xmlns/schema/quantitation_2 ",
    props_schemas.Input2.iloc[0],
    " http://www.matrixscience.com/xmlns/schema/quantitation_1 ",
    props_schemas.Input1.iloc[0]
])
unimod_schema = ''.join([
    "http://www.unimod.org/xmlns/schema/unimod_2 ",
    props_schemas.Input3.iloc[0]
])
```

---

## Cross-referencing the Mascot Server Perl bindings

When the Python msparser docs are unclear, consult the **Perl** bindings of the same SDK — they expose the same C++ API and are often documented more concretely. The most useful reference is `<WORKSPACE>/mascot server scripts/lib/MascotResults.pm`, which is the canonical consumer Matrix Science use internally to render Mascot Server result pages.

Useful patterns to look up there:
- **Modifications iteration** — `MascotResults.pm:1047-1055` shows the 1-based `getFixedModsName(1++)` loop pattern, authoritative for modification access.
- **Query/peptide iteration** — search the file for `->getPeptide(` to see how the production server walks results.
- **Quantitation method handling** — multiple worked examples for averaging, ratio extraction, normalisation.

The Perl signatures translate to Python verbatim — `$obj->method($arg)` becomes `obj.method(arg)`. The only routine differences are:
- Perl uses `++$i` for the start of 1-based loops; Python uses `range(1, n + 1)`.
- Perl's `defined()` checks become `is not None` or truthiness checks in Python.
- SWIG output parameters that are returned via `OUTPUT` macros (e.g. `getPoint`, `getQueryAndRank`) come back as tuples in Python: `ok, query, rank = key.getQueryAndRank()`.

When Python and Perl docs disagree, Perl is usually more current — Matrix Science's web codebase exercises the API more heavily.

---

## msparser Python Examples

Located in `msparser/example_python/`:

| Example | Description |
|---------|-------------|
| `resfile_info.py` | Load and inspect results files |
| `resfile_params.py` | Access search parameters |
| `resfile_summary.py` | Generate protein/peptide summaries |
| `msparser_full.py` | Complete workflow |
| `resfile_ms2quantitation.py` | MS2 quantitation workflow |
| `resfile_customquantitation.py` | Custom quantitation setup |
| `config_mascotdat.py` | Mascot.dat configuration |
| `config_masses.py` | Mass definitions |
| `config_enzymes.py` | Enzyme configuration |
| `config_modfile.py` | Modifications |
| `tools_stats.py` | Statistical functions |
| `tools_quant_helper.py` | Quantitation helpers |
| `tools_treecluster.py` | Hierarchical clustering |
