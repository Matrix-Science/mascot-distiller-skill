# Setup: Locating the Workspace and Distiller Install

This file gives concrete commands for resolving the two paths the `mascot-distiller` skill needs:

- `<WORKSPACE>` — the local checkout of the report-building project
- `<DISTILLER_INSTALL>` — the Mascot Distiller installation directory

The skill's main `SKILL.md` describes the resolution order; this file gives the actual commands. Use these in order until one returns a valid path, then verify and save to project memory.

---

## 1. Check project memory

```bash
# Check whether paths have already been resolved for this project
ls "$CLAUDE_PROJECT_DIR/memory/mascot_distiller_paths.md"
```

If the file exists, parse the two values from it and skip everything below. If the recorded paths don't pass the verification check (see §5), treat them as stale and re-discover.

---

## 2. Check environment variables

```bash
# In bash / Git Bash
echo "${MASCOT_DISTILLER_WORKSPACE:-(unset)}"
echo "${MASCOT_DISTILLER_INSTALL:-(unset)}"
```

```powershell
# In PowerShell
$env:MASCOT_DISTILLER_WORKSPACE
$env:MASCOT_DISTILLER_INSTALL
```

---

## 3. Probe defaults — Distiller install directory

### 3a. Standard Program Files location

Distiller is 64-bit only — the last 32-bit release predates the Python reports system, so any valid dev environment has a 64-bit install.

```bash
test -d "/c/Program Files/Matrix Science/Mascot Distiller" && \
  echo "/c/Program Files/Matrix Science/Mascot Distiller"
```

### 3b. Windows registry

Mascot Distiller's installer writes its install directory to the registry:

```powershell
Get-ItemProperty -Path "HKLM:\SOFTWARE\Matrix Science\Mascot Distiller" `
                 -Name "InstallDir" -ErrorAction SilentlyContinue
```

From bash, invoke via `powershell -NoProfile -Command "..."`.

### 3c. Verify

A directory is a valid `<DISTILLER_INSTALL>` only if it contains BOTH:
- `MascotDistiller.exe`
- a `reports\` subdirectory with at least one `.py` file (e.g. `proteins.py`)

```bash
INSTALL="/c/Program Files/Matrix Science/Mascot Distiller"
test -f "$INSTALL/MascotDistiller.exe" && \
  test -d "$INSTALL/reports" && \
  ls "$INSTALL/reports/"*.py >/dev/null 2>&1 && \
  echo "OK: $INSTALL"
```

---

## 4. Probe defaults — Workspace

There is no canonical install location for the report-building workspace; it's wherever the user keeps their development copy. Heuristics:

```bash
# Is the current directory the workspace?
test -d "./reports" && test -d "./dev-reports" && test -d "./msparser" && \
  echo "$(pwd)"

# Is a parent directory the workspace?
git rev-parse --show-toplevel 2>/dev/null
```

Common locations to ask the user about (in order):
1. `~/dev/Matrix Science/Mascot Distiller report building`
2. `~/dev/Mascot Distiller report building`
3. `~/source/Mascot Distiller report building`
4. `~/Documents/Mascot Distiller report building`
5. Anywhere they've previously mentioned in conversation, or where the conversation's working directory sits

### 4a. Verify

A directory is a valid `<WORKSPACE>` only if it contains:
- `reports/` (with `LoadQuantitation.py`, `WriteReports.py`, `CreateQuantDataFrames.py`)
- `dev-reports/`
- `msparser/` (the SDK)
- `scripts/` (with `deploy-report.ps1`)

```bash
WS="$1"
for d in reports dev-reports msparser scripts; do
  test -d "$WS/$d" || { echo "Missing: $WS/$d"; exit 1; }
done
test -f "$WS/reports/LoadQuantitation.py" && \
  test -f "$WS/scripts/deploy-report.ps1" && \
  echo "OK: $WS"
```

---

## 5. Save to project memory

Once both paths are resolved AND verified, write `mascot_distiller_paths.md` in the project's memory directory:

```markdown
---
name: Mascot Distiller paths
description: Workspace and install paths for the mascot-distiller skill on this machine
type: reference
---

- `<WORKSPACE>` = `/absolute/path/to/Mascot Distiller report building`
- `<DISTILLER_INSTALL>` = `C:\Program Files\Matrix Science\Mascot Distiller`

Verified YYYY-MM-DD by checking that `<WORKSPACE>` contains
`reports/`, `dev-reports/`, `msparser/`, `scripts/` and that `<DISTILLER_INSTALL>`
contains `MascotDistiller.exe` and `reports\`.
```

Then add to `MEMORY.md`:

```
- [Mascot Distiller paths](mascot_distiller_paths.md) — workspace and install dir for this machine
```

---

## 6. SDK location

The msparser SDK ships **inside** the workspace at `<WORKSPACE>/msparser/`. There are two pieces:

| Subdirectory | Purpose |
|--------------|---------|
| `msparser/python36_and_later/` | The importable Python module (`msparser.py` + `_msparser.pyd`). Distiller's embedded Python loads this automatically when running deployed reports. |
| `msparser/example_python/` | 30+ reference scripts for the SDK API. Read-only; use as documentation. |
| `msparser/vs2015/include/` | C++ headers — useful for looking up exact method signatures the SWIG wrapper exposes (e.g. `ms_xic.hpp`). |
| `msparser/config/` | XSD schemas (`quantitation_2.xsd`, `unimod_2.xsd`, etc.) — needed when loading `.dat` files. |

For ad-hoc Python testing **outside** Distiller, point Python at the SDK:

```bash
# Bash
export PYTHONPATH="<WORKSPACE>/msparser/python36_and_later:$PYTHONPATH"
python -c "import msparser; print(msparser.ms_mascotresfilebase.__doc__[:200])"
```

```powershell
# PowerShell
$env:PYTHONPATH = "<WORKSPACE>\msparser\python36_and_later;$env:PYTHONPATH"
python -c "import msparser; print(msparser.ms_mascotresfilebase.__doc__[:200])"
```

If the user maintains a separate copy of msparser elsewhere (e.g. a network share or vendored SDK release), record that as a third path in `mascot_distiller_paths.md`:

```
- `<MSPARSER_SDK>` = `C:\path\to\standalone\msparser`  (optional override)
```

and prefer it over `<WORKSPACE>/msparser/` when both exist.

---

## 7. Non-Windows hosts

Distiller itself is Windows-only, so there is no `<DISTILLER_INSTALL>` on macOS or Linux. The skill's report-development workflow still works (reports are plain Python), but:

- Deployment scripts (`scripts/deploy-report.ps1`) are PowerShell-only.
- GUI testing requires a Windows host with Distiller installed.
- The `msparser` SDK has Linux builds (under `msparser/gcc*/` if present), but the embedded Python in Distiller is the canonical target.

On non-Windows, save only `<WORKSPACE>` to memory and note `<DISTILLER_INSTALL>` as `(none — non-Windows host)`.
