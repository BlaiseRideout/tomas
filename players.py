#!/usr/bin/env python3

import json
import csv
import re
import io
import logging
import datetime
import sqlite3
from collections import *

import tornado.web
import handler
import db
import seating
import settings
import util

log = logging.getLogger('WebServer')

ValidPlayersSQL = """
SELECT {columns} FROM Players
 JOIN Countries ON Players.Country = Countries.Id
 LEFT OUTER JOIN Compete ON Players.Id = Compete.Player
 LEFT OUTER JOIN Tournaments ON Compete.Tournament = Tournaments.Id
 LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId
 WHERE Players.ReplacedBy ISNULL {conditions}
 GROUP BY Players.Id ORDER BY lower(Players.Name)
"""

def playerColumns():
    player_fields = [f for f in db.table_field_names('Players')
                     if f not in ('ReplacedBy')]
    columns = ["Players.{}".format(f) for f in player_fields] + [
        "Flag_Image", "COUNT(DISTINCT Tournaments.Id)",
        "MAX(Tournaments.Start)", "COUNT(Scores.Id)"
    ] 
    colnames = player_fields + ["Flag", "Tournaments", "Latest", "Scores"]
    colheads = [{"Name": util.prettyWords(col)} for col in colnames 
                if col not in ('Id', 'Flag_Image', 'Scores')]
    colheads[len(player_fields) - 1]["Attrs"] = "colspan=2"
    return columns, colnames, colheads
        
class PlayersHandler(handler.BaseHandler):
    def get(self, rest=''):
        return self.render("playerlist.html")

class PlayersListHandler(handler.BaseHandler):
    def get(self):
        columns, colnames, colheads = playerColumns()
        condition = ""
        args = []
        players = self.get_argument("players", None)
        if players and isinstance(players, str):
            players = [id if id.isdigit() else False 
                       for id in players.split()]
            if all(players):
                condition = "AND Players.Id in ({})".format(",".join(players))
        try:
            with db.getCur() as cur:
                sql = ValidPlayersSQL.format(
                    columns=",".join(columns), conditions=condition)
                cur.execute(sql, args)
                players = [dict(zip(colnames, row)) for row in cur.fetchall()]
                result = {'status': 0, 'data': players}
        except Exception as e:
            result = {'status': 1,
                      'message': 'Unable to get players from database. ' +
                      str(e) }
        self.write(result)
        
    @tornado.web.authenticated
    def post(self):
        global sql, args
        encoded_item = self.get_argument('item', None)
        item = json.loads(encoded_item)
        result = {'status': 0, 'message': ''}
        if item.get('Id', None) is None or not isinstance(item['Id'], int):
            result['message'] = 'Invalid Id field for player, {}'.format(item)
            result['status'] = -1
            self.write(result)
            return
        if not isinstance(item.get('Country', None), int) and item['Id'] >= 0:
            result['message'] = 'Invalid Country for Player, {}'.format(item)
            result['status'] = -2
            self.write(result)
            return
        id = abs(item['Id'])
        result['message'] = 'Item {}'.format(
            'inserted' if id == 0 else 'deleted' if item['Id'] < 0 else
            'updated')
        player_fields = [f for f in db.table_field_names('Players')
                         if f not in ('ReplacedBy')]
        columns = [f for f in player_fields if f in item and f not in ['Id']]
        cleanPlayerItem(item, columns)
        try:
            with db.getCur() as cur:
                if id > 0:
                    sql, args = 'SELECT Id FROM Players WHERE Id = ?', (id, )
                    cur.execute(sql, args)
                    matches = len(cur.fetchall())
                    if matches == 0:
                        result['message'] = 'No player with Id {}'.format(id)
                        result['status'] = -3
                    elif matches > 1:
                        result['message'] = (
                            'Multiple players with Id {}'.format(id))
                        result['status'] = -4
                if item['Id'] >= 0:
                    sql = 'SELECT Id FROM Countries WHERE Id = ?'
                    args = (item['Country'], )
                    cur.execute(sql, args)
                    matches = len(cur.fetchall())
                    if matches != 1:
                        result['message'] = (
                            'Invalid Country for Player {}'.format(item))
                        result['status'] = -5
                if result['status'] == 0:
                    values = [item[f] for f in columns]
                    if item['Id'] < 0:
                        sql = 'DELETE FROM Players WHERE Id = ?'
                        args = (id, )
                    elif item['Id'] == 0:
                        sql = 'INSERT INTO Players ({}) VALUES ({})'.format(
                            ', '.join(columns),
                            ', '.join(['?' for v in values]))
                        args = values
                    else:
                        sql = 'UPDATE Players SET {} WHERE Id = ?'.format(
                                ', '.join('{} = ?'.format(f) for f in columns))
                        args = values + [id]
                    log.info('Executing "{}" on {}'.format(sql, args))
                    cur.execute(sql, args)
                    if item['Id'] == 0:
                        item['Id'] = cur.lastrowid
                        log.info('Last Player Row ID is now {}'.format(
                            item['Id']))
                    item['Id'] = abs(item['Id']) # Put cleaned item record
                    result['item'] = item # with correct Id in rsespone
        except Exception as e:
            result['message'] = (
                'Exception in database change. SQL = {}. Args = {}. {}'.format(
                    sql, args, e))
            log.error(result['message'])
            result['status'] = -10
            
        self.write(result)

