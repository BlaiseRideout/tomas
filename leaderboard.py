#!/usr/bin/env python3

import json
import operator

import db
import handler
import settings


def findLeaderboard(leaderboards, player):
    if len(leaderboards) == 1:
        return leaderboards[0]
    else:
        for leaderboard in leaderboards:
            if player in leaderboard:
                return leaderboard
    raise ValueError("Can't introduce new player partway through tournament that has rounds without cut mobility!")

def flattenLeaderboard(leaderboard):
    return sorted(
        leaderboard.values(),
        # key=operator.itemgetter('type', 'total'),
        key=lambda r: (2 if r['type'] == 'Regular' else 
                       1 if r['type'] == 'Inactive' else 0,
                       r['total']),
        reverse=True
    )

def dictifyLeaderboard(leaderboard):
    return dict([
        (entry['player'], entry)
        for entry in leaderboard
    ])

def getPenalties(roundId):
    # Get the new round's penalties
    penaltyQuery = """SELECT
            Players.Id, COALESCE(SUM(Penalty), 0) as Penalty
        FROM Players
        LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId
        LEFT OUTER JOIN Penalties ON Scores.Id = Penalties.ScoreId
        WHERE Scores.Round == ?
        GROUP BY Players.Id;"""

    with db.getCur() as cur:
        cur.execute(penaltyQuery, (roundId,))
        return dict(cur.fetchall())

def cutLeaderboards(leaderboards, playerRound):
    # Cut the leaderboard when appropriate

    if playerRound is None:
        return leaderboards

    cutSize = playerRound['cutSize']

    if cutSize == 0:
        cutSize = settings.DEFAULTCUTSIZE

    # If we should cut the leaderboards this round
    if (playerRound['cut'] is not None and
            playerRound['cut'] > 0 and
            not playerRound['cutMobility']):
        old_leaderboards = leaderboards
        leaderboards = []
        if playerRound['cutCount'] <= 0:
            cutsMade = -math.inf
        else:
            cutsMade = 0
        for leaderboard in old_leaderboards:
            if len(leaderboard) > cutSize and cutsMade < playerRound['cutCount']:
                leaderboard = flattenLeaderboard(leaderboard)
                for i in range(0, len(leaderboard), cutSize):
                    nextI = i + cutSize

                    if (    nextI >= len(leaderboard)               # If this is the last leaderboard
                            or
                            (len(leaderboard) - nextI < cutSize and # If the next leaderboard wouldn't reach the cutSize,
                                playerRound['combineLastCut'])      #   and we're combining smaller leaderboards
                            or
                            cutsMade >= playerRound['cutCount']):   # If we've reached our cutCount
                        leaderboards += [dictifyLeaderboard(leaderboard[i:])]
                        break
                    else:
                        leaderboards += [dictifyLeaderboard(leaderboard[i:nextI])]
                        cutsMade += 1
            else:
                leaderboards += [leaderboard]

    return leaderboards

