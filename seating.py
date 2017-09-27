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

ORDERINGS = [
    ("Number", "ORDER BY Players.Number ASC"),
    ("Score", "ORDER BY NetScore DESC"),
    ("Rank", "ORDER BY LastRank ASC, NetScore DESC")
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

class OrderingsHandler(handler.BaseHandler):
    def get(self):
        return self.write(json.dumps(
            [
                {
                    'Id': num,
                    'Name': ordering[0]
                }
                for num, ordering in enumerate(ORDERINGS)
            ]
        ))

def getSeating():
    with db.getCur() as cur:
        cur.execute("""
                SELECT Rounds.Id,
                 Rounds.Winds,
                 Seating.TableNum,
                 Seating.Wind,
                 Players.Id,
                 Players.Name,
                 Countries.Code,
                 Countries.Flag_Image,
                 COALESCE(Scores.Rank, 0),
                 COALESCE(Scores.RawScore, 0),
                 COALESCE(Scores.Score, 0),
                 COALESCE(Scores.Chombos, 0)
                 FROM Rounds
                 LEFT OUTER JOIN Seating
                   ON Rounds.Id = Seating.Round
                 LEFT OUTER JOIN Players
                   ON Players.Id = Seating.Player
                 LEFT OUTER JOIN Scores
                   ON Rounds.Id = Scores.Round AND Players.Id = Scores.PlayerId
                 LEFT OUTER JOIN Countries
                   ON Countries.Id = Players.Country
            """)
        rounds = {}
        for row in cur.fetchall():
            roundID, winds, table, wind, playerid, name, country, flag, rank, rawscore, score, chombos  = row
            if roundID is not None:
                if not roundID in rounds:
                    rounds[roundID] = {
                                'winds':winds,
                                'tables':{},
                                'has_scores': False
                            }
                if table is not None:
                    if not table in rounds[roundID]['tables']:
                        rounds[roundID]['tables'][table] = {}
                    if wind is not None and name is not None:
                        rounds[roundID]['has_scores'] |= rawscore > 0
                        rounds[roundID]['tables'][table][wind] = {
                                "id":playerid,
                                "name":name,
                                "country":country,
                                "flag":flag,
                                "rank":rank,
                                "rawscore":rawscore,
                                "score": round(score, 1) if isinstance(score, float) else score,
                                "chombos":chombos
                            }
        winds = "東南西北"
        rounds = [
                {
                    'round':      roundID,
                    'winds':      tables['winds'],
                    'has_scores': rounds[roundID]['has_scores'],
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
                            for table, players in tables['tables'].items() if len(players) == 4
                        ]
                }
                for roundID, tables in rounds.items()
            ]
        for a_round in rounds:
            for table in a_round['tables']:
                table['total'] = sum([player['player']['rawscore'] for player in table['players']])
        return rounds

class ShowSeatingHandler(handler.BaseHandler):
    def get(self):
        return self.render("tables.html", rounds = getSeating())

def fixTables(players, cur, duplicates, diversity, round):
    if diversity:
        heuristic = lambda p1, p2: \
                1 if p1["Country"] == p2["Country"] else 0
    else:
        heuristic = lambda p1, p2: 0

    if duplicates:
        playergames = playerGames(players, cur)
        oldheuristic = heuristic
        heuristic = \
                (lambda playergames: \
                    lambda p1, p2: \
                        (playergames[(p1["Id"], p2["Id"])] if (p1["Id"], p2["Id"]) in playergames else (\
                            playergames[(p1["Id"], p2["Id"])] if (p1["Id"], p2["Id"]) in playergames else \
                            0)) + oldheuristic(p1, p2)
                )(playergames)

    improved = 0
    iterations = 100
    while improved < 5 and iterations > 0:
        oldScore = tablesScore(players, heuristic)
        improvePlayers(players, heuristic)
        newScore = tablesScore(players, heuristic)
        if oldScore > newScore:
            improved = 0
        else:
            break
        improved += 1
        iterations -= 1

    return players

def improvePlayers(players, heuristic):
    t = 0
    while t < len(players):
        table = players[t:t+4]
        for i in range(len(table)):
            for j in range(i + 1, len(table)):
                if heuristic(table[i], table[j]) > 0:
                    if table[i]["Rank"] > table[j]["Rank"]:
                        toReplace = i
                    else:
                        toReplace = j
                    replacements = players[0:t] + players[t + 4:]
                    replacements.sort(key=lambda p:abs(table[toReplace]["Rank"] - p["Rank"]))
                    for replacement in replacements:
                        repPlayer = replacement["Seat"] % 4
                        repTable = replacement["Seat"] - repPlayer
                        repTable = players[repTable:repTable + 4]
                        curTable = table[:]
                        oldScore = tableScore(repTable, heuristic) + tableScore(curTable, heuristic)
                        curTable[toReplace], repTable[repPlayer] = repTable[repPlayer], curTable[toReplace]
                        newScore = tableScore(repTable, heuristic) + tableScore(curTable, heuristic)
                        if newScore < oldScore:
                            players[table[toReplace]["Seat"]], players[replacement["Seat"]] = players[replacement["Seat"]], players[table[toReplace]["Seat"]]
                            break
        t += 4

