#!/usr/bin/env python3

import json
import os
import re
import tornado.web

import handler
import db
import settings

email_pattern = re.compile(r'^[A-Z0-9][A-Z0-9._-]*@[A-Z0-9._-]*\.[A-Z]\w+$',
                           re.IGNORECASE)

class PreferencesHandler(handler.BaseHandler):
    @tornado.web.authenticated
    def get(self):
        stylesheets = sorted(os.listdir("static/css/colors"))
        stylesheet = stylesheets[0]
        cutsize = None
        with db.getCur() as cur:
            cur.execute("SELECT Email FROM Users WHERE Id = ?",
                        self.current_user)
            email = cur.fetchone()
            if email is not None:
                email = email[0]
            if email:
                cur.execute(
                    "SELECT Value FROM Preferences"
                    " WHERE UserId = ? AND Preference ='stylesheet'",
                    (self.current_user,))
                pref = cur.fetchone()
                if pref is not None:
                    stylesheet = pref[0]
            if self.get_is_admin():
                cur.execute("SELECT Value FROM GlobalPreferences WHERE Preference = 'CutSize'")
                cutsize = cur.fetchone()
                if cutsize is None:
                    cutsize = settings.DEFAULTCUTSIZE
                else:
                    cutsize = cutsize[0]
        return self.render("preferences.html", email=email,
                           stylesheets=stylesheets, cutsize=cutsize)

    @tornado.web.authenticated
    def post(self):
        global email_pattern
        stylesheet = self.get_argument('stylesheet', None)
        email = self.get_argument('email', None)
        cutsize = self.get_argument('cutsize', None)
        if (stylesheet is None or email is None or
            email_pattern.match(email) is None):
            self.render("message.html",
                        message="Please pick a stylesheet and enter a valid email",
                        title="Preference Errors",
                        next="Preferences", next_url="/preferences")
        else:
            with db.getCur() as cur:
                cur.execute(
                    "DELETE FROM Preferences"
                    " WHERE UserId = ? AND Preference = 'stylesheet';",
                    (self.current_user,))
                cur.execute(
                    "INSERT INTO Preferences(UserId, Preference, Value)"
                    " VALUES(?, 'stylesheet', ?);",
                    (self.current_user, stylesheet))
                cur.execute(
                    "UPDATE Users SET Email = LOWER(?)"
                    " WHERE Id = ? AND Email != LOWER(?)",
                    (email, self.current_user, email))
                if self.get_is_admin() and cutsize is not None:
                    cur.execute("REPLACE INTO GlobalPreferences(Preference, Value) VALUES('CutSize', ?)", (cutsize,))
            self.set_secure_cookie("stylesheet", stylesheet)
            self.render("message.html",
                        message="",
                        title="Preferences Updated",
                        next="Preferences", next_url="/preferences")