def leaderData(tournamentid):
    query = """SELECT
         Players.Id, Players.Name, Countries.Code, Flag_Image, Type,
         COUNT(Scores.Id) AS GamesPlayed,
         COALESCE(ROUND(SUM(Scores.Score) * 100) / 100, 0) AS TotalPoints,
         COALESCE(Rounds.Id, 0), (Rounds.SoftCut + Rounds.Cut), Rounds.CutMobility,
         COALESCE(Rounds.cutSize, 0), Rounds.CombineLastCut, Rounds.CutCount
       FROM Players
       LEFT JOIN Scores ON Players.Id = Scores.PlayerId
       LEFT JOIN Rounds ON Scores.Round = Rounds.Id
       LEFT JOIN Countries ON Players.Country = Countries.Id
       WHERE Players.Type != ?
       AND Players.Tournament = ?
       GROUP BY Players.Id, Rounds.Id
       ORDER BY Rounds.Id ASC;"""

    fields = ['player', 'name', 'country', 'flag_image', 'type',
                'gamesPlayed',
                'points',
                'round', 'cut', 'cutMobility',
                'cutSize', 'combineLastCut', 'cutCount']

    zeroScores = {'total': 0,
                    'points':0,
                    'gamesPlayed': 0,
                    'penalty': 0}
    with db.getCur() as cur:
        cur.execute(query, (db.playertypecode['UnusedPoints'], tournamentid))
        rows = cur.fetchall()

    scores = [dict(zip(fields, row)) for row in rows]

    leaderboards = [{}]
    currentRound = None
    penalties = None
    for playerRound in scores:
        playerRound['type'] = db.playertypes[int(playerRound['type'] or 0)]

        # If we've reached a new round
        if currentRound is None or playerRound['round'] != currentRound['round']:
            # Potentially cut the leaderboard
            leaderboards = cutLeaderboards(leaderboards, currentRound)

            currentRound = playerRound
            # Get the new round's penalties
            penalties = getPenalties(currentRound['round'])

        player = playerRound['player']
        leaderboard = findLeaderboard(leaderboards, player)

        if player not in leaderboard:
            leaderboard[player] = dict(playerRound)
            leaderboard[player].update(zeroScores)

        leaderboard[player]['points'] += playerRound['points']
        leaderboard[player]['total'] += playerRound['points']
        leaderboard[player]['gamesPlayed'] += playerRound['gamesPlayed']

        if player in penalties:
            leaderboard[player]['penalty'] += penalties[player]
            leaderboard[player]['total'] += penalties[player]

    place = 1
    old_leaderboards = leaderboards
    leaderboards = []
    lastTotal = None
    for leaderboard in old_leaderboards:
        leaderboard = flattenLeaderboard(leaderboard)
        for rec in leaderboard:
            if lastTotal is not None and rec['total'] != lastTotal:
                place += 1
            rec['place'] = place
            rec['points'] = round(rec['points'], 2)
            rec['total'] = round(rec['total'], 2)
            lastTotal = rec['total']
        leaderboards += leaderboard

    return (leaderboards, place == 1)

class LeaderDataHandler(handler.BaseHandler):
    @handler.tournament_handler_ajax
    def get(self):
        leaderboard, allTied = leaderData(self.tournamentid)
        self.write(json.dumps({'leaderboard':leaderboard,'allTied':allTied}))

class LeaderboardHandler(handler.BaseHandler):
    @handler.tournament_handler
    def get(self):
        leaderboard, allTied = leaderData(self.tournamentid)
        self.render("leaderboard.html", leaderboard = leaderboard, allTied = allTied)

class ScoreboardHandler(handler.BaseHandler):
    @handler.tournament_handler
    def get(self):
        query = """SELECT
           Players.Id, Players.Name, Countries.Code, flag_image, Type,
           Rounds.Number, Rounds.Name, Scores.Rank,
           ROUND(Scores.Score * 100) / 100,
           COALESCE(SUM(Penalties.Penalty), 0),
           COALESCE(ROUND((Scores.Score + COALESCE(SUM(Penalties.Penalty), 0))
                          * 100) / 100, 0)
           FROM Scores
           LEFT JOIN Rounds ON Scores.Round = Rounds.Id
           LEFT JOIN Players ON Scores.PlayerId = Players.Id
           LEFT JOIN Countries ON Players.Country = Countries.Id
           LEFT OUTER JOIN Penalties ON Scores.Id = Penalties.ScoreId
           WHERE Players.Type != ?
           AND Players.Tournament = ?
           GROUP BY Scores.Id
           ORDER BY Type ASC, Players.Name ASC
        """
        fields = ['id', 'name', 'country', 'flag_image', 'type',
                  'round', 'roundname', 'rank', 'points', 'penalty', 'total']
        with db.getCur() as cur:
            scoreboard = {}
            rounds = []
            cur.execute(query, (db.playertypecode['UnusedPoints'], self.tournamentid))
            for i, row in enumerate(cur.fetchall()):
                rec = dict(zip(fields, row))
                if rec['round'] not in [r[0] for r in rounds]:
                    rounds += [(rec['round'], rec['roundname'])]
                if rec['id'] not in scoreboard:
                    scoreboard[rec['id']] = dict(zip(fields[0:5], row[0:5]))
                    scoreboard[rec['id']]['type'] = db.playertypes[int(rec['type'])]
                    scoreboard[rec['id']]['scores'] = {}
                scoreboard[rec['id']]['scores'][rec['round']] = {
                        'rank':rec['rank'],
                        'score': round(rec['points'], 1),
                        'penalty':rec['penalty'],
                        'total': round(rec['total'], 1)
                    }
            scoreboard = list(scoreboard.values())
            scoreboard.sort(key = operator.itemgetter('type', 'name'))
            rounds.sort()
        self.render("scoreboard.html", scoreboard = scoreboard, rounds = rounds)
