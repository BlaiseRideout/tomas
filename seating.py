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
                                for table, players in tables.items() if len(players) == 4
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
                        SELECT
                        Players.Id,
                        Players.Country,
                        Pool,
                        COALESCE(SUM(Scores.Score), 0) AS NetScore
                         FROM Players
                           LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId AND Scores.Round < ?
                         WHERE Players.Inactive = 0
                         GROUP BY Players.Id
                         ORDER BY NetScore DESC
                    """, (round,))
                players = [
                        {
                            "Id": player,
                            "Country": country,
                            "Pool": pool,
                            "Score": score
                        }
                        for player, country, pool, score in cur.fetchall()
                    ]

                if algorithm is None:
                    algorithm = 0

                if seed is not None and len(seed) > 0:
                    random.seed(seed)

                if usepools:
                    pools = {}
                    for player in players:
                        player["Pool"] = player["Pool"] or ""
                        if not player["Pool"] in pools:
                            pools[player["Pool"]] = []
                        pools[player["Pool"]] += [player]
                    players = []
                    for pool in pools.values():
                        players += ALGORITHMS[algorithm].seat(pool)
                else:
                    players = ALGORITHMS[algorithm].seat(players)

                if duplicates:
                    playergames = playerGames(players, cur)
                    heuristic = \
                            (lambda playergames: \
                                lambda p1, p2: \
                                    playergames[(p1["Id"], p2["Id"])] or playergames[(p1["Id"], p2["Id"])] or 0
                            )(playergames)
                    players = bestArrangement(players, heuristic)

                if diversity:
                    heuristic = lambda p1, p2: \
                            1 if p1["Country"] == p2["Country"] else 0
                    players = bestArrangement(players, heuristic)

                random.seed()

                if len(players) > 0:
                    bindings = []
                    for i, player in enumerate(players):
                        bindings += [round, player["Id"], int(i / 4), i % 4]
                    cur.execute("DELETE FROM Seating WHERE Round = ?", (round,))
                    playerquery = "(?, ?, ?, ?)"
                    cur.execute("""
                        INSERT INTO Seating (Round, Player, TableNum, Wind)
                        VALUES {0}
                    """.format(",".join([playerquery] * len(players))),
                        bindings
                    )
                self.write(json.dumps({"status":"success"}))

POPULATION = 32
IMPROVECOUNT = 10

defaultHeuristic = lambda p1, p2:0

def bestArrangement(tables, heuristic = defaultHeuristic, population = POPULATION):
    numplayers = len(tables)

    tables = tables[:]
    tabless = [(tablesScore(tables, heuristic), tables)] * POPULATION

    improved = 0

    while tabless[0][0] > 0 and improved < IMPROVECOUNT:
        for j in range(POPULATION):
            newTables = mutateTables(tabless[j][1])
            score = tablesScore(newTables, heuristic)
            tabless += [(score, newTables)]
        bestScore = tabless[0][0]

        tabless.sort(key=itemgetter(0))
        tabless = tabless[0:POPULATION]

        if bestScore != tabless[0][0]:
            improved = 0
        else:
            improved += 1


    return tabless[0][1]

def mutateTables(tables):
    tables = tables[:]
    a = random.randint(0, len(tables) - 1)
    tableset = set(range(0, int(len(tables) / 4)))
    table = int(a / 4)
    otable = random.sample(tableset - set([table]), 1)[0]
    b = otable * 4 + random.randint(0, 3)
    tables[a], tables[b] = tables[b], tables[a]

    return tables

def tablesScore(players, heuristic = defaultHeuristic):
    numplayers = len(players)
    score = 0

    for i in range(0, numplayers, 4):
        table = players[i:i+4]
        score += tableScore(table, heuristic)

    return score

def tableScore(players, heuristic = defaultHeuristic):
    numplayers = len(players)

    score = 0
    for i in range(numplayers):
        for j in range(i + 1, numplayers):
            score += heuristic(players[i], players[j])
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
