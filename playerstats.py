#!/usr/bin/env python3

import json
import logging
from collections import *

import db
import handler
from util import *

log = logging.getLogger('WebServer')

def playersTournaments(playerId, cur=None):
    """Get a list of tournament dictionaries with all the tournament info
    and the player's role in the tournament as fields.
    If the player is in multiple tournaments, the first dictionary in the
    list will be for 'All Tournaments' with an Id of 'all' and the other
    fields as None.
    """
    columns = ('Tournaments.Id', 'Name', 'Number', 'Pool', 'Wheel', 'Type')
    sql = ("SELECT {}"
           " FROM Tournaments JOIN Compete ON Tournament = Tournaments.Id"
           " WHERE Player = ?"
           " ORDER BY Start DESC").format(','.join(columns))
    args = (playerId, )
    if cur:
        cur.execute(sql, args)
        results = cur.fetchall()
    else:
        with db.getCur() as cursor:
            cursor.execute(sql, args)
            results = cursor.fetchall()
    if len(results) >  1:
        all = ['all', 'All Tournaments'] + [None] * (len(columns) - 2)
        results = [all] + results
    return [dict(zip(map(db.fieldname, columns), row)) for row in results]

def getPlayerTournamentData(playerID, playerTourneys, cur):
    tourneys = [
        {'Name': '{} Stats'.format(
            'All Tournament' if tourney['Id'] == 'all' else tourney['Name']),
         'scoresSubquery': 
         """FROM Scores
                 LEFT JOIN Rounds ON Round = Rounds.Id
            WHERE PlayerId = ? {}""".format(
                '' if tourney['Id'] == 'all' else
                'AND Tournament = {}'.format(tourney['Id'])),
         'scoresParams': (playerID,),
         'penaltyCondition': 'Tournament {}'.format(
             'NOTNULL' if tourney['Id'] == 'all' else
             '= ' + str(tourney['Id'])),
         'gamesCondition': 'AND Tournament = {}'.format(
             'NULL' if tourney['Id'] == 'all' else tourney['Id']),
         'seatingCondition': 'AND Rounds.Tournament = {}'.format(
             'NULL' if tourney['Id'] == 'all' else tourney['Id']),
         'player': tourney,
         'Id': tourney['Id'],
         'playerID': playerID,
        } for tourney in playerTourneys
    ]
    for tourney in tourneys:
        populate_queries(tourney, cur)
    return tourneys
    
_statquery = """
    SELECT Max(Score),MIN(Score),COUNT(*),
      ROUND(SUM(Score) * 1.0/COUNT(*) * 100) / 100,
      ROUND(SUM(Rank) * 1.0/COUNT(*) * 100) / 100,
      MIN(Rank), MAX(Rank),
      MIN(Round), MAX(Round)
    {scoresSubquery} """
_statqfields = ('maxscore', 'minscore', 'numgames', 'avgscore',
                'avgrank', 'maxrank', 'minrank',
                'minround', 'maxround')

_penaltiesquery = """
    SELECT Penalty, Description, Referee, Round, Tournament, GameId 
    FROM Penalties
      JOIN Scores ON ScoreId = Scores.Id
      JOIN Rounds ON Round = Rounds.Id
    WHERE {penaltyCondition} AND PlayerId = ?
"""
_penaltiesqfields = [
    'penalty', 'description', 'referee', 'round', 'tournament', 'game']

_rankhistogramquery = """
    SELECT Rank, COUNT(*) {scoresSubquery} GROUP BY Rank ORDER BY Rank"""
_rankhfields = ['rank', 'rankcount']
    
_gamesQuery = """
    SELECT Scores2.Round, Rounds.Number, Rounds.Name, Scores.GameId,
      Scores2.Rank, ROUND(Scores2.Score * 100) / 100, Players.Name, Players.Id,
      Countries.Code, Countries.Flag_Image
    FROM Scores JOIN Scores AS Scores2
        ON Scores.GameId = Scores2.GameId AND Scores.Round = Scores2.Round
      JOIN Players ON Players.Id = Scores2.PlayerId
      JOIN Countries ON Players.Country = Countries.Id
      JOIN Rounds ON Rounds.Id = Scores2.Round
     WHERE Scores.PlayerId = ? AND Scores2.PlayerId != ? {gamesCondition}
    ORDER BY Scores2.Round, Scores2.Rank"""
_gamesqfields = ('roundID', 'rNumber', 'rName', 'game', 'rank', 'score',
    'name', 'id', 'country', 'flag')

_seatingQuery = """
    SELECT Seating.Round, Rounds.Name, Rounds.Winds,
      S2.TableNum, S2.Wind, Players.Name,
      Countries.Code, Countries.Flag_Image
    FROM Seating JOIN Seating AS S2
        ON Seating.TableNum = S2.TableNum AND Seating.Round = S2.Round
      JOIN Players ON Players.Id = S2.Player
      JOIN Countries ON Players.Country = Countries.Id
      JOIN Rounds ON Seating.Round = Rounds.Id
    WHERE Seating.Player = ? {seatingCondition}
      AND Seating.Round NOT IN (SELECT Round FROM Scores WHERE PlayerId = ?)
    ORDER BY S2.Round, S2.TableNum, S2.Wind"""
_seatingtablefields = ['round', 'roundname', 'showwinds', 'table']
_seatingplayerfields = ['wind', 'name', 'country', 'flag']

#      AND NOT EXISTS 
#        (SELECT Id FROM Scores WHERE PlayerId = ? AND Round = Seating.Round) 

