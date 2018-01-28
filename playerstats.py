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
         MIN(Round), MAX(Round),
         SUM(COALESCE(Penalties.Penalty, 0))
         {subquery} """
    _statqfields = ['maxscore', 'minscore', 'numgames', 'avgscore',
                    'avgrank', 'maxrank', 'minrank',
                    'minround', 'maxround',
                    'penalties']
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
                               for i in range(1, settings.LOWESTRANK + 1)]
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
                 'subquery': "FROM Scores LEFT OUTER JOIN Penalties ON ScoreId = Scores.Id WHERE PlayerId = ? ",
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
                    "SELECT Scores2.Round, Scores2.Rank, ROUND(Scores2.Score * 100) / 100, Players.Name,"
                    " Countries.Code, Countries.Flag_Image FROM Scores"
                    " JOIN Scores AS Scores2"
                    "  ON Scores.GameId = Scores2.GameId AND Scores.Round = Scores2.Round"
                    " JOIN Players"
                    "  ON Players.Id = Scores2.PlayerId"
                    " JOIN Countries"
                    "  ON Players.Country = Countries.Id"
                    " WHERE Scores.PlayerId = ? AND Scores2.PlayerId != ?"
                    " ORDER BY Scores2.Round, Scores2.Rank",
                    (playerID, db.getUnusedPointsPlayerID())
                )
            cols = ['rank', 'score', 'name', 'country', 'flag']
            playergames = []
            for row in cur.fetchall():
                score = dict(zip(cols, row[1:]))
                if len(playergames) == 0 or playergames[-1]['round'] != row[0]:
                    playergames += [{
                        'round': row[0],
                        'scores': []
                    }]
                playergames[-1]['scores'] += [score]

            cur.execute(
                    "SELECT Seating.Round, Rounds.Winds, Seating2.TableNum,"
                    " Seating2.Wind, Players.Name,"
                    " Countries.Code, Countries.Flag_Image FROM Seating"
                    " JOIN Seating AS Seating2"
                    "  ON Seating.TableNum = Seating2.TableNum AND Seating.Round = Seating2.Round"
                    " JOIN Players"
                    "  ON Players.Id = Seating2.Player"
                    " JOIN Countries"
                    "  ON Players.Country = Countries.Id"
                    " JOIN Rounds"
                    "  ON Seating.Round = Rounds.Id"
                    " WHERE Seating.Player = ?"
                    " AND Seating.Round NOT IN (SELECT Round FROM Scores WHERE PlayerId = ?)"
                    " ORDER BY Seating2.Round, Seating2.TableNum, Seating2.Wind",
                    (playerID, playerID)
                )

            tablecols = ['round','showwinds', 'table']
            cols = ['wind', 'name', 'country', 'flag']
            futuregames = []
            for row in cur.fetchall():
                table = dict(zip(tablecols, row[0:len(tablecols)]))
                seat = dict(zip(cols, row[len(tablecols):]))
                seat['wind'] = winds[seat['wind']]
                if len(futuregames) == 0 or futuregames[-1]['round'] != table['round']:
                    table['seating'] = []
                    futuregames += [table]
                futuregames[-1]['seating'] += [seat]

            self.write({
                'playerstats': periods,
                'playergames': playergames,
                'futuregames': futuregames
            })

class PlayerStatsHandler(handler.BaseHandler):
    def get(self, player):
        HISTORY_COOKIE = "stats_history"
        with db.getCur() as cur:
            name = player
            cur.execute("SELECT Id,Name FROM Players WHERE Id = ? OR Name = ?", (player, player))
            player = cur.fetchone()
            if player is None or len(player) == 0:
                return self.render("playerstats.html", name=name,
                                   error = "Couldn't find player")
            history = stringify(self.get_secure_cookie(HISTORY_COOKIE))
            if history is None:
                history = []
            else:
                history = json.loads(history)
            if player[1] in history:
                history.remove(player[1])
            history.insert(0, player[1])

            history = history[0:settings.STATSHISTORYSIZE]
            self.set_secure_cookie(HISTORY_COOKIE, json.dumps(history))

            player, name = player
            self.render("playerstats.html",
                        error = None,
                        name = name,
                        history = history
                )
