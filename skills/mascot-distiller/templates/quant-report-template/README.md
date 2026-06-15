# Quant report template

Copy this directory into `<WORKSPACE>/dev-reports/<your-name>/`, then:

1. Rename both files: `<your-name>.py` and `<your-name>.py.xml`.
2. Edit the XML: set `title`, `grouping`, `Description`, `Supports` flags, wizard pages.
3. Edit the `.py`: replace the placeholder banner, fill in your data extraction logic in `create_report()`.
4. Add tests under `tests/` (see the table-peptides-int-all report for a stub-msparser example).
5. Deploy: `<WORKSPACE>\scripts\deploy-report.ps1 -ReportName "<your-name>"` (elevated PowerShell).
6. Test in Distiller GUI: load a `.rov`, run from Analysis → Reports → Custom → "<your title>".

## What this template gives you for free

- **UTF-8 with BOM-safe header** (`# -*- coding: utf-8 -*-`) — avoids the `SyntaxError: Non-UTF-8 code starting with '\xff'` trap.
- **Module-level logger reference** — prevents the GC race that drops final log messages.
- **Final `mylogger_.setColsToOutput(1)` line** — keeps the logger alive until Distiller drains its event queue.
- **`__version__` and copyright banner** — required for release per the project release checklist.
- **Standard property subset extraction** — the four sets every report needs (`LoggingOptions`, `PathOptions`, `ReportHeader`, `RawFile`).
- **Component name iteration** — 0-based, the convention msparser uses.
- **`is_average` derivation** — handles the MS1/MS2/Average branching cleanly.

## What you still need to write

- The actual per-protein, per-peptide, or per-component logic in `create_report()`.
- Wizard pages in the XML — see `references/XML_SCHEMA.md` for parameter types and idioms.
- Any custom property identifiers — declare them in the XML, read them in Python via `props_csv[props_csv.Identifier == "myParamName"].Input1.iloc[0]`.

## Pre-deploy checks

See `references/CHECKLIST.md` in the skill for the full list.
