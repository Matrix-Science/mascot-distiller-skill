#!/usr/bin/env bash
# lint-report.sh — pre-deploy sanity checks for a Distiller custom report.
#
# Runs all the checks from references/CHECKLIST.md in one pass. Exit code is
# the number of failures; warnings don't affect exit code.
#
# Usage:
#     ./lint-report.sh <WORKSPACE>/dev-reports/<name>/<name>
#
# (Pass the basename without the .py extension.)
#
# Copy into <WORKSPACE>/scripts/ or wherever else is convenient. Works from
# Git Bash on Windows and bash/zsh on macOS/Linux.

set -u

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path-to-report-basename>" >&2
    echo "Example: $0 ../dev-reports/my-report/my-report" >&2
    exit 2
fi

BASE="$1"
PY="${BASE}.py"
XML="${BASE}.py.xml"
FAILS=0
WARNS=0

fail() { echo "FAIL: $*" >&2; FAILS=$((FAILS + 1)); }
warn() { echo "WARN: $*" >&2; WARNS=$((WARNS + 1)); }
pass() { echo "PASS: $*"; }

# 1. Both files exist with matching basename
[[ -f "$PY"  ]] || fail "missing $PY"
[[ -f "$XML" ]] || fail "missing $XML"
[[ $FAILS -gt 0 ]] && { echo ""; echo "Aborting: required files missing."; exit $FAILS; }
pass "both .py and .py.xml exist"

# 2. File encoding is UTF-8 (or ASCII, which is a valid subset)
ENC=$(file -b "$PY" 2>/dev/null || echo "unknown")
if echo "$ENC" | grep -qE "UTF-8|ASCII"; then
    pass "encoding: $ENC"
else
    fail "encoding is $ENC — convert to UTF-8 (see CHECKLIST.md)"
fi

# 3. Python parses
if python -m py_compile "$PY" 2>/tmp/lint-err; then
    pass "python parses"
    rm -f /tmp/lint-err
else
    fail "python parse error:"
    cat /tmp/lint-err >&2
fi

# 4. XML is well-formed
if command -v xmllint >/dev/null 2>&1; then
    if xmllint --noout "$XML" 2>/tmp/lint-err; then
        pass "xml is well-formed"
    else
        fail "xml malformed:"
        cat /tmp/lint-err >&2
    fi
elif command -v python >/dev/null 2>&1; then
    if python -c "import xml.etree.ElementTree as ET; ET.parse('$XML')" 2>/tmp/lint-err; then
        pass "xml is well-formed (python fallback)"
    else
        fail "xml malformed:"
        cat /tmp/lint-err >&2
    fi
else
    warn "no XML validator available — skipping xml check"
fi

# 5. Module-level logger + GC-prevention line
if grep -qE "^[[:space:]]*mylogger_? *= *msparser\.ms_stdout_logger" "$PY"; then
    pass "module-level logger present"
else
    fail "no module-level 'mylogger_ = msparser.ms_stdout_logger()' — see gotcha #1"
fi

if grep -qE "setColsToOutput\(1\)" "$PY"; then
    pass "logger GC-prevention line present"
else
    fail "missing 'mylogger_.setColsToOutput(1)' at end of main() — see gotcha #1"
fi

# 6. No hard-coded user-specific paths
if grep -nE "C:\\\\Users\\\\[a-zA-Z]+|/Users/[a-zA-Z]+|/home/[a-zA-Z]+" "$PY" > /tmp/lint-err; then
    fail "hard-coded user paths found:"
    cat /tmp/lint-err >&2
else
    pass "no hard-coded user paths"
fi
rm -f /tmp/lint-err

# 7. grouping="" in XML root (not "Custom" — see gotcha #12)
if grep -qE 'grouping="Custom"' "$XML"; then
    fail 'grouping="Custom" in XML root — use grouping="" (see SKILL.md gotcha #12)'
elif grep -qE 'grouping=""' "$XML"; then
    pass 'grouping is empty (report will appear under Analysis → Reports → Custom)'
else
    warn "grouping attribute not found or has unusual value — double-check SKILL.md gotcha #12"
fi

# 8. mapsTo="AnalysisInputs" parameters use magic names (see gotcha #13)
if grep -q 'mapsTo="AnalysisInputs"' "$XML"; then
    if grep -qE 'name="(signifThreshold|filterSignif|maxRatio|useProtein|excludeDatabase)"[^>]*mapsTo="AnalysisInputs"' "$XML" \
       || grep -qE 'mapsTo="AnalysisInputs"[^>]*name="(signifThreshold|filterSignif|maxRatio|useProtein|excludeDatabase)"' "$XML"; then
        pass 'mapsTo="AnalysisInputs" uses a magic parameter name'
    else
        fail 'mapsTo="AnalysisInputs" with non-magic parameter name — Distiller will silently drop the value (see SKILL.md gotcha #13)'
        grep -nE 'mapsTo="AnalysisInputs"' "$XML" >&2
    fi
fi

# 9. Copyright banner (release warn, not hard fail)
if head -10 "$PY" | grep -qi "Matrix Science"; then
    pass "copyright banner present"
else
    warn "no 'Matrix Science' banner in first 10 lines (required for release)"
fi

# 10. Explicit __version__
if grep -qE '^__version__\s*=' "$PY"; then
    pass "__version__ defined"
else
    warn "no __version__ defined (required for release)"
fi

# 11. Debug code markers
DEBUG_HITS=$(grep -cnE "TODO|FIXME|XXX|HACK|^[[:space:]]*print\(|breakpoint\(\)" "$PY" || true)
if [[ "$DEBUG_HITS" -gt 0 ]]; then
    warn "$DEBUG_HITS debug markers (TODO/FIXME/print/breakpoint) — audit before release"
    grep -nE "TODO|FIXME|XXX|HACK|^[[:space:]]*print\(|breakpoint\(\)" "$PY" >&2
else
    pass "no debug markers"
fi

echo ""
if [[ $FAILS -eq 0 ]]; then
    echo "Summary: OK — ${WARNS} warning(s)"
    exit 0
else
    echo "Summary: ${FAILS} failure(s), ${WARNS} warning(s)"
    exit $FAILS
fi
