# Distiller logging — setting it up and reading it

Mascot Distiller runs everything through a **logging monitor**: every
component (the Distiller app, MDRO raw-data library, msparser, quantitation
library) posts events with a severity and a source. The monitor filters them
by level and sends them to the **Log pane**, to **`Distiller.log`**, or, for
headless and Daemon runs, to a per-run log file. Your custom report posts
to the same monitor via `msparser.ms_loggingmonitor` (see §6).

> Sources: Distiller help (*Log Preferences*, *Tools menu*, *Technical
> Support*, *Command line arguments*) plus real logs from Distiller 2.9.242.

---

## 1. Turning logging on (Workstation GUI)

**Tools → Preferences → Log tab** (*Log Preferences*):

| Control | Effect |
|---------|--------|
| **Enable logging** | Master switch. Nothing is logged unless it is checked |
| Component drop-down | Apply the level to the **entire application** or to one component (Distiller / MDRO / msparser / quant library) |
| **Level** | Error · Warning · Information · Debug 1 · Debug 2 · Debug 3 (each adds more) |
| **Log to File** | Also write events to `Distiller.log` |
| **Roll over log file at startup** | Keep the previous log (up to 30 days) each time Distiller starts |
| **Show Log at Startup** | Default state of **View → Log** |

- **View → Log** shows or hides the log history pane, which is docked at the bottom by default.
- **Tools → Log** opens a submenu to clear the log, open it in a text editor, delete it, or open the Log Preferences dialog.

**Recommended levels:**

| Purpose | Level |
|---------|-------|
| Normal use | Error + Warning |
| Reproducing a problem or preparing a support request (what Matrix Science asks for) | Error + Warning + Information, with Log to File on |
| Only when support asks | Debug 1–3. These levels "can slow down processing substantially" and produce huge files |

### Where the settings live

The settings are stored per user in `%APPDATA%\Matrix Science\Mascot Distiller\Distiller.rst`:

```xml
<loggingTab Logging="1" LogLevels="3" DeleteLogFile="1" DisplayLogPane="0" LogToFile="1"
            DistillerLogLevels="3" MDROLogLevels="3" MSParserLogLevels="3" MSQuantLibLogLevels="3" />
```

The `*LogLevels` values are the same **bitmask** as the command-line `-loglevel` switch (verified on 2.9.242: `-loglevel 4` logs Information *without* errors, and `7` logs both):

| Bit | Level |
|-----|-------|
| 1 | Error |
| 2 | Warning |
| 4 | Information |
| 8 | Debug 1 |
| 16 | Debug 2 |
| 32 | Debug 3 |

So `3` means Error + Warning, and `7` adds Information. Each component has its own mask, which is how the drop-down's per-component setting is stored. Edit these through the dialog, not by hand, while Distiller is running.

---

## 2. Where the log files are

| Run type | Log location |
|----------|--------------|
| Workstation GUI | `%LOCALAPPDATA%\Matrix Science\Mascot Distiller\Distiller.log` |
| Rolled-over logs | Same folder, `Distiller.log.<unix-epoch-seconds>` (for example `Distiller.log.1790893507`) |
| Command line (`MascotDistiller.exe ... -batch`) | Whatever `-logfile <path>` names, filtered by `-loglevel <mask>`. Use `-e <file>` to get just the last error when the return code is non-zero |
| Mascot Daemon with the Distiller import filter | `<Daemon MGF root>\<task_uid> <task_label>\<hash>___<raw>.-1.rov.import.log`, one per raw file, next to the `.rov` and `.mgf` |

The Daemon `*.import.log` is the one to look at when a Daemon task finishes
but the project has no quantitation. It records the whole pipeline for that
file: open the raw file, log in to Mascot, download the result, run
quantitation, save. See [DAEMON_QUANTITATION.md](DAEMON_QUANTITATION.md).

Headless example:

```
MascotDistiller.exe sample.rov -batch -quantitate -logfile run.log -loglevel 7 -e run.err
```

`MascotDistiller.exe` returns before processing finishes. Tail the
`-logfile` until the final `Done!` line appears (see §4), or use
`-showConsole 2` (see [COMMAND_LINE.md](COMMAND_LINE.md)).

