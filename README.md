# Mascot Distiller Skill

**Version:** 1.0.0 &nbsp;|&nbsp; **License:** Apache-2.0

An Agent Skill that teaches AI coding assistants how to build **custom Mascot Distiller reports** — Python scripts that Distiller runs after a search to produce quantitative proteomics output (CSV, HTML, SVG, PNG).

The skill itself is just markdown — `skills/mascot-distiller/SKILL.md` plus reference files and templates under `skills/mascot-distiller/`. It does not contain or redistribute the licensed msparser SDK.

> Mascot Distiller runs on **Windows only**, so this skill targets a Windows environment.

## What it covers

- The `msparser` SDK for post-search results: protein/peptide hits, quant ratios, and integrated XICs read from the quantitation cache
- The wizard XML schema that defines a report's UI (`AutoGenerateOptions`, `SkipIf`, `mapsTo`, `@{Var}`, full-page patterns)
- The two-file `.py` + `.py.xml` report pattern, with a ready-to-copy starter template
- Visualisation recipes (Plotly embedding, XIC overlays, annotated MS2, heatmaps)
- Pre-deploy checklists and batch/regression-testing guidance
- The `.rov` project container — it's a ZIP, and knowing the stream layout gets you search parameters, peak-detection options and the quant method that msparser doesn't expose
- **De novo sequencing from the command line** — including the non-obvious part: parameters live *inside the project*, and stale cached solutions get silently re-exported as if they were fresh

## Prerequisites

You still need the **msparser SDK** to actually run any code the assistant writes.

It ships **inside your Mascot Distiller installation** (the report-building workspace), under `<WORKSPACE>\msparser\` — Distiller's embedded Python loads it automatically when running deployed reports. The skill walks the assistant through discovering these paths on your machine (see `skills/mascot-distiller/references/SETUP.md`).

If you need the SDK separately, download it from:
**https://www.matrixscience.com/msparser_download.html**

## Install — Claude Code

Pick one location depending on whether you want the skill globally or per-project.

**Globally (all projects):**
```powershell
git clone https://github.com/Matrix-Science/mascot-distiller-skill.git
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse mascot-distiller-skill\skills\mascot-distiller "$env:USERPROFILE\.claude\skills\"
```

**Per project** (run from your project's root):
```powershell
New-Item -ItemType Directory -Force .claude\skills | Out-Null
Copy-Item -Recurse "C:\path\to\mascot-distiller-skill\skills\mascot-distiller" .claude\skills\
```

If you'd rather not use the command line, clone or download the repo in File Explorer and copy the `skills\mascot-distiller` folder into either:
- `%USERPROFILE%\.claude\skills\` (global), or
- `<your-project>\.claude\skills\` (per-project)

### After install

Restart Claude Code (or start a new session). The skill auto-loads when you mention Mascot Distiller reports, the wizard XML, msparser quantitation, `.dat` results, integrated XICs, etc. You can also force it with `/skill mascot-distiller`.

## Install — other AI coding tools

The skill format follows Anthropic's [Agent Skills](https://www.anthropic.com/news/skills) spec, which several tools now support:

| Tool | Supported | Install location |
|---|---|---|
| **Claude Code** (CLI / desktop / IDE plugins) | yes | `%USERPROFILE%\.claude\skills\` or `.claude\skills\` (project) |
| **Claude API / Agent SDK** | yes | Pass via the Skills API or bundle with your agent |
| **GitHub Copilot CLI** | yes (auto-discovered from installed plugins) | Plugin's `skills\` directory |
| **Gemini CLI** | yes (loaded via `activate_skill`) | `%USERPROFILE%\.gemini\skills\` |
| **Cursor / Windsurf / Cline / Aider / etc.** | no native skill loader | See "Manual use" below |

### Manual use (any assistant)

For tools that don't yet support the skill format, the SKILL.md is just a long-form prompt:

1. **Paste it in** — open `skills/mascot-distiller/SKILL.md` and paste the contents into the chat / system prompt.
2. **Reference it as context** — most assistants let you @-mention or attach files. Point at `skills/mascot-distiller/SKILL.md` and the relevant `references/*.md`.

## Using the skill

Once installed, just ask in plain language. Examples:

- *"Create a new Distiller report that exports the top-3 peptide intensities per protein to CSV."*
- *"Add a wizard parameter to my report that lets the user pick a minimum protein score."*
- *"Read the integrated XICs from this `.dat` file and plot them as an interactive Plotly HTML."*
- *"Lint my report before I deploy it — check encoding, schema, logger, and hard-coded paths."*
- *"Run Distiller de novo on this `.rov` at 10 ppm / 0.02 Da and tell me why my last run ignored the tolerances I set."*
- *"What's actually inside this `.rov` — which database was searched, and with what peak detection options?"*

## Repo layout

```
skills/mascot-distiller/
  SKILL.md                          # main skill entry point
  references/
    SETUP.md                        # path discovery: workspace, Distiller install, SDK
    MSPARSER_API.md                 # msparser API (post-search results / quantitation, XICs)
    XML_SCHEMA.md                   # raw wizard XML definition schema
    WIZARD_COOKBOOK.md              # wizard XML idioms
    REPORT_EXAMPLES.md              # annotated complete-report examples
    VISUALIZATIONS.md               # plot recipes
    QUANT_PROTOCOL_HELPER.md        # MS1/MS2/Average dispatch helper
    CHECKLIST.md                    # pre-deploy and release checklists
    BATCH_TESTING.md                # regression testing / CI
    PROCESSING_OPTIONS.md           # *.opt peak-detection schema versions
    ROV_FILE_FORMAT.md              # .rov is a ZIP — stream layout
    DE_NOVO.md                      # de novo sequencing from the command line
    COMMAND_LINE.md                 # driving Distiller unattended
  templates/
    quant-report-template/          # recommended starting point for a new report
    denovo-cli/                     # unattended de novo: seed, patch, run
    lint-report.sh                  # one-shot pre-deploy audit script
    downgrade-opt-to-1.6.ps1        # processing-options downgrade helper
```

The msparser SDK directory (`SDK/`) is gitignored — it is licensed software and is not redistributed here.

## Related

- **Companion skill**: `mascot-mdro` — drives the COM-based Mascot Distiller SDK (MDRO) for raw-data work: peak detection, TICs, spectra, and peak list export (MGF/DTA/PKL). MDRO is a paid product, licensed separately.

## License

The skill content in this repository (the markdown under `skills/` and the documentation at the repo root) is licensed under the **Apache License, Version 2.0** (Apache-2.0). See [LICENSE](LICENSE) for the full text.

The msparser SDK itself is **not** covered by this license — it is proprietary software licensed separately by Matrix Science. You must obtain it from https://www.matrixscience.com/msparser_download.html (or from your Mascot Distiller installation) under its own terms.
