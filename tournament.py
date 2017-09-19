#!/usr/bin/env python3

import json

import handler
import db
import seating

class TournamentHandler(handler.BaseHandler):
    def get(self):
        no_user = False
        with db.getCur() as cur:
            cur.execute("SELECT COUNT(*) FROM Users")
            no_user = cur.fetchone()[0] == 0

        return self.render("tournament.html", no_user=no_user)

class PlayersHandler(handler.BaseHandler):
    def get(self):
        with db.getCur() as cur:
            cur.execute(
                "SELECT Players.Id, Players.Name, Countries.Code, Countries.Id, Flag_Image,"
                " Association, Pools.Name"
                " FROM Players"
                " LEFT OUTER JOIN Countries"
                "   ON Countries.Id = Players.Country"
                " LEFT OUTER JOIN Pools"
                "   ON Players.Pool = Pools.Id")
            rows = [{"id": row[0], "name": row[1], "country": row[2], "countryid": row[3], "flag_image": row[4], "association": row[5], "pool": row[6]} for row in cur.fetchall()]
            return self.write(json.dumps({'players':rows}))
    def post(self):
        player = self.get_argument("player", None)
        if player is None:
            return self.write(json.dumps({'status':"error", 'message':"Please provide a player"}))
        info = self.get_argument("info", None)
        if info is None:
            return self.write(json.dumps({'status':"error", 'message':"Please provide an info object"}))
        info = json.loads(info)
        with db.getCur() as cur:
            for colname, val in info.items():
                cur.execute("UPDATE Players SET {0} = ? WHERE Id = ?".format(colname), (val, player)) # TODO: fix SQL injection
            return self.write(json.dumps({'status':"success"}))

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
        with db.getCur() as cur:
            cur.execute("SELECT Id, Algorithm, Seed, SoftCut, Duplicates, Diversity, UsePools FROM Rounds")
            rounds = [
                    {
                        "id": roundid,
                        "algorithm": algorithm,
                        "algname": seating.ALGORITHMS[algorithm].name,
                        "seed": seed,
                        "softcut": softcut,
                        "duplicates": duplicates,
                        "diversity": diversity,
                        "usepools": usepools
                    }
                    for roundid, algorithm, seed, softcut, duplicates, diversity, usepools in cur.fetchall()
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
