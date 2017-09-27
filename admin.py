#!/usr/bin/env python3

import json
import re
import tornado.web

import handler
import db
import util
import login

user_fields = ["id", "email", "password", "admin"]

valid = {
    'all': re.compile(r'^[\w\s():,.\'+-\u202F]*$'),
    'email': re.compile(r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]+$', re.IGNORECASE),
    'admin': re.compile(r'^(0|1|Y|N|YES|NO)$')
}
               
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
        global valid
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
                    if not col in ('del', 'reset') and not (
                            col in user_fields and
                            (valid[col].match(val) if col in valid else
                             valid['all'].match(val))):
                        return self.write(json.dumps(
                            {'status':"error",
                             'message':"Invalid column or value provided"}))
                    if col == 'admin':
                        cur.execute("DELETE from Admins WHERE Id = ?", (user,))
                        if val.lower().startswith('y') or val == '1':
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

class DeleteGameHandler(handler.BaseHandler):
    @handler.is_admin
    def get(self, q):
        with db.getCur() as cur:
            cur.execute("SELECT Rank, Players.Name, Scores.RawScore / 1000.0, Scores.Score, Scores.Chombos FROM Scores INNER JOIN Players ON Players.Id = Scores.PlayerId WHERE GameId = ?", (q,))
            rows = cur.fetchall()
            if len(rows) == 0:
                self.render("message.html", message = "Game not found", title = "Delete Game")
            else:
                scores = {}
                for row in rows:
                    scores[row[0]] = (row[1], row[2], round(row[3], 2), row[4])
                self.render("deletegame.html", id=q, scores=scores)
    @handler.is_admin
    def post(self, q):
        with db.getCur() as cur:
            cur.execute("SELECT EXISTS(SELECT * FROM Scores WHERE GameId = ?)", (q,))
            if cur.fetchone()[0] == 0:
                self.render("message.html", message = "Game not found", title = "Delete Game")
            else:
                cur.execute("DELETE FROM Scores WHERE GameId = ?", (q,))
                self.redirect("/history")

class EditGameHandler(handler.BaseHandler):
    @tornado.web.authenticated
    def post(self):
        scores = self.get_argument('tablescores', None)
        scores = json.loads(scores)
        self.write(json.dumps(db.updateGame(scores)))


