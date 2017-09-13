#!/usr/bin/env python3

import sys
import os.path
import os
import math
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.template
import signal
import json
import datetime

from quemail import QueMail
import handler
import util
import db
import settings

import login
#import seating
import leaderboard
import playerstats
import tournament

# import and define tornado-y things
from tornado.options import define, options
cookie_secret = util.randString(32)

class MainHandler(handler.BaseHandler):
    def get(self):
        no_user = False
        with db.getCur() as cur:
            cur.execute("SELECT COUNT(*) FROM Users")
            no_user = cur.fetchone()[0] == 0
            tournaments = []

        self.render("index.html", no_user = no_user, tournaments = tournaments)


class Application(tornado.web.Application):
    def __init__(self):
        db.init()

        handlers = [
                (r"/", MainHandler),
                (r"/setup", login.SetupHandler),
                (r"/login", login.LoginHandler),
                (r"/logout", login.LogoutHandler),
                (r"/invite", login.InviteHandler),
                (r"/settings", login.SettingsHandler),
                (r"/verify/([^/]+)", login.VerifyHandler),
                (r"/reset", login.ResetPasswordHandler),
                (r"/reset/([^/]+)", login.ResetPasswordLinkHandler),
                (r"/newtournament", tournament.NewTournamentHandler),
                (r"/tournament/([^/]+)", tournament.TournamentHandler),
                #(r"/leaderboard(/[^/]*)?", leaderboard.LeaderboardHandler),
                (r"/leaderdata(/[^/]*)?", leaderboard.LeaderDataHandler),
                (r"/playerstats/(.*)", playerstats.PlayerStatsHandler),
                (r"/playerstatsdata/(.*)", playerstats.PlayerStatsDataHandler),
        ]
        settings = dict(
                template_path = os.path.join(os.path.dirname(__file__), "templates"),
                static_path = os.path.join(os.path.dirname(__file__), "static"),
                debug = True,
                cookie_secret = cookie_secret,
                login_url = "/login"
        )
        tornado.web.Application.__init__(self, handlers, **settings)

def periodicCleanup():
    with db.getCur() as cur:
        cur.execute("DELETE FROM VerifyLinks WHERE Expires <= datetime('now')")

def main():
    if len(sys.argv) > 1:
        try:
            socket = int(sys.argv[1])
        except:
            socket = sys.argv[1]
    else:
        socket = "/tmp/tomas.sock"

    if hasattr(settings, 'EMAILSERVER'):
        qm = QueMail.get_instance()
        qm.init(settings.EMAILSERVER, settings.EMAILUSER, settings.EMAILPASSWORD, settings.EMAILPORT, True)
        qm.start()

    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application(), max_buffer_size=24*1024**3)
    if isinstance(socket, int):
        http_server.add_sockets(tornado.netutil.bind_sockets(socket))
    else:
        http_server.add_socket(tornado.netutil.bind_unix_socket(socket))

    signal.signal(signal.SIGINT, sigint_handler)

    tornado.ioloop.PeriodicCallback(periodicCleanup, 60 * 60 * 1000).start() # run periodicCleanup once an hour
    # start it up
    tornado.ioloop.IOLoop.instance().start()

    if qm is not None:
        qm.end()


def sigint_handler(signum, frame):
    tornado.ioloop.IOLoop.instance().stop()

if __name__ == "__main__":
    main()
