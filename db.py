#!/usr/bin/env python3

import warnings
import sqlite3
import random
import datetime
import csv

import util
import settings

class getCur():
    con = None
    cur = None
    def __enter__(self):
        self.con = sqlite3.connect(settings.DBFILE)
        self.cur = self.con.cursor()
        return self.cur
    def __exit__(self, type, value, traceback):
        if self.cur and self.con and not value:
            self.cur.close()
            self.con.commit()
            self.con.close()

        return False

def init():
    warnings.filterwarnings('ignore', r'Table \'[^\']*\' already exists')

    with getCur() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS Countries("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Name TEXT,"
                "IOC TEXT"
            ");")

        cur.execute("CREATE TABLE IF NOT EXISTS Rounds("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Number INTEGER,"
                "Seed TEXT,"
                "SoftCut INTEGER,"
                "Duplicates INTEGER,"
                "Diversity TINYINT,"
                "UsePools TINYINT"
            ");")

        cur.execute("CREATE TABLE IF NOT EXISTS Pools("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Name TEXT"
            ");")

        cur.execute("CREATE TABLE IF NOT EXISTS Players("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Name TEXT,"
                "Country INTEGER,"
                "Association TEXT,"
                "Pool INTEGER,"
                "FOREIGN KEY(Country) REFERENCES Countries(Id) ON DELETE CASCADE"
            ");")

        cur.execute("CREATE TABLE IF NOT EXISTS Scores("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "GameId INTEGER,"
                "PlayerId INTEGER,"
                "Rank TINYINT,"
                "RawScore INTEGER,"
                "Score REAL,"
                "Date DATE,"
                "Chombos INTEGER,"
                "FOREIGN KEY(PlayerId) REFERENCES Players(Id) ON DELETE CASCADE"
            ");")

        cur.execute("CREATE TABLE IF NOT EXISTS Users("
                "Id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "Email TEXT NOT NULL,"
                "Password TEXT NOT NULL,"
                "UNIQUE(Email)"
            ");")

        cur.execute("SELECT COUNT(*) FROM Countries")
        if cur.fetchone()[0] == 0:
            with open("countries.csv", "r") as countriesfile:
                reader = csv.reader(countriesfile)
                for row in reader:
                    name = row[0]
                    IOC = row[1]
                    cur.execute("INSERT INTO Countries(Name, IOC) VALUES(?, ?)", (name, IOC))

def addGame(scores, gamedate = None, gameid = None):
    if gamedate is None:
        gamedate = datetime.datetime.now().strftime("%Y-%m-%d")

    if scores is None:
        return {"status":1, "error":"Please enter some scores"}

    if len(scores) != 4 and len(scores) != 5:
        return {"status":1, "error":"Please enter 4 or 5 scores"}

    total = 0
    for score in scores:
        total += score['score']

        if score['player'] == "":
            return {"status":1, "error":"Please enter all player names"}

    if total != len(scores) * 25000:
        return {"status":1, "error":"Scores do not add up to " + len(scores) * 25000}

    scores.sort(key=lambda x: x['score'], reverse=True)

    with getCur() as cur:
        if gameid is None:
            cur.execute("SELECT GameId FROM Scores ORDER BY GameId DESC LIMIT 1")
            row = cur.fetchone()
            if row is not None:
                gameid = row[0] + 1
            else:
                gameid = 0
        else:
            cur.execute("DELETE FROM Scores WHERE GameId = ?", (gameid,))

        for i in range(0, len(scores)):
            score = scores[i]

            cur.execute("SELECT Id FROM Players WHERE Id = ? OR Name = ?", (score['player'], score['player']))
            player = cur.fetchone()
            if player is None or len(player) == 0:
                cur.execute("INSERT INTO Players(Name) VALUES(?)", (score['player'],))
                cur.execute("SELECT Id FROM Players WHERE Name = ?", (score['player'],))
                player = cur.fetchone()
            player = player[0]

            adjscore = util.getScore(score['score'], len(scores), i + 1) - score['chombos'] * 8
            cur.execute("INSERT INTO Scores(GameId, PlayerId, Rank, PlayerCount, RawScore, Chombos, Score, Date, Quarter) VALUES(?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y', ?) || ' ' || case ((strftime('%m', ?) - 1) / 3) when 0 then '1st' when 1 then '2nd' when 2 then '3rd' when 3 then '4th' end)", (gameid, player, i + 1, len(scores), score['score'], score['chombos'], adjscore, gamedate, gamedate, gamedate))
    return {"status":0}
