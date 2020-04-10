#!/usr/bin/env python3

import json
import re
import logging
import datetime
import sqlite3

import tornado.web
import handler
import db
import settings
import tournament

log = logging.getLogger('WebServer')

summaryNumber = 3      # Show this many items in summary

class TournamentHomeHandler(handler.BaseHandler):
    def get(self):
        rows = []
        countries = tournament.getCountries()
        with db.getCur() as cur:
            cur.execute("SELECT COUNT(*) FROM Users")
            no_user = cur.fetchone()[0] == 0
            no_countries = len(countries) == 0
            columns = ['Id', 'Name', 'Start', 'End', 'Logo']
            tmt_colnames = ['Name', 'Start', 'End',]
            sql = ("SELECT {columns} FROM Tournaments"
                   " ORDER BY End DESC LIMIT ?").format(
                       columns=",".join(columns))
            args = (summaryNumber,)
            cur.execute(sql, args)
            tournaments = [dict(zip(map(db.fieldname, columns), row))
                           for row in cur.fetchall()]

            columns = ['Players.Id', 'Players.Name', 'Association',
                       'Flag_Image']
            plr_colnames = ['Name', 'Association',
                            {'label': 'Country', 'key': 'Flag_Image'}]
            sql = """
            SELECT {columns}, SUM(Scores.Score) / COUNT(Scores.Id) AS AvgScore
            FROM Players LEFT OUTER JOIN Countries
                ON Players.Country = Countries.Id
              LEFT OUTER JOIN Compete on Compete.Player = Players.Id
              LEFT OUTER JOIN Tournaments 
                ON Compete.Tournament = Tournaments.Id
              LEFT OUTER JOIN Rounds ON Rounds.Tournament = Tournaments.Id
              LEFT OUTER JOIN Scores ON Scores.Round = Rounds.Id
            GROUP BY Players.Id
            ORDER BY Tournaments.End DESC, AvgScore DESC, Players.Name ASC
            LIMIT ?""".format(columns=",".join(columns))
            args = (summaryNumber,)
            cur.execute(sql, args)
            players = [dict(zip(map(db.fieldname, columns), row))
                       for row in cur.fetchall()]
            
        return self.render(
            "tournamentHome.html",
            tournaments=tournaments, tmt_colnames=tmt_colnames,
            players=players, plr_colnames=plr_colnames,
            no_user=no_user, no_countries=no_countries)

