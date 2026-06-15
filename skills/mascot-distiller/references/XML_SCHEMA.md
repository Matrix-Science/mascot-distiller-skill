# XML Report Definition Schema Reference

Complete reference for `distiller_report_definition_1.xsd` - the XML schema for Mascot Distiller report definitions.

## Root Element

```xml
<?xml version="1.0" encoding="utf-8"?>
<DistillerReport
    majorVersion="1"
    minorVersion="0"
    title="Report Display Name"
    grouping=""
    xmlns="http://www.matrixscience.com/xmlns/schema/distiller_report_definition_1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.matrixscience.com/xmlns/schema/distiller_quantitation_2
        distiller_report_definition_1.xsd">
```

### Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `majorVersion` | Yes | Schema major version (always `"1"`) |
| `minorVersion` | Yes | Schema minor version (always `"0"`) |
| `title` | Yes | Report name in Distiller GUI |
| `grouping` | Yes | Menu folder path. **Convention: always use `""` (empty string)** — Distiller files empty-grouping reports under **Analysis → Reports → Custom** automatically. All reports in the reference `reports/` directory (top-3, proteins_ibaq, table-peptides-int-all, etc.) use `grouping=""`. Setting `grouping="Custom"` creates a nested `Custom/` folder *inside* Custom (i.e. the report gets buried) and can cause it to not appear at all on some Distiller builds. Use nested paths like `"Custom/Intensity"` only when you deliberately want a sub-folder. |

---

## Description Element

```xml
<Description>Calculate protein component intensity using top-3 method</Description>
```

Appears as tooltip in Distiller GUI when hovering over the report name.

---

## Supports Element

Declares which quantitation protocols the report can handle.

```xml
<Supports
    average="true"
    precursor="true"
    replicate="true"
    reporter="true"
    multiplex="true"/>
```

Set any to `"false"` to hide the report when that protocol is active. The report only appears in Distiller when the current project's quantitation method matches at least one supported protocol.

---

## Inputs Element

Contains `ReportConfiguration` and `Wizard` sections.

```xml
<Inputs>
    <ReportConfiguration>
        <!-- Fixed configuration parameters -->
    </ReportConfiguration>
    <Wizard>
        <!-- Interactive wizard pages -->
    </Wizard>
</Inputs>
```

---

## ReportConfiguration

Defines fixed parameter values passed to the report, not shown in the wizard.

```xml
<ReportConfiguration>
    <!-- Export format - tells Distiller what output type to expect -->
    <Parameter name="exportFormat" label="Format" value="CSV"
               type="text" mapsTo="ExportFileType"/>

    <!-- Variable substitution from Distiller -->
    <Parameter name="databaseCount" label="no databases"
               type="integer" value="@{DatabaseNames.Count}"/>
</ReportConfiguration>
```

### Parameter attributes (ReportConfiguration)

| Attribute | Description |
|-----------|-------------|
| `name` | Identifier used in Properties CSV |
| `label` | Human-readable label |
| `value` | Fixed value or Distiller variable (`@{...}`) |
| `type` | Data type: `text`, `integer`, `floatingPoint`, etc. |
| `mapsTo` | Maps to a standard Distiller property identifier |

### Distiller variable substitution

Use `@{VariableName}` syntax to inject Distiller runtime values:
- `@{DatabaseNames.Count}` - Number of databases in the search

---

## Wizard Element

Defines interactive wizard pages shown to the user before report execution.

```xml
<Wizard>
    <WelcomeText>Introduction text on first page.</WelcomeText>

    <Page title="Page 1 Title">
        <!-- Parameters -->
    </Page>

    <Page title="Page 2 Title">
        <!-- Parameters -->
    </Page>

    <CompletionText>Click 'Finish' to run the report.</CompletionText>
</Wizard>
```

### WelcomeText

Shown on the first wizard page. No user inputs, just informational text.

### CompletionText

Shown on the final wizard page with the "Finish" button.

---

## Page Element

Each `<Page>` becomes a wizard step with user inputs.

```xml
<Page title="Report Options">
    <HelpText>Instructions shown above the parameters.</HelpText>

    <Parameter name="paramName" label="Display Label" type="select">
        <Option value="val1" displayString="Option 1" selected="true"/>
        <Option value="val2" displayString="Option 2"/>
    </Parameter>
</Page>
```

### Conditional Page Skipping

```xml
<Page title="Database Selection">
    <SkipIf>
        <SkipIfParameter name="databaseCount" value="1"/>
    </SkipIf>
    <!-- Page is skipped when databaseCount equals 1 -->
</Page>
```

---

## Parameter Types

### select (dropdown)

```xml
<Parameter name="selectionType" label="Selection type" type="select">
    <Option value="unique_sequence" displayString="Unique sequence" selected="true"/>
    <Option value="unique_mr" displayString="Unique Mr"/>
    <Option value="unique_mz" displayString="Unique M/Z"/>
</Parameter>
```

### radio (radio buttons)

