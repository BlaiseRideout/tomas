#!/usr/bin/env python3
import tornado.web
import json

import util
import settings

import db

class BaseHandler(tornado.web.RequestHandler):
    tournamentid = None
    tournamentname = None
    def get_current_user(self):
        if settings.DEVELOPERMODE:
            return "1"
        else:
            return util.stringify(self.get_secure_cookie("user"))

    def get_is_admin(self):
        if settings.DEVELOPERMODE:
            return True
        else:
            return util.stringify(self.get_secure_cookie("admin")) == "1"

    def get_stylesheet(self):
        return util.stringify(self.get_secure_cookie("stylesheet"))

    def render(self, template_name, **kwargs):
        config = {
            'current_user': self.current_user,
            'is_admin': self.get_is_admin(),
            'stylesheet': self.get_stylesheet(),
            'proxyprefix': settings.PROXYPREFIX,
            'websitename': settings.WEBSITENAME,
            'tournamentid': self.tournamentid,
            'tournamentname': self.tournamentname,
            'owner': getattr(self, 'owner', None),
            'SponsorLink': settings.SPONSORLINK,
            'useLocal': util.useLocal,
        }
        config.update(kwargs)
        tornado.web.RequestHandler.render(self, template_name, **config)

def is_admin(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.get_is_admin():
            self.render("message.html",
                        message = "You must be an administrator to do that")
        else:
            func(self, *args, **kwargs)

    return func_wrapper

def is_owner(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.get_is_admin():
            with db.getCur() as cur:
                cur.execute("SELECT Owner FROM Tournaments WHERE Id = ?",
                            (self.tournamentid,))
                owner = cur.fetchone()
                if owner is None:
                    self.render("message.html",
                                message = "Tournament not found")
                    return
                if str(owner[0]) != self.current_user:
                    self.render("message.html",
                                message = "You must be the tournament owner or "
                                "an admin to do that")
                    return
        func(self, *args, **kwargs)

    return func_wrapper


class AuthenticationHandler(BaseHandler):
    def get(self):
        status = {'user': self.get_current_user(), 'admin': False }
        # Check admin status from database rather than browser cookie to
        # be slightly more up to date
        with db.getCur() as cur:
            cur.execute("SELECT EXISTS(SELECT * FROM Admins WHERE Id = ?)",
                        (self.get_current_user(),))
            status['admin'] = cur.fetchone()[0] == 1
        return self.write(json.dumps(status))

def is_admin_ajax(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.get_is_admin():
            self.write('{"status":"error", "message":"You must be admin to do that"}')
        else:
            func(self, *args, **kwargs)

    return func_wrapper

def is_owner_ajax(func):
    def func_wrapper(self, *args, **kwargs):
        if not self.get_is_admin():
            with db.getCur() as cur:
                cur.execute("SELECT Owner FROM Tournaments WHERE Id = ?",
                            (self.tournamentid,))
                owner = cur.fetchone()
                if owner is None:
                    self.write('{"status":"error",'
                               ' "message":"Tournament not found"}')
                    return
                if str(owner[0]) != self.current_user:
                    self.write('{"status":"error",'
                               ' "message":"You must be the tournament owner '
                               'or an admin to do that"}')
                    return
        func(self, *args, **kwargs)

    return func_wrapper

def tournament_handler(func):
    def func_wrapper(self, tournament, *args, **kwargs):
        with db.getCur() as cur:
            cur.execute("SELECT Id, Name, Owner FROM Tournaments"
                        " WHERE Name = ? OR Id = ?", (tournament, tournament))
            row = cur.fetchone()
            if row is None:
                return self.render("message.html",
                            message = "Tournament not found")
        self.tournamentid, self.tournamentname, self.owner = row
        return func(self, *args, **kwargs)
    return func_wrapper

def tournament_handler_ajax(func):
    def func_wrapper(self, tournament, *args, **kwargs):
        with db.getCur() as cur:
            cur.execute("SELECT Id, Name, Owner FROM Tournaments"
                        " WHERE Name = ? OR Id = ?", (tournament,tournament))
            row = cur.fetchone()
            if row is None:
                return self.write('{"status":"error", '
                                  '"message":"Tournament not found"}')
        self.tournamentid, self.tournamentname, self.owner = row
        return func(self, *args, **kwargs)

    return func_wrapper
