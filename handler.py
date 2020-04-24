#!/usr/bin/env python3
import tornado.web
import json
import os.path

import util
import settings

import db

class BaseHandler(tornado.web.RequestHandler):
    tournamentid = None
    tournamentname = None
    def get_current_user(self):
        if settings.DEVELOPERMODE or os.path.exists('DEVELOPERMODE'):
            return "1"
        else:
            return util.stringify(self.get_secure_cookie("user"))

    def get_is_admin(self):
        if settings.DEVELOPERMODE or os.path.exists('DEVELOPERMODE'):
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

def is_authenticated_ajax(func):
    def func_wrapper(self, *args, **kwargs):
        user = self.get_current_user()
        if not (user and isinstance(user, str) and user.isdigit()):
            self.write({"status": "error",
                        "message":"You must log in to do that"})
        else:
            func(self, *args, **kwargs)

    return func_wrapper

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

def valid_ID(ID, tablename, response=None, msg=None, IDfield='Id'):
    """Check if the ID is a valid Id field in the table.
    If a response dictionary is provided, set its status field to -1
    and its message field to an appropriate message to pass back
    to the browser in a JSON response.  The msg will be added on
    to any error message.
    If a single matching ID is found and the response is a dictionary,
    the status field of the response is set to 0.
    Return True if ID is valid, False otherwise."""
    if ID or isinstance(ID, int):
        with db.getCur() as cur:
            sql = "SELECT {} FROM {} WHERE {} = ?".format(
                IDfield, tablename, IDfield)
            args = (ID, )
            cur.execute(sql, args)
            rows = cur.fetchall()
    else:
        rows = []
    if len(rows) == 0:
        if response:
            response['status'] = -1
            response['message'] = 'Invalid {} field for {}. {}'.format(
                IDfield, tablename, msg or '')
        return False
    if len(rows) > 1:
        if response:
            response['status'] = -1
            response['message'] = (
                'Internal error. {} = {} matches multiple rows in {}. {}'
                .format(IDfield, ID, tablename, msg or ''))
        return False
    if isinstance(response, dict):
        response['status'] = 0
    return True
