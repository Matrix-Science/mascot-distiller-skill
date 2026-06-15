# Report Examples

Annotated examples of complete Mascot Distiller reports covering common patterns.

## Example 1: Top-3 Protein Intensity (All Quantitation Types)

The canonical example demonstrating all quantitation methods. Located at `reports/top-3.py`.

### What it does

Calculates protein component intensity from the average of the top 3 most intense peptide matches. Supports Average, Precursor (MS1), and Reporter/Multiplex (MS2) quantitation methods.

### Key patterns demonstrated

1. **Branching on quantitation type** - Different code paths for Average, MS1, and MS2
2. **Wizard parameters** - Selection type dropdown, conditional database exclusion page, header toggle
3. **Component iteration** - Getting component names and iterating over them
4. **CSV output** - With and without report header
5. **Progress reporting** - `WriteReports.OutputProgress()`

### Flow

```python
main()
  -> Load properties CSV
  -> Extract wizard parameters (selectionType, exportHeader, excludeDatabase)
  -> Initialize logging
  -> LoadQuantitation.DoLoad(propsPath)
  -> CreateTop3Report(...)
       -> Determine isMS1 / isAverage
       -> Get component names
       -> For each protein:
            -> calculateProteinIntensity(...)
                 -> Average: calculateProteinIntensityAverage()
                      uses quant.getAveragePeptideIntensity()
                 -> MS1: calculateProteinIntensityMS1()
                      iterates match objects with quality thresholds
                 -> MS2: calculateProteinIntensityMS2()
                      iterates peptide quant keys, groups by selection type
       -> Build DataFrame, output CSV
```

### Average method pattern

```python
# Configure the average method
qMethod.getProtocol().getAverage().setSelection(peptideSelectionType)
qMethod.getProtocol().getAverage().setNumPeptides(3)

# Calculate
include = msparser.ms_peptide_quant_key_vector()
exclude = msparser.ms_peptide_quant_key_vector()
intensity = quant.getAveragePeptideIntensity(
    protein.getAccession(), protein.getDB(), include, exclude)
if intensity[0]:  # (bool success, float value)
    return intensity[1]
```

### MS2 method pattern (Reporter/Multiplex)

```python
# Must initialize protein ratio first
ratioName = quant.getQuantitationMethod().getReportRatioByNumber(0).getName()
proteinRatio = quant.getProteinRatio(
    protein.getAccession(), protein.getDB(), ratioName)

# Get peptide keys and intensities
peptideKeys = quant.getPeptideQuantKeys(protein.getAccession(), protein.getDB())
groupIntensities = {}
for i in range(peptideKeys.size()):
    intensities = quant.getComponentIntensities(peptideKeys.get(i))
    ok, query, rank = peptideKeys.get(i).getQueryAndRank()
    peptide = pepSum.getPeptide(query, rank)

    # Group by selection type
    if peptideSelectionType == 'unique_sequence':
        key = peptide.getPeptideStr()
    elif peptideSelectionType == 'unique_mr':
        key = peptide.getPeptideStr() + '_' + pepSum.getReadableVarMods(query, rank)
    elif peptideSelectionType == 'unique_mz':
        key = '{}_{}_{}'.format(peptide.getPeptideStr(),
                                pepSum.getReadableVarMods(query, rank),
                                peptide.getCharge())

    if key in groupIntensities:
        groupIntensities[key] += intensities[componentIndex]
    else:
        groupIntensities[key] = intensities[componentIndex]

# Top-3 average
if len(groupIntensities) >= 3:
    sortedIntensities = sorted(groupIntensities.values(), reverse=True)
    return sum(sortedIntensities[:3]) / 3
```

### MS1 method pattern (Precursor)

