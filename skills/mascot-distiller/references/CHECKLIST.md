# Pre-deploy and release checklist

Run before copying a custom report to `<DISTILLER_INSTALL>\reports\`. Most of these catch failure modes that cost an hour to diagnose in production.

## Pre-deploy (every time you run `deploy-report.ps1`)

### 1. File encoding is UTF-8 (no BOM)

```bash
file "<WORKSPACE>/dev-reports/<name>/<name>.py"
# Want: ASCII text, or UTF-8 Unicode text
# Bad:  UTF-16 little-endian — Distiller's Python errors with
#       "SyntaxError: Non-UTF-8 code starting with '\xff'"
```

If wrong, convert:
```python
with open("<name>.py", "r", encoding="utf-16-le") as f:
    content = f.read().lstrip("\ufeff")
with open("<name>.py", "w", encoding="utf-8") as f:
    f.write(content)
```

### 2. Both files exist with matching basename

```bash
ls "<WORKSPACE>/dev-reports/<name>/<name>.py" \
   "<WORKSPACE>/dev-reports/<name>/<name>.py.xml"
```

### 3. XML validates against the schema

```powershell
# Quick well-formedness check
[xml](Get-Content "<WORKSPACE>\dev-reports\<name>\<name>.py.xml") | Out-Null
# Returns silently on success; throws on malformed XML.
```

For full schema validation, load against `<WORKSPACE>\Documentation\distiller_report_definition_1.xsd` in any XML validator.

### 4. Python is parseable

```bash
python -m py_compile "<WORKSPACE>/dev-reports/<name>/<name>.py"
# Compiles to .pyc on success; prints a SyntaxError otherwise.
# Distiller ships Python 3.6+ — avoid 3.10+ syntax (match statements, etc.)
```

### 5. Logger pattern is correct

Grep the script for the GC-prevention pattern:

```bash
grep -E "^mylogger_? *=|setColsToOutput\(1\)" "<name>.py"
# Want both: a module-level "mylogger_ = msparser.ms_stdout_logger()"
# AND a "setColsToOutput(1)" near the end of main().
# Missing either causes intermittent log-event drops or hangs.
```

### 6. No hard-coded user paths

```bash
grep -nE "C:\\\\Users\\\\[a-z]+|/Users/[a-z]+" "<name>.py"
# Should return nothing. Use props_csv values, not hard-coded paths.
```

### 7. `grouping=""` in the XML root element

```bash
grep -E 'grouping="[^"]*"' "<name>.py.xml"
# Want: grouping=""
# Bad:  grouping="Custom"  — nests the report in Custom/Custom/ and on some
#       Distiller builds hides it entirely. See SKILL.md gotcha #12.
```

### 8. `mapsTo="AnalysisInputs"` parameters use one of the five magic names

If any wizard parameter has `mapsTo="AnalysisInputs"`, check its `name=` is one of `signifThreshold`, `filterSignif`, `maxRatio`, `useProtein`, `excludeDatabase`. Any other name means Distiller silently drops the user's choice. See SKILL.md gotcha #13.

```bash
grep -nE 'mapsTo="AnalysisInputs"' "<name>.py.xml"
# For each hit, confirm the `name=` attribute matches one of the five above.
```

## Release checklist (cutting a versioned build)

In addition to all the pre-deploy checks above:

### 9. Copyright banner present

```bash
head -10 "<name>.py" | grep -i "Matrix Science"
```

### 10. Explicit `__version__`

```bash
grep -E '^__version__\s*=' "<name>.py"
```

### 11. No experimental debug code

```bash
grep -nE "TODO|FIXME|XXX|HACK|print\(|breakpoint\(\)" "<name>.py"
# Audit each hit. print() statements bypass the Distiller log monitor —
# use msparser.ms_loggingmonitor.getDefaultMonitor().logMessage(...) instead.
```

### 12. Tests pass

```bash
cd "<WORKSPACE>/dev-reports/<name>" && python -m pytest tests/ -v
# Tests use stub-msparser; they cannot catch C++ access violations.
# See critical gotcha #10 in SKILL.md for the multifile crash pattern.
```

### 13. Distiller integration test on real data

Stub tests are *not enough*. Always run at least one full Distiller batch job:
- Open a `.rov` representative of the data the report targets.
- Run the report through the wizard end-to-end.
- Check the output file opens and contains expected columns/values.
- Watch the Distiller log pane for warnings or errors.

### 14. Multifile project test (if applicable)

If the report touches `getPeptide`, `getQuery`, or any per-file iteration, also test against a multifile `.rov`:
- Verify no access violation (`ec=-1073741819`) appears in the log.
- Confirm queries from different sub-files appear correctly attributed.
- For quant reports, confirm each component maps to exactly one expected run (no reuse, none dropped) and that matches aren't duplicated once per file (see SKILL.md gotchas #14–#15).

## One-shot Bash audit

```bash
F="<WORKSPACE>/dev-reports/<name>/<name>"
file "$F.py" | grep -q "UTF-8\|ASCII" || echo "FAIL: encoding"
test -f "$F.py.xml"                   || echo "FAIL: xml missing"
python -m py_compile "$F.py" 2>&1 | grep -v "^$" && echo "FAIL: parse"
grep -q "setColsToOutput(1)" "$F.py"  || echo "FAIL: logger GC"
grep -q 'grouping=""' "$F.py.xml"     || echo "FAIL: grouping should be empty string"
if grep -q 'mapsTo="AnalysisInputs"' "$F.py.xml"; then
    grep -qE 'name="(signifThreshold|filterSignif|maxRatio|useProtein|excludeDatabase)"[^>]*mapsTo="AnalysisInputs"' "$F.py.xml" \
        || echo "FAIL: mapsTo=AnalysisInputs with non-magic parameter name (see gotcha #13)"
fi
grep -q "^__version__" "$F.py"        || echo "WARN: no __version__"
grep -q "Matrix Science" "$F.py"      || echo "WARN: no copyright"
echo "Checks complete."
```
