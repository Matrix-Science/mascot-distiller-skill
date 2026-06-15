#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# REPORT-NAME-HERE
#
# Copyright YYYY Matrix Science Limited.  All Rights Reserved.
###############################################################################
"""One-line description of what this report produces."""

__version__ = "0.1.0"

import io
import sys

import pandas
import msparser

import CreateQuantDataFrames
import LoadQuantitation
import WriteReports

# Module-level logger reference — required to prevent garbage collection
# while Distiller is still pumping log events. See SKILL.md gotcha #1.
mylogger_ = msparser.ms_stdout_logger()


def main():
    if len(sys.argv) < 2:
        sys.exit("Must specify properties filename as parameter")

    props_path = sys.argv[1]
    props_csv = pandas.read_csv(
        props_path, delimiter=",", header=0,
        keep_default_na=False, quotechar='"',
    )

    # Standard property subsets every report needs
    props_logging  = props_csv[props_csv.Identifier == "LoggingOptions"]
    props_options  = props_csv[props_csv.Identifier == "PathOptions"]
    props_header   = props_csv[props_csv.Identifier == "ReportHeader"]
    props_rawfiles = props_csv[props_csv.Identifier == "RawFile"]

    save_path = props_options.Input2.iloc[0]

    # Custom wizard parameters — uncomment and rename per your XML.
    # props_my_param = props_csv[props_csv.Identifier == "myParamName"]
    # my_value = props_my_param.Input1.iloc[0]

    # Initialise logging
    mylogger_.setColsToOutput(int(props_logging.Input2.iloc[0]))
    monitor = msparser.ms_loggingmonitor.getDefaultMonitor()
    monitor.setLogMask(int(props_logging.Input1.iloc[0]))
    monitor.addLogEventsHandler(mylogger_)

    # Load search and quantitation results
    load_res = LoadQuantitation.DoLoad(props_path)
    if not load_res:
        sys.exit("No Results Parameters Supplied")

    create_report(load_res, save_path, props_header, props_rawfiles)

    # Final logger touch — must be the last thing in main(); prevents the
    # logger being collected before Distiller drains its event queue.
    mylogger_.setColsToOutput(1)


def create_report(load_res, save_path, props_header, props_rawfiles):
    is_ms1   = load_res[0].isMS1
    quant    = load_res[0].qObj
    pep_sum  = load_res[0].pepSum
    q_method = load_res[0].qMethod

    # Branch on protocol if your report supports more than one
    is_average = is_ms1 and (q_method.getProtocol().getAverage() is not None)

    # Component names (0-based)
    component_names = [
        q_method.getComponentByNumber(c).getName()
        for c in range(q_method.getNumberOfComponents())
    ]

    proteins = CreateQuantDataFrames.pullProteinsFrom(pep_sum)
    rows = []
    for i, protein in enumerate(proteins):
        WriteReports.OutputProgress("Processing proteins", i + 1, len(proteins))

        accession = protein.getAccession()
        rows.append({
            "Hit":         protein.getHitNumber(),
            "Accession":   accession,
            "Description": pep_sum.getProteinDescription(accession),
            "Score":       protein.getScore(),
            "Peptides":    protein.getNumPeptides(),
            # Add your per-protein columns here
        })

    df = pandas.DataFrame(rows)
    df.to_csv(save_path, index=False, encoding="utf-8")
    WriteReports.OutputProgress("Report complete", 1, 1)


if __name__ == "__main__":
    sys.exit(main())