```xml
<Parameter name="exportHeader" label="Export header" type="radio">
    <Option value="True" displayString="True" selected="true"/>
    <Option value="False" displayString="False"/>
</Parameter>
```

### text (free text input)

```xml
<Parameter name="customLabel" label="Report label" type="text">
    <Option value="default text" displayString="Default Value" selected="true"/>
</Parameter>
```

### integer

```xml
<Parameter name="topN" label="Number of peptides" type="integer">
    <Option value="3" displayString="3" selected="true"/>
</Parameter>
```

### floatingPoint

```xml
<Parameter name="threshold" label="Score threshold" type="floatingPoint">
    <Option value="0.05" displayString="0.05" selected="true"/>
</Parameter>
```

### checkbox

```xml
<Parameter name="includeDecoys" label="Include decoy hits" type="checkbox">
    <Option value="True" displayString="Include"/>
</Parameter>
```

### multiSelect

```xml
<Parameter name="components" label="Components" type="multiSelect">
    <Option value="light" displayString="Light"/>
    <Option value="heavy" displayString="Heavy" selected="true"/>
</Parameter>
```

### file

```xml
<Parameter name="inputFile" label="Additional data file" type="file">
</Parameter>
```

### autocomplete

```xml
<Parameter name="proteinName" label="Protein" type="autocomplete">
</Parameter>
```

---

## Auto-Generated Options

Distiller can automatically populate dropdown options from project metadata.

```xml
<Parameter name="excludeDatabase" type="select" label="Database"
           mapsTo="AnalysisInputs">
    <AutoGenerateOptions>databases</AutoGenerateOptions>
    <Option value="" displayString="" selected="true"/>
</Parameter>
```

The `mapsTo` attribute maps the selected value to a standard Distiller property identifier (e.g., `AnalysisInputs`).

---

## Option Attributes

| Attribute | Description |
|-----------|-------------|
| `value` | Value passed to Python script via Properties CSV |
| `displayString` | Text shown to user in the GUI |
| `selected` | Set to `"true"` for default selection |

---

## Accessing Wizard Parameters in Python

Parameters defined in the XML are accessible in the Properties CSV by their `name`:

```xml
<!-- In XML -->
<Parameter name="selectionType" label="Selection type" type="select">
    <Option value="unique_sequence" displayString="Unique sequence" selected="true"/>
</Parameter>
```

```python
# In Python
props_csv = pandas.read_csv(propsPath, delimiter=',', header=0,
                            keep_default_na=False, quotechar="\"")
props_selection = props_csv[props_csv.Identifier == 'selectionType']
value = props_selection.Input1.iloc[0]  # "unique_sequence"
```

---

## Complete Example: top-3.py.xml

```xml
<?xml version="1.0" encoding="utf-8"?>
<DistillerReport majorVersion="1" minorVersion="0"
    title="Top 3 protein intensity" grouping=""
    xmlns="http://www.matrixscience.com/xmlns/schema/distiller_report_definition_1"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.matrixscience.com/xmlns/schema/distiller_quantitation_2
        distiller_report_definition_1.xsd">

    <Description>Calculate protein component intensity from the average
        of the top 3 most intense peptide matches</Description>

    <Supports average="true" precursor="true" replicate="true"
             reporter="true" multiplex="true"/>

    <Inputs>
        <ReportConfiguration>
            <Parameter name="exportFormat" label="Format" value="CSV"
                       type="text" mapsTo="ExportFileType"/>
            <Parameter name="databaseCount" label="no databases"
                       type="integer" value="@{DatabaseNames.Count}"/>
        </ReportConfiguration>

        <Wizard>
            <WelcomeText>This report generates a CSV file containing protein
                component intensity values calculated using the top-3 method
            </WelcomeText>

            <Page title="Peptide selection criteria">
                <HelpText>The selection type determines grouping criteria
                </HelpText>
                <Parameter name="selectionType" label="Selection type"
                           type="select">
                    <Option value="unique_sequence"
                            displayString="Unique sequence" selected="true"/>
                    <Option value="unique_mr" displayString="Unique Mr"/>
                    <Option value="unique_mz" displayString="Unique M/Z"/>
                </Parameter>
            </Page>

            <Page title="Exclude contaminants database matches?">
                <HelpText>Choose a contaminants database to exclude</HelpText>
                <SkipIf>
                    <SkipIfParameter name="databaseCount" value="1"/>
                </SkipIf>
                <Parameter name="excludeDatabase" type="select"
                           label="Contaminants database"
                           mapsTo="AnalysisInputs">
                    <AutoGenerateOptions>databases</AutoGenerateOptions>
                    <Option value="" displayString="" selected="true"/>
                </Parameter>
            </Page>

            <Page title="Output report header?">
                <HelpText>Include header information?</HelpText>
                <Parameter name="exportHeader"
                           label="Export header information" type="radio">
                    <Option value="True" displayString="True"
                            selected="true"/>
                    <Option value="False" displayString="False"/>
                </Parameter>
            </Page>

            <CompletionText>Click 'Finish' to run the report.</CompletionText>
        </Wizard>
    </Inputs>
</DistillerReport>
```
