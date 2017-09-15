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
            cur.execute("SELECT Players.Id, Players.Name, Countries.IOC, Association, Pools.Name FROM Players LEFT OUTER JOIN Countries ON Countries.Id = Players.Country LEFT OUTER JOIN Pools ON Players.Pool = Pools.Id")
            rows = [{"id": row[0], "name": row[1], "country": row[2], "association": row[3], "pool": row[4]} for row in cur.fetchall()]
            return self.write(json.dumps(rows))


