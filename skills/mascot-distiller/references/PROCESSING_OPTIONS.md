# Processing Options (`*.opt`) — schema versions and downgrading

Mascot Distiller stores per-instrument peak-detection settings as XML
`*.opt` files (a.k.a. processing options) in:

```
C:\ProgramData\Matrix Science\Mascot Distiller\processing options\
```

Each file declares its schema version on the root element:

```xml
<processingOptions xmlns="http://www.matrixscience.com/xmlns/schema/mdro_proc_opts_1"
                   majorVersion="1" minorVersion="9" ...>
```

> Strictly a Distiller / MDRO concept rather than report-development.
> Kept here because customer support frequently needs to send
> processing-options files back to sites running older Distiller versions
> that reject newer schemas.

## Schema version reference

Versions add elements; older parsers reject unknown elements. To send a
file to a customer on an older build, strip elements introduced after
their schema version and update `minorVersion=`.

| Version | Notable additions vs prior |
|---------|---------------------------|
| 1.6 | Has `<collapseMSn>` in `<timeDomainOptions>`; uses two `<peakSelectionOptions level="1"/"2">` blocks |
| 1.7+ | Drops `<collapseMSn>`; merges to a single `<peakSelectionOptions>` (level attribute optional); adds `<precursorIonMobilityGroupTol>` in `<timeDomainOptions>` |
| 1.9 | Adds Waters `<vendorOption type="11" option="bSumIMS">`; adds Sciex `<vendorOption type="12" option="MinPeakArea">` |

(Inferred by diffing files in the field — confirm against the XSD at
`http://www.matrixscience.com/xmlns/schema/mdro_proc_opts_1/mdro_proc_opts_1.xsd`
if you need authoritative ranges.)

## Downgrade script

`templates/downgrade-opt-to-1.6.ps1` produces a 1.6-tagged copy of any
`*.opt` file (default folder: standard processing-options dir):

```powershell
# every .opt file in the default folder
& "$env:USERPROFILE\.claude\skills\mascot-distiller\templates\downgrade-opt-to-1.6.ps1"

# only Ascend variants
& "$env:USERPROFILE\.claude\skills\mascot-distiller\templates\downgrade-opt-to-1.6.ps1" -Filter 'Ascend*.opt'

# single file, overwrite prior output
& "$env:USERPROFILE\.claude\skills\mascot-distiller\templates\downgrade-opt-to-1.6.ps1" `
    -Path 'C:\ProgramData\Matrix Science\Mascot Distiller\processing options\Custom.ThermoXcalibur.opt' `
    -Force
```

What it does for each input `<name>.<vendor>.opt`:

1. Sets `minorVersion="6"` on the root element.
2. Removes elements not present in 1.6:
   - `<precursorIonMobilityGroupTol>` (1.7+)
   - `<vendorOption type="11" option="bSumIMS">` (Waters, 1.9+)
   - `<vendorOption type="12" option="MinPeakArea">` (Sciex, 1.9+)
3. Writes to `<name>_1_6.<vendor>.opt` alongside the input.
4. Normalises line endings to **CRLF** and uses **UTF-8 without BOM**
   (matching what Distiller writes).
5. Skips files already containing `_1_6` in the name and files already
   at schema 1.6 or lower; will not overwrite an existing output unless
   `-Force` is passed.

## Caveats — "permissive" 1.6 output

The script only **removes** post-1.6 elements. It does not re-insert
1.6-only elements that newer files no longer carry:

- `<collapseMSn>` (was inside `<timeDomainOptions>`)
- The split `<peakSelectionOptions level="1">` / `level="2">` blocks
  (newer files use a single un-leveled block)

In practice older Distiller builds parse this leniently — they tolerate
the missing/merged elements because the XSD wasn't fully strict. If a
strict customer parser rejects the output, hand-edit the file to add a
default `<collapseMSn>false</collapseMSn>` and clone the
`<peakSelectionOptions>` block once with `level="1"` and once with
`level="2"`.

## Line endings

`Distiller` itself writes `*.opt` files with CRLF. Some files in the
processing-options folder end up LF-only after going through Linux/git
toolchains; the downgrade script always emits CRLF, so a customer
receiving the converted file gets the format Distiller expects.
