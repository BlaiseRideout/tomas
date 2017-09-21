#!/usr/bin/env python3

import json
import re

import tornado.web
import handler
import db
import seating
import settings

class TournamentHandler(handler.BaseHandler):
    def get(self):
        no_user = False
        with db.getCur() as cur:
            cur.execute("SELECT COUNT(*) FROM Users")
            no_user = cur.fetchone()[0] == 0

        return self.render("tournament.html", no_user=no_user,
                           tournamentname=settings.TOURNAMENTNAME)

player_fields = ["id", "name", "number", "country", "countryid", "flag_image",
                 "association", "pool", "inactive"]
valid = {
    'all': re.compile(r'^[\w\s():,.\'+-\u202F]*$'),
    'name': re.compile(r'^[\w\s():,.\'+-\u202F]+$'),
    'number': re.compile(r'^\d*$')
}

class PlayersHandler(handler.BaseHandler):
    global player_fields
    def get(self):
        editable = self.current_user is not None
        with db.getCur() as cur:
            cur.execute(
                "SELECT Players.Id, Players.Name, Number, Countries.Code,"
                " Countries.Id, Flag_Image, Association, Pool, Inactive"
                " FROM Players LEFT OUTER JOIN Countries"
                "   ON Countries.Id = Players.Country"
                " ORDER BY Players.Name asc")
            rows = [dict(zip(player_fields, row)) for row in cur.fetchall()]
            return self.write(json.dumps({'players':rows, 'editable': editable}))
    @tornado.web.authenticated
    def post(self):
        global player_fields
        global valid
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
                    col = colname.lower()
                    if not (col in player_fields and
                            (valid[col].match(val) if col in valid else 
                             valid['all'].match(val))):
                        return self.write(json.dumps(
                            {'status':"error", 
                             'message':"Invalid column or value provided"}))
                    if player == '-1':
                        cur.execute("INSERT INTO Players (Name, Country, Inactive) VALUES"
                                    " ('\u202Fnewplayer',"
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
            cur.execute("SELECT Id, COALESCE(Algorithm, 0), Seed, SoftCut,"
                        "Duplicates, Diversity, UsePools FROM Rounds")
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