```python
matchesCount = quant.getNumMatchesForHit(
    protein.getHitNumber(), protein.getMemberNumber())

# Quality thresholds
qm = quant.getQuantitationMethod()
quality = qm.getQuality()
matchedFractionThreshold = (float(quality.getIsolatedPrecursorThreshold())
                            if quality.isIsolatedPrecursor() else 1)
totalIntensityThreshold = (float(quality.getTotalIntensityThreshold())
                           if quality.isTotalIntensity() else 1)
correlationThreshold = float(qm.getIntegration().getMatchedRho())

groupIntensities = {}
for i in range(1, matchesCount + 1):  # 1-based!
    match = quant.getMatchForHit(i,
        protein.getHitNumber(), protein.getMemberNumber())

    # Build grouping key
    if peptideSelectionType == 'unique_sequence':
        key = match.getPeptideString()
    elif peptideSelectionType == 'unique_mr':
        key = match.getPeptideString() + '_' + match.getReadableLabelFreeVarMods()
    elif peptideSelectionType == 'unique_mz':
        key = '{}_{}_{}'.format(match.getPeptideString(),
                                match.getReadableLabelFreeVarMods(),
                                match.getChargeState())

    component = match.getComponent(componentName)

    # Apply quality thresholds
    csData = match.getChargeStateData()
    if (quality.isIsolatedPrecursor()
            and csData.getMatchedFraction() < matchedFractionThreshold):
        continue
    if (quality.isTotalIntensity()
            and csData.getTotalIntensity() < totalIntensityThreshold):
        continue
    if csData.getMatchedRho() < correlationThreshold:
        continue

    if key in groupIntensities:
        groupIntensities[key] += component.getAbsoluteValue()
    else:
        groupIntensities[key] = component.getAbsoluteValue()

# Top-3 average
if len(groupIntensities) >= 3:
    sortedIntensities = sorted(groupIntensities.values(), reverse=True)
    return sum(sortedIntensities[:3]) / 3
```

---

## Example 2: Simple Protein List (Template)

Located at `dev-reports/templates/template-simple.py`. The minimal starting point.

### What it does

Lists all proteins with hit number, accession, and description.

### Key patterns demonstrated

1. **Minimal boilerplate** - The smallest working report
2. **Protein iteration** - Using `pullProteinsFrom()`
3. **Simple CSV output** - Direct DataFrame to CSV

### Key code

```python
proteins = CreateQuantDataFrames.pullProteinsFrom(pepSum)
data = []
for i, protein in enumerate(proteins):
    WriteReports.OutputProgress('Processing proteins', i + 1, len(proteins))
    row = [
        protein.getHitNumber(),
        protein.getAccession(),
        pepSum.getProteinDescription(protein.getAccession()),
    ]
    data.append(row)

header = ['Hit Number', 'Accession', 'Description']
df = pandas.DataFrame(data, None, header)
df.to_csv(savePath, index=False)
```

---

## Example 3: Report with Multiple Output Formats

Pattern for supporting both CSV and HTML output.

```python
# In XML: Add export format options
# <Parameter name="exportFormat" label="Format" type="select" mapsTo="ExportFileType">
#     <Option value="CSV" displayString="CSV" selected="true"/>
#     <Option value="HTM" displayString="HTML"/>
# </Parameter>

# In Python
props_export = props_csv[props_csv.Identifier == 'ExportFileType']
exportFormat = props_export.Input1.iloc[0]

if exportFormat == 'CSV':
    df.to_csv(savePath, index=False)
elif exportFormat == 'HTM':
    html = df.to_html(index=False)
    with open(savePath, 'w', encoding='utf-8') as f:
        f.write(html)
```

---

## Example 4: Report with Header Information

```python
import reportHeader

# Generate header
headers = reportHeader.createReportHeader(
    props_header, props_rawfiles, props_instruments,
    'proteins',  # reportType
    loadRes,
    'CSV'  # or 'HTML'
)

# Write CSV with header
s = io.StringIO()
s.write(headers[0])  # Header text
s.write('\n')
df.to_csv(s, index=False)
with open(savePath, 'w', encoding='utf-8') as f:
    f.write(s.getvalue())
```

### Manual header (simpler approach from top-3.py)

```python
s = io.StringIO()
csvRow = '{0},{1}\n'
s.write(csvRow.format('Project file', props_header.Input2.iloc[0]))
numFiles = props_rawfiles.shape[0]
datfiles = props_header.Input3.iloc[0].split(",")
for i in range(numFiles):
    s.write(csvRow.format('Raw file ' + str(i + 1), props_rawfiles.Input1.iloc[i]))
    if len(datfiles) == numFiles:
        s.write(csvRow.format('Mascot search result ' + str(i + 1), datfiles[i]))
s.write('\n')
df.to_csv(s, index=False)
with open(savePath, 'w', encoding='utf-8') as f:
    f.write(s.getvalue())
```

---

## Example 5: Excluding Contaminant Database Hits

