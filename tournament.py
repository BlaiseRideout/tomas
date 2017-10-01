#!/usr/bin/env python3

import json
import csv
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
                 "association", "pool", "type"]
valid = {
    'all': re.compile(r'^[\w\s():,.\'+-\u202F]*$'),
    'name': re.compile(r'^[\w\s():,.\'+-\u202F]+$'),
    'number': re.compile(r'^\d*$')
}

def getPlayers(self):
    editable = self.current_user is not None
    with db.getCur() as cur:
        cur.execute(
            "SELECT Players.Id, Players.Name, Number, Countries.Code,"
            " Countries.Id, Flag_Image, Association, Pool, Type"
            " FROM Players LEFT OUTER JOIN Countries"
            "   ON Countries.Id = Players.Country"
            " ORDER BY Players.Name asc")
        rows = [dict(zip(player_fields, row)) for row in cur.fetchall()]
        for row in rows:
            row['type'] = db.playertypes[int(row['type'] or 0)]
        return {'players':rows, 'editable': editable}

class ShowPlayersHandler(handler.BaseHandler):
    def get(self):
        data = getPlayers(self)
        return self.render("players.html", editable = data['editable'],
                           players = data['players'])

class DeletePlayerHandler(handler.BaseHandler):
    @tornado.web.authenticated
    def post(self):
        player = self.get_argument("player", None)
        if player is None:
            return self.write({'status':"error", 'message':"Please provide a player"})
        try:
            with db.getCur() as cur:
                if player == "all":
                    cur.execute("DELETE FROM Players")
                else:
                    cur.execute("DELETE FROM Players WHERE Id = ?", (player,))
                return self.write({'status':"success"})
        except:
            return self.write({'status':"error",
                 'message':"Couldn't delete player"})

class PlayersHandler(handler.BaseHandler):
    global player_fields
    def get(self):
        return self.write(getPlayers(self))
    @handler.is_admin_ajax
    def post(self):
        global player_fields
        global valid
        player = self.get_argument("player", None)
        if player is None or not (player.isdigit() or player == '-1'):
            return self.write({'status':"error", 'message':"Please provide a player"})
        info = self.get_argument("info", None)
        if info is None:
            return self.write({'status':"error", 'message':"Please provide an info object"})
        info = json.loads(info)
        try:
            with db.getCur() as cur:
                for colname, val in info.items():
                    col = colname.lower()
                    if not (col in player_fields and
                            (valid[col].match(val) if col in valid else
                             valid['all'].match(val))):
                        return self.write({'status':"error",
                             'message':"Invalid column or value provided"})
                    if player == '-1':
                        cur.execute("INSERT INTO Players (Name, Country) VALUES"
                                    " ('\u202Fnewplayer',"
                                    "  (select Id from Countries limit 1))")
                    else:
                        if colname == "Type":
                            if val == "2":
                                cur.execute(
                                        "UPDATE Players SET Country = (SELECT Id FROM Countries"
                                        "  WHERE Name = 'Substitute' OR 'Code' = 'SUB' OR IOC_Code = 'SUB')"
                                        " WHERE Id = ?",
                                        (player,))
                            else:
                                cur.execute(
                                        "UPDATE Players SET Country = (SELECT Id FROM Countries"
                                        "  WHERE NOT (Name = 'Substitute' OR 'Code' = 'SUB' OR IOC_Code = 'SUB'))"
                                        " WHERE Id = ?",
                                        (player,))
                        cur.execute("UPDATE Players SET {0} = ? WHERE Id = ?"
                                    .format(colname),
                                    (val, player))
            return self.write({'status':"success"})
        except:
            return self.write({'status':"error",
                 'message':"Invalid info provided"})

