#!/usr/bin/env python3

__doc__ = """
Load the tournament database with a list of players in a CSV file.
The players file should have 4 columns: Name, Country, ??, and Association
Commas in values must be quoted to prevent them from being interpreted
as field separators.
"""

import argparse
import db
import csv

def load_players(playerfile, headers=False):
    with db.getCur() as cur:
        players = []
        reader = csv.reader(playerfile)
        for row in reader:
            if not headers:
                name = row[0]
                country = row[1]
                association = row[3]
                cur.execute(
                    "INSERT INTO Players(Name, Country, Association)"
                    " VALUES(?,"
                    "   (SELECT Id FROM Countries"
                    "      WHERE Name = ? OR Code = ? OR IOC_Code = ?),"
                    "   ?);",
                    (name, country, country, country, association))
            else:
                headers = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'players', nargs='*', type=argparse.FileType(encoding='UTF-8'),
        help="CSV File containing player data")
    parser.add_argument(
        '-s', '--skip-header-row', default=False, action='store_true',
        help="All player files have a header row (which will be skipped).")
    parser.add_argument(
        '-c', '--clear', default=False, action='store_true',
        help="Clear player data prior to loading files")
    args = parser.parse_args()

    db.init()
    if args.clear:
        with db.getCur() as cur:
            cur.execute("DELETE FROM Players")
            
    for i, f in enumerate(args.players if args.players else [sys.stdin]):
        print("Loading players from {0}...".format(f.name))
        load_players(f, headers=args.skip_header_row)
