#!/usr/bin/env python3

import json
import operator

import db
import handler
import settings

def leaderData():
    query = """SELECT
         Players.Name, Countries.Code, Flag_Image, Type,
         COUNT(Scores.Id) AS GamesPlayed,
         COALESCE(
             ROUND(SUM(Scores.Score) * 1.0 / COUNT(Scores.Score) * 100) / 100
             , 0) AS AvgScore,
         COALESCE(PenaltyPoints.sum, 0) as Penalty,
         COALESCE(
             ROUND(SUM(Scores.Score) * 1.0 / COUNT(Scores.Score) * 100) / 100
              + PenaltyPoints.sum, 0) as Total
       FROM Players
       LEFT JOIN Scores ON Players.Id = Scores.PlayerId
       LEFT OUTER JOIN 
         (SELECT Players.Id, COALESCE(SUM(Penalty), 0) as sum FROM Players
            LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId
            LEFT OUTER JOIN Penalties ON Scores.Id = Penalties.ScoreId
                        GROUP BY Players.Id) AS PenaltyPoints
         ON Players.Id = PenaltyPoints.Id
       LEFT JOIN Countries ON Players.Country = Countries.Id
       WHERE Players.Type != ?
       GROUP BY Players.Id
       ORDER BY Type ASC, GamesPlayed DESC, Total DESC, Penalty DESC;"""
    fields = ['name', 'country', 'flag_image', 'type', 'games_played',
              'score', 'penalty', 'total']
    with db.getCur() as cur:
        leaderboard = []
        last_total = None
        cur.execute(query, (db.playertypes.index('UnusedPoints'),))
        for i, row in enumerate(cur.fetchall()):
            rec = dict(zip(fields, row))
            rec['type'] = db.playertypes[int(rec['type'] or 0)]
            if rec['total'] != last_total:
                place = i+1
            last_total = rec['total']
            rec['place'] = place
            leaderboard.append(rec)
        return leaderboard
    return None

class LeaderDataHandler(handler.BaseHandler):
    def get(self):
        leaderboard = leaderData()
        self.write(json.dumps({'leaderboard':leaderboard}))

class LeaderboardHandler(handler.BaseHandler):
    def get(self):
        leaderboard = leaderData()
        self.render("leaderboard.html", leaderboard = leaderboard)

class ScoreboardHandler(handler.BaseHandler):
    def get(self):
        query = """SELECT
           Players.Id, Players.Name, Countries.Code, Flag_Image, Type,
           Scores.Round, Scores.Rank, ROUND(Scores.Score * 100) / 100, 
           COALESCE(SUM(Penalties.Penalty), 0), 
           COALESCE(ROUND(Scores.Score * 100) / 100, 0) + 
             COALESCE(SUM(Penalties.Penalty), 0)
           FROM Scores
           LEFT JOIN Players ON Scores.PlayerId = Players.Id
           LEFT JOIN Countries ON Players.Country = Countries.Id
           LEFT OUTER JOIN Penalties ON Scores.Id = Penalties.ScoreId
           WHERE Players.Type != ?
           GROUP BY Scores.Id
           ORDER BY Type ASC, Players.Name ASC
        """
        fields = ['id', 'name', 'country', 'flag_image', 'type',
                  'round', 'rank', 'score', 'penalty', 'total']
        with db.getCur() as cur:
            scoreboard = {}
            rounds = []
            cur.execute(query, (db.playertypes.index('UnusedPoints'),))
            for i, row in enumerate(cur.fetchall()):
                rec = dict(zip(fields, row))
                if rec['round'] not in rounds:
                    rounds += [rec['round']]
                if rec['id'] not in scoreboard:
                    scoreboard[rec['id']] = dict(zip(fields[0:5], row[0:5]))
                    scoreboard[rec['id']]['type'] = db.playertypes[int(rec['type'])]
                    scoreboard[rec['id']]['scores'] = {}
                scoreboard[rec['id']]['scores'][rec['round']] = {
                        'rank':rec['rank'],
                        'score': round(rec['score'], 1),
                        'penalty':rec['penalty'],
                        'total': round(rec['total'], 1)
                    }
            scoreboard = list(scoreboard.values())
            scoreboard.sort(key = operator.itemgetter('type', 'name'))
            rounds.sort()
        self.render("scoreboard.html", scoreboard = scoreboard, rounds = rounds)
