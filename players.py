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

class PlayersListHandler(handler.BaseHandler):
    def get(self, rest=''):
        player_fields = [f for f in db.table_field_names('Players')
                         if f not in ('Country', 'ReplacedBy')]
        with db.getCur() as cur:
            columns = ["Players.{}".format(f) for f in player_fields] + [
                "Code", "Flag_Image", "COUNT(DISTINCT Tournaments.Id)",
                "MAX(Tournaments.Start)"] 
            colnames = player_fields + [
                "Country", "Flag_Image", "Tournaments", "Latest"]
            colheads = [{"Name": util.prettyWords(col)} for col in colnames 
                        if col not in ('Id', 'Flag_Image')]
            colheads[len(player_fields) - 1]["Attrs"] = "colspan=2"
            cur.execute(
                "SELECT {columns} FROM Players"
                " JOIN Countries ON Players.Country = Countries.Id"
                " LEFT OUTER JOIN Compete ON Players.Id = Compete.Player"
                " JOIN Tournaments ON Compete.Tournament = Tournaments.Id"
                " WHERE Players.ReplacedBy ISNULL"
                " GROUP BY Players.Id"
                " ORDER BY Players.Name".format(
                        columns=",".join(columns)))
            players = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return self.render(
            "playerlist.html", players=players, colheads=colheads)
