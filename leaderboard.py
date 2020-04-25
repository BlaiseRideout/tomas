#!/usr/bin/env python3

import json
import operator

import db
import handler
import settings
import collections


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
        key=lambda r: (r['cutName'],
                       0 if r['type'] == 'Regular' else 
                       1 if r['type'] == 'Inactive' else
                       2 if r['type'] == 'Substitute' else 3,
                       - r['total']),
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

notplayed = 'not participating'

def cutLeaderboards(leaderboards, playerRound):
    # Cut the leaderboard when appropriate

    if playerRound is None:
        return leaderboards

    # Should we cut the leaderboards?  Active players come first
    # so playerRound should have the cutName for an active player
    # if there is one.
    if (playerRound['cutName'] not in [None, '', notplayed] and
        not playerRound['cutMobility']):
        old_leaderboards = leaderboards
        leaderboards = []
        cuts = collections.defaultdict(lambda : [])
        for cutdict in old_leaderboards:
            for player in cutdict.values():
                cuts[player['cutName']].append(player)
        leaderboards = [dictifyLeaderboard(flattenLeaderboard(
            dictifyLeaderboard(cuts[cutName])))
                        for cutName in sorted(cuts.keys())]
    return leaderboards

def leaderData(tournamentid):
    query = """SELECT
         Players.Id, Players.Name, Countries.Code, Flag_Image, Type,
         COUNT(Scores.Id) AS GamesPlayed,
         COALESCE(ROUND(SUM(Scores.Score) * 100) / 100, 0) AS TotalPoints,
         COALESCE(Rounds.Id, 0), Rounds.Number, (Rounds.SoftCut + Rounds.Cut),
         Rounds.CutMobility, COALESCE(Rounds.cutSize, 0),
         Rounds.CombineLastCut, COALESCE(Rounds.CutCount, 0),
         COALESCE(Seating.CutName, ?)
       FROM Players
       LEFT JOIN Compete ON Players.Id = Compete.Player
       LEFT JOIN Rounds ON Rounds.Tournament = Compete.Tournament
       LEFT JOIN Scores ON Players.Id = Scores.PlayerId AND
            Rounds.Id = Scores.Round
       LEFT JOIN Seating ON Rounds.Id = Seating.Round AND 
            Players.Id = Seating.Player AND 
            Seating.Tournament = Compete.Tournament 
       LEFT JOIN Countries ON Players.Country = Countries.Id
       WHERE Compete.Tournament = ?
       GROUP BY Players.Id, Rounds.Id
       ORDER BY Rounds.Id ASC, Type ASC;"""

    fields = ['player', 'name', 'country', 'flag_image', 'type',
              'gamesPlayed',
              'points',
              'round', 'roundNum', 'cutFlag',
              'cutMobility', 'cutSize',
              'combineLastCut', 'cutCount', 
              'cutName']

    with db.getCur() as cur:
        cur.execute(query, (notplayed, tournamentid))
        rows = cur.fetchall()
    scores = [dict(zip(fields, row)) for row in rows]

    zeroScores = {'total': 0, 'points':0, 'gamesPlayed': 0, 'penalty': 0}
    
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
        if playerRound['cutName']:
            leaderboard[player]['cutName'] = playerRound['cutName']

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
        self.render("leaderboard.html", leaderboard = leaderboard,
                    allTied = allTied)

def getTournamentScores(tournamentID):
    # Note: using Compete.Tournament instead of Rounds.Tournament in the
    # following query avoids selecting unusedpointplayer scores
    query = """SELECT
    Players.Id, Players.Name, Countries.Code, flag_image, Type,
    Rounds.Number, Rounds.Name, Scores.Rank,
    ROUND(Scores.Score * 100) / 100,
    COALESCE(SUM(Penalties.Penalty), 0),
    COALESCE(ROUND((Scores.Score + COALESCE(SUM(Penalties.Penalty), 0)) * 100) /
                   100, 0)
    FROM Scores LEFT JOIN Rounds ON Scores.Round = Rounds.Id
      LEFT JOIN Players ON Scores.PlayerId = Players.Id
      LEFT JOIN Compete ON Players.Id = Compete.Player
      LEFT JOIN Countries ON Players.Country = Countries.Id
      LEFT OUTER JOIN Penalties ON Scores.Id = Penalties.ScoreId
    WHERE Compete.Tournament = ? AND Rounds.Tournament = Compete.Tournament
    GROUP BY Scores.Id
    ORDER BY Type ASC, Players.Name ASC
    """.strip() 
    fields = ['id', 'name', 'country', 'flag_image', 'type',
              'round', 'roundname', 'rank', 'points', 'penalty', 'total']
    scoreboard = {}
    rounds = []
    with db.getCur() as cur:
        cur.execute(query, (tournamentID,))
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
    return scoreboard, rounds
