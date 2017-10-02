#!/usr/bin/env python3

__doc__ = """
Load the tournament database with scores in a csv file
"""

import argparse
import db
import csv
import sys

fields = ["GameId", "Round", "PlayerId", "Rank", "RawScore", "Score"]

def load_scores(scorefile, headers=False):
    with db.getCur() as cur:
        scores = []
        reader = csv.reader(scorefile)
        rownum = 0
        for row in reader:
            if len(row) != len(fields):
                print("Row {0} of {1} has {2} field(s), not {3}. Skipping..."
                      .format(rownum, scorefile.name, len(row), len(fields)),
                      file=sys.stderr)
                headers = False
                continue
            if not headers:
                rec = [int(x) if x.isdigit() else float(x) for x in row]
                cur.execute(
                    "INSERT INTO Scores ({0}) VALUES ({1})".format(
                        ','.join(fields), ','.join(['?'] * len(fields))),
                    rec)
            headers = False
            rownum += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'scores', nargs='*', type=argparse.FileType(encoding='UTF-8'),
        help="CSV File containing score data")
    parser.add_argument(
        '-s', '--skip-header-row', default=True, action='store_true',
        help="All score files have a header row (which will be skipped).")
    parser.add_argument(
        '-c', '--clear', default=False, action='store_true',
        help="Clear score data prior to loading files")
    args = parser.parse_args()

    db.init()
    if args.clear:
        with db.getCur() as cur:
            cur.execute("DELETE FROM Scores")

    for i, f in enumerate(args.scores if args.scores else [sys.stdin]):
        print("Loading scores from {0}...".format(f.name))
        load_scores(f, headers=args.skip_header_row)
