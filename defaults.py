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
#   DEFAULTCUTSIZE controls how many players are included by default
#   in subsequent rounds and the size of groups after soft cuts
DEFAULTCUTSIZE = 32
#   MAXSWAPDISTANCE is the maximum difference in rank that will
#   be swapped to resolve duplicates and diversity
MAXSWAPDISTANCE = 10
#   DUPLICATEIMPORTANCE is the factor by which duplicate resolution
#   is prioritized over diversity resolution
DUPLICATEIMPORTANCE = 4
#   LINKVALIDDAYS is the number of days links for invitations and
#   password resets should remain valid.  They expire after LINKVALIDDAYS
#   has passed.
LINKVALIDDAYS = 7
#   STATSHISTORYSIZE is the number of players who will be displayed
#   in the "Recently Viewed" section of the player stats page
STATSHISTORYSIZE = 10
#   SCOREPERPLAYER sets the initial score each player has at the start of
#   each round.  It is used to determine what the total raw scores should
#   sum to at the end of each round and how to calculate points from those
#   sums
SCOREPERPLAYER = 30000
#   UNUSEDSCOREINCREMENT is smallest score amount that can be marked
#   as unused at the end of game.  The unused score must be a multiple of
#   this increment, typically 1000 for a riichi bet.
UNUSEDSCOREINCREMENT = 1000

# EMAIL
#   These settings are for the outbound email server that sends invites
#   and password reset links to users.
EMAILSERVER = "smtp.server.com"
EMAILPORT = 587
EMAILUSER = "email@address.com"
EMAILFROM = "{0} <{1}>".format("Tournament Mahjong", EMAILUSER)
EMAILPASSWORD = ""
