#!/usr/bin/env python3

import random
import string
import re
from quemail import QueMail, Email
from urllib.parse import *
import os

import settings

def randString(length):
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for x in range(length))

def sendEmail(toaddr, subject, body):
    fromaddr = settings.EMAILFROM

    qm = QueMail.get_instance()
    qm.send(Email(subject=subject, text=body, adr_to=toaddr, adr_from=fromaddr, mime_type='html'))

def getScore(score, numplayers, rank):
    return score / 1000.0 - 25 + settings.UMAS[numplayers][rank - 1]

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

def stringify(x):
    if x is None or isinstance(x, str):
        return x
    elif isinstance(x, bytes):
        return x.decode()
    else:
        return str(x)

def prettyWords(text):
    result = []
    _ = [result.extend(breakCamelCase(w)) for w in text.split('_') if w != '']
    return ' '.join(result)

capword = re.compile(r'[A-Z]?[a-z-]*')
def breakCamelCase(words):
    return [m.group(0) for m in capword.finditer(words) if m.group(0) != '']
    
winds = "東南西北"

localDirs = ('js', 'css')
localDirRoot = "static"
localExtensions = tuple('.' + dir for dir in localDirs)

def useLocal(URL):
    "Convert Internet URLs to locally served file if configured in settings"
    if not settings.USELOCALCOPY:
        return URL
    try:
        url = urlparse(URL)
    except Exception:
        return URL
    if url.scheme == '':     # Relative URL's don't need to be redirected
        return URL
    path, name = os.path.split(url.path)
    if not name:
        return URL
    base, ext = os.path.splitext(name)
    if ext in localExtensions and os.path.exists( # Look in local directory
            os.path.join(localDirRoot, ext[1:], name)):
        return settings.PROXYPREFIX + os.path.join(localDirRoot, ext[1:], name)
    return URL
        
    
    

