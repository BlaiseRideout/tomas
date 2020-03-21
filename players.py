#!/usr/bin/env python3

import json
import csv
import re
import io
import logging
import datetime
import sqlite3

import tornado.web
import handler
import db
import seating
import settings
import util

log = logging.getLogger('WebServer')

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
        try:
            with db.getCur() as cur:
                cur.execute(
                    "SELECT {columns} FROM Players"
                    " JOIN Countries ON Players.Country = Countries.Id"
                    " LEFT OUTER JOIN Compete ON Players.Id = Compete.Player"
                    " LEFT OUTER JOIN Tournaments"
                    "   ON Compete.Tournament = Tournaments.Id"
                    " LEFT OUTER JOIN Scores ON Players.Id = Scores.PlayerId"
                    " WHERE Players.ReplacedBy ISNULL"
                    " GROUP BY Players.Id"
                    " ORDER BY Players.Name".format(
                        columns=",".join(columns)))
                players = [dict(zip(colnames, row)) for row in cur.fetchall()]
#                for item in players:
#                    item['Country'] += ' ' + item['Flag_Image']
                result = {'status': 0, 
                          'data': players, 'itemsCount': len(players)}
        except Exception as e:
            result = {'status': 1,
                      'message': 'Unable to get players from database. ' +
                      str(e) }
        self.write(result)
        
    @tornado.web.authenticated
    def post(self):
        encoded_item = self.get_argument('item', None)
        item = json.loads(encoded_item)
        result = {'status': 0, 'message': ''}
        if item.get('Id', None) is None or not isinstance(item['Id'], int):
            result['message'] = 'Invalid Id field in item, {}'.format(
                repr(item.get('Id', None)))
            result['status'] = -1
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
                        result['status'] = -2
                    elif matches > 1:
                        result['message'] = (
                            'Multiple players with Id {}'.format(id))
                        result['status'] = -3
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
                        log.info('Last Player Row ID is now {}'.format(
                            cur.lastrowid))
        except Exception as e:
            result['message'] = (
                'Exception in database change. SQL = {}. {}'.format(sql, e))
            result['status'] = -5
            
        self.write(result)

def cleanPlayerItem(item, columns):
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
