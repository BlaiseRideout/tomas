#!/usr/bin/env python3

import json
import db
import handler
from util import *

class PlayerStatsDataHandler(handler.BaseHandler):
    _statquery = """
       SELECT Max(Score),MIN(Score),COUNT(*),
         ROUND(SUM(Score) * 1.0/COUNT(*) * 100) / 100,
         ROUND(SUM(Rank) * 1.0/COUNT(*) * 100) / 100,
         MIN(Rank), MAX(Rank),
         MIN(Round), MAX(Round) {subquery} """
    _statqfields = ['maxscore', 'minscore', 'numgames', 'avgscore',
                    'avgrank', 'maxrank', 'minrank',
                    'minround', 'maxround']
    _rankhistogramquery = """
        SELECT Rank, COUNT(*) {subquery} GROUP BY Rank ORDER BY Rank"""
    _rankhfields = ['rank', 'rankcount']

    def populate_queries(self, cur, period_dict):
        cur.execute(self._statquery.format(**period_dict),
                    period_dict['params'])
        period_dict.update(
            dict(zip(self._statqfields,
                     map(lambda x: round(x, 2) if isinstance(x, float) else x,
                         cur.fetchone()))))
        cur.execute(self._rankhistogramquery.format(**period_dict),
                    period_dict['params'])
        rank_histogram = dict([map(int, r) for r in cur.fetchall()])
        rank_histogram_list = [{'rank': i, 'count': rank_histogram.get(i, 0)}
                               for i in range(1, 6)]
        period_dict['rank_histogram'] = rank_histogram_list

    def get(self, player):
        with db.getCur() as cur:
            name = player
            cur.execute("SELECT Id,Name FROM Players WHERE Id = ? OR Name = ?", (player, player))
            player = cur.fetchone()
            if player is None or len(player) == 0:
                self.write(json.dumps({'status': 1,
                                       'error': "Couldn't find player"}))
                return
            playerID, name = player

            periods = [
                {'name': 'All Rounds Stats',
                 'subquery': "FROM Scores WHERE PlayerId = ?",
                 'params': (playerID,)
                },
            ]
            p = periods[0]
            self.populate_queries(cur, p)
            p['showstats'] = True
            if p['numgames'] == 0:
                return self.render("playerstats.html", name=name,
                                   error = "Couldn't find any scores for")

            cur.execute(
                    "SELECT Scores2.Round, Scores2.Rank, ROUND(Scores2.Score * 100) / 100, Players.Name FROM Scores"
                    " JOIN Scores AS Scores2"
                    "  ON Scores.GameId = Scores2.GameId AND Scores.Round = Scores2.Round"
                    " JOIN Players"
                    "  ON Players.Id = Scores2.PlayerId"
                    " WHERE Scores.PlayerId = ?"
                    " ORDER BY Scores2.Round",
                    (playerID,)
                )
            playergames = []
            for roundnum, rank, score, name in cur.fetchall():
                if len(playergames) == 0 or playergames[-1]['round'] != roundnum:
                    playergames += [{
                        'round': roundnum,
                        'scores': [
                            {
                                'rank':rank,
                                'name':name,
                                'score':score
                            }
                        ]
                    }]
                else:
                    playergames[-1]['scores'] += [
                        {
                            'rank':rank,
                            'name':name,
                            'score':score
                        }
                    ]

            self.write({
                'playerstats': periods,
                'playergames': playergames
            })

class PlayerStatsHandler(handler.BaseHandler):
    def get(self, player):
        with db.getCur() as cur:
            name = player
            cur.execute("SELECT Id,Name FROM Players WHERE Id = ? OR Name = ?", (player, player))
            player = cur.fetchone()
            if player is None or len(player) == 0:
                return self.render("playerstats.html", name=name,
                                   error = "Couldn't find player")

            player, name = player
            self.render("playerstats.html",
                        error = None,
                        name = name
                )

    def post(self, player):
        name = self.get_argument("name", player)
        if name != player:
            args = []
            cols = []
            if name != player:
                cols += ["Name = ?"]
                args += [name]
            if len(args) > 0:
                query = "UPDATE Players SET " + ",".join(cols) + " WHERE Id = ? OR Name = ?"
                args += [player, player]
                with db.getCur() as cur:
                    cur.execute(query, args)
            self.redirect("/playerstats/" + name)
