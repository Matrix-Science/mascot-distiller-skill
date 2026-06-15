# Wizard parameter cookbook

Reusable XML idioms for the `<Inputs><Wizard>` section of a report's `.py.xml`. Complements [XML_SCHEMA.md](XML_SCHEMA.md), which defines the grammar; this file covers **patterns** — what to use when.

## Reading a parameter in Python

Every wizard `<Parameter name="X">` becomes a row in the properties CSV with `Identifier=X` and the user's choice in `Input1`:

```python
props = pandas.read_csv(props_path, keep_default_na=False, quotechar='"')
value = props[props.Identifier == "X"].Input1.iloc[0]
```

For `multiSelect`, each selected option is a separate row (same Identifier, different `Input1`):

```python
rows = props[props.Identifier == "X"]
values = rows.Input1.tolist()
```

For `checkbox`: `Input1` is `"true"` or `"false"` (literal strings, not booleans).

## Auto-populated dropdowns (`AutoGenerateOptions`)

Use when the options come from the loaded project, not the XML author:

```xml
<Parameter name="excludeDatabase" type="select" label="Contaminant database"
           mapsTo="AnalysisInputs">
    <AutoGenerateOptions>databases</AutoGenerateOptions>
    <Option value="" displayString="(none)" selected="true"/>
</Parameter>
```

Supported source names (from the Distiller schema):

| Source | Populates with |
|--------|----------------|
| `databases` | Database names from the loaded search |
| `quantComponents` | Component names (light/heavy/115/116/…) |
| `quantRatios` | Defined ratios (L/H, 115/114, …) |
| `sampleNames` | Replicate sample names |
| `rawFileNames` | Raw files in the project |

Always include one manual `<Option>` with `selected="true"` to define the default — an empty option `value=""` is the usual fallback.

## Conditional page skipping (`SkipIf`)

Hide a page when a previous answer makes it irrelevant:

```xml
<Page title="Select contaminant database">
    <SkipIf>
        <SkipIfParameter name="databaseCount" value="1"/>
    </SkipIf>
    <HelpText>Skipped automatically for single-database searches.</HelpText>
    <Parameter name="excludeDatabase" type="select" label="Database"
               mapsTo="AnalysisInputs">
        <AutoGenerateOptions>databases</AutoGenerateOptions>
        <Option value="" displayString="(none)" selected="true"/>
    </Parameter>
</Page>
```

You need a parameter to compare against. Declare one in `<ReportConfiguration>` using Distiller variable substitution:

```xml
<ReportConfiguration>
    <Parameter name="databaseCount" label="database count" type="integer"
               value="@{DatabaseNames.Count}"/>
</ReportConfiguration>
```

Multiple `SkipIfParameter` elements are AND-ed together. There's no OR; duplicate the page or invert the logic if you need one.

## Distiller variable substitution (`@{Var}`)

Inside `value=""` attributes of `<ReportConfiguration>` parameters, `@{Name}` expands at wizard time from project metadata:

| Variable | Meaning |
|----------|---------|
| `@{DatabaseNames.Count}` | Number of databases in the search |
| `@{SampleNames.Count}` | Number of replicate samples |
| `@{RawFileNames.Count}` | Number of raw files |
| `@{ProtocolType}` | `average`, `precursor`, `replicate`, `reporter`, `multiplex`, `null` |

These only work in `value=""` on a `<Parameter>` in `<ReportConfiguration>`, not inside wizard pages directly. Wizard pages reference them by the parameter `name` via `<SkipIf>`.

## `mapsTo` — writing into standard property groups

By default a wizard parameter writes its own Identifier row. Use `mapsTo` to have it stored under one of Distiller's predefined groups:

```xml
<Parameter name="excludeDatabase" type="select" mapsTo="AnalysisInputs" ...>
```

Now the value lands in the `AnalysisInputs` row instead of a dedicated `excludeDatabase` row.

### `AnalysisInputs` has a fixed column schema — parameter names are magic

**Which `InputN` column the value lands in is determined by the parameter's `name=`, not by XML order.** Using any other name silently fails — the value goes nowhere and the report sees an empty slot. The five slots are baked into `reports/LoadQuantitation.py` (`AnalysisConsts` namedtuple, read at `DoLoad` time):

| Input slot | Field            | Type              | Required parameter `name=` |
|------------|------------------|-------------------|----------------------------|
| `Input1`   | `signif`         | numeric           | `signifThreshold`          |
| `Input2`   | `filter`         | bool (TRUE/FALSE) | `filterSignif`             |
| `Input3`   | `maxRatio`       | numeric           | `maxRatio`                 |
| `Input4`   | `useProt`        | bool (TRUE/FALSE) | `useProtein`               |
| `Input5`   | `excludeDatabase`| numeric           | `excludeDatabase`          |

If you need a database selector, the parameter **must** be named `excludeDatabase` — even if your report's semantics are "flag as contaminant, don't exclude" (the Python code is free to interpret the value however it wants). Any other name will leave `AnalysisInputs.Input5` empty. This exact bug shipped in `table-proteins-int-mod` in 2026-04 — the wizard page rendered, the user selected a DB, nothing happened downstream, and the cause was `name="contaminantDatabase"` instead of `name="excludeDatabase"`.

### Other `mapsTo` groups

