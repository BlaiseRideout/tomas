#!/usr/bin/env python3

# DB
#  DBFILE is the name of the file that contains the scores and player database.
DBFILE = "scores.db"
DBBACKUPS = "backups"
DBDATEFORMAT = "%Y-%m-%d-%H-%M-%S"

# PREFERENCES
#   DROPGAMES is the default number of games a player must complete in a
#   quarter in order to have the lowest score dropped from the average.
DROPGAMES = 9
#   LINKVALIDDAYS is the number of days links for invitations and
#   password resets should remain valid.  They expire after LINKVALIDDAYS
#   has passed.
LINKVALIDDAYS = 7

# EMAIL
#   These settings are for the outbound email server that sends invites
#   and password reset links to users.
EMAILSERVER = "smtp.server.com"
EMAILPORT = 587
EMAILUSER = "email@address.com"
EMAILFROM = "{0} <{1}>".format("Tournament Mahjong", EMAILUSER)
EMAILPASSWORD = ""
