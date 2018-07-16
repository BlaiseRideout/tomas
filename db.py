#!/usr/bin/env python3

import warnings
import sqlite3
import random
import datetime
import csv
import re
import os
import shutil
import logging

import util
import settings
from sqlite_schema import *

log = logging.getLogger("WebServer")

class getCur():
    con = None
    cur = None
    def __enter__(self):
        self.con = sqlite3.connect(settings.DBFILE)
        self.cur = self.con.cursor()
        self.cur.execute("PRAGMA foreign_keys = 1;")
        return self.cur
    def __exit__(self, type, value, traceback):
        if self.cur and self.con and not value:
            self.cur.close()
            self.con.commit()
            self.con.close()

        return False

schema = {
    'Users': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Email TEXT NOT NULL",
        "Password TEXT NOT NULL",
        "UNIQUE(Email)"
    ],
    'Admins': [
        "Id INTEGER PRIMARY KEY NOT NULL",
        "FOREIGN KEY(Id) REFERENCES Users(Id) ON DELETE CASCADE"
    ],
    'Tournaments': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT",
        "Owner INTEGER",
        "Start DATE DEFAULT CURRENT_DATE",
        "End DATE DEFAULT CURRENT_DATE",
        "Location TEXT",
        "Country INTEGER",
        "Logo TEXT",
        "LinkURL TEXT",
        "FOREIGN KEY(Owner) REFERENCES Users(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE"
    ],
    'Countries': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Name TEXT",
        "Code TEXT",
        "IOC_Code TEXT",
        "IOC_Name TEXT",
        "Flag_Image TEXT"
    ],
    'Rounds': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Tournament INTEGER",
        "Number INTEGER",
        "Name TEXT",
        "Ordering INTEGER",
        "Algorithm INTEGER",
        "Seed TEXT DEFAULT ''",
        "Cut TINYINT DEFAULT 0",
        "SoftCut TINYINT DEFAULT 0",
        "CutMobility TINYINT DEFAULT 0",
        "CombineLastCut TINYINT DEFAULT 0",
        "CutSize INTEGER DEFAULT NULL",
        "Duplicates TINYINT DEFAULT 1",
        "Diversity TINYINT DEFAULT 1",
        "UsePools TINYINT DEFAULT 1",
        "Winds TINYINT DEFAULT 1",
        "Games INTEGER DEFAULT 1",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE"
    ],
    'Players': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Tournament INTEGER",
        "Name TEXT NOT NULL",
        "Number INTEGER",
        "Country INTEGER",
        "Association TEXT",
        "Pool TEXT",
        "Wheel TINYINT DEFAULT 0",
        "Type TINYINT DEFAULT 0",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE",
        "CONSTRAINT NumberInTournament UNIQUE(Number, Tournament)"
    ],
    'Seating': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "Round INTEGER",
        "Tournament INTEGER",
        "Player INTEGER",
        "TableNum INTEGER",
        "Wind TINYINT",
        "FOREIGN KEY(Tournament) REFERENCES Tournaments(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Player) REFERENCES Players(Id) ON DELETE CASCADE",
        "FOREIGN KEY(Round) REFERENCES Rounds(Id) ON DELETE CASCADE"
    ],
    'Scores': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "GameId INTEGER",
        "Round INTEGER",
        "PlayerId INTEGER",
        "Rank TINYINT",
        "RawScore INTEGER",
        "Score REAL",
        "FOREIGN KEY(Round) REFERENCES Rounds(Id) ON DELETE CASCADE",
        "FOREIGN KEY(PlayerId) REFERENCES Players(Id) ON DELETE CASCADE",
        "CONSTRAINT OneScorePerPlayerPerGame UNIQUE (Round, GameId, PlayerId)"
    ],
    'Penalties': [
        "Id INTEGER PRIMARY KEY AUTOINCREMENT",
        "ScoreId INTEGER",
        "Penalty INTEGER",
        "Description TEXT NOT NULL",
        "Referee TEXT",
        "FOREIGN KEY(ScoreId) REFERENCES Scores(Id) ON DELETE CASCADE",
    ],
    'ResetLinks': [
        'Id CHAR(32) PRIMARY KEY NOT NULL',
        'User INTEGER',
        'Expires DATETIME',
        'FOREIGN KEY(User) REFERENCES Users(Id) ON DELETE CASCADE'
    ],
    'VerifyLinks': [
        'Id CHAR(32) PRIMARY KEY NOT NULL',
        'Email TEXT NOT NULL',
        'Expires DATETIME'
    ],
    'Preferences': [
        'UserId INTEGER',
        'Preference TEXT NOT NULL',
        'Value SETTING NOT NULL',
        'FOREIGN KEY(UserId) REFERENCES Users(Id) ON DELETE CASCADE'
    ],
}

