#!/usr/bin/env python3

import json

import handler
import db

class TournamentHandler(handler.BaseHandler):
    def get(self):
        return self.render("tournament.html")

class PlayersHandler(handler.BaseHandler):
    def get(self):
        with db.getCur() as cur:
            cur.execute("SELECT Players.Id, Players.Name, Countries.Code, Association, Pools.Name FROM Players LEFT OUTER JOIN Countries ON Countries.Id = Players.Country LEFT OUTER JOIN Pools ON Players.Pool = Pools.Id")
            rows = [{"id": row[0], "name": row[1], "country": row[2], "association": row[3], "pool": row[4]} for row in cur.fetchall()]
            return self.write(json.dumps({'players':rows}))

class AddRoundHandler(handler.BaseHandler):
    def post(self):
        with db.getCur() as cur:
            cur.execute("INSERT INTO Rounds(Number) VALUES((SELECT COUNT(*) + 1 FROM Rounds))")
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
            cur.execute("SELECT Id, Number, Seed, SoftCut, Duplicates, Diversity, UsePools FROM Rounds")
            rows = [{"id": row[0], "number": row[1], "seed": row[2], "softcut": row[3], "duplicates": row[4], "diversity": row[5], "usepools": row[6]} for row in cur.fetchall()]
            return self.write(json.dumps({'rounds':rows}))
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
                cur.execute("UPDATE Rounds SET {0} = ?".format(colname), (val,))
            return self.write(json.dumps({'status':"success"}))
