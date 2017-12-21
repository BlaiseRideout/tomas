#!/usr/bin/env python3

import datetime

# Tournament Name - Used in email communications and headers
TOURNAMENTNAME = "{0} Tournament".format(datetime.date.today().strftime('%Y'))

# DB
#  DBFILE is the name of the file that contains the scores and player database.
DBFILE = "scores.db"
DBBACKUPS = "backups"
DBDATEFORMAT = "%Y-%m-%d-%H-%M-%S"

# PREFERENCES
# Tournament related
#   DEFFAULTCUTSIZE controls the default number of players that advance
#   between rounds.
DEFAULTCUTSIZE = 32
#   MAXSWAPDISTANCE is the maximum difference in rank that will
#   be swapped to resolve duplicates and diversity
MAXSWAPDISTANCE = 10
#   DUPLICATEIMPORTANCE is the factor by which duplicate resolution
#   is prioritized over diversity resolution
DUPLICATEIMPORTANCE = 4
#   UNUSEDPOINTSINCREMENT is smallest amount of points that can be marked
#   as unused at the end of game.  The unused points must be a multiple of
#   this increment, typically 1000 for a riichi bet.
UNUSEDPOINTSINCREMENT = 1000

# Application behavior
#   LINKVALIDDAYS is the number of days links for invitations and
#   password resets should remain valid.  They expire after LINKVALIDDAYS
#   has passed.
LINKVALIDDAYS = 7
#   STATSHISTORYSIZE is the number of players who will be displayed
#   in the "Recently Viewed" section of the player stats page
STATSHISTORYSIZE = 10
#   PROXYPREFIX is the URL prefix needed for users accessing this web server
#   through a proxy server.  If this web server is being accessed directly,
#   leave this as '/' or empty ''.
PROXYPREFIX = '/'

# EMAIL
#   These settings are for the outbound email server that sends invites
#   and password reset links to users.
EMAILSERVER = "smtp.server.com"
EMAILPORT = 587
EMAILUSER = "email@address.com"
EMAILFROM = "{0} <{1}>".format("Tournament Mahjong", EMAILUSER)
EMAILPASSWORD = ""