def cleanPlayerItem(item, columns):
    global sql, args
    for field in ['Name', 'Association']:
        if field in columns:
            item[field] = item[field].strip()
    if 'Country' in columns and isinstance(item['Country'], str):
        with db.getCur() as cur:
            sql = 'SELECT Id FROM Countries WHERE Code = ?'
            args = (item['Country'].upper(), )
            cur.execute(sql, args)
            result = cur.fetchone()
            if result:
                item['Country'] = result[0]

class MergePlayersHandler(handler.BaseHandler):
    
    @tornado.web.authenticated
    def post(self):
        global sql, args
        encoded_request = self.get_argument('request', None)
        request = json.loads(encoded_request)
        result = {'status': 0, 'message': ''}
        if not (isinstance(request, dict) and 'playerIDs' in request):
            result['message'] = 'Invalid request to merge players, {}'.format(
                request)
            result['status'] = -1
        elif not (isinstance(request['playerIDs'], list) and
                  all(map(lambda x: isinstance(x, int) and x > 0,
                          request['playerIDs'])) and
                  len(request['playerIDs']) > 1):
            result['message'] = 'Invalid Player IDs in request, {}'.format(
                request['playerIDs'])
            result['status'] = -2
        else:
            columns, colnames, colheads = playerColumns()
            try:
                with db.getCur() as cur:
                    sql = ValidPlayersSQL.format(
                        columns=",".join(columns), 
                        conditions='AND Players.Id IN ({})'.format(
                            ",".join(map(str, playerIDs))))
                    args = playerIDs
                    cur.execute(sql, args)
                    players = [dict(zip(colnames, row)) 
                               for row in cur.fetchall()]
                    missing = set(playerIDs) - set(p['Id'] for p in players)
                    if len(missing) > 0:
                        result['message'] = 'Missing Player IDs, {}'.format(
                            missing)
                        result['status'] = -3
                    else:
                        merge_record = self.combine_player_records(
                            players, colnames)
                        result['merged'] = merge_record
                        if 'performMerge' in request and request['peformMerge']:
                            self.merge_player_records(
                                playerIDs, merge_record, colnames, cur, result)
            except Exception as e:
                result['message'] = (
                    'Exception in database query. SQL = {}. Args = {}. {}'
                    .format(sql, args, e))
                log.error(result['message'])
                result['status'] = -10
            
        self.write(result)

    def combine_player_records(players, colnames):
        res = {}
        maxitem = 0
        for col in colnames: # For each column, histogram values
            hist = defaultdict(lambda: 0)
            for player in players:
                val = "" if player[col] is None else player[col]
                hist[val] += 1
            # Sort possible values by non-null flag, number of occurrences,
            # string length or numeric value, # of uppercase letters
            metrics = [(val, 1 if len(str(val)) > 0 else 0, hist[val],
                       val if isinstance(val, int) else len(val),
                       sum(1 if c.isupper() else 0 for c in val) 
                       if isinstance(val, str) else 0)
                      for val in hist]
            metrics.sort(key=lambda tupl: tupl[1:])
            res[col] = metrics[-1][0]  # Take highest after sort
        return res

    def merge_player_records(playerIDs, merge_record, colnames, cur, result):
        global sql, args
        keys = list(merge_record.keys())
        sql = 'INSERT INTO Players ({}) VALUES ({})'.format(
            ', '.join(keys), ', '.join(['?' for k in keys]))
        args = [merge_record[k] for k in keys]
        cur.execute(sql, args)
        merge_reocrd['Id'] = cur.lastrowid
        for table, field in (
                ('Players', 'ReplacedBy'), ('Scores', 'PlayerId'), 
                ('Compete', 'Player'), ('Seating', 'Player')):
            sql = ('UPDATE {table} SET ({field} = {mergeID})'
                   '  WHERE {field} in ({playerIDs})'.format(
                       table=table, field=field, mergeID=merge_record['Id'],
                       playerIDs=', '.join(str(id) for id in playerIDs)))
            cur.execute(sql)
        result['status'] = 0
        result['message'] = '{} player records merged into ID {}'.format(
            len(playerIDs), merge_record['Id'])
