#!/usr/bin/env python3

import json
import re
import logging
import tornado.web
from tornado.escape import *

import handler
import db
import util
import login
import settings

log = logging.getLogger("WebServer")

user_fields = ["id", "email", "password", "admin"]

class ManageUsersHandler(handler.BaseHandler):
    @handler.is_admin
    def get(self):
        global user_fields
        with db.getCur() as cur:
            cur.execute(
                "SELECT Users.Id, Email, Password, Admins.Id IS NOT NULL"
                " FROM Users LEFT JOIN Admins ON Admins.Id = Users.Id")
            users = [dict(zip(user_fields, row)) for row in cur.fetchall()]
            for user in users:
                user['admin'] = user['admin'] != 0
            invite_fields = ["id", "email", "expires"]
            cur.execute(
                "SELECT {} FROM VerifyLinks ORDER BY {} DESC".format(
                    ', '.join(invite_fields), invite_fields[-1]))
            invites = [dict(zip(invite_fields, row)) for row in cur.fetchall()]

        page = self.render("users.html", users=users, invites=invites)

    @handler.is_admin_ajax
    def post(self):
        global user_fields
        userdata = json.loads(self.get_argument('userdata', None))
        if userdata is None or not (
                isinstance(userdata['userID'], int) or
                userdata['userID'].isdigit() or userdata['userID'] == "-1"):
            return self.write(json.dumps(
                {'status':"error", 'message':"Invalid user ID provided"}))
        if not userdata['action'] in ['delete', 'update', 'resetpwd', 'add']:
            return self.write(json.dumps(
                {'status':"error",
                 'message':"Invalid action requested: {}".format(
                     userdata['action'])}))
        try:
            user = str(userdata['userID'])
            action = userdata['action']
            updatedict = dict(
                [i for i in userdata.items()
                 if not i[0] in ['action', 'userID']])
            log.debug('Request to {} user {} {}'.format(
                userdata['action'], userdata['userID'], updatedict))
            with db.getCur() as cur:
                if action != 'add':
                    cur.execute("SELECT Id FROM Users WHERE Id = ?", (user,))
                    if cur.fetchone() is None:
                        return self.write(json.dumps(
                            {'status':"error",
                             'message':"Please provide a valid user ID"}))
                else:
                    cur.execute("INSERT INTO Users (Email, Password) VALUES"
                                " (?, ?)", ('newuser', '?'))
                    user = str(cur.lastrowid)
                    log.info('Inserted new user ID {}'.format(user))

                if action == 'delete':
                    cur.execute("DELETE from Admins WHERE Id = ?", (user,))
                    cur.execute("DELETE from Users WHERE Id = ?", (user,))
                    log.info('Deleted user {}'.format(user))
                elif action == 'resetpwd':
                    code = util.randString(login.VerifyLinkIDLength)
                    cur.execute("INSERT INTO ResetLinks(Id, User, Expires) "
                                "VALUES (?, ?, ?)",
                                (code, user,
                                 login.expiration_date(duration=1).isoformat()))
                    log.info('Set up password reset for user {}'.format(
                        user))
                    return self.write(json.dumps(
                        {'status':"success",
                         'redirect': "{}/reset/{}?nexturi={}&nexttask={}".format(
                             settings.PROXYPREFIX.rstrip('/'), code,
                             url_escape('{}/?tab=users.html'.format(
                                 settings.PROXYPREFIX.rstrip('/'))),
                             url_escape('Return to Users'))}))
                elif action == 'update':
                    for colname, val in updatedict.items():
                        col = colname.lower()
                        if isinstance(val, str):
                            val = val.lower()
                        if not col in user_fields or not db.valid[
                                col if col in db.valid else 'all'].match(val):
                            return self.write(json.dumps(
                                {'status':"error",
                                 'message':"Invalid column or value provided"}))
                    if not updatedict.get('Admin', False) == '1':
                        cur.execute("DELETE from Admins WHERE Id = ?", (user,))
                        log.debug('Removed admin privilege from user {}'
                                 .format(user))
                    else:
                        cur.execute(
                            "INSERT OR IGNORE INTO Admins (Id) VALUES (?)",
                            (user,))
                        log.debug('Granted admin privilege to user {}'
                                 .format(user))
                    for colname, val in updatedict.items():
                        if not colname.lower() in ('id', 'admin', 'password'):
                            cur.execute("UPDATE Users SET {} = ? WHERE Id = ?"
                                        .format(colname),
                                        (val, user))
                            log.debug('Set {} to {} for user {}'.format(
                                colname, val, user))
                elif action == 'add':
                    pass
                else:
                    return self.write(json.dumps(
                        {'status':"error",
                         'message': "Unknown action '{}' reqeusted".format(
                             action)}))
            return self.write(json.dumps({'status':"success"}))
        except Exception as e:
            log.error('Error in ManageUsersHandler.post: {}'.format(e))
            return self.write(json.dumps(
                {'status':"error",
                 'message':"Invalid info provided"}))

class ManageInvitesHandler(handler.BaseHandler):
    @handler.is_admin_ajax
    def post(self, inviteID):
        invitedata = json.loads(self.get_argument('invitedata', None))
        if invitedata is None or not (
                isinstance(inviteID, str) and
                len(inviteID) == login.VerifyLinkIDLength):
            return self.write(json.dumps(
                {'status':"error", 'message':"Invalid invite ID provided"}))
        try:
            action = invitedata['action']
            with db.getCur() as cur:
                if action == 'drop':
                    cur.execute("DELETE from VerifyLinks WHERE Id = ?",
                                (inviteID,))
                    log.info('Deleted invite {}'.format(inviteID))
                else:
                    return self.write(json.dumps(
                        {'status':"error",
                         'message':"Invalid action requested: {}".format(
                             invitedata['action'])}))
            return self.write(json.dumps({'status':"success"}))
        except Exception as e:
            log.error('Error in ManageInvitesHandler.post: {}'.format(e))
            return self.write(json.dumps(
                {'status':"error",
                 'message':"Invalid info provided"}))
