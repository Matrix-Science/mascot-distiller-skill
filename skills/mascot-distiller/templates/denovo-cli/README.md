# De novo from the command line

Two scripts that run Mascot Distiller de novo sequencing unattended with
parameters that actually take effect.

| File | Purpose |
|---|---|
| `run_denovo.py` | Drives the whole thing: seed → patch → run, with a fragment-tolerance backoff ladder. |
| `patch_rov_denovo.py` | Rewrites the `<denovotagTab>` block inside a `.rov` and purges cached solutions. Importable (`patch_rov(...)`) or standalone. |

Plain Python 3.8+ — no msparser, no Distiller SDK. Both scripts only need
`MascotDistiller.exe` on the machine.

## Why they exist

De novo parameters are **not** read from the preferences file at run time and
**not** taken from the command line. They come from a copy stored inside the
`.rov` project. Editing `Distiller.rst` changes nothing, and the documented
`/s <preferences>` switch is accepted and ignored.

Worse, once a project has de novo results Distiller caches them and a later run
**re-exports the cache** — exit 0, plausible output, and a header showing your
new tolerances over the old solutions.

`patch_rov_denovo.py` handles both: it patches the parameters and drops the
`rover_data+N` cache members so the next run genuinely recomputes.

Full background, output format, sequence notation and the other failure modes:
[references/DE_NOVO.md](../../references/DE_NOVO.md).

## Use

```powershell
# Point at the install if it isn't in the default Program Files location
$env:MASCOT_DISTILLER_INSTALL = "C:\Program Files\Matrix Science\Mascot Distiller"

python run_denovo.py --rov project.rov --out denovo.csv `
    --seed-start 5 --seed-end 400 `
    --frag-tol 0.02 --pep-tol 10 --instrument ESI-TRAP `
    --fixed-mod "Carbamidomethyl (C)" --var-mod "Oxidation (M)"
```

Patch only, without running:

```powershell
python patch_rov_denovo.py --rov project.rov --frag-tol 0.02 --pep-tol 10
```

## Two things to get right

**Set the fragment tolerance to what the instrument supports.** The stock
0.300 Da is more than an order of magnitude too loose for Orbitrap MS2, and the
damage is visible in the output — sprawling alternative-composition lists where
a correct tolerance gives one or two candidates.

**Do not add variable modifications speculatively.** Each one multiplies the
candidate space with no sequence to prune it, and measurably *reduces* the
number of spectra sequenced correctly. Add `Phospho (ST)` / `Phospho (Y)` when
the sample is phosphoenriched; otherwise leave the list short.
