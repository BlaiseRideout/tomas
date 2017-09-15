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

def prompt(msg, default=None):
    resp = None
    accepted_responses = ['y', 'Y', 'yes', 'Yes', 'n', 'N', 'no', 'No']
    guide = "[y/n]"
    if default and default in accepted_responses:
        accepted_responses.append('')
        guide = "[Y/n]" if default.lower().startswith('y') else "[y/N]"
    while resp not in accepted_responses:
        resp = input("{0} {1}? ".format(msg, guide))
        if resp not in accepted_responses:
            print("Unrecognized response, '{0}'.\nPlease choose among {1}".
                  format(resp, accepted_responses))
    return (resp.lower().startswith('y') if len(resp) > 0 or default == None
            else default.lower().startswith('y'))