class UploadPlayersHandler(handler.BaseHandler):
    @handler.is_admin_ajax
    def post(self):
        global player_fields
        global valid
        if 'file' not in self.request.files or len(self.request.files['file']) == 0:
            return self.write({'status':"error", 'message':"Please provide a players file"})
        players = self.request.files['file'][0]['body']
        try:
            with db.getCur() as cur:
                reader = csv.reader(players.decode('utf-8').splitlines())
                good = 0
                bad = 0
                for row in reader:
                    if len(row) < 3:
                        bad += 1;
                        continue
                    somefilled = False
                    for i in range(len(row)):
                        if row[i] == '':
                            row[i] = None
                        else:
                            somefilled = True
                    name = row[0]
                    number = row[1]
                    country = row[2]
                    if (not somefilled or (name.lower() == 'name' and
                                           number.lower() == 'number')):
                        if not somefilled:
                            bad += 1
                        continue
                    if len(row) >= 4:
                        association = row[3]
                    else:
                        association = ""
                    if len(row) >= 5:
                        pool = row[4]
                    else:
                        pool = ""
                    if len(row) >= 6:
                        status = row[5] or 0
                        if status in db.playertypes:
                            status = db.playertypes.index(status)
                    else:
                        status = 0
                    cur.execute(
                        "INSERT INTO Players(Name, Number, Country, Association, Pool, Type)"
                        " VALUES(?, ?,"
                        "   (SELECT Id FROM Countries"
                        "      WHERE Name = ? OR Code = ? OR IOC_Code = ?),"
                        "   ?, ?, ?);",
                        (name, number, country, country, country, association, pool, status))
                    good += 1
            return self.write({'status':"success",
                               'message':
                               ("{0} player record(s) loaded, "
                                "{1} player record(s) skipped").format(
                                    good, bad)})
        except Exception as e:
            return self.write({'status':"error",
                    'message':"Invalid players file provided: " + str(e)})


class AddRoundHandler(handler.BaseHandler):
    @handler.is_admin_ajax
    def post(self):
        with db.getCur() as cur:
            cur.execute("INSERT INTO Rounds(Id) VALUES((SELECT COUNT(*) + 1 FROM Rounds))")
            return self.write({'status':"success"})

class DeleteRoundHandler(handler.BaseHandler):
    @handler.is_admin_ajax
    def post(self):
        round = self.get_argument("round", None)
        if round is None:
            return self.write({'status':"error", 'message':"Please provide a round"})
        with db.getCur() as cur:
            cur.execute("DELETE FROM Rounds WHERE Id = ?", (round,))
            return self.write({'status':"success"})

def getSettings(self):
    editable = self.current_user is not None
    with db.getCur() as cur:
        cur.execute("SELECT Id, COALESCE(Ordering, 0), COALESCE(Algorithm, 0), Seed, Cut, SoftCut, CutSize,"
                    "Duplicates, Diversity, UsePools, Winds, Games FROM Rounds")
        rounds = [
                {
                    "id": roundid,
                    "ordering": ordering,
                    "orderingname": seating.ORDERINGS[ordering][0],
                    "algorithm": algorithm,
                    "algname": seating.ALGORITHMS[algorithm].name,
                    "seed": seed or "",
                    "cut": cut,
                    "softcut": softcut,
                    "cutsize": cutsize,
                    "duplicates": duplicates,
                    "diversity": diversity,
                    "usepools": usepools,
                    "winds": winds,
                    "games": games
                }
                for roundid, ordering, algorithm, seed, cut, softcut, cutsize, duplicates, diversity, usepools, winds, games in cur.fetchall()
            ]
        cutsize = settings.DEFAULTCUTSIZE
        return {'rounds':rounds, 'cutsize':cutsize}
    return None

class SettingsHandler(handler.BaseHandler):
    @handler.is_admin_ajax
    def get(self):
        return self.write(getSettings(self))
    @handler.is_admin_ajax
    def post(self):
        round = self.get_argument("round", None)
        if round is None:
            return self.write({'status':"error", 'message':"Please provide a round"})
        settings = self.get_argument("settings", None)
        if settings is None:
            return self.write({'status':"error", 'message':"Please provide a settings object"})
        settings = json.loads(settings)
        print(settings)
        with db.getCur() as cur:
            for colname, val in settings.items():
                cur.execute("UPDATE Rounds SET {0} = ? WHERE Id = ?".format(colname), (val, round)) # TODO: fix SQL injection
            return self.write({'status':"success"})


class ShowSettingsHandler(handler.BaseHandler):
    def get(self):
        roundsettings = getSettings(self)
        return self.render("roundsettings.html", rounds=roundsettings['rounds'], cutsize=roundsettings['cutsize'])

class CountriesHandler(handler.BaseHandler):
    def get(self):
        with db.getCur() as cur:
            cur.execute("SELECT Id, Name, Code, IOC_Code, IOC_Name, Flag_Image FROM Countries")
            return self.write(json.dumps([{'Id': row[0], 'Name': row[1], 'Code': row[2], 'IOC_Code': row[3], 'IOC_Name': row[4], 'Flag_Image': row[5]} for row in cur.fetchall()]))