# Decode table for Players.Type values
playertypes = ['Regular', 'Inactive', 'Substitute', 'UnusedPoints']
playertypecode = dict([(val, i) for i, val in enumerate(playertypes)])

def init(force=False, dbfile=settings.DBFILE, verbose=0):
    existing_schema = get_sqlite_db_schema(dbfile)
    desired_schema = parse_database_schema(schema)
    if not compare_and_prompt_to_upgrade_database(
            desired_schema, existing_schema, dbfile,
            ordermatters=False, prompt_prefix='SCHEMA CHANGE: ', 
            force_response='y' if force else None, 
            backup_dir=settings.DBBACKUPS, 
            backup_prefix=settings.DBDATEFORMAT + '-', verbose=verbose):
        log.error('Database upgrade during initialization {}.'.format(
            'failed' if force else 'was either cancelled or failed'))

    with getCur() as cur:
        cur.execute("SELECT COUNT(*) FROM Countries")
        if cur.fetchone()[0] == 0:
            countries_file = 'countries.csv'
            try:
                vars = {
                    'URLprefix': (settings.SERVERPREFIX or '') +
                    settings.PROXYPREFIX
                }
                log.info("Countries table is empty.  Loading {} with substitutions {}"
                         .format(countries_file, vars))
                with open(countries_file, "r", encoding='utf-8') as countriesfile:
                    reader = csv.reader(countriesfile)
                    for row in reader:
                        cur.execute(
                            "INSERT INTO Countries"
                            " (Name, Code, IOC_Code, IOC_Name, Flag_Image)"
                            " VALUES(?, ?, ?, ?, ?)",
                            list(map(lambda x: x.format(**vars), row)))
            except Exception as e:
                log.error("Error loading countries from {}: {}".format(
                    countries_file, e))

def make_backup():
    backupdb = datetime.datetime.now().strftime(settings.DBDATEFORMAT) + "-" + os.path.split(settings.DBFILE)[1]
    backupdb = os.path.join(settings.DBBACKUPS, backupdb)
    log.info("Making backup of database {0} to {1}".format(settings.DBFILE, backupdb))
    if not os.path.isdir(settings.DBBACKUPS):
        os.mkdir(settings.DBBACKUPS)
    shutil.copyfile(settings.DBFILE, backupdb)

def words(spec):
    return re.findall(r'\w+', spec)

def table_field_names(tablename):
    return [words(fs)[0] for fs in schema.get(tablename, []) 
            if not words(fs)[0].upper() in [
                    'FOREIGN', 'UNIQUE', 'CONSTRAINT', 'PRIMARY', 'CHECK']]

_unusedPointsPlayer = None
unusedPointsPlayerName = '!#*UnusedPointsPlayer*#!'

def getUnusedPointsPlayerID():
    """ Get the ID of the Players table entry that records unused points in
    games.  If an entry doesn't exist, create one."""
    global _unusedPointsPlayer, unusedPointsPlayerName, playertypes
    if _unusedPointsPlayer:
        return _unusedPointsPlayer
    with getCur() as cur:
        cur.execute("SELECT Id from Players WHERE Name = ? AND Type = ?",
                    (unusedPointsPlayerName, playertypecode['UnusedPoints']))
        result = cur.fetchall()
        if len(result) > 1:
            raise Exception("More than 1 player defined for unused points")
        elif len(result) == 1:
            _unusedPointsPlayer = result[0][0]
        else:
            cur.execute(
                "INSERT INTO Players (Name, Type) VALUES (?, ?)",
                (unusedPointsPlayerName, playertypecode['UnusedPoints']))
            _unusedPointsPlayer = cur.lastrowid
    return _unusedPointsPlayer

