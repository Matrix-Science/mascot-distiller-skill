# `.rov` Distiller Project File Format

The per-raw-file Distiller projects (`*.rov`, including the
`dc6ac4f...___<raw>.raw.-1.rov` cache files Distiller writes inside a
project's `.files/` directory) are **ZIP archives** containing several
named streams. Knowing the layout is useful when:

- a custom report needs more context than msparser exposes (peak
  detection options, original Mascot search submission, original
  Distiller version that produced the project);
- you want to verify "does this `.rov` actually have a search result?"
  without running the full report harness;
- you're debugging a project that opens fine in Distiller but
  misbehaves when `LoadQuantitation.DoLoad()` reads it.

## Stream layout

Inside the ZIP you'll typically see:

| Stream name | Type | Purpose |
|---|---|---|
| `mdro_proc_opts` | XML | Distiller peak detection options. Same schema as the `*.opt` files documented in [PROCESSING_OPTIONS.md](PROCESSING_OPTIONS.md) — `<processingOptions xmlns="http://www.matrixscience.com/xmlns/schema/mdro_proc_opts_1">`. Not exposed via msparser; parse the XML directly. |
| `mdro_search_status` | XML (small) | Search task manifest — `taskId`, search title, Mascot server URL, results-file path, submit time, status message. Useful as a quick "what did this project search?" probe. |
| `mdro_search_status+N` (N>=1) | binary | The actual Mascot **`.dat` results file** in MIME multipart format. Use msparser's `ms_mascotresfilebase.createResfile()` to read it. |
| `mdro_pkl` | binary | Peak list (typically the largest stream by far). |
| `mdro_project_<UUID>` | XML | Project metadata: Distiller version (`mdroVersion`), experiment type, the full stream list. |
| `rover_data`, `rover_data+N` | XML / binary | Distiller's main project XML (`<distillerProject>`) plus segment indices. Carries the URL-encoded quantitation method and a snapshot of the relevant `mascot.dat` databases section. |

## msparser cannot open a `.rov` natively

Three approaches that **don't work**:

| Attempted | Result |
|---|---|
| `ms_mascotresfilebase.createResfile(rov_path)` | "Invalid results file format - missing or corrupt headers" — it reads the ZIP magic bytes as a malformed `.dat` header |
| `ms_distiller_data.loadXmlFile(schema_dir, rov_path)` | "XML library failure: invalid byte at position 1" — it tries to parse the ZIP as raw XML |
| `ms_distiller_data.loadXmlFile(schema_dir, extracted_rover_data)` | On at least some builds: "schemaLocation does not contain namespace-location pairs" — a strict schema-validation quirk; not the path to recommend |

So the practical pattern is **always**: open the ZIP yourself, extract
the relevant stream, then hand it to msparser.

## Pattern: read search params from a `.rov`

```python
import os, sys, tempfile, zipfile
sys.path.insert(0, r"<MSPARSER_SDK>/python36_and_later")
import msparser

def open_rov_resfile(rov_path):
    """Extract the embedded Mascot .dat from a Distiller .rov and return
    (resfile, tempdir). Caller cleans up tempdir."""
    with zipfile.ZipFile(rov_path) as z:
        candidates = sorted(
            n for n in z.namelist()
            if n.startswith("mdro_search_status+")
        )
        if not candidates:
            return None, None
        tempdir = tempfile.mkdtemp(prefix="rov_")
        out = os.path.join(tempdir, "results.dat")
        with z.open(candidates[0]) as src, open(out, "wb") as dst:
            while chunk := src.read(1 << 20):
                dst.write(chunk)

    res = msparser.ms_mascotresfilebase.createResfile(out)
    if not res.isValid():
        return None, tempdir
    return res, tempdir
```

After that, every standard msparser accessor works:

```python
res, tmp = open_rov_resfile(rov_path)
try:
    print("anyMSMS         :", res.anyMSMS())
    print("anyFastaMatches :", res.anyFastaMatches())
    print("hasQuantitation :", res.hasQuantitation())
    p = res.params()
    print("Enzyme          :", p.getCLE())
    print("Fixed mod 1     :", p.getFixedModsName(1))   # 1-based
    print("Variable mod 1  :", p.getVarModsName(1))     # 1-based
finally:
    res = None  # drop msparser handle before deleting the temp .dat
    import shutil; shutil.rmtree(tmp, ignore_errors=True)
```

The `mascot-parser` skill's "any/has/is" accessor list (`anyMSMS`,
`anyPMF`, `anySQ`, `anyFastaMatches`, `anySpectralLibraryMatches`,
`anyErrorTolerantMatches`, `anyCrosslinkedMatches`, `hasQuantitation`,
`hasEnzyme`) all work normally on the resfile returned here.

