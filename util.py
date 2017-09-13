#!/usr/bin/env python3

import random
import string
from quemail import QueMail, Email

import settings

def randString(length):
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for x in range(length))

def sendEmail(toaddr, subject, body):
    fromaddr = settings.EMAILFROM

    qm = QueMail.get_instance()
    qm.send(Email(subject=subject, text=body, adr_to=toaddr, adr_from=fromaddr, mime_type='html'))

def getScore(score, numplayers, rank):
    umas = {4:[15,5,-5,-15],
            5:[15,5,0,-5,-15]}
    return score / 1000.0 - 25 + umas[numplayers][rank - 1]