---

## 3. Log line format

Every log is tab-separated, with a header row and space-padded columns:

```
TIME                      MSG_NUM  SEVERITY     SOURCE        SRC_FILE                           LINE  THREAD      MESSAGE
2026-08-07T22:02:44+04:00 ...      LVL_INFO     MDRO_LIB_API  ErrorHandler.cs                    ...   0x00011814  Retrieved 49287 scans from the data source.
2026-08-07T22:03:10+04:00 ...      LVL_INFO     PURIFIER_API                                     ...   ...         Creating ms2 quantitation cache file(s)
```

| Column | Notes |
|--------|-------|
| `TIME` | ISO 8601 with UTC offset |
| `SEVERITY` | `LVL_ERROR`, `LVL_WARNING`, `LVL_INFO`, `LVL_DEBUG1..3` |
| `SOURCE` | Component: `PURIFIER_APP` / `PURIFIER_API` (Distiller), `MDRO_LIB_API` (raw data, peak picking), `MSPARSER_API` (Mascot server traffic, result parsing), `QUANTLIB_API` (quantitation) |
| `SRC_FILE` / `LINE` | Often blank |
| `THREAD` | Useful for separating multi-threaded peak picking |

.NET stack traces are spread over several following rows, each starting with `   at ...`.

### Parse it (pandas)

```python
import re
import pandas as pd

COLS = ['time', 'msg_num', 'severity', 'source', 'src_file', 'line', 'thread', 'message']
SECRET = re.compile(r'(password=)[^&\s\']*', re.I)


def read_distiller_log(path):
    """Parse Distiller.log / *.rov.import.log / -logfile output into a DataFrame.

    Lines without 7 tabs (stack-trace continuations) are appended to the
    previous message. Passwords in logged login URLs are masked.
    """
    rows = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for raw in f:
            raw = raw.rstrip('\r\n')
            parts = raw.split('\t', 7)
            if len(parts) == 8 and parts[0].strip() != 'TIME':
                rows.append([p.strip() for p in parts])
            elif rows and raw.strip() and not raw.startswith('TIME'):
                rows[-1][7] += '\n' + raw.strip()
    df = pd.DataFrame(rows, columns=COLS)
    df['message'] = df['message'].str.replace(SECRET, r'\1***', regex=True)
    df['time'] = pd.to_datetime(df['time'], errors='coerce', utc=True)
    return df


df = read_distiller_log(r'...\Distiller.log')
print(df.groupby(['severity', 'source']).size())
problems = df[df.severity.isin(['LVL_ERROR', 'LVL_WARNING'])].drop_duplicates('message')
```

I tested this on a 137-line Daemon `*.import.log` and on `Distiller.log` with stack traces.

---

## 4. Reading a Daemon/batch run log: the milestones

In a healthy quantitating run (Daemon, reporter protocol) these INFO lines appear in order:

```
Cache directory : C:\ProgramData\Matrix Science\Mascot Distiller\Temp
Opened MDRO project successfully.
Opening sample 1 of data source: <raw file>
Retrieved 49287 scans from the data source.            <- raw file readable
Getting configuration file quantitation.xml from ...   <- server config cached
Downloading search task id 178615439801
... client.pl?result_file_name ... filename=../data/20260807/F020090.msr
IsPercolator=True                                      <- 2.9+: Percolator honoured
Extracting required peaklist information required for MS2 quantitation
Creating ms2 quantitation cache file(s)                <- quantitation actually ran
Save search 1
Done!                                                  <- finished
```

- If the `quantitation` lines are missing, no quantitation method reached Distiller. Check `QUANTITATION=` and the task's save-project and quantitate fields.
- If the log never reaches `Done!`, look at the last `LVL_ERROR` before it stops.

### Usually harmless, from real logs