def updateGame(scores):
    if scores is None:
        return {"status":"error", "message":"Please enter some scores"}

    if len(scores) != 4 and len(scores) != 5:
        return {"status":"error", "message":"Please enter 4 or 5 scores"}

    try:
        with getCur() as cur:
            total = 0
            gameID = None
            roundID = None
            unusedPointsIncluded = False
            for score in scores:
                total += score['rawscore']

                for table, id in [('Players', 'playerid'),
                                  ('Rounds', 'roundid')]:
                    if score['playerid'] == getUnusedPointsPlayerID():
                        continue
                    cur.execute("SELECT Id from {0} WHERE Id = ?".format(table),
                                (score[id],))
                    if cur.fetchone() is None:
                        return {"status":"error",
                                "message":"ID {0} not in {1}".format(
                                    score[id], table)}
                if gameID is not None and gameID != score['gameid']:
                    return {"status":"error",
                            "message": "Inconsistent game IDs"}
                gameID = score['gameid']
                if roundID is not None and roundID != score['roundid']:
                    return {"status":"error",
                            "message": "Inconsistent round IDs"}
                roundID = score['roundid']
                if score['playerid'] == getUnusedPointsPlayerID():
                    unusedPointsIncluded = True
                    if len(scores) == 4:
                        return {"status":"error",
                                "message":"Unused points can only be 5th score"}
            if len(scores) == 5 and not unusedPointsIncluded:
                return {"status":"error",
                        "message":"Only 4 scores can be submitted per game"}
            if total != 4 * settings.SCOREPERPLAYER:
                return {"status":"error",
                        "message":"Scores do not add up to {0}".format(
                            4 * settings.SCOREPERPLAYER)}

            identifiers = ['roundid', 'gameid', 'playerid']
            fields = ['rank', 'rawscore', 'score']
            cur.executemany(
                    "INSERT OR IGNORE INTO Scores (Round, GameId, PlayerId) VALUES (?, ?, ?)",
                    map(lambda score: [score[f] for f in identifiers], scores))
            cur.executemany(
                "UPDATE Scores SET Rank = ?, RawScore = ?, Score = ?"
                " WHERE Round = ? AND GameId = ? AND PlayerId = ?",
                map(lambda score: [score[f] for f in fields] + [score[f] for f in identifiers], scores))
            # If unused points is edited to be 0, remove the score record so
            # it won't show up in the display
            if unusedPointsIncluded and 0 in [
                    score['rawscore'] for score in scores
                    if score['playerid'] == getUnusedPointsPlayerID()]:
                cur.execute("DELETE FROM Scores"
                            " WHERE Round = ? AND GameId = ? AND PlayerId = ?",
                        (roundID, gameID, getUnusedPointsPlayerID()))
            cur.execute("SELECT Id, PlayerId FROM Scores"
                        " WHERE Round = ? AND GameId = ?",
                        (roundID, gameID))
            IDpairs = cur.fetchall()
    except Exception as e:
        return {"status":"error",
                "message": "Error during database update of scores, {0}".format(e)}

    return {"status": "success", "IDpairs": IDpairs, "message":"Updated game scores"}

penalty_fields = ['penalty', 'description', 'referee']

valid = {
    'all': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'description': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'penalty': re.compile(r'^-?\d*$'),
    'name': re.compile(r'^[\w\s():,.\'+\u202F-]*$'),
    'number': re.compile(r'^\d*$'),
    'email': re.compile(r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]+$', re.IGNORECASE),
    'admin': re.compile(r'^(0|1|Y|N|YES|NO)$')
}

def updatePenalties(scoreID, penalties):
    global penalty_fields
    global valid
    if penalties is None:
        return {"status":"error", "message":"Please enter a list of penalties"}

    try:
        with getCur() as cur:
            cur.execute("SELECT Id from Scores WHERE Id = ?", (scoreID,))
            if cur.fetchone() is None:
                return {"status": "error",
                        "message":"Score ID {0} not in Scores".format(scoreID)}
            message = ''
            for penalty in penalties:
                if str(penalty['scoreID']) != str(scoreID):
                    return {"status":"error",
                            "message": "All penalties must be for a single player score record"}
                if penalty['penalty'] > 0:
                    message += ' All penalties must be negative integers.'
                for field, val in penalty.items():
                    if field not in penalty_fields or not isinstance(val, str):
                        continue
                    if not valid[field if field in valid else 'all'].match(val):
                        message += " Invalid entry for {0} field.".format(
                                    field)
            if len(message) > 0:
                return {"status": "error", "message": message}

            cur.execute("DELETE FROM Penalties WHERE ScoreId = ?", (scoreID,))
            fields = ['scoreID', 'penalty', 'description', 'referee']
            cur.executemany(
                "INSERT INTO Penalties"
                " (ScoreId, Penalty, Description, Referee)"
                " VALUES (?, ?, ?, ?)",
                map(lambda penalty: [penalty[f] for f in fields], penalties))
    except Exception as e:
        return {"status":"error",
                "message": "Error during database update of penalties, {0}".format(e)}

    return {"status": "success"}
