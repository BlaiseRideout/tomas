#!/usr/bin/env python3

import db
import csv

def main():
    db.init()
    with db.getCur() as cur:
        players = []
        with open("players.csv", "r") as playerfile:
            cur.execute("DELETE FROM Players")
            reader = csv.reader(playerfile)
            headers = True
            for row in reader:
                if not headers:
                    name = row[0]
                    country = row[1]
                    association = row[3]
                    cur.execute("INSERT INTO Players(Name, Country, Association) VALUES(\
                            ?,\
                            (SELECT Id FROM Countries WHERE Name = ? OR IOC = ?),\
                            ?\
                        );", (name, country, country, association))
                else:
                    headers = False

if __name__ == "__main__":
    main()
