#!/usr/bin/env python3

import json
import re
import tornado.web

import handler
import db
import util
import login
import settings

user_fields = ["id", "email", "password", "admin"]

class ManageUsersHandler(handler.BaseHandler):
    @handler.is_admin
    def get(self):
        global user_fields
        with db.getCur() as cur:
            cur.execute(
                "SELECT Users.Id, Email, Password, Admins.Id IS NOT NULL"
                " FROM Users LEFT JOIN Admins ON Admins.Id = Users.Id")
            rows = [dict(zip(user_fields, row)) for row in cur.fetchall()]
            for row in rows:
                if row['admin'] == 0:
                    row['admin'] = ''
            return self.write(json.dumps({'users': rows}))

    @handler.is_admin_ajax
    def post(self):
        global user_fields
        user = self.get_argument("user", None)
        if user is None or not (user.isdigit() or user == "-1"):
            return self.write(json.dumps(
                {'status':"error", 'message':"Please provide a user ID"}))
        info = self.get_argument("info", None)
        if info is None:
            return self.write(json.dumps(
                {'status':"error", 'message':"Please provide an info object"}))
        info = json.loads(info)
        try:
            with db.getCur() as cur:
                if user.isdigit():
                    cur.execute("SELECT Id FROM Users WHERE Id = ?", (user,))
                    if cur.fetchone() is None:
                        return self.write(json.dumps(
                            {'status':"error",
                             'message':"Please provide a valid user ID"}))
                elif user == '-1':
                    cur.execute("INSERT INTO Users (Email, Password) VALUES"
                                " (?, ?)", ('newuser', '?'))
                    user = str(cur.lastrowid)
                for colname, val in info.items():
                    col = colname.lower()
                    if isinstance(val, str):
                        val = val.lower()
                    if not col in ('del', 'reset') and not (
                            col in user_fields and
                            (db.valid[col].match(val) if col in db.valid else
                             db.valid['all'].match(val))):
                        return self.write(json.dumps(
                            {'status':"error",
                             'message':"Invalid column or value provided"}))
                    if col == 'admin':
                        cur.execute("DELETE from Admins WHERE Id = ?", (user,))
                        if val.startswith('y') or val == '1':
                            cur.execute("INSERT INTO Admins (Id) VALUES (?)",
                                        (user,))
                    elif col == 'del':
                        cur.execute("DELETE from Users WHERE Id = ?", (user,))
                    elif col == 'reset':
                        code = util.randString(32)
                        cur.execute("INSERT INTO ResetLinks(Id, User, Expires) "
                                    "VALUES (?, ?, ?)",
                                    (code, user,
                                     login.expiration_date(duration=1).isoformat()))
                        return self.write(json.dumps(
                            {'status':"success",
                             'redirect': "/reset/{0}".format(code)}))
                    else:
                        cur.execute("UPDATE Users SET {0} = ? WHERE Id = ?"
                                    .format(colname),
                                    (val, user))
            return self.write(json.dumps({'status':"success"}))
        except:
            return self.write(json.dumps(
                {'status':"error",
                 'message':"Invalid info provided"}))

class EditGameHandler(handler.BaseHandler):
    @tornado.web.authenticated
    def post(self):
        scores = self.get_argument('tablescores', None)
        scores = json.loads(scores)
        self.write(json.dumps(db.updateGame(scores)))

class EditPenaltiesHandler(handler.BaseHandler):
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

    @tornado.web.authenticated
    def post(self):
        scoreID = self.get_argument('scoreID', None)
        penalties = json.loads(self.get_argument('penalties', None))
        self.write(json.dumps(db.updatePenalties(scoreID, penalties)))


