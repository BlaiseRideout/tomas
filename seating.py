#!/usr/bin/env python3

import json
import tornado.web
import db
import random
import datetime
import math
from operator import itemgetter

import handler
import settings

class SeatingAlg():
    name = None
    def seat(self, players):
        return players

class Random(SeatingAlg):
    name = "Random"
    def seat(self, players):
        players = players[:]
        random.shuffle(players)
        return players

class Snake(SeatingAlg):
    name = "Snake"
    def seat(self, players):
        rowlen = int(len(players) / 4)
        numplayers = rowlen * 4
        players = [players[i:i + rowlen] for i in range(0, numplayers, rowlen)]
        for i, row in enumerate(players):
            if i % 2 == 1:
                row.reverse()
        return list(sum(zip(*players), ()))

class StraightAcross(SeatingAlg):
    name = "Straight Across"
    def seat(self, players):
        rowlen = int(len(players) / 4)
        numplayers = rowlen * 4
        players = [players[i:i + rowlen] for i in range(0, numplayers, rowlen)]
        return list(sum(zip(*players), ()))

ALGORITHMS = [
    Random(),
    Snake(),
    StraightAcross()
]

class AlgorithmsHandler(handler.BaseHandler):
    def get(self):
        return self.write(json.dumps(
            [
                {
                    'Id': num,
                    'Name': alg.name
                }
                for num, alg in enumerate(ALGORITHMS)
            ]
        ))

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
                        "SELECT Id, Algorithm, Seed, SoftCut, Duplicates, Diversity, UsePools"
                        " FROM Rounds WHERE Id = ?",
                        (round,)
                    )
                round, algorithm, seed, softcut, duplicates, diversity, usepools = cur.fetchone()
                cur.execute("""
                        SELECT Players.Id,
                        COALESCE(SUM(Scores.Score), 0) AS NetScore
                         FROM Players
                           LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId AND Scores.Round < ?
                         GROUP BY Players.Id
                         ORDER BY NetScore DESC
                    """, (round,))
                players = [row[0] for row in cur.fetchall()]

                if algorithm is None:
                    algorithm = 0
                players = ALGORITHMS[algorithm].seat(players)

                if len(players) > 0:
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

POPULATION = 256

def bestArrangement(tables, playergames, population = POPULATION):
    numplayers = len(tables)

    tabless = []
    for i in range(POPULATION):
        tables = tables[:]
        random.shuffle(tables)
        tabless += [(tablesScore(tables, playergames), tables)]
    tabless.sort(key=itemgetter(0))

    minScore = tabless[0][0]
    iteration = 0

    while iteration < numplayers and minScore > 0:
        for j in range(POPULATION):
            newTables = mutateTables(tabless[j][1])
            tabless += [(tablesScore(newTables, playergames), newTables)]
        tabless.sort(key=itemgetter(0))
        tabless = tabless[0:POPULATION]

        iteration += 1
        if minScore != tabless[0][0]:
            minScore = tabless[0][0]
            improved = 0

    return tabless[0][1]

def mutateTables(tables):
    tables = tables[:]
    a = random.randint(0, len(tables) - 1)
    b = random.randint(0, len(tables) - 1)
    tables[a], tables[b] = tables[b], tables[a]

    return tables

def tablesScore(players, playergames):
    numplayers = len(players)
    if numplayers >= 8:
        tables_5p = numplayers % 4
        total_tables = int(numplayers / 4)
        tables_4p = total_tables - tables_5p
    else:
        if numplayers >= 5:
            tables_5p = 1
        else:
            tables_5p = 0
        total_tables = 1
        tables_4p = total_tables - tables_5p

    score = 0

    for i in range(0, tables_4p * 4, 4):
        table = players[i:i+4]
        score += tableScore(table, playergames)

    for i in range(tables_4p * 4, numplayers, 5):
        table = players[i:i+5]
        score += tableScore(table, playergames)

    return score

def tableScore(players, playergames):
    numplayers = len(players)

    score = 0
    for i in range(numplayers):
        for j in range(i + 1, numplayers):
            if (players[i], players[j]) in playergames:
                score += playergames[(players[i], players[j])]
            elif (players[j], players[i]) in playergames:
                score += playergames[(players[j], players[i])]
    return score

def playerGames(players, c):
    numplayers = len(players)

    playergames = dict()

    for i in range(numplayers):
        for j in range(i + 1, numplayers):
            games = c.execute("""
                SELECT COUNT(*) FROM Scores
                WHERE PlayerId = ? AND GameId IN (
                    SELECT GameId FROM Scores WHERE PlayerId = ?
                  )
                """, (players[i], players[j])).fetchone()[0]
            if games != 0:
                playergames[(players[i], players[j])] = games

    return playergames
