# Batch & regression testing with MDXE

`MDXE.pl` is the headless test harness for Distiller custom reports, shipped in `<WORKSPACE>/Documentation/MDXE.pl`. It drives Distiller in batch mode against a `.rov` project, runs a named report, and writes the output to disk — no GUI, no wizard interaction.

Use MDXE for:
- **Regression tests** — did my changes alter report output?
- **CI-style iteration** — run a report against a known input without reopening Distiller
- **Reproducing user-reported bugs** — capture the exact inputs and rerun deterministically

MDXE is Perl; it requires a Perl interpreter (Strawberry Perl or ActivePerl on Windows) and it talks to Distiller via the MDRO COM API. For a Python port of the same patterns, or for driving MDRO directly (peak detection, TICs, spectra, peak-list export), see the companion `mascot-mdro` skill.

## Config file format

`MDXE.pl` reads a plain-text config (`MDXEconfig.txt` is the reference example in `<WORKSPACE>/Documentation/`). The expected keys:

```
ReportName = my-report
RovFile    = C:\path\to\project.rov
OutFile    = C:\temp\my-report-output.csv
# Any wizard parameters the report needs, keyed by the Identifier from the XML:
selectionType  = unique_sequence
exportHeader   = true
excludeDatabase =
```

The wizard-parameter keys must match the `name=` of each `<Parameter>` in the `.py.xml`. Anything missing gets the `selected="true"` default from the XML.

## Running

```powershell
cd <WORKSPACE>
perl Documentation\MDXE.pl -c "Documentation\MDXEconfig.txt" -i "<input-dir>"
```

Flags:
- `-c CONFIG` — path to the config file (required)
- `-i DIR` — directory containing the `.rov` referenced by `RovFile` if it's a relative path
- `-v` — verbose logging

Exit code:
- `0` — report ran and wrote the output file
- non-zero — Distiller reported an error (see the log output)

## One-shot test helper

Wrap the invocation so it's a single command for the common case:

```bash
#!/usr/bin/env bash
# test-report.sh — run a report against a known .rov and show the diff
set -euo pipefail

REPORT="${1:?Usage: test-report.sh <report-name> <rov-file> [expected-output]}"
ROV="${2:?Need .rov path}"
EXPECTED="${3:-}"
OUT="/tmp/${REPORT}-$(date +%s).csv"

cat > /tmp/mdxe-config.txt <<EOF
ReportName = ${REPORT}
RovFile    = ${ROV}
OutFile    = ${OUT}
EOF

perl "<WORKSPACE>/Documentation/MDXE.pl" \
  -c /tmp/mdxe-config.txt \
  -i "$(dirname "$ROV")"

echo "Output: $OUT"

if [[ -n "$EXPECTED" ]]; then
    diff -u "$EXPECTED" "$OUT" && echo "PASS" || { echo "DIFF DETECTED"; exit 1; }
fi
```

Usage:

```bash
./test-report.sh top-3 /msdata/ref/silac-proj.rov /msdata/ref/top-3.expected.csv
```

## What to include in a regression set

A minimal regression fixture has:

1. **One `.rov` per quantitation protocol** the report supports (Average, Precursor, Replicate, Reporter, Multiplex).
2. **One single-file `.rov`** (for reports that touch queries — multifile is the crash-prone case).
3. **One multifile `.rov`** with ≥ 3 sub-files (to catch the access-violation trap from SKILL.md gotcha #10).
4. **One `.rov` with an empty result set** (rare but informative — most reports crash because they assume at least one protein).
5. **Expected CSV/HTML output** for each, captured after a known-good run and checked into the repo.

## Diffing strategies

CSV diffs are noisy when row order isn't guaranteed. Pre-sort before diffing:

```bash
sort expected.csv > /tmp/a.csv
sort actual.csv   > /tmp/b.csv
diff -u /tmp/a.csv /tmp/b.csv
```

For floating-point columns (intensities, ratios), exact-match diffs break on platform-specific rounding. Use tolerance-aware comparison:

```bash
python -c "
import sys, csv, math
def rows(p): return list(csv.DictReader(open(p, encoding='utf-8')))
a, b = rows(sys.argv[1]), rows(sys.argv[2])
assert len(a) == len(b), f'Row count differs: {len(a)} vs {len(b)}'
for i, (ra, rb) in enumerate(zip(a, b)):
    for k in ra:
        va, vb = ra[k], rb[k]
        try:
            fa, fb = float(va), float(vb)
            assert math.isclose(fa, fb, rel_tol=1e-4), f'row {i} col {k}: {fa} != {fb}'
        except ValueError:
            assert va == vb, f'row {i} col {k}: {va!r} != {vb!r}'
print('OK')
" expected.csv actual.csv
```

## What MDXE can't test

- **Wizard UI behaviour** — `SkipIf` conditions, parameter validation, dropdown population. Test manually in the Distiller GUI.
- **Property-page layouts** — only relevant if the report uses `ProcOptsSheet`; requires a desktop.
- **Long-running behaviour** — MDXE times out by default. For slow reports, split into unit-testable helpers and test each separately.
- **Access violations** — if a report triggers a C++ crash, Perl sees a broken pipe or missing output, not the actual error. Check the Distiller log at `%LOCALAPPDATA%\Matrix Science\Mascot Distiller\` for diagnostics.

## CI considerations

- **Runner must be Windows** with Distiller installed. Linux and macOS runners can't drive MDRO.
- **No headless desktop** — COM + instrument DLLs need a real interactive session. Use a self-hosted Windows runner with auto-logon.
- **License** — Distiller requires a valid licence. Shared runners must have a licence that covers automated use; check with Matrix Science before deploying to CI.
- **Artefacts** — persist both the output CSV and the Distiller log from each run. Logs are the first place to look when a test fails inexplicably.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `MDXE.pl` returns quickly with no output file | Report name didn't match deployed filename — deploy first |
| `No Results Parameters Supplied` in log | `.rov` has no quantitation; use an `.rov` produced from a quant protocol |
| `ec=-1073741819` or process disappears | C++ access violation — usually multifile query-numbering bug |
| `SyntaxError: Non-UTF-8 code starting with '\xff'` | `.py` is UTF-16; convert to UTF-8 (see CHECKLIST.md) |
| Output file exists but is empty | Report wrote to `save_path` before filling rows; check `PathOptions.Input2` handling |
| `Cannot find MascotDistiller.exe` | `<DISTILLER_INSTALL>` incorrect in PATH or registry; see SETUP.md |
