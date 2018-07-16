#!/usr/bin/env python3

import json
import tornado.web

import handler
import db

class EditGameHandler(handler.BaseHandler):
    @handler.tournament_handler_ajax
    @tornado.web.authenticated
    def post(self):
        scores = self.get_argument('tablescores', None)
        scores = json.loads(scores)
        self.write(json.dumps(db.updateGame(scores, self.tournamentid)))

class EditPenaltiesHandler(handler.BaseHandler):
    @handler.tournament_handler_ajax
    def get(self, scoreid):
        with db.getCur() as cur:
            fields = ["id", "penalty", "description", "referee"]
            cur.execute("SELECT {0} FROM Penalties WHERE ScoreId = ?".format(
                ", ".join(fields)),
                        (scoreid,));
            penalties = [dict(zip(fields, row)) for row in cur.fetchall()]

        rows = self.render_string("penalties.html", penalties=penalties,
                                  scoreid=scoreid)
        self.write(rows)

    @handler.tournament_handler_ajax
    @tornado.web.authenticated
    def post(self):
        scoreID = self.get_argument('scoreID', None)
        penalties = json.loads(self.get_argument('penalties', None))
        self.write(json.dumps(db.updatePenalties(scoreID, penalties)))


