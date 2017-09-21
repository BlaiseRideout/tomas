#!/usr/bin/env python3

import json
import db
import handler
import settings

class LeaderDataHandler(handler.BaseHandler):
    def get(self):
        query = """SELECT
             Players.Name, Countries.Code, Flag_Image, Inactive,
             COUNT(Scores.Id) AS GamesPlayed,
             COALESCE(
                 ROUND(SUM(Scores.Score) * 1.0 / COUNT(Scores.Score) * 100) / 100
                 , 0) AS AvgScore
           FROM Players
           LEFT JOIN Scores ON Players.Id = Scores.PlayerId
           LEFT JOIN Countries ON Players.Country = Countries.Id
           GROUP BY Players.Id
           ORDER BY Inactive ASC, GamesPlayed DESC, AvgScore DESC;"""
        fields = ['name', 'country', 'flag_image', 'inactive', 'games_played',
                  'score']
        with db.getCur() as cur:
            leaderboard = []
            last_score = None
            cur.execute(query)
            for i, row in enumerate(cur.fetchall()):
                rec = dict(zip(fields, row))
                if rec['score'] != last_score:
                    place = i+1
                last_score = rec['score']
                rec['place'] = place
                leaderboard.append(rec)

            self.write(json.dumps({'leaderboard':leaderboard}))
