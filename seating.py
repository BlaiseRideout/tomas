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

def getSeating(roundid = None):
    with db.getCur() as cur:
        query = """
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
            """
        bindings = ()
        if roundid is not None:
            query += " WHERE Rounds.Id = ?"
            bindings = (roundid,)
        cur.execute(query, bindings)
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

class SeatingCsvHandler(handler.BaseHandler):
    def get(self):
        round = int(self.get_argument("round", 1))
        rounds = getSeating(round)
        self.set_header("Content-Type", "application/octet-stream")
        for r in rounds:
            if r["round"] == round:
                return self.render("tables.csv", round = r)
        return self.render("tables.csv", round = {
            'winds':False,
            'tables':[]
            })

class ShowSeatingHandler(handler.BaseHandler):
    def get(self):
        return self.render("tables.html", rounds = getSeating())

class SeatingHandler(handler.BaseHandler):
    def get(self):
        return self.write(json.dumps({'rounds':getSeating()}))
    def post(self):
        round = self.get_argument('round', None)
        if round is not None:
            ret = {"status":"error", "message":"Unknown error occurred"}
            with db.getCur() as cur:
                # Get round settings
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
                    cutsize = settings.DEFAULTCUTSIZE

                # Fetch players to be seated
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
                         WHERE Players.Type = 0
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

                # Fetch substitutes
                query = """
                        SELECT
                        Players.Id
                         FROM Players
                           LEFT OUTER JOIN Countries ON Players.Country = Countries.Id
                         WHERE Players.Type = 2
                         GROUP BY Players.Id
                    """
                cur.execute(query)
                subs = []
                for i, row in enumerate(cur.fetchall()):
                    subs += [{
                                    "Rank":len(players) + i,
                                    "Id":row[0]
                                }]

                # Organize players into pools if enabled
                if usepools:
                    playerpools = pools
                    pools = {}
                    for pool, players in playerpools.items():
                        for player in players:
                            playerpool = pool + (player["Pool"] or "")
                            if not playerpool in pools:
                                pools[playerpool] = []
                            pools[playerpool] += [player]

                # Add substitutes to make pool sizes divisible by 4
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

                # Cut seats only the top players, softcut groups players by ordering
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
                            if not cut and (i + cutsize * 2 > len(players) and len(players) - (i + cutsize) < cutsize / 2):
                                pools[playerpool] += players[i:]
                            else:
                                pools[playerpool] += players[i:cutsize]

                if seed is not None and len(seed) > 0:
                    random.seed(seed)

                players = []
                for pool in pools.values():
                    pool = ALGORITHMS[algorithm].seat(pool)
                    poolplayers, status = fixTables(pool, cur, duplicates, diversity, round)
                    players += poolplayers

                random.seed()

                if len(players) > 0:
                    bindings = []
                    for i, player in enumerate(players):
                        bindings += [round, player["Id"], int(i / 4) + 1, i % 4]
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
                        improvements = []
                        if diversity:
                            improvements += ["diversity"]
                        if duplicates:
                            improvements += ["duplicates"]
                        if len(improvements) > 0:
                            ret["message"] = status
                        else:
                            ret["message"] = "Players successfully seated"
                self.write(json.dumps(ret))

def fixTables(players, cur, duplicates, diversity, round):
    if diversity:
        heuristic = lambda p1, p2: \
                1 if "Country" in p1 and "Country" in p2 and p1["Country"] == p2["Country"] else 0
    else:
        heuristic = lambda p1, p2: 0

    if duplicates:
        playergames = \
            (lambda games:
                lambda p1, p2:
                    games[(p1, p2)] if (p1, p2)  in games else (
                            games[(p1, p2)] if (p1, p2) in games else 0)
            )(playerGames(players, cur, round))
        oldheuristic = heuristic
        heuristic = \
                (lambda playergames:
                    lambda p1, p2:
                         playergames(p1["Id"], p2["Id"]) * settings.DUPLICATEIMPORTANCE + oldheuristic(p1, p2)
                )(playergames)

    for i, player in enumerate(players):
        player["Seat"] = i

    swaps = 0
    maxswap = 0
    iterations = 0
    while iterations < 5:
        oldScore = tablesScore(players, heuristic)
        swapsmade, distance = improvePlayers(players, heuristic)
        swaps += swapsmade
        maxswap = max(maxswap, distance)
        newScore = tablesScore(players, heuristic)
        if oldScore <= newScore:
            break
        iterations += 1

    status = "{0} swaps made (max distance {1}) in {3} phases to score {2}".format(
                                    str(swaps),
                                    maxswap,
                                    newScore,
                                    iterations)
    return (players, status)

def improvePlayers(players, heuristic):
    t = 0
    swaps = 0
    maxswap = 0
    while t < len(players):
        table = players[t:t+4]
        for i in range(len(table)):
            j = i + 1
            while j < len(table):
                if heuristic(table[i], table[j]) > 0:
                    candidatei = bestSwap(players, heuristic, t, i)
                    candidatej = bestSwap(players, heuristic, t, j)

                    if candidatei[0] < candidatej[0]:
                        curPlayer = i
                        seat2 = candidatei[1]
                    else:
                        curPlayer = j
                        seat2 = candidatej[1]
                    seat1 = table[curPlayer]["Seat"]

                    players[seat1], players[seat2] = players[seat2], players[seat1]
                    players[seat1]["Seat"], players[seat2]["Seat"] = seat1, seat2
                    table = players[t:t+4]
                    distance = abs(players[seat1]["Rank"] - players[seat2]["Rank"])
                    maxswap = max(maxswap, distance)
                    swaps += 1
                j += 1
        t += 4
    return (swaps, maxswap)

def bestSwap(players, heuristic, t, player):
    table = players[t:t+4]
    toReplace = table[player]

    replacements = players[0:t] + players[t + 4:]
    replacements.sort(key=lambda replacement:abs(replacement["Rank"] - toReplace["Rank"]))

    candidates = []

    for replacement in replacements:
        distance = abs(replacement["Rank"] - toReplace["Rank"])
        if distance > settings.MAXSWAPDISTANCE:
            break

        repPlayer = replacement["Seat"] % 4
        repTable = replacement["Seat"] - repPlayer
        repTable = players[repTable:repTable + 4]

        curTable = table[:]

        curTable[player], repTable[repPlayer] = repTable[repPlayer], curTable[player]
        newScore = tableScore(repTable, heuristic) + tableScore(curTable, heuristic)

        candidates += [(newScore + distance / settings.MAXSWAPDISTANCE, replacement["Seat"])]
    candidates.sort(key=itemgetter(0))

    return candidates[0]

def tablesScore(players, heuristic):
    numplayers = len(players)
    score = 0

    for i in range(0, numplayers, 4):
        table = players[i:i+4]
        score += tableScore(table, heuristic)

    return score

def tableScore(players, heuristic):
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
