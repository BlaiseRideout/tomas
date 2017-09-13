#!/usr/bin/env python3

import handler
import db

class NewTournamentHandler(handler.BaseHandler):
    def get(self):
        self.render("newtournament.html")
    def post(self):
        name = self.get_argument("name", None)
        if name is None:
            return self.render("newtournament.html")
        with db.getCur() as cur:
            cur.execute("INSERT INTO Tournaments(Name, Owner) VALUES(?, ?)", (name, self.current_user))
            self.redirect("/tournament/" + name)


class TournamentHandler(handler.BaseHandler):
    def get(self, q):
        with db.getCur() as cur:
            cur.execute("SELECT Name FROM Tournaments WHERE Name = ?", (q,))
            row = cur.fetchone()
            if row is not None:
                name = row[0]
                return self.render("tournament.html", name = name)
            else:
                return self.render("message.html", message = "No such tournament found.")