class SeatingHandler(handler.BaseHandler):
    def get(self):
        return self.write(json.dumps({'rounds':getSeating()}))
    def post(self):
        round = self.get_argument('round', None)
        if round is not None:
            ret = {"status":"error", "message":"Unknown error occurred"}
            with db.getCur() as cur:
                cur.execute(
                        """SELECT
                            Id,
                            COALESCE(Ordering, 0),
                            COALESCE(Algorithm, 0),
                            Seed,
                            Cut,
                            SoftCut,
                            CutSize,
                            Duplicates,
                            Diversity,
                            UsePools
                             FROM Rounds WHERE Id = ?""",
                        (round,)
                    )
                round, ordering, algorithm, seed, cut, softcut, cutsize, duplicates, diversity, usepools = cur.fetchone()
                cut = cut == 1
                softcut = softcut == 1
                duplicates = duplicates == 1
                diversity = diversity == 1
                usepools = usepools == 1

                if (cut or softcut) and not cutsize:
                    cur.execute("SELECT Value FROM GlobalPreferences WHERE Preference = 'CutSize'")
                    cutsize = cur.fetchone()
                    if cutsize is None:
                        cutsize = settings.DEFAULTCUTSIZE
                    else:
                        cutsize = int(cutsize[0])

                query = """
                        SELECT
                        Players.Id,
                        Players.Country,
                        Pool,
                        COALESCE(SUM(Scores.Score), 0) AS NetScore,
                        LastScore.Rank AS LastRank
                         FROM Players
                           LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId AND Scores.Round < ?
                           LEFT OUTER JOIN Scores AS LastScore ON Players.Id = LastScore.PlayerId AND LastScore.Round = ? - 1 AND LastScore.Rank != 0
                         WHERE Players.Inactive = 0
                         GROUP BY Players.Id
                    """
                query += ORDERINGS[ordering][1]
                cur.execute(query, (round, round))
                players = []
                for i, row in enumerate(cur.fetchall()):
                    player, country, pool, score, lastrank = row
                    if ordering != 2 or lastrank:
                        players += [{
                                        "Rank":i,
                                        "Id": player,
                                        "Country": country,
                                        "Pool": pool,
                                        "LastRank": lastrank
                                    }]
                pools = {"": players}

                query = """
                        SELECT
                        Players.Id
                         FROM Players
                           LEFT OUTER JOIN Countries ON Players.Country = Countries.Id
                         WHERE Players.Inactive = 2
                         GROUP BY Players.Id
                    """
                cur.execute(query)
                subs = []
                for i, row in enumerate(cur.fetchall()):
                    subs += [{
                                    "Rank":len(players) + i,
                                    "Id":row[0]
                                }]

                if usepools:
                    playerpools = pools
                    pools = {}
                    for pool, players in playerpools.items():
                        for player in players:
                            playerpool = pool + (player["Pool"] or "")
                            if not playerpool in pools:
                                pools[playerpool] = []
                            pools[playerpool] += [player]

                for pool in pools.values():
                    subsNeeded = (4 - len(pool) % 4)
                    if subsNeeded != 4:
                        if len(subs) >= subsNeeded:
                            pool += subs[0:subsNeeded]
                            subs = subs[subsNeeded:]
                        else:
                            ret["status"] = "warn"
                            ret["message"] = "Not enough substitutes to seat all players"
                            pool = pool[0:int(len(pool) / 4) * 4]

                if softcut or cut:
                    playerpools = pools
                    pools = {}
                    for pool, players in playerpools.items():
                        if len(players) <= cutsize:
                            continue
                        for i in range(0, cutsize if cut else len(players), cutsize):
                            playerpool = pool + str(i)
                            if not playerpool in pools:
                                pools[playerpool] = []
                            if i + cutsize * 2 > len(players) and len(players) - (i + cutsize) < cutsize / 2:
                                pools[playerpool] += players[i:]
                            else:
                                pools[playerpool] += players[i:cutsize]

                if seed is not None and len(seed) > 0:
                    random.seed(seed)

                players = []
                for pool in pools.values():
                    pool = ALGORITHMS[algorithm].seat(pool)
                    for i, player in enumerate(pool):
                        player["Seat"] = i
                    players += fixTables(pool, cur, duplicates, diversity, round)

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
                    if ret["status"] != "warn":
                        ret["status"] = "success"
                self.write(json.dumps(ret))

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

def playerGames(players, c, round = None):
    numplayers = len(players)

    playergames = dict()

    query = """
        SELECT COUNT(*) FROM Scores
        WHERE PlayerId = ? AND GameId IN (
            SELECT GameId FROM Scores WHERE PlayerId = ?
          )
        """
    gbindings = []
    if round is not None:
        query += " AND Round < ?"
        gbindings += [round]
    for i in range(numplayers):
        for j in range(i + 1, numplayers):
            bindings = [players[i]['Id'], players[j]['Id']]
            games = c.execute(query, bindings + gbindings).fetchone()[0]
            if games != 0:
                playergames[(players[i]['Id'], players[j]['Id'])] = games

    return playergames