```python
# XML: Add database selection with AutoGenerateOptions
# Python: Read the excludeDatabase parameter
props_analysis = props_csv[props_csv.Identifier == 'AnalysisInputs']
excludeDatabase = (float(props_analysis.Input5.values[0])
                   if props_analysis.Input5.values[0] != '' else '')

# In protein loop:
for protein in proteins:
    if protein.getDB() == excludeDatabase:
        continue
    # process protein...
```

---

## Example 6: XIC Report for All Identified Peaks (MS1)

Outputs the extracted ion chromatogram (XIC) trace for every identified peptide in an MS1 quantitation project. Two outputs:

1. A **summary CSV** with one row per (protein, peptide, charge, component, raw file) and the peak/region RT bounds + apex intensity.
2. A **trace CSV** with every XIC point (rt, scanId, intensity) keyed back to the summary rows.

A real production version would also embed Plotly traces in HTML — pattern shown at the end.

### Why this is non-trivial

XIC data lives on `ms_ms1quant_match_component`, two levels below the protein hit. You must iterate:

```
protein -> matches (1-based) -> components (by name) -> file_index (for multifile) -> XIC -> points (1-based)
```

For multifile projects, a component may contribute to multiple raw files; each has its own XIC trace. Always probe `getNumFileIndexesMatched()` first.

### Supports stanza

XIC only exists for MS1 protocols:

```xml
<Supports average="true" precursor="true" replicate="true"
         reporter="false" multiplex="false"/>
```

### Core Python

```python
def extract_xic_rows(loadRes, savePathSummary, savePathPoints):
    if not loadRes or not loadRes[0].isMS1:
        sys.exit("XIC report requires an MS1 quantitation protocol "
                 "(average, precursor, or replicate).")

    quant   = loadRes[0].qObj
    pepSum  = loadRes[0].pepSum
    qMethod = loadRes[0].qMethod

    component_names = [
        qMethod.getComponentByNumber(c).getName()
        for c in range(qMethod.getNumberOfComponents())
    ]

    summary_rows = []
    point_rows   = []
    proteins     = CreateQuantDataFrames.pullProteinsFrom(pepSum)

    for pi, protein in enumerate(proteins):
        WriteReports.OutputProgress('Extracting XICs', pi + 1, len(proteins))
        accession = protein.getAccession()
        hitNo     = protein.getHitNumber()
        memberNo  = protein.getMemberNumber()
        n_matches = quant.getNumMatchesForHit(hitNo, memberNo)

        for mi in range(1, n_matches + 1):
            match = quant.getMatchForHit(mi, hitNo, memberNo)
            seq   = match.getPeptideString()
            mods  = match.getReadableLabelFreeVarMods()
            z     = match.getChargeState()

            for comp_name in component_names:
                if not match.hasComponent(comp_name):
                    continue
                component = match.getComponent(comp_name)

                n_files = component.getNumFileIndexesMatched()
                file_indexes = (
                    [component.getFileIndex(k) for k in range(n_files)]
                    if n_files > 0 else [-1]
                )

                for file_index in file_indexes:
                    try:
                        xic = component.getXic(file_index)
                    except Exception:
                        xic = None
                    if xic is None or xic.getNumPoints() == 0:
                        continue

                    row_id = '|'.join([
                        str(hitNo), accession, seq, mods, str(z),
                        comp_name, str(file_index)
                    ])

                    # Summary row
                    apex_int = max(
                        (xic.getPoint(p)[2] for p in range(1, xic.getNumPoints() + 1)),
                        default=0.0,
                    )
                    summary_rows.append({
                        'row_id'        : row_id,
                        'hit'           : hitNo,
                        'accession'     : accession,
                        'description'   : pepSum.getProteinDescription(accession),
                        'sequence'      : seq,
                        'modifications' : mods,
                        'charge'        : z,
                        'component'     : comp_name,
                        'file_index'    : file_index,
                        'rt_peak_start' : xic.getRtPeakStart(),
                        'rt_peak_end'   : xic.getRtPeakEnd(),
                        'rt_region_start': xic.getRtRegionStart(),
                        'rt_region_end' : xic.getRtRegionEnd(),
                        'scan_start'    : xic.getStartScanId(),
                        'scan_end'      : xic.getEndScanId(),
                        'peak_state'    : xic.getPeakState(),
                        'n_points'      : xic.getNumPoints(),
                        'apex_intensity': apex_int,
                        'intensity_sum' : component.getAbsoluteValue(file_index),
                    })

                    # Trace rows
                    for p in range(1, xic.getNumPoints() + 1):
                        rt, scan_id, intensity = xic.getPoint(p)
                        point_rows.append({
                            'row_id'   : row_id,
                            'rt'       : rt,
                            'scan_id'  : scan_id,
                            'intensity': intensity,
                        })

    pandas.DataFrame(summary_rows).to_csv(savePathSummary, index=False)
    pandas.DataFrame(point_rows).to_csv(savePathPoints, index=False)
    WriteReports.OutputProgress('XIC report complete', 1, 1)
```

