#!/usr/bin/env python3

import json
import db
import handler
import settings

class LeaderDataHandler(handler.BaseHandler):
    def get(self):
        query = """SELECT
             Players.Name,
             Countries.IOC,
             COALESCE(ROUND(SUM(Scores.Score) * 1.0 / COUNT(Scores.Score) * 100)
               / 100, 0) AS AvgScore
           FROM Players
           LEFT JOIN Scores ON Players.Id = Scores.PlayerId
           LEFT JOIN Countries ON Players.Country = Countries.Id
           GROUP BY Players.Id
           ORDER BY AvgScore DESC;"""
        with db.getCur() as cur:
            leaderboard = []
            place=1
            cur.execute(query)
            for row in cur.fetchall():
                leaderboard += [
                    {'place': place,
                     'name':row[0],
                     'country':row[1],
                     'score':row[2]}]
                place += 1
            self.write(json.dumps({'leaderboard':leaderboard}))
