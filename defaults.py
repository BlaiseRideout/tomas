#!/usr/bin/env python3

import datetime

# Tournament Name - Used in email communications and headers
WEBSITENAME = "Tournament Mahjong"

# Linked web site - Link for upper left corner 'sponsor' logo
SPONSORLINK = "https://seattlemahjong.com"

# DB
#  DBFILE is the name of the file that contains the scores and player database.
DBFILE = "scores.db"
DBBACKUPS = "backups"
DBDATEFORMAT = "%Y-%m-%d-%H-%M-%S"

# PREFERENCES
# Tournament related
#   DEFAULTCUTSIZE controls how many players are included by default
#   in subsequent rounds and the size of groups after soft cuts
DEFAULTCUTSIZE = 32
#   MAXSWAPDISTANCE is the maximum difference in rank that will
#   be swapped to resolve duplicates and diversity
MAXSWAPDISTANCE = 10
#   DUPLICATEIMPORTANCE is the factor by which duplicate resolution
#   is prioritized over diversity resolution
DUPLICATEIMPORTANCE = 4
#   SCOREPERPLAYER sets the initial score each player has at the start of
#   each round.  It is used to determine what the total raw scores should
#   sum to at the end of each round and how to calculate points from those
#   sums
SCOREPERPLAYER = 30000
#   UNUSEDSCOREINCREMENT is smallest score amount that can be marked
#   as unused at the end of game.  The unused score must be a multiple of
#   this increment, typically 1000 for a riichi bet.
UNUSEDSCOREINCREMENT = 1000
#   LOWESTRANK is the lowest rank players can have.  This is normally 4 for
#   4th place, but in some cases a 5th player is allowed to rotate in.
LOWESTRANK = 4
#   UMAS are the bonuses awarded to players for their ranking after
#   completing a hanchan.  They can be different for 4-player and 5-player
#   tables.  The list of bonuses for each type goes from highest ranked to
#   lowest ranked.  Ties are split by giving each player the average of
#   the umas for the ranks.
UMAS = {4:[15,5,-5,-15],
        5:[15,5,0,-5,-15]}


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
#   leave this as '/'.
PROXYPREFIX = '/'
#   SERVERPREFIX is the protocol scheme and hostname for the server
#   that users access.  This will be the beginning of links sent in email
#   to users when managing their accounts.  Leave this as None if no
#   proxy is set up since the server can be determined from the input
#   request.  If defined, include the scheme and optionally the port, e.g.
#   SERVERPREFIX = 'https://myhost.com'
#   or
#   SERVERPREFIX = 'http://myhost.com:8080'
SERVERPREFIX = None

# EMAIL
#   These settings are for the outbound email server that sends invites
#   and password reset links to users.
EMAILSERVER = "smtp.server.com"
EMAILPORT = 587
EMAILUSER = "email@address.com"
EMAILFROM = "{0} <{1}>".format("Tournament Mahjong", EMAILUSER)
EMAILPASSWORD = ""