| `mapsTo`          | Where it lands                 | Slot binding    |
|-------------------|--------------------------------|-----------------|
| `AnalysisInputs`  | fixed schema above             | **by name**     |
| `ActionOptions`   | `Input1`..`Input5`             | by XML order    |
| `ExportFileType`  | `Input1`                       | single slot     |
| `SummaryInputs`   | `Input1`..`Input9`             | by XML order    |
| `Imputation`      | report-specific                | by name         |

Use `mapsTo` when you're setting one of the pre-baked options the helpers already read; invent your own Identifier for anything else.

### When `mapsTo="AnalysisInputs"` isn't what you want

If you need a database selector that does **not** map to `AnalysisInputs.Input5` — for example, two independent database selectors on the same page, or a marker that's semantically disconnected from Distiller's "exclude database" concept — drop `mapsTo` entirely and read the value under the parameter's own Identifier:

```xml
<Parameter name="markerDatabase" type="select" label="Flag as contaminant">
    <AutoGenerateOptions>databases</AutoGenerateOptions>
    <Option value="" displayString="(none)" selected="true"/>
</Parameter>
```

```python
props_marker = props_csv[props_csv.Identifier == "markerDatabase"]
marker_db = props_marker.Input1.iloc[0] if len(props_marker) else ""
```

`<AutoGenerateOptions>databases</AutoGenerateOptions>` has only been verified with `mapsTo="AnalysisInputs"` in the reference reports; if you try this standalone form, test it against a project with more than one database before relying on it.

## Parameter type recipes

### Single-choice dropdown (short list)

```xml
<Parameter name="selectionType" label="Group peptides by" type="select">
    <Option value="unique_sequence" displayString="Unique sequence" selected="true"/>
    <Option value="unique_mr"       displayString="Unique Mr"/>
    <Option value="unique_mz"       displayString="Unique M/Z"/>
</Parameter>
```

### Radio buttons (3-5 exclusive options — more visible than a dropdown)

```xml
<Parameter name="outputFormat" label="Output format" type="radio">
    <Option value="csv"  displayString="CSV"  selected="true"/>
    <Option value="html" displayString="HTML"/>
    <Option value="both" displayString="Both (CSV + embedded HTML)"/>
</Parameter>
```

### Multi-select (pick several from a list)

```xml
<Parameter name="componentsToPlot" label="Components" type="multiSelect">
    <AutoGenerateOptions>quantComponents</AutoGenerateOptions>
</Parameter>
```

In Python: `props[props.Identifier == "componentsToPlot"].Input1.tolist()`.

### Integer with bounds

```xml
<Parameter name="topN" label="Top N peptides" type="integer"
           value="3" minValue="1" maxValue="100"/>
```

### Floating point

```xml
<Parameter name="mzTolerance" label="m/z window (Da)" type="floatingPoint"
           value="0.02" minValue="0.001" maxValue="1.0"/>
```

### Checkbox (boolean)

```xml
<Parameter name="includeHeader" label="Include header rows" type="checkbox"
           value="true"/>
```

Python: `props[props.Identifier == "includeHeader"].Input1.iloc[0] == "true"`.

### Text input (free-form)

```xml
<Parameter name="title" label="Report title" type="text"
           value="My report"/>
```

### File picker

```xml
<Parameter name="spikeFile" label="Spike-in reference" type="file"
           filter="CSV files|*.csv|All files|*.*"/>
```

The `filter` syntax is the Win32 file-dialog convention: `Label|wildcards|Label|wildcards|...`.

## Common full-page patterns

### Format + header toggle page

```xml
<Page title="Output options">
    <HelpText>Configure how results are exported.</HelpText>
    <Parameter name="exportFormat" label="Format" type="select"
               mapsTo="ExportFileType">
        <Option value="CSV" displayString="CSV" selected="true"/>
        <Option value="HTM" displayString="HTML"/>
    </Parameter>
    <Parameter name="exportHeader" label="Include report header"
               type="checkbox" value="true"/>
</Page>
```

### Peptide-selection + top-N page (MS1 quant reports)

```xml
<Page title="Peptide selection">
    <HelpText>How to group and select peptides when summarising to protein level.</HelpText>
    <Parameter name="selectionType" label="Group peptides by" type="select">
        <Option value="unique_sequence" displayString="Unique sequence" selected="true"/>
        <Option value="unique_mr"       displayString="Unique Mr"/>
        <Option value="unique_mz"       displayString="Unique M/Z"/>
    </Parameter>
    <Parameter name="topN" label="Top N peptides to average" type="integer"
               value="3" minValue="1" maxValue="20"/>
</Page>
```

### Contaminant-exclusion page (skipped when only one DB)

```xml
<Page title="Exclude contaminants">
    <SkipIf>
        <SkipIfParameter name="databaseCount" value="1"/>
    </SkipIf>
    <HelpText>Optionally exclude hits from a contaminant database.</HelpText>
    <Parameter name="excludeDatabase" type="select" label="Database to exclude"
               mapsTo="AnalysisInputs">
        <AutoGenerateOptions>databases</AutoGenerateOptions>
        <Option value="" displayString="(none)" selected="true"/>
    </Parameter>
</Page>
```

## Debugging wizard values

If a parameter isn't arriving in the Python script the way you expect, you don't need a debug report — **turn up Distiller's logging verbosity** and the full contents of the properties CSV are written to the Distiller log. Enable it from Distiller's logging options, re-run your wizard, and read the exact Identifier / Input1..N values Distiller generated straight from the log.

This catches typos in `name=`, missed `mapsTo` wiring, and cases where a parameter's selected default isn't what you thought.