| Message | Why it's harmless |
|---------|------------------|
| `Failed to get HTTP proxy. The proxy auto-configuration script could not be downloaded` / `...URL was not found` | Logged as an ERROR on every server contact, but harmless when there is no PAC proxy |
| `Unable to log into server 'https://www.matrixscience.com/cgi/'. Login result code=2 (L_UNKNOWNUSER)` | Distiller also checks the public Matrix Science server listed in External Servers. Your local credentials aren't valid there |
| `Requested MDRO project stream 'mdroProjectStmRover' offset '0' is not present` (WARNING) | Expected on a freshly created project before its first save |
| `Cache file ...Temp/cache/0x.../xxxx is missing or cannot be opened` (WARNING) | A cache miss. Distiller regenerates the file |
| `Retrieving extended info for scan - Master Scan Number appears to be corrupted ... Defaulting to MDRO precursor tree build` | A Thermo raw-file quirk. Distiller falls back to its own precursor assignment |
| `The search uses a modification with composition including the element 'p'...assuming 100% at mass 30.973762` | Phosphorus is mono-isotopic, so the assumption is correct |

### Real problems

| Message | Meaning |
|---------|---------|
| `Fatal COM Exception 'Unable to open MDRO project file. (Open failed: The system cannot find the path specified.)'` | The `.rov` path doesn't exist. The command line opens the project before doing anything else (so `-rawFile` can't create a new project from the command line) |
| `Failed to load subproject '<...>.files\<hash>___<raw>...'` | A multi-file master can't find its sub-projects. They were moved, renamed or deleted |
| `Automatically cancelled request made to load replicate data from a memory efficient multifile subproject` | Replicate data only exists on the master project. Open or report on the master, not the sub-project |
| `Call to QuantlibProject::setExistingResultsDetails() ignored for subproject: N for replicate protocol` | Same cause, seen from the quantitation library |
| `Failed to receive HTTP response. The server name or address could not be resolved` | The Mascot Server in External Servers can't be reached |
| `No Results Parameters Supplied` | The `.rov` has no quantitation. Use a project made with a quantitation method (see BATCH_TESTING.md) |
| `ec=-1073741819` | Access violation (C++ crash), usually in a report. See CHECKLIST.md |

---

## 5. Credentials are logged in plain text

At **Information** level, `MSPARSER_API` records every Mascot login URL in
full, **including `password=` in clear text**. This happens in both
`Distiller.log` and the Daemon `*.import.log` files. Before you attach a log
to a support email, ticket or chat:

```bash
sed -E -i 's/(password=)[^&[:space:]'"'"']*/\1***/Ig' Distiller.log
```

The parser above masks passwords automatically. Turn off Information level
when you've finished debugging.

---

## 6. Logging from a custom report

Your report is the same kind of component. Distiller passes the current
log mask to the report through the properties CSV
(`LoggingOptions`: `Input1` = log mask, `Input2` = columns to output), and
the report forwards it to the monitor:

```python
mylogger_ = msparser.ms_stdout_logger()          # module level, keeps it alive

props_logging = props_csv[props_csv.Identifier == 'LoggingOptions']
mylogger_.setColsToOutput(int(props_logging.Input2.iloc[0]))
monitor = msparser.ms_loggingmonitor.getDefaultMonitor()
monitor.setLogMask(int(props_logging.Input1.iloc[0]))
monitor.addLogEventsHandler(mylogger_)

monitor.logMessage(msparser.ms_loggingmonitor.LVL_WARNING,
                   msparser.ms_loggingmonitor.SRC_APPLICATION,
                   0, f'{n_skipped} peptides skipped: no XIC', __file__, 0)
```

- **To see your report's DEBUG messages, raise Distiller's log level.** The
  report only receives the mask Distiller is using, so a `LVL_DEBUG1`
  message is dropped while Distiller is set to Error + Warning.
- At a high enough level, Distiller writes the **entire properties CSV**
  into the log. That is the quickest way to see which wizard inputs a report
  receives.
- **Use `logMessage`, not `print()`.** `print()` output bypasses the
  monitor's filtering and source tagging (see CHECKLIST.md).
- **Keep the GC guard.** End `main()` with `mylogger_.setColsToOutput(1)`
  (SKILL.md gotcha), or log events can be dropped or hang.

Full API: [MSPARSER_API.md → Logging](MSPARSER_API.md).