### Optional: embed Plotly chromatograms in HTML

```python
import plotly.graph_objs as go
from plotly.offline import plot as plotly_plot

def xic_html(savePath, summary_rows, point_rows_by_id):
    parts = ["<html><head><meta charset='utf-8'></head><body>"]
    for row in summary_rows:
        rid = row['row_id']
        pts = point_rows_by_id.get(rid, [])
        if not pts:
            continue
        fig = go.Figure(go.Scatter(
            x=[p['rt'] for p in pts],
            y=[p['intensity'] for p in pts],
            mode='lines',
            name=f"{row['sequence']} +{row['charge']} ({row['component']})",
        ))
        # Shade integrated peak region
        fig.add_vrect(
            x0=row['rt_peak_start'], x1=row['rt_peak_end'],
            fillcolor='LightSalmon', opacity=0.3, line_width=0,
        )
        fig.update_layout(
            title=f"{row['accession']} — {row['sequence']} (+{row['charge']}, {row['component']})",
            xaxis_title='Retention time (s)',
            yaxis_title='Intensity',
            height=300, margin=dict(l=40, r=10, t=40, b=40),
        )
        parts.append(plotly_plot(fig, output_type='div', include_plotlyjs='cdn'))
    parts.append("</body></html>")
    with open(savePath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
```

### Wizard parameters worth exposing

- **Components** (multiSelect with `AutoGenerateOptions=quantComponents`): let the user pick which components to plot.
- **Min intensity** (floatingPoint): skip rows where the apex intensity is below a threshold (keeps the report small).
- **Output format** (select: `CSV`, `HTML`, `Both`): decide whether to render the Plotly HTML.
- **Include discarded peaks** (checkbox): exclude rows where `xic.getPeakState() == 3`.

### Gotchas specific to XIC

- **MS2 protocols**: `Supports reporter="false" multiplex="false"`, or guard `loadRes[0].isMS1` and exit cleanly.
- **`getXic()` may throw** for components whose XIC data didn't make it into the cache — wrap in try/except.
- **Empty XICs**: `getNumPoints() == 0` is common for components present in the method but not measured for that match. Skip silently.
- **1-based**: `getPoint(p)` is `range(1, n+1)`. Off-by-one here will silently drop the first or last scan.
- **Multifile**: do NOT loop `range(getNumberOfResfiles())` — use `component.getFileIndex(k)` for the indexes that this specific component actually saw.
- **Memory**: a large project can produce 100k+ trace rows. For HTML output, paginate or filter to the top-N hits before generating Plotly divs.

---

## Available Reports in `reports/` Directory

| Report | Description | Key Patterns |
|--------|-------------|-------------|
| `top-3.py` | Top-3 protein intensity | All quant types, wizard, CSV |
| `proteins.py` | Protein table | Standard protein iteration |
| `peptides.py` | Peptide table | Peptide-level reporting |
| `quality.py` | Quality control | QC metrics |
| `average-peptides.py` | Average peptide quantitation | Average method |
| `average-proteins.py` | Average protein quantitation | Average method |
| `pca.py` | PCA analysis | Statistics, HTML+SVG output |
| `kmeans-cluster.py` | K-means clustering | StatisticsOperations |
| `hierarchical-cluster.py` | Hierarchical clustering | StatisticsOperations |
| `anova.py` | ANOVA analysis | Statistical testing |
| `volcano-plot.py` | Volcano plots | Visualization |
| `box-and-whisker.py` | Box plots | Visualization |
| `alignment.py` | Retention time alignment | Time alignment data |
| `table-proteins.py` | Protein table for export | Copy-paste format |
| `table-peptides.py` | Peptide table for export | Copy-paste format |