def populate_queries(tourney_dict, cur):
    """Update the tourney dictionary for a single tournament with the results
    of all the stats queries"""
    cur.execute(_statquery.format(**tourney_dict), tourney_dict['scoresParams'])
    tourney_dict.update(
        dict(zip(_statqfields,
                 map(lambda x: round(x, 2) if isinstance(x, float) else x,
                     cur.fetchone()))))
    cur.execute(_rankhistogramquery.format(**tourney_dict),
                tourney_dict['scoresParams'])
    rank_histogram = dict([map(int, r) for r in cur.fetchall()])
    rank_histogram_list = [{'rank': i, 'count': rank_histogram.get(i, 0)}
                           for i in range(1, settings.LOWESTRANK + 1)]
    tourney_dict['rank_histogram'] = rank_histogram_list
    cur.execute(_gamesQuery.format(**tourney_dict),
                (tourney_dict['playerID'], db.getUnusedPointsPlayerID()))
    games = []
    for row in cur.fetchall():
        score = dict(zip(_gamesqfields, row))
        if len(games) == 0 or games[-1]['round'] != score['roundID']:
            games += [{
                'game': score['game'],
                'round': score['roundID'],
                'number': score['rNumber'],
                'roundname': score['rName'],
                'scores': [],
                'penalties': [],
            }]
        games[-1]['scores'] += [score]
    cur.execute(_penaltiesquery.format(**tourney_dict),
                (tourney_dict['playerID'],))
    tourney_dict['totalpenalties'] = 0
    games_with_penalties = defaultdict(lambda: list())
    for row in cur.fetchall():
        penalty = dict(zip(_penaltiesqfields, row))
        tourney_dict['totalpenalties'] += penalty['penalty']
        key = '{}-{}'.format(penalty['game'], penalty['round'])
        games_with_penalties[key].append(penalty)
    for game in games:
        key = '{}-{}'.format(game['game'], game['round'])
        if key in games_with_penalties:
            game['penalties'] = games_with_penalties[key]
    tourney_dict['playergames'] = games

    cur.execute(_seatingQuery.format(**tourney_dict),
                (tourney_dict['playerID'], tourney_dict['playerID']))
    futuregames = []
    for row in cur.fetchall():
        table = dict(zip(_seatingtablefields, row[0:len(_seatingtablefields)]))
        seat = dict(zip(_seatingplayerfields, row[len(_seatingplayerfields):]))
        seat['wind'] = winds[seat['wind']]
        if (len(futuregames) == 0 or 
            futuregames[-1]['round'] != table['round']):
            table['seating'] = []
            futuregames += [table]
        futuregames[-1]['seating'] += [seat]
    tourney_dict['futuregames'] = futuregames

class PlayerStatsDataHandler(handler.BaseHandler):
    def get(self, playerspec):
        with db.getCur() as cur:
            columns = db.table_field_names('Players')
            cur.execute("SELECT {} FROM Players WHERE Id = ? OR Name = ?"
                        .format(','.join(columns)),
                        (playerspec, playerspec))
            player = cur.fetchone()
            if player is None or len(player) == 0:
                self.write(json.dumps({'status': 1,
                                       'error': "Couldn't find player " + name}))
                return
            player = dict(zip(columns), player)
            playerID = player['Id']
            playerTourneys = playersTournaments(playerID, cur)
            tourneys = getPlayerTournamentData(playerID, playerTourneys, cur)
        self.write({'status': 0, 'playerstats': tourneys, })

class PlayerStatsHandler(handler.BaseHandler):
    def get(self, player):
        HISTORY_COOKIE = "stats_history"
        with db.getCur() as cur:
            name = player
            cols = ['Players.{}'.format(f) 
                    for f in db.table_field_names('Players')] + [
                            'Code', 'Flag_Image'] + [
                            f for f in db.table_field_names('Compete')
                                if f not in ('Id',)]
            sql = """
              SELECT {}
              FROM Players LEFT OUTER JOIN Countries
                     ON Countries.Id = Players.Country
                   LEFT OUTER JOIN Compete ON Compete.Player = Players.Id
              WHERE Players.Id = ? OR Players.Name = ?""".format(
                  ','.join(cols))
            cur.execute(sql, (player, player))

            player = cur.fetchone()
            if player is None or len(player) == 0:
                return self.render(
                    "playerstats.html", player = {'Name':name},
                    error = "Couldn't find player {}".format(name))
            player = dict(zip(map(db.fieldname, cols), player))

            playerTourneys = playersTournaments(player['Id'], cur)
            selectedTournament = self.get_argument("tournament", None)
            if selectedTournament and isinstance(selectedTournament, str):
                if selectedTournament != 'all' and selectedTournament.isdigit():
                    if not int(selectedTournament) in [
                            t['Id'] for t in playerTourneys]:
                        log.error('Request for stats on tournament ID {} '
                                  'but player ID {} did not compete in that '
                                  'tournament'.format(
                                      selectedTournament, playerID))
                        selectedTournament = None
            tourneys = getPlayerTournamentData(player['Id'],
                                               playerTourneys, cur)

            history = stringify(self.get_secure_cookie(HISTORY_COOKIE))
            if history is None:
                history = []
            else:
                history = json.loads(history)

            playerKey = [player['Id'], player['Name']]
            if playerKey in history:
                history.remove(playerKey)
            history.insert(0, playerKey)

            history = history[0:settings.STATSHISTORYSIZE]
            self.set_secure_cookie(HISTORY_COOKIE, json.dumps(history))

        return self.render(
            "playerstats.html", error = None,
            player=player, tourneys=tourneys, history = history,
            playertypes=db.playertypes, selectedTournament=selectedTournament)
