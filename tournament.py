#!/usr/bin/env python3

import json
import re

import tornado.web
import handler
import db

class TournamentHandler(handler.BaseHandler):
    def get(self):
        no_user = False
        with db.getCur() as cur:
            cur.execute("SELECT COUNT(*) FROM Users")
            no_user = cur.fetchone()[0] == 0

        return self.render("tournament.html", no_user=no_user)

player_fields = ["id", "name", "country", "countryid", "flag_image",
                 "association", "pool", "inactive"]
valid_values = re.compile(r'^[\w\s():,.\'+-]*$')

class PlayersHandler(handler.BaseHandler):
    global player_fields
    def get(self):
        editable = self.current_user is not None
        with db.getCur() as cur:
            cur.execute(
                "SELECT Players.Id, Players.Name, Countries.Code, Countries.Id,"
                " Flag_Image, Association, Pool, Inactive"
                " FROM Players LEFT OUTER JOIN Countries"
                "   ON Countries.Id = Players.Country"
                " ORDER BY Players.Name asc")
            rows = [dict(zip(player_fields, row)) for row in cur.fetchall()]
            return self.write(json.dumps({'players':rows, 'editable': editable}))
    @tornado.web.authenticated
    def post(self):
        global player_fields
        global valid_values
        player = self.get_argument("player", None)
        if player is None or not (player.isdigit() or player == '-1'):
            return self.write(json.dumps(
                {'status':"error", 'message':"Please provide a player"}))
        info = self.get_argument("info", None)
        if info is None:
            return self.write(json.dumps(
                {'status':"error", 'message':"Please provide an info object"}))
        info = json.loads(info)
        try:
            with db.getCur() as cur:
                for colname, val in info.items():
                    if (colname.lower() not in player_fields or 
                        not valid_values.match(val) or
                        (colname.lower() == 'name' and len(val) == 0)):
                        return self.write(json.dumps(
                            {'status':"error", 
                             'message':"Invalid column or value provided"}))
                    if player == '-1':
                        cur.execute("INSERT INTO Players (Name, Country, Inactive) VALUES"
                                    " ('newplayer',"
                                    "  (select Id from Countries limit 1), 1)")
                    else:
                        cur.execute("UPDATE Players SET {0} = ? WHERE Id = ?"
                                    .format(colname),
                                    (val, player))
            return self.write(json.dumps({'status':"success"}))
        except:
            return self.write(json.dumps(
                {'status':"error", 
                 'message':"Invalid info provided"}))

class AddRoundHandler(handler.BaseHandler):
    def post(self):
        with db.getCur() as cur:
            cur.execute("INSERT INTO Rounds(Id) VALUES((SELECT COUNT(*) + 1 FROM Rounds))")
            return self.write(json.dumps({'status':"success"}))

class DeleteRoundHandler(handler.BaseHandler):
    def post(self):
        round = self.get_argument("round", None)
        if round is None:
            return self.write(json.dumps({'status':"error", 'message':"Please provide a round"}))
        with db.getCur() as cur:
            cur.execute("DELETE FROM Rounds WHERE Id = ?", (round,))
            return self.write(json.dumps({'status':"success"}))

class SettingsHandler(handler.BaseHandler):
    def get(self):
        editable = self.current_user is not None
        with db.getCur() as cur:
            cur.execute("SELECT Id, Seed, SoftCut, Duplicates, Diversity, UsePools FROM Rounds")
            rounds = [
                    {
                        "id": roundid,
                        "seed": seed,
                        "softcut": softcut,
                        "duplicates": duplicates,
                        "diversity": diversity,
                        "usepools": usepools
                    }
                    for roundid, seed, softcut, duplicates, diversity, usepools in cur.fetchall()
                ]
            return self.write(json.dumps({'rounds':rounds}))
    def post(self):
        round = self.get_argument("round", None)
        if round is None:
            return self.write(json.dumps({'status':"error", 'message':"Please provide a round"}))
        settings = self.get_argument("settings", None)
        if settings is None:
            return self.write(json.dumps({'status':"error", 'message':"Please provide a settings object"}))
        settings = json.loads(settings)
        print(settings)
        with db.getCur() as cur:
            for colname, val in settings.items():
                cur.execute("UPDATE Rounds SET {0} = ? WHERE Id = ?".format(colname), (val, round)) # TODO: fix SQL injection
            return self.write(json.dumps({'status':"success"}))

class CountriesHandler(handler.BaseHandler):
    def get(self):
        with db.getCur() as cur:
            cur.execute("SELECT Id, Name, Code, IOC_Code, IOC_Name, Flag_Image FROM Countries")
            return self.write(json.dumps([{'Id': row[0], 'Name': row[1], 'Code': row[2], 'IOC_Code': row[3], 'IOC_Name': row[4], 'Flag_Image': row[5]} for row in cur.fetchall()]))

class SeatingHandler(handler.BaseHandler):
    def get(self):
        with db.getCur() as cur:
            cur.execute("""
                    SELECT Rounds.Id, Seating.TableNum, Seating.Wind, Players.Name,
                     Countries.Code, Countries.Flag_Image
                     FROM Rounds
                     LEFT OUTER JOIN Seating
                       ON Rounds.Id = Seating.Round
                     LEFT OUTER JOIN Players
                       ON Players.Id = Seating.Player
                     LEFT OUTER JOIN Countries
                       ON Countries.Id = Players.Country
                """)
            rounds = {}
            for row in cur.fetchall():
                round, table, wind, name, country, flag = row
                if round is not None:
                    if not round in rounds:
                        rounds[round] = {}
                    if table is not None:
                        if not table in rounds[round]:
                            rounds[round][table] = {}
                        if wind is not None and name is not None:
                            rounds[round][table][wind] = {"name":name, "country":country, "flag":flag}
            winds = "東南西北"
            rounds = [
                    {
                        'round':round,
                        'tables':
                            [
                                {
                                    'table':table,
                                    'players':
                                        [
                                            {
                                                'player': name,
                                                'wind':winds[wind]
                                            }
                                            for wind, name in players.items()
                                        ]
                                }
                                for table, players in tables.items()
                            ]
                    }
                    for round, tables in rounds.items()
                ]
            return self.write(json.dumps({'rounds':rounds}))
    def post(self):
        round = self.get_argument('round', None)
        if round is not None:
            with db.getCur() as cur:
                cur.execute(
                        "SELECT Id, Seed, SoftCut, Duplicates, Diversity, UsePools"
                        " FROM Rounds WHERE Id = ?",
                        (round,)
                    )
                round, seed, softcut, duplicates, diversity, usepools = cur.fetchone()
                cur.execute("""
                        SELECT Players.Id,
                        COALESCE(SUM(Scores.Score), 0) AS NetScore
                         FROM Players
                           LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId
                         GROUP BY Players.Id
                         ORDER BY NetScore DESC
                    """)
                players = [row[0] for row in cur.fetchall()]
                bindings = []
                for i, player in enumerate(players):
                    bindings += [round, player, int(i / 4), i % 4]
                cur.execute("DELETE FROM Seating WHERE Round = ?", (round,))
                playerquery = "(?, ?, ?, ?)"
                cur.execute("""
                    INSERT INTO Seating (Round, Player, TableNum, Wind)
                    VALUES {0}
                """.format(",".join([playerquery] * len(players))),
                    bindings
                )
                self.write(json.dumps({"status":"success"}))