## Pattern: read peak detection options from a `.rov`

`mdro_proc_opts` is plain XML — no msparser involved:

```python
import zipfile
from xml.etree import ElementTree as ET

with zipfile.ZipFile(rov_path) as z:
    with z.open("mdro_proc_opts") as f:
        root = ET.fromstring(f.read())

# Walk MS1 / MS2 / time-domain / vendor blocks
for child in root:
    print(child.tag, child.attrib, [c.tag for c in child])
```

Schema versions and downgrade rules: see
[PROCESSING_OPTIONS.md](PROCESSING_OPTIONS.md). The stream embedded in
the `.rov` follows the same `mdro_proc_opts_1` schema as the standalone
`*.opt` files in
`C:\ProgramData\Matrix Science\Mascot Distiller\processing options\`.

## Pattern: read the quantitation method

The quant method lives URL-encoded inside an attribute on
`<MascotImportOptions>` in `rover_data`:

```python
import urllib.parse
import zipfile
from xml.etree import ElementTree as ET

with zipfile.ZipFile(rov_path) as z:
    rover_xml = z.read("rover_data").decode("utf-8", errors="replace")

root = ET.fromstring(rover_xml)
NS = "{http://www.matrixscience.com/xmlns/schema/distiller_data_1}"
for node in root.iter(f"{NS}MascotImportOptions"):
    encoded = node.attrib.get("quantMethod", "")
    if encoded:
        decoded_xml = urllib.parse.unquote(encoded)
        # decoded_xml is a full <quantitation> document conforming to
        # quantitation_2.xsd — feed to ms_quant_method via loadXml if
        # you need the typed object.
        break
```

Note the default namespace on `rover_data` — `iter()` with a bare tag
name (without the `{ns}` prefix) returns nothing.

## All-in-one extractor

This skill ships an `_extract_rov_params.py` script in the report
workspace at `dev-reports/_extract_rov_params.py` that combines all of
the above into one CLI:

```
python dev-reports/_extract_rov_params.py <path-to-.rov>
```

It prints sections for project metadata, search task, peak detection
options, search-results predicates, search parameters (via msparser),
modifications (via msparser), the quant method (URL-decoded XML), and
the `mascot.dat` databases snapshot.

## Gotchas

1. **Don't pass merged-`.rov` files (the project root `.rov`) to
   `open_rov_resfile()` expecting a single `.dat`.** The merged project
   stitches multiple per-file caches together; its layout differs.
   This pattern is for the per-raw-file caches in `<project>.files/`.
2. **Drop the msparser resfile reference before `shutil.rmtree(tempdir)`**
   on Windows — msparser holds the file handle, and `rmtree` will fail
   with a permission error if the resfile is still alive.
3. **`mdro_search_status` (no suffix) is the small XML manifest, not
   the `.dat`.** The `.dat` lives in `mdro_search_status+N` for `N>=1`.
   The bare-name stream contains only the search-task pointer.
4. **The `.dat` inside the `.rov` is full-fidelity** — every Mascot
   search parameter and modification is there, even though some Mascot
   server admins delete the `<mascot>/data/<date>/` files after a few
   weeks. This is sometimes the only surviving copy.
